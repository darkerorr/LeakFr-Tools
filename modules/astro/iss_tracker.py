from datetime import datetime, timezone
import requests
from rich.table import Table
from rich.prompt import Confirm
from rich.markup import escape
from core.common import console, titre, bad, kv, attente, ouvrir_url, BX, C_ASTRO, TIMEOUT

def iss():
    titre("ISS : POSITION EN DIRECT", C_ASTRO)
    try:
        with attente("Contact de la station"):
            pos = requests.get("http://api.open-notify.org/iss-now.json",
                               timeout=TIMEOUT).json()
            ast = requests.get("http://api.open-notify.org/astros.json",
                               timeout=TIMEOUT).json()
    except Exception as e:
        bad(f"Erreur : {e}")
        return
    lat = float(pos["iss_position"]["latitude"])
    lon = float(pos["iss_position"]["longitude"])
    quand = datetime.fromtimestamp(pos["timestamp"], tz=timezone.utc)
    carte = f"https://www.google.com/maps?q={lat},{lon}"
    kv("Position actuelle", [
        ("Latitude", f"{lat:.4f}°"),
        ("Longitude", f"{lon:.4f}°"),
        ("Heure (UTC)", quand.strftime("%d/%m/%Y %H:%M:%S")),
        ("Altitude moyenne", "~420 km"),
        ("Vitesse", "~27 600 km/h (un tour de Terre en ~92 min)"),
        ("Carte", carte),
    ], C_ASTRO)

    gens = ast.get("people", [])
    t = Table(title=f"Humains dans l'espace : {ast.get('number', len(gens))}",
              title_style=f"bold {C_ASTRO}", box=BX, border_style=C_ASTRO,
              header_style=f"bold {C_ASTRO}")
    t.add_column("Nom", style="bold")
    t.add_column("Vaisseau")
    for p in gens:
        t.add_row(escape(p.get("name", "?")), escape(p.get("craft", "?")))
    console.print(t)
    if Confirm.ask("Ouvrir la position sur la carte ?", default=False):
        ouvrir_url(carte)
