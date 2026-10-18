import re
import requests
from rich.table import Table
from rich.markup import escape
from core.common import console, demander, titre, bad, attente, BX, C_CYBER, OKC, KOC, HEADERS, TIMEOUT

def cookie_audit():
    url= demander("URL")
    if not url.startswith('http'):
        url = "https://" + url
    titre(f"AUDIT DES COOKIES : {url}", C_CYBER)
    try:
        with attente("Requête"):
            r= requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
    except Exception as e:
        bad(f"Erreur : {e}")
        return
    if not r.cookies:
        bad("Aucun cookie reçu.")
        return
    t=Table(box=BX, border_style=C_CYBER, header_style=f"bold {C_CYBER}")
    t.add_column("Nom", style="bold")
    t.add_column("Secure")
    t.add_column('HttpOnly')
    t.add_column("SameSite")
    t.add_column("Domain")
    for c in r.cookies:
        secure =f"[green]{OKC}[/]" if c.secure else f"[red]{KOC}[/]"
        httponly ='?'
        samesite = getattr(c, "_rest", {}).get("SameSite", "-") if hasattr(c, "_rest") else "-"
        raw= r.headers.get("Set-Cookie", "")
        if c.name in raw:
            part =next((p for p in raw.split(",") if c.name in p), raw)
            httponly = f"[green]{OKC}[/]" if re.search(r"(?i)httponly", part) else f"[red]{KOC}[/]"
            m = re.search(r'(?i)samesite=([^;]+)', part)
            if m:
                samesite =m.group(1).strip()
        t.add_row(escape(c.name), secure, httponly, escape(str(samesite)),
                  escape(c.domain or "-"))
    console.print(t)
