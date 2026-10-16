import re
import requests
from core.common import demander, titre, bad, kv, attente, C_RECON, HEADERS, TIMEOUT

def lookup_mac():
    titre("LOOKUP FABRICANT MAC", C_RECON)
    mac = demander("Adresse MAC (ex: 00:1A:2B:3C:4D:5E)")
    mac_n = re.sub(r"[^0-9A-Fa-f]", "", mac)
    if len(mac_n) < 6:
        bad("MAC invalide (au moins 3 octets / OUI).")
        return
    oui = mac_n[:6].upper()
    formatee = ":".join(mac_n[i:i + 2] for i in range(0, min(len(mac_n), 12), 2))
    try:
        with attente("Interrogation macvendors"):
            r = requests.get(f"https://api.macvendors.com/{oui}",
                             headers=HEADERS, timeout=TIMEOUT)
        if r.status_code == 200 and r.text.strip():
            kv("Résultat", [("MAC", formatee), ("OUI", oui),
                            ("Fabricant", r.text.strip())], C_RECON)
        else:
            bad("Fabricant introuvable pour cet OUI.")
    except Exception as e:
        bad(f"Erreur : {e}")
