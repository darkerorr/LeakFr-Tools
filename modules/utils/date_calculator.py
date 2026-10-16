"""Calcul de différences de dates sans dépendance externe."""
from datetime import datetime, timedelta

from core.common import C_UTIL, demander, kv, titre, warn


def _parse_date(value):
    for pattern in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(value.strip(), pattern).date()
        except ValueError:
            continue
    raise ValueError("Formats acceptes : AAAA-MM-JJ ou JJ/MM/AAAA")


def calculer_dates():
    titre("CALCULATEUR DE DATES", C_UTIL)
    mode = demander("Mode : 1 difference entre dates, 2 ajouter/retirer des jours", defaut="1")
    try:
        if mode == "1":
            debut = _parse_date(demander("Premiere date (AAAA-MM-JJ ou JJ/MM/AAAA)"))
            fin = _parse_date(demander("Seconde date (AAAA-MM-JJ ou JJ/MM/AAAA)"))
            delta = (fin - debut).days
            kv("Difference", [
                ("Premier jour", debut.isoformat()), ("Second jour", fin.isoformat()),
                ("Jours signes", delta), ("Jours absolus", abs(delta)),
                ("Semaines completes", abs(delta) // 7),
            ], C_UTIL)
        elif mode == "2":
            origine = _parse_date(demander("Date de depart (AAAA-MM-JJ ou JJ/MM/AAAA)"))
            jours_txt = demander("Nombre de jours (negatif pour retrancher)")
            jours = int(jours_txt)
            resultat = origine + timedelta(days=jours)
            kv("Date calculee", [
                ("Depart", origine.isoformat()), ("Decalage (jours)", jours),
                ("Resultat", resultat.isoformat()), ("Jour de semaine", resultat.strftime("%A")),
            ], C_UTIL)
        else:
            warn("Mode inconnu : choisissez 1 ou 2.")
    except (ValueError, OverflowError) as exc:
        warn(f"Saisie invalide : {exc}")
