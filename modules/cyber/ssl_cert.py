import ssl
import socket
from datetime import datetime, timezone
from core.common import demander, titre, bad, kv, attente, nettoyer_cible, C_CYBER, OKC, KOC, TIMEOUT

def certificat_ssl():
    hote = nettoyer_cible(demander("Domaine (ex: google.com)"))
    if not hote:
        return
    hote = hote.split("/")[0].split(":")[0]
    titre(f"CERTIFICAT SSL/TLS : {hote}", C_CYBER)
    try:
        with attente("Handshake TLS"):
            ctx = ssl.create_default_context()
            with socket.create_connection((hote, 443), timeout=TIMEOUT) as sock:
                with ctx.wrap_socket(sock, server_hostname=hote) as ssock:
                    cert = ssock.getpeercert()
                    version = ssock.version()
                    cipher = ssock.cipher()
    except Exception as e:
        bad(f"Erreur : {e}")
        return

    def nom_rdn(rdns):
        parts = []
        for rdn in rdns:
            for attr, val in rdn:
                parts.append(f"{attr}={val}")
        return ", ".join(parts)

    not_before = datetime.strptime(cert["notBefore"], "%b %d %H:%M:%S %Y %Z")
    not_after = datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z")
    reste = (not_after.replace(tzinfo=timezone.utc) - datetime.now(timezone.utc)).days
    sans = [x[1] for x in cert.get("subjectAltName", []) if x[0] == "DNS"]
    kv("Certificat", [
        ("Sujet", nom_rdn(cert.get("subject", ()))),
        ("Émetteur", nom_rdn(cert.get("issuer", ()))),
        ("Valide depuis", not_before.strftime("%d/%m/%Y")),
        ("Expire le", not_after.strftime("%d/%m/%Y")),
        ("Jours restants", f"{reste} ({OKC} OK)" if reste > 14 else f"{reste} ({KOC} bientôt)"),
        ("TLS", version),
        ("Cipher", f"{cipher[0]} ({cipher[1]} bits)" if cipher else "?"),
        ("SAN", ", ".join(sans[:12]) + ("..." if len(sans) > 12 else "") if sans else "-"),
    ], C_CYBER)
