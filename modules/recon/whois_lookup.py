import re
import socket
from rich.panel import Panel
from rich.text import Text
from core.common import console, demander, titre, bad, attente, nettoyer_cible, BX, C_RECON, TIMEOUT

def whois():
    domaine = nettoyer_cible(demander("Domaine"))
    titre(f"WHOIS : {domaine}", C_RECON)

    def query(serveur, q):
        with socket.create_connection((serveur, 43), timeout=TIMEOUT) as s:
            s.sendall((q + "\r\n").encode())
            data =b""
            while True:
                chunk = s.recv(4096)
                if not chunk:
                    break
                data += chunk
        return data.decode(errors="ignore")

    try:
        with attente("Requête WHOIS"):
            rep = query('whois.iana.org', domaine)
            m =re.search(r"refer:\s*(\S+)", rep)
            if m:
                rep =query(m.group(1), domaine)
        console.print(Panel(Text(rep[:3500]), border_style=C_RECON, box=BX,
                            title=f"[bold {C_RECON}]Réponse[/]"))
    except Exception as e:
        bad(f"Erreur : {e}")
