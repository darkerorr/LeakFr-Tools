import re
from urllib.parse import urlparse, parse_qs
import requests
from rich.table import Table
from rich.markup import escape
from core.common import console, demander, titre, ok, warn, kv, attente, BX, C_OSINT, HEADERS, TIMEOUT

def analyse_url():
    url = demander("URL à analyser")
    if not url:
        return
    if not url.startswith("http"):
        url = "https://" + url
    titre(f"ANALYSE D'URL", C_OSINT)
    p = urlparse(url)
    params = parse_qs(p.query, keep_blank_values=True)
    lignes = [
        ("URL", url),
        ("Schéma", p.scheme or "?"),
        ("Hôte", p.hostname or "?"),
        ("Port", str(p.port or ("443" if p.scheme == "https" else "80"))),
        ("Chemin", p.path or "/"),
        ("Fragment", p.fragment or "-"),
        ("Paramètres", f"{len(params)} clé(s)"),
    ]
    kv("Structure", lignes, C_OSINT)
    if params:
        t = Table(box=BX, border_style=C_OSINT, header_style=f"bold {C_OSINT}",
                  title="Query string")
        t.add_column("Clé", style="bold")
        t.add_column("Valeur")
        for k, vals in params.items():
            t.add_row(escape(k), escape(", ".join(vals)))
        console.print(t)
    try:
        with attente("Résolution de la chaîne de redirection"):
            r = requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
        if r.history:
            for i, h in enumerate(r.history, 1):
                ok(f"Hop {i} : {h.status_code} → {h.headers.get('Location', h.url)}")
        ok(f"Finale : {r.status_code} → {r.url}")
        titre_html = re.search(r"(?is)<title[^>]*>(.*?)</title>", r.text)
        if titre_html:
            ok(f"Titre page : {re.sub(r'\s+', ' ', titre_html.group(1)).strip()[:120]}")
    except Exception as e:
        warn(f"Fetch impossible : {e}")
