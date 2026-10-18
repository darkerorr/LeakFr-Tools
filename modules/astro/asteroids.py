from datetime import datetime, timezone
import requests
from rich.markup import escape
from core.common import titre, bad, warn, attente, afficher_pagine, C_ASTRO
from modules.astro.nasa import avertir_si_publique, params_nasa

def asteroides():
    jour = datetime.now(timezone.utc).date().isoformat()
    titre(f"ASTÉROÏDES PROCHES DE LA TERRE : {jour}", C_ASTRO)
    params, source_cle = params_nasa({"start_date": jour, "end_date": jour})
    if avertir_si_publique(source_cle):
        warn(f"Requête réelle avec la {source_cle}. Ajoute ta clé dans "
             "Paramètres > Clé API NASA (ou NASA_API_KEY) pour lever la limite.")
    try:
        with attente("Interrogation de la NASA (NeoWs)"):
            r = requests.get("https://api.nasa.gov/neo/rest/v1/feed",
                             params=params, timeout=25)
        if r.status_code == 429:
            warn(f"Limite de la clé ({source_cle}) atteinte, réessaie plus tard.")
            return
        data = r.json()
    except Exception as e:
        bad(f"Erreur : {e}")
        return
    objs = [o for liste in data.get("near_earth_objects", {}).values() for o in liste]
    if not objs:
        bad("Aucun objet trouvé.")
        return
    rows = []
    for o in objs:
        try:
            ca = o["close_approach_data"][0]
            m = o["estimated_diameter"]["meters"]
            diam = (m["estimated_diameter_min"] + m["estimated_diameter_max"]) / 2
            vit = float(ca["relative_velocity"]["kilometers_per_hour"])
            dist = float(ca["miss_distance"]["kilometers"])
            lune = float(ca["miss_distance"]["lunar"])
            rows.append((o["name"], f"{diam:,.0f}".replace(",", " "),
                         f"{vit:,.0f}".replace(",", " "),
                         f"{dist:,.0f}".replace(",", " "), f"{lune:.1f}",
                         "OUI" if o["is_potentially_hazardous_asteroid"] else "non"))
        except Exception:
            continue
    rows.sort(key=lambda x: float(x[4]))

    def rendu(r):
        danger = "[bold red]OUI[/]" if r[5] == "OUI" else "[green]non[/]"
        return [escape(r[0]), f"{r[1]} m", f"{r[2]} km/h", f"{r[3]} km",
                f"{r[4]} x Terre-Lune", danger]

    afficher_pagine("ASTÉROÏDES DU JOUR (du plus proche au plus loin)",
                    ["Nom", "Diamètre moy.", "Vitesse", "Distance", "En distances lunaires",
                     "Potentiellement dangereux"],
                    rows, rendu, par_page=12, fichier=f"asteroides_{jour}.csv",
                    couleur=C_ASTRO, caption="Source : NASA NeoWs")
