import re
from datetime import datetime
import requests
from rich.markup import escape
from core.common import console, demander, choisir_option, titre, bad, attente, nettoyer_cible, afficher_pagine, C_GOLD, HEADERS

def wayback():
    cible = nettoyer_cible(demander("URL ou domaine (ex: example.com)"))
    if not cible:
        return
    modes = ["Cette page exacte (toutes les versions archivées)", "Tout le domaine (pages uniques, code 200)"]
    mode = choisir_option('ETENDUE DES ARCHIVES', modes)
    if mode is None:
        return

    params={"url": cible, "output": "json",
              "fl": "timestamp,original,statuscode,mimetype", "limit": 10000}
    if mode ==modes[0]:
        params["collapse"] = "digest"
    else:
        params.update({'matchType': 'domain', 'collapse': 'urlkey',
                       "filter":"statuscode:200"})

    titre(f"WAYBACK MACHINE : {cible}", C_GOLD)
    try:
        with attente("Interrogation de archive.org"):
            r = requests.get('https://web.archive.org/cdx/search/cdx',
                             params=params, headers=HEADERS, timeout=90)
            data = r.json()
    except Exception as e:
        bad(f"Erreur : {e}")
        return

    rows=[tuple(x) for x in data[1:]] if data and len(data) > 1 else []
    if not rows:
        bad('Aucune archive trouvée.')
        return
    rows.sort(key=lambda x: x[0], reverse=True)

    def dt(ts):
        try:
            return datetime.strptime(ts[:14], '%Y%m%d%H%M%S')
        except Exception:
            return None

    premier, dernier=dt(rows[-1][0]), dt(rows[0][0])
    caption=""
    if premier and dernier:
        caption = (f"Première archive : {premier:%d/%m/%Y}   |   "
                   f"Dernière : {dernier:%d/%m/%Y}")

    def rendu(row):
        ts, original, code, mime= row
        d = dt(ts)
        date = f"{d:%d/%m/%Y}" if d else ts
        heure = f"{d:%H:%M:%S}" if d else ""
        if code.startswith('2'):
            c = f"[bold green]{code}[/]"
        elif code.startswith("3"):
            c = f"[bold yellow]{code}[/]"
        elif code in ("-", ""):
            c = "[dim]-[/]"
        else:
            c= f"[bold red]{code}[/]"
        o=original if len(original) <= 60 else original[:57] + "..."
        return [date, heure, c, escape(mime), escape(o)]

    def lien(row):
        return f"https://web.archive.org/web/{row[0]}/{row[1]}"

    nom_fichier="wayback_" + re.sub(r"[^\w.-]", "_", cible) + ".csv"
    afficher_pagine('ARCHIVES WAYBACK MACHINE',
                    ["Date", "Heure", "Code", "Type", "URL d'origine"],
                    rows, rendu, lien=lien, par_page=15,
                    fichier=nom_fichier, couleur=C_GOLD, caption=caption)
