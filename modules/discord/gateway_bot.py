"""Client Gateway Discord base sur discord.py.

Le protocole WebSocket n'est plus maintenu a la main : discord.py gere la
connexion, les heartbeats, la reconnexion et les sessions. Cette classe
expose une interface synchrone au panel Rich et garantit qu'une seule
connexion est ouverte a la fois.
"""
import asyncio
import concurrent.futures
import threading
import time

try:  # pragma: no cover - depend de l'environnement
    import discord
    DISCORD_IMPORT_ERROR = None
except ImportError as exc:  # pragma: no cover
    discord = None
    DISCORD_IMPORT_ERROR = str(exc)

STATUTS = {"online", "idle", "dnd", "invisible"}
TYPES_ACTIVITE = {0, 1, 2, 3, 5}


class DiscordGatewayClient:
    """Connexion Gateway unique, pilotable depuis une interface synchrone."""

    def __init__(self, token, client_factory=None):
        self._token = (token or "").strip()
        self._client_factory = client_factory
        self.connected = False
        self.reconnecting = False
        self.running = False
        self.presence_status = "online"
        # Aucune activite personnalisee par defaut : on n'ecrase pas la presence
        # du bot avec un texte arbitraire a chaque connexion.
        self.activity_name = ""
        self.activity_type = 0
        self.stream_url = ""
        self.user_data = {}
        self.last_error = None
        self.started_at = None
        self.log_messages = []
        self._client = None
        self._loop = None
        self._thread = None
        self._ready = False
        self._started = threading.Event()
        self._closed = threading.Event()
        self._arret_demande = threading.Event()
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Journalisation
    # ------------------------------------------------------------------
    def log(self, message):
        """Ajoute un evenement lisible, sans jamais conserver le token."""
        texte = self._redact(message)
        with self._lock:
            self.log_messages.append(f"[{time.strftime('%H:%M:%S')}] {texte}")
            del self.log_messages[:-30]

    def _redact(self, message):
        texte = str(message or "")
        if self._token and len(self._token) >= 8:
            texte = texte.replace(self._token, "[token masque]")
        return texte[:300]

    def _erreur(self, exc):
        message = f"{type(exc).__name__}: {exc}"
        self.last_error = self._redact(message)
        self.log(f"Erreur Gateway : {self.last_error}")

    # ------------------------------------------------------------------
    # Etat
    # ------------------------------------------------------------------
    @property
    def latency_ms(self):
        client = self._client
        if not self.connected or client is None:
            return None
        try:
            latence = client.latency
        except (AttributeError, RuntimeError):
            return None
        if latence is None or latence != latence:  # NaN
            return None
        return round(latence * 1000)

    @property
    def guild_count(self):
        """Serveurs reellement charges dans le cache discord.py.

        Retourne ``None`` tant que la Gateway n'a pas recu READY : aucune
        valeur n'est inventee et aucune estimation REST n'est utilisee.
        """
        client = self._client
        if client is None or not self._ready:
            return None
        guildes = getattr(client, "guilds", None)
        if guildes is None:
            return None
        try:
            return len(guildes)
        except TypeError:
            return None

    @property
    def session_ouverte(self):
        """Vrai tant que le thread Gateway vit encore (reconnexion incluse)."""
        thread = self._thread
        if thread is None or not thread.is_alive():
            return False
        return not self._closed.is_set()

    @property
    def etat(self):
        """Etat lisible : connectee, reconnexion, demarrage ou arretee."""
        if self.connected:
            return "connectee"
        if self.reconnecting and self.session_ouverte:
            return "reconnexion"
        if self.session_ouverte:
            return "demarrage"
        return "arretee"

    @property
    def uptime_seconds(self):
        """Duree reelle depuis le premier READY, meme pendant une reconnexion."""
        if not self.started_at:
            return None
        return max(0, int(time.time() - self.started_at))

    # ------------------------------------------------------------------
    # Connexion
    # ------------------------------------------------------------------
    def start(self, timeout=15):
        """Demarre la connexion et attend l'evenement READY."""
        with self._lock:
            if self.running:
                self.log("Connexion deja active : aucune seconde session ouverte.")
                return self.connected
            if not self._token:
                self.last_error = "Token Bot absent."
                return False
            if discord is None:
                self.last_error = ("discord.py est requis pour la Gateway : "
                                   f"{DISCORD_IMPORT_ERROR}")
                self.log(self.last_error)
                return False
            self.running = True
            self.last_error = None
            self._ready = False
            self.reconnecting = False
            self.started_at = None
            self._started.clear()
            self._closed.clear()
            self._arret_demande.clear()
            self._thread = threading.Thread(target=self._thread_main,
                                            name="discord-gateway", daemon=True)
            self._thread.start()

        if not self._started.wait(timeout):
            self.last_error = "Delai de connexion Gateway depasse."
            self.log(self.last_error)
            # Arret demande avant que le client soit pret : aucun thread ne
            # doit continuer une connexion que l'appelant a abandonnee.
            if not self.stop(timeout=max(1.0, timeout)):
                self.log("Arret force : le thread Gateway ne repond pas au delai.")
                self._closed.wait(max(1.0, timeout))
            return False
        return self.connected

    def _thread_main(self):
        loop = asyncio.new_event_loop()
        self._loop = loop
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._run())
        except BaseException as exc:  # noqa: BLE001 - remonte dans le journal
            self._erreur(exc)
        finally:
            self.connected = False
            self.reconnecting = False
            self.running = False
            self._ready = False
            self.started_at = None
            try:
                loop.run_until_complete(loop.shutdown_asyncgens())
            except BaseException:  # noqa: BLE001 - fermeture best effort
                pass
            loop.close()
            self._loop = None
            self._client = None
            self._started.set()
            self._closed.set()

    async def _run(self):
        intents = discord.Intents.none()
        intents.guilds = True
        if self._arret_demande.is_set():
            return
        client = (self._client_factory(intents) if self._client_factory
                  else discord.Client(intents=intents, chunk_guilds_at_startup=False))
        self._client = client
        if self._arret_demande.is_set():
            # stop() a ete demande pendant la creation du client : on ferme
            # sans ouvrir de session residuelle.
            await client.close()
            return

        @client.event
        async def on_ready():
            if self._arret_demande.is_set():
                return
            self.connected = True
            self.reconnecting = False
            self._ready = True
            if self.started_at is None:
                self.started_at = time.time()
            utilisateur = client.user
            self.user_data = {
                "id": str(getattr(utilisateur, "id", "") or ""),
                "username": getattr(utilisateur, "name", "") or getattr(utilisateur, "display_name", ""),
                "discriminator": getattr(utilisateur, "discriminator", "0"),
            }
            self.log("Gateway connectee : session READY.")
            try:
                # Sans activite configuree, on applique seulement le statut
                # standard : aucune activite arbitraire n'est imposee.
                activite = self._activite_discord()
                if activite is None:
                    await client.change_presence(status=self._statut_discord())
                else:
                    await client.change_presence(status=self._statut_discord(),
                                                 activity=activite)
            except (discord.HTTPException, OSError, TypeError, ValueError) as exc:
                self._erreur(exc)
            finally:
                self._started.set()

        @client.event
        async def on_disconnect():
            self.connected = False
            self.reconnecting = True
            self.log("Connexion Gateway perdue ; discord.py tente une reconnexion.")

        @client.event
        async def on_resumed():
            self.connected = True
            self.reconnecting = False
            self._ready = True
            self.log("Session Gateway reprise.")

        try:
            await client.start(self._token, reconnect=True)
        except discord.LoginFailure:
            self.last_error = "Token Bot refuse par Discord (401)."
            self.log(self.last_error)
        except discord.PrivilegedIntentsRequired:
            self.last_error = ("Intents privilegies refuses : activez uniquement "
                               "les intents necessaires dans le portail developpeur.")
            self.log(self.last_error)
        except asyncio.CancelledError:
            self.log("Connexion Gateway annulee.")
        except (OSError, discord.GatewayNotFound, discord.ConnectionClosed,
                discord.HTTPException) as exc:
            self._erreur(exc)
        finally:
            self.connected = False
            self.reconnecting = False
            try:
                if not client.is_closed():
                    await client.close()
            except (OSError, discord.HTTPException):
                pass

    # ------------------------------------------------------------------
    # Presence
    # ------------------------------------------------------------------
    def _statut_discord(self):
        return {
            "online": discord.Status.online,
            "idle": discord.Status.idle,
            "dnd": discord.Status.dnd,
            "invisible": discord.Status.invisible,
        }.get(self.presence_status, discord.Status.online)

    def _activite_discord(self):
        if not self.activity_name:
            return None
        if self.activity_type == 1:
            return discord.Streaming(name=self.activity_name, url=self.stream_url)
        return discord.Activity(type=discord.ActivityType(self.activity_type),
                                name=self.activity_name)

    def update_presence(self, status="online", activity_name="", activity_type=0,
                        stream_url=""):
        """Valide puis applique la presence ; retourne (succes, message)."""
        if status not in STATUTS:
            return False, "Statut de presence invalide."
        try:
            activity_type = int(activity_type)
        except (TypeError, ValueError):
            return False, "Type d'activite invalide."
        if activity_type not in TYPES_ACTIVITE:
            return False, "Type d'activite invalide."
        activity_name = (activity_name or "").strip()
        if len(activity_name) > 128:
            return False, "Le texte d'activite depasse 128 caracteres."
        if activity_type == 1:
            if not stream_url.startswith(("https://", "http://")):
                return False, "Une activite Streaming exige une URL http(s)."
        elif stream_url:
            return False, "L'URL de stream n'est valide que pour le type Streaming."

        self.presence_status = status
        self.activity_name = activity_name
        self.activity_type = activity_type
        self.stream_url = stream_url

        client, loop = self._client, self._loop
        if not self.connected or client is None or loop is None or not loop.is_running():
            return False, "Gateway non connectee : presence non envoyee."
        try:
            futur = asyncio.run_coroutine_threadsafe(
                client.change_presence(status=self._statut_discord(),
                                       activity=self._activite_discord()),
                loop,
            )
            futur.result(timeout=5)
        except concurrent.futures.TimeoutError:
            futur.cancel()
            return False, "Delai depasse lors de l'envoi de la presence."
        except (discord.HTTPException, OSError, RuntimeError) as exc:
            return False, self._redact(f"Presence refusee : {type(exc).__name__}.")
        self.log(f"Presence actualisee : {status.upper()} | {activity_name or 'sans activite'}")
        return True, "Presence envoyee."

    # ------------------------------------------------------------------
    # Arret
    # ------------------------------------------------------------------
    def stop(self, timeout=5):
        """Ferme la connexion, la boucle et le thread ; True si tout est arrete."""
        self.running = False
        self._arret_demande.set()
        client, loop = self._client, self._loop
        if client is not None and loop is not None and loop.is_running():
            try:
                futur = asyncio.run_coroutine_threadsafe(client.close(), loop)
                futur.result(timeout=timeout)
            except (concurrent.futures.TimeoutError, RuntimeError, OSError):
                pass
            except Exception:  # noqa: BLE001 - fermeture best effort
                pass
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=timeout)
        en_vie = bool(thread is not None and thread.is_alive())
        self.connected = False
        self.reconnecting = False
        if not en_vie:
            self._client = None
            self.started_at = None
        self.log("Bot deconnecte (session Gateway fermee).")
        return not en_vie
