from datetime import datetime
import requests
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Confirm
from core.common import console, demander, titre, bad, warn, kv, attente, ouvrir_url, BX, C_ASTRO

def apod():
    titre("IMAGE ASTRONOMIQUE DU JOUR (NASA)", C_ASTRO)
    saisie = demander("Date AAAA-MM-JJ (Entrée = aujourd'hui)", defaut="")
    params = {"api_key": "DEMO_KEY"}
    if saisie:
        try:
            datetime.strptime(saisie, "%Y-%m-%d")
        except ValueError:
            bad("Format invalide. Exemple : 2000-01-31")
            return
        params["date"] = saisie
    try:
        with attente("Interrogation de la NASA"):
            r = requests.get("https://api.nasa.gov/planetary/apod",
                             params=params, timeout=20)
    except Exception as e:
        bad(f"Erreur : {e}")
        return
    if r.status_code == 429:
        warn("Limite de la clé publique DEMO atteinte, réessaie plus tard.")
        return
    try:
        d = r.json()
    except Exception:
        bad("Réponse illisible.")
        return
    if "title" not in d:
        bad(d.get("msg") or str(d.get("error", "Réponse inattendue")))
        return
    url = d.get("hdurl") or d.get("url") or ""
    kv("Fiche", [("Titre", d.get("title")), ("Date", d.get("date")),
                 ("Auteur", d.get("copyright", "NASA / domaine public").strip()),
                 ("Type", d.get("media_type")), ("Lien", url)], C_ASTRO)
    console.print(Panel(Text(d.get("explanation", "")), box=BX, border_style=C_ASTRO,
                        title=f"[bold {C_ASTRO}]Explication (en anglais)[/]"))
    if url and Confirm.ask("Ouvrir dans le navigateur ?", default=True):
        ouvrir_url(url)
