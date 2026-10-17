"""Stockage JSON local pour les preferences non sensibles.

Les fichiers sont ecrits de facon atomique et, sur les systemes qui le
permettent, avec des permissions restreintes au proprietaire. Aucun token
ni secret ne doit etre transmis a ces fonctions.
"""
import json
import os
from pathlib import Path

TAILLE_MAX = 2_000_000


def charger_json(path, defaut):
    """Charge un fichier JSON borne ; retourne ``defaut`` si absent ou invalide."""
    chemin = Path(path)
    try:
        if not chemin.is_file() or chemin.stat().st_size > TAILLE_MAX:
            return defaut
        return json.loads(chemin.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return defaut


def ecrire_json(path, donnees):
    """Ecrit un JSON atomique avec permissions restreintes."""
    chemin = Path(path)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    temporaire = chemin.with_name(chemin.name + ".tmp")
    temporaire.write_text(json.dumps(donnees, ensure_ascii=False, indent=2) + "\n",
                          encoding="utf-8")
    try:
        os.chmod(temporaire, 0o600)
    except OSError:
        pass
    os.replace(temporaire, chemin)
    try:
        os.chmod(chemin, 0o600)
    except OSError:
        pass
    return chemin
