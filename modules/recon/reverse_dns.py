import re
import socket
from core.common import demander, titre, bad, kv, attente, nettoyer_cible, resoudre, C_RECON

def reverse_dns():
    cible = nettoyer_cible(demander("IP (ou domaine à résoudre d'abord)"))
    if not cible:
        return
    ip = cible if re.match(r"^\d+\.\d+\.\d+\.\d+$", cible) else resoudre(cible)
    if not ip:
        bad("IP invalide / irrésolue.")
        return
    titre(f"REVERSE DNS (PTR) : {ip}", C_RECON)
    try:
        with attente("Résolution PTR"):
            host, aliases, _ = socket.gethostbyaddr(ip)
        kv("Résultat", [("IP", ip), ("PTR", host),
                        ("Alias", ", ".join(aliases) if aliases else "-")], C_RECON)
    except socket.herror:
        bad("Aucun enregistrement PTR.")
    except Exception as e:
        bad(f"Erreur : {e}")
