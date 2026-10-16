import base64
import json
import os
import socket
import ssl
import struct
import threading
import time


class DiscordGatewayClient:
    """Client WebSocket natif TLS pour connecter réellement un Bot Discord à la Gateway."""

    def __init__(self, token: str):
        self.token = token.strip()
        self.sock = None
        self.connected = False
        self.running = False
        self.heartbeat_interval = 41.25
        self.last_sequence = None
        self.session_id = None
        self.presence_status = "online"
        self.activity_name = "Auditing Security"
        self.activity_type = 0  # 0=Playing, 1=Streaming, 2=Listening, 3=Watching
        self.stream_url = ""
        self.user_data = None
        self.thread = None
        self.lock = threading.Lock()
        self.log_messages = []

    def log(self, msg: str):
        with self.lock:
            ts = time.strftime("%H:%M:%S")
            self.log_messages.append(f"[{ts}] {msg}")
            if len(self.log_messages) > 15:
                self.log_messages.pop(0)

    def _send_frame(self, payload_dict):
        if not self.sock:
            return
        payload_bytes = json.dumps(payload_dict).encode("utf-8")
        frame = bytearray([0x81])  # FIN + Text frame
        length = len(payload_bytes)

        # Clients must mask frames sent to server
        mask_key = os.urandom(4)
        if length < 126:
            frame.append(0x80 | length)
        elif length < 65536:
            frame.append(0x80 | 126)
            frame.extend(struct.pack("!H", length))
        else:
            frame.append(0x80 | 127)
            frame.extend(struct.pack("!Q", length))

        frame.extend(mask_key)
        masked_payload = bytes(b ^ mask_key[i % 4] for i, b in enumerate(payload_bytes))
        frame.extend(masked_payload)

        try:
            self.sock.sendall(frame)
        except Exception:
            self.connected = False

    def _recv_frame(self, initial_buffer=b""):
        data = initial_buffer
        while len(data) < 2:
            chunk = self.sock.recv(4096)
            if not chunk:
                return None, None, b""
            data += chunk

        b1, b2 = data[0], data[1]
        opcode = b1 & 0x0F
        is_masked = bool(b2 & 0x80)
        payload_len = b2 & 0x7F
        offset = 2

        if payload_len == 126:
            while len(data) < 4:
                data += self.sock.recv(4096)
            payload_len = struct.unpack("!H", data[2:4])[0]
            offset = 4
        elif payload_len == 127:
            while len(data) < 10:
                data += self.sock.recv(4096)
            payload_len = struct.unpack("!Q", data[2:10])[0]
            offset = 10

        mask_key = None
        if is_masked:
            while len(data) < offset + 4:
                data += self.sock.recv(4096)
            mask_key = data[offset : offset + 4]
            offset += 4

        while len(data) < offset + payload_len:
            data += self.sock.recv(4096)

        raw = data[offset : offset + payload_len]
        remaining = data[offset + payload_len :]

        if is_masked and mask_key:
            payload = bytes(b ^ mask_key[i % 4] for i, b in enumerate(raw))
        else:
            payload = raw

        return opcode, payload, remaining

    def update_presence(self, status="online", activity_name="", activity_type=0, stream_url=""):
        self.presence_status = status
        self.activity_name = activity_name
        self.activity_type = activity_type
        self.stream_url = stream_url

        activities = []
        if activity_name:
            act = {"name": activity_name, "type": activity_type}
            if activity_type == 1 and stream_url:
                act["url"] = stream_url
            activities.append(act)

        payload = {
            "op": 3,
            "d": {
                "since": None,
                "activities": activities,
                "status": status,
                "afk": False,
            },
        }
        self._send_frame(payload)
        self.log(f"Présence actualisée : {status.upper()} | {activity_name or 'Sans activité'}")

    def _loop(self):
        try:
            host = "gateway.discord.gg"
            ctx = ssl.create_default_context()
            raw_sock = socket.create_connection((host, 443), timeout=10)
            self.sock = ctx.wrap_socket(raw_sock, server_hostname=host)

            sec_key = base64.b64encode(os.urandom(16)).decode("utf-8")
            handshake = (
                f"GET /?v=10&encoding=json HTTP/1.1\r\n"
                f"Host: {host}\r\n"
                f"Upgrade: websocket\r\n"
                f"Connection: Upgrade\r\n"
                f"Sec-WebSocket-Key: {sec_key}\r\n"
                f"Sec-WebSocket-Version: 13\r\n\r\n"
            )
            self.sock.sendall(handshake.encode("utf-8"))

            buf = b""
            while b"\r\n\r\n" not in buf:
                chunk = self.sock.recv(1024)
                if not chunk:
                    raise ConnectionError("Fermeture prématurée du handshake")
                buf += chunk

            header, rest = buf.split(b"\r\n\r\n", 1)
            if b"101 Switching Protocols" not in header:
                raise ConnectionError("Handshake Gateway refusé")

            self.connected = True
            self.log("Connecté physiquement à la Gateway Discord (TLS wss://)")

            last_hb_time = 0

            while self.running:
                # Heartbeat check
                now = time.time()
                if now - last_hb_time >= self.heartbeat_interval:
                    self._send_frame({"op": 1, "d": self.last_sequence})
                    last_hb_time = now

                self.sock.settimeout(0.5)
                try:
                    opcode, payload, rest = self._recv_frame(rest)
                except socket.timeout:
                    continue
                except Exception:
                    break

                if opcode is None or opcode == 0x8:  # Close frame
                    break
                elif opcode == 0x9:  # Ping
                    self._send_frame({"op": 11})  # Pong
                    continue

                if opcode == 0x1:  # Text frame
                    try:
                        msg = json.loads(payload.decode("utf-8"))
                    except Exception:
                        continue

                    op = msg.get("op")
                    s = msg.get("s")
                    t = msg.get("t")
                    d = msg.get("d", {})

                    if s is not None:
                        self.last_sequence = s

                    # Opcode 10: Hello -> Start identify & heartbeat
                    if op == 10:
                        self.heartbeat_interval = d.get("heartbeat_interval", 41250) / 1000.0
                        self._send_frame({"op": 1, "d": None})
                        last_hb_time = time.time()

                        # Identify
                        activities = []
                        if self.activity_name:
                            act = {"name": self.activity_name, "type": self.activity_type}
                            if self.activity_type == 1 and self.stream_url:
                                act["url"] = self.stream_url
                            activities.append(act)

                        identify_payload = {
                            "op": 2,
                            "d": {
                                "token": self.token,
                                "intents": 3276799,  # Full intents
                                "properties": {
                                    "os": "Windows",
                                    "browser": "OSINT-Pentest-Suite",
                                    "device": "Desktop",
                                },
                                "presence": {
                                    "activities": activities,
                                    "status": self.presence_status,
                                    "afk": False,
                                },
                            },
                        }
                        self._send_frame(identify_payload)
                        self.log("Identifié auprès de Discord avec tous les intents.")

                    elif op == 0:  # Dispatch event
                        if t == "READY":
                            self.user_data = d.get("user", {})
                            self.session_id = d.get("session_id")
                            u_tag = f"{self.user_data.get('username')}#{self.user_data.get('discriminator', '0')}"
                            self.log(f"SESSION READY : {u_tag} est EN LIGNE !")
                        elif t == "MESSAGE_CREATE":
                            author = d.get("author", {}).get("username", "?")
                            content = d.get("content", "")[:35]
                            if content and not d.get("author", {}).get("bot"):
                                self.log(f"Message de {author} : {content}")

                    elif op == 1:  # Heartbeat request
                        self._send_frame({"op": 1, "d": self.last_sequence})
                    elif op == 7 or op == 9:  # Reconnect or Invalid session
                        break

        except Exception as e:
            self.log(f"Déconnecté de la Gateway : {e}")
        finally:
            self.connected = False
            self.running = False
            if self.sock:
                try:
                    self.sock.close()
                except Exception:
                    pass
            self.sock = None
            self.log("Bot éteint (Socket fermé).")

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        self.connected = False
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
