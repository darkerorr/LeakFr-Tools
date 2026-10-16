import re
import requests
from core.common import demander, titre, bad, kv, attente, nettoyer_cible, resoudre, C_RECON, TIMEOUT

def asn_info():
    cible = nettoyer_cible(demander("IP ou domaine"))
    ip = cible if re.match(r"^\d+\.\d+\.\d+\.\d+$", cible) else resoudre(cible)
    if not ip:
        bad("Impossible de résoudre.")
        return
    titre(f"INFO ASN / RÉSEAU : {ip}", C_RECON)
    try:
        with attente("ip-api.com"):
            d = requests.get(f"http://ip-api.com/json/{ip}",
                             params={"fields": "status,message,as,asname,isp,org,query,"
                                               "country,regionName,city,reverse,mobile,"
                                               "proxy,hosting"},
                             timeout=TIMEOUT).json()
        if d.get("status") != "success":
            bad(d.get("message", "échec"))
            return
        kv("Résultat", [
            ("IP", d.get("query")),
            ("AS", d.get("as")),
            ("Nom AS", d.get("asname")),
            ("ISP", d.get("isp")),
            ("Org", d.get("org")),
            ("Pays", d.get("country")),
            ("Ville", d.get("city")),
            ("PTR", d.get("reverse") or "-"),
            ("Mobile", "oui" if d.get("mobile") else "non"),
            ("Proxy/VPN", "oui" if d.get("proxy") else "non"),
            ("Hosting", "oui" if d.get("hosting") else "non"),
        ], C_RECON)
    except Exception as e:
        bad(f"Erreur : {e}")
