import requests
from rich.table import Table
from rich.markup import escape
from core.common import console, demander, titre, ok, bad, attente, BX, C_CYBER, C_GOLD, HEADERS, TIMEOUT

def chaine_redirect():
    url = demander("URL de départ")
    if not url.startswith("http"):
        url = "https://" + url
    titre("CHAÎNE DE REDIRECTIONS", C_CYBER)
    try:
        with attente("Suivi des redirections"):
            r = requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
    except Exception as e:
        bad(f"Erreur : {e}")
        return
    t = Table(box=BX, border_style=C_CYBER, header_style=f"bold {C_CYBER}")
    t.add_column("#", style=f"bold {C_GOLD}", justify="right")
    t.add_column("Code")
    t.add_column("URL")
    for i, h in enumerate(r.history, 1):
        t.add_row(str(i), str(h.status_code), escape(h.url))
    t.add_row(str(len(r.history) + 1), f"[bold green]{r.status_code}[/]", escape(r.url))
    console.print(t)
    ok(f"{len(r.history)} redirection(s)")
