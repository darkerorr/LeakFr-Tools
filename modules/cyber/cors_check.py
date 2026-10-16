import requests
from core.common import demander, titre, ok, bad, warn, kv, attente, C_CYBER, KOC, HEADERS, TIMEOUT

def cors_check():
    url = demander("URL API / site")
    if not url.startswith("http"):
        url = "https://" + url
    titre(f"TEST CORS : {url}", C_CYBER)
    origin = demander("Origin de test", defaut="https://evil.example")
    try:
        with attente("Requête preflight-like"):
            r = requests.get(url, headers={**HEADERS, "Origin": origin},
                             timeout=TIMEOUT)
    except Exception as e:
        bad(f"Erreur : {e}")
        return
    acao = r.headers.get("Access-Control-Allow-Origin", "")
    acac = r.headers.get("Access-Control-Allow-Credentials", "")
    acam = r.headers.get("Access-Control-Allow-Methods", "")
    kv("Headers CORS", [
        ("Origin envoyé", origin),
        ("Allow-Origin", acao or f"{KOC} absent"),
        ("Allow-Credentials", acac or "-"),
        ("Allow-Methods", acam or "-"),
    ], C_CYBER)
    if acao == "*":
        warn("ACA-Origin = * (ouvert à tous les sites).")
    elif acao == origin:
        warn("Le serveur reflète ton Origin — à vérifier avec Credentials.")
    elif not acao:
        ok("Pas de CORS permissif détecté sur cette requête GET.")
