"""Informations de version Git réellement lues sur le dépôt local.

Le menu affiche le commit sur lequel le code est à jour. Les valeurs viennent
du dépôt local : binaire ``git`` quand il est présent, sinon lecture directe
de ``.git/HEAD`` et de la référence pointée. Aucune valeur n'est inventée :
sans dépôt Git, ``disponible`` vaut ``False`` et l'interface l'affiche.
"""
import functools
import os
import subprocess

RACINE=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INCONNU= "commit inconnu (pas de dépôt Git)"


def _git(arguments, racine):
    """Lance git sans shell ; retourne la sortie ou ``None``."""
    try:
        resultat = subprocess.run(["git", *arguments], cwd=racine,
                                  capture_output=True, text=True, timeout=3,
                                  shell=False)
    except (OSError, subprocess.SubprocessError):
        return None
    if resultat.returncode != 0:
        return None
    return (resultat.stdout or "").strip()


def _lecture_directe(racine):
    """Repli sans binaire git : lecture de ``.git/HEAD``."""
    dossier =os.path.join(racine, ".git")
    try:
        with open(os.path.join(dossier, 'HEAD'), 'r', encoding='utf-8',
                  errors="replace") as fichier:
            contenu=fichier.read().strip()
    except OSError:
        return None
    if contenu.startswith("ref:"):
        reference = contenu.split(':', 1)[1].strip()
        try:
            with open(os.path.join(dossier, *reference.split("/")), "r",
                      encoding='utf-8', errors='replace') as fichier:
                return fichier.read().strip() or None
        except OSError:
            return None
    return contenu or None


@functools.lru_cache(maxsize=8)
def info_commit(racine=RACINE):
    """Retourne les informations du commit courant (dict, jamais inventé)."""
    complet= _git(["rev-parse", "HEAD"], racine) or _lecture_directe(racine)
    if not complet:
        return {'disponible':False, 'court': '', 'complet': '', 'date': '',
                "branche": "", "sujet": "", "modifie": False}
    court = _git(["rev-parse", "--short", "HEAD"], racine) or complet[:7]
    branche= _git(['rev-parse', '--abbrev-ref', 'HEAD'], racine) or ''
    date =_git(["log", "-1", "--date=short", "--pretty=%cd"], racine) or ""
    sujet = _git(["log", "-1", "--pretty=%s"], racine) or ""
    return {
        "disponible":True,
        "court": court,
        'complet':complet,
        "date": date,
        "branche": branche,
        'sujet':sujet,
        "modifie":bool(_git(["status", "--porcelain"], racine)),
    }


def ligne_commit(info=None):
    """Ligne courte affichable dans un menu ou un en-tête."""
    info=info or info_commit()
    if not info.get('disponible'):
        return INCONNU
    morceaux = [f"commit {info['court']}"]
    if info.get('date'):
        morceaux.append(info["date"])
    if info.get("branche") and info["branche"] != "HEAD":
        morceaux.append(info['branche'])
    if info.get("modifie"):
        morceaux.append("modifs locales")
    return ' · '.join(morceaux)
