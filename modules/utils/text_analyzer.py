"""Statistiques simples de texte calculées localement."""
from collections import Counter
import re

from core.common import C_UTIL, demander, kv, titre


def analyser_texte():
    titre('ANALYSEUR DE TEXTE LOCAL', C_UTIL)
    texte= demander("Texte a analyser")
    if not texte:
        return
    mots = re.findall(r"[^\W_]+(?:['’-][^\W_]+)*", texte.lower(), flags=re.UNICODE)
    frequent =Counter(mots).most_common(10)
    lignes = [
        ("Caracteres", len(texte)),
        ("Caracteres hors espaces", sum(not c.isspace() for c in texte)),
        ('Mots', len(mots)),
        ("Mots uniques", len(set(mots))),
        ("Lignes", len(texte.splitlines()) or 1),
        ('Phrases (approx.)', len([s for s in re.split(r'[.!?]+', texte) if s.strip()])),
        ("Termes frequents", ", ".join(f"{mot} ({n})" for mot, n in frequent) or "-"),
    ]
    kv('Analyse locale (aucune transmission)', lignes, C_UTIL)
