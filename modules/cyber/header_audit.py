import requests
from rich.table import Table
from core.common import console, demander, titre, bad, kv, jauge, attente, BX, C_CYBER, OKC, KOC, HEADERS, TIMEOUT

def audit_headers():
    url = demander("URL (ex: https://example.com)")
    if not url.startswith("http"):
        url = "https://" + url
    titre(f"AUDIT DES HEADERS : {url}", C_CYBER)
    attendus = {
        "Strict-Transport-Security": "Force le HTTPS",
        "Content-Security-Policy": "Protège contre le XSS",
        "X-Frame-Options": "Protège contre le clickjacking",
        "X-Content-Type-Options": "Empêche le MIME sniffing",
        "Referrer-Policy": "Contrôle les infos de referrer",
        "Permissions-Policy": "Limite les API du navigateur",
    }
    try:
        with attente("Requête"):
            r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    except Exception as e:
        bad(f"Erreur : {e}")
        return
    t = Table(box=BX, border_style=C_CYBER, header_style=f"bold {C_CYBER}")
    t.add_column("Header", style="bold")
    t.add_column("État")
    t.add_column("Rôle", style="dim")
    presents = 0
    for h, desc in attendus.items():
        if h in r.headers:
            presents += 1
            t.add_row(h, f"[bold green]{OKC} présent[/]", desc)
        else:
            t.add_row(h, f"[bold red]{KOC} manquant[/]", desc)
    console.print(t)
    score = presents / len(attendus)
    couleur = "green" if score >= 0.8 else "yellow" if score >= 0.5 else "red"
    kv("Résumé", [("Code HTTP", r.status_code),
                  ("Serveur", r.headers.get("Server", "non communiqué")),
                  ("Score", f"{presents}/{len(attendus)}"),
                  ("Jauge", jauge(score * 100, 20, couleur))], couleur)
