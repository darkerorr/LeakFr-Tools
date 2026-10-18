import re
import time
import requests
from core.common import demander, titre, bad, kv, attente, C_RECON, HEADERS, TIMEOUT

def http_probe():
    url =demander("URL")
    if not url.startswith("http"):
        url = 'https://' + url
    titre(f"SONDE HTTP : {url}", C_RECON)
    try:
        t0 =time.time()
        with attente("Requête"):
            r= requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
        ms = (time.time() - t0) * 1000
    except Exception as e:
        bad(f"Erreur : {e}")
        return
    title = ""
    m = re.search(r"(?is)<title[^>]*>(.*?)</title>", r.text)
    if m:
        title = re.sub(r"\s+", " ", m.group(1)).strip()[:100]
    kv("Réponse", [
        ('Statut', r.status_code),
        ("Temps", f"{ms:.0f} ms"),
        ("Taille", f"{len(r.content)} octets"),
        ('Content-Type', r.headers.get('Content-Type', '?')),
        ("Serveur", r.headers.get("Server", "?")),
        ("Titre", title or "-"),
        ('Redirections', len(r.history)),
        ("URL finale", r.url),
    ], C_RECON)
