import math
from datetime import datetime, timezone, timedelta
import requests
from core.common import console, demander, titre, bad, kv, jauge, attente, C_ASTRO, C_GOLD, TIMEOUT

def phase_lune(dt):
    cycle = 29.530588853
    ref = datetime(2000, 1, 6, 18, 14, tzinfo=timezone.utc)
    age = ((dt - ref).total_seconds() / 86400) % cycle
    illum = (1 - math.cos(2 * math.pi * age / cycle)) / 2 * 100
    noms = [(1.85, "Nouvelle Lune"), (5.54, "Premier croissant"),
            (9.23, "Premier quartier"), (12.92, "Gibbeuse croissante"),
            (16.61, "Pleine Lune"), (20.30, "Gibbeuse décroissante"),
            (23.99, "Dernier quartier"), (27.68, "Dernier croissant")]
    nom = "Nouvelle Lune"
    for limite, n in noms:
        if age < limite:
            nom = n
            break
    return age, illum, nom, cycle

def lune_soleil():
    titre("LUNE & SOLEIL", C_ASTRO)
    maintenant = datetime.now(timezone.utc)
    age, illum, nom, cycle = phase_lune(maintenant)
    nouvelle = maintenant + timedelta(days=cycle - age)
    pleine = maintenant + timedelta(days=(cycle / 2 - age) % cycle)
    kv("Phase de la Lune", [
        ("Phase", nom),
        ("Âge de la Lune", f"{age:.1f} jours"),
        ("Illumination", f"{illum:.0f} %"),
        ("", jauge(illum, 30, C_GOLD)),
        ("Prochaine Pleine Lune", pleine.strftime("%d/%m/%Y")),
        ("Prochaine Nouvelle Lune", nouvelle.strftime("%d/%m/%Y")),
    ], C_ASTRO)
    console.print("[dim]Calcul approximatif (à quelques heures près).[/]\n")

    ville = demander("Ville pour le lever/coucher du Soleil (Entrée = passer)", defaut="")
    if not ville:
        return
    try:
        with attente("Recherche"):
            g = requests.get("https://geocoding-api.open-meteo.com/v1/search",
                             params={"name": ville, "count": 1, "language": "fr"},
                             timeout=TIMEOUT).json()
            res = g.get("results")
            if res:
                lieu = res[0]
                f = requests.get("https://api.open-meteo.com/v1/forecast",
                                 params={"latitude": lieu["latitude"],
                                         "longitude": lieu["longitude"],
                                         "daily": "sunrise,sunset", "timezone": "auto",
                                         "forecast_days": 1}, timeout=TIMEOUT).json()
        if not res:
            bad("Ville introuvable.")
            return
        lev = datetime.fromisoformat(f["daily"]["sunrise"][0])
        cou = datetime.fromisoformat(f["daily"]["sunset"][0])
        duree = cou - lev
        h, reste = divmod(int(duree.total_seconds()), 3600)
        kv(f"Soleil : {lieu['name']} ({lieu.get('country', '?')})", [
            ("Lever", lev.strftime("%H:%M")),
            ("Coucher", cou.strftime("%H:%M")),
            ("Durée du jour", f"{h} h {reste // 60:02d} min"),
            ("Fuseau", f.get("timezone", "?")),
        ], C_ASTRO)
    except Exception as e:
        bad(f"Erreur : {e}")
