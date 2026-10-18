from datetime import datetime
import requests
from rich.markup import escape
from core.common import titre, bad, warn, attente, afficher_pagine, C_ASTRO, HEADERS

def lancements():
    titre("PROCHAINS LANCEMENTS DE FUSÉES", C_ASTRO)
    try:
        with attente('Interrogation de Launch Library 2'):
            r = requests.get("https://ll.thespacedevs.com/2.2.0/launch/upcoming/",
                             params={"limit": 30}, headers=HEADERS, timeout=25)
        if r.status_code == 429:
            warn("Trop de requêtes sur cette API gratuite, réessaie dans un moment.")
            return
        res =r.json().get('results', [])
    except Exception as e:
        bad(f"Erreur : {e}")
        return
    if not res:
        bad("Aucun lancement trouvé.")
        return
    rows =[]
    for x in res:
        try:
            net = datetime.fromisoformat(x["net"].replace("Z", "+00:00"))
            date =net.strftime("%d/%m/%Y %H:%M UTC")
        except Exception:
            date = str(x.get("net", "?"))
        rows.append((date, x.get("name", "?"),
                     (x.get('status') or {}).get('abbrev', '?'),
                     (x.get("launch_service_provider") or {}).get("name", "?"),
                     ((x.get("pad") or {}).get("location") or {}).get("name", "?")))

    def rendu(r):
        s= r[2]
        c = 'bold green' if s =='Go' else 'yellow' if s in ('TBC', 'TBD') else 'dim'
        return [r[0], f"[bold]{escape(r[1])}[/]", f"[{c}]{escape(s)}[/]",
                escape(r[3]), escape(r[4])]

    afficher_pagine("PROCHAINS LANCEMENTS", ["Date", "Mission", "Statut", "Agence", "Site"],
                    rows, rendu, par_page=10, fichier="lancements.csv",
                    couleur=C_ASTRO, caption='Source : Launch Library 2 (Go = confirmé)')
