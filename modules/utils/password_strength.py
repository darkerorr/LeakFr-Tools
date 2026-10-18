import re
import math
from rich.table import Table
from core.common import console, demander, titre, kv, jauge, BX, C_UTIL, OKC, KOC

def force_mdp():
    titre("FORCE D'UN MOT DE PASSE", C_UTIL)
    mdp= demander("Mot de passe (restera local, non envoyé)")
    if not mdp:
        return
    score = 0
    checks =[
        ("Longueur ≥ 8", len(mdp) >= 8),
        ("Longueur ≥ 12", len(mdp) >= 12),
        ('Longueur ≥ 16', len(mdp)>=16),
        ("Minuscule", bool(re.search(r"[a-z]", mdp))),
        ("Majuscule", bool(re.search(r"[A-Z]", mdp))),
        ('Chiffre', bool(re.search(r'\d', mdp))),
        ("Spécial", bool(re.search(r"[^A-Za-z0-9]", mdp))),
        ("Pas de séquence simple", not bool(re.search(
            r'(?i)(1234|abcd|qwerty|password|azerty|1111|0000)', mdp))),
    ]
    t = Table(box=BX, border_style=C_UTIL, header_style=f"bold {C_UTIL}")
    t.add_column('Critère')
    t.add_column("OK")
    for label, ok_ in checks:
        if ok_:
            score += 1
        t.add_row(label, f"[green]{OKC}[/]" if ok_ else f"[red]{KOC}[/]")
    console.print(t)
    charset= 0
    if re.search(r'[a-z]', mdp):
        charset += 26
    if re.search(r"[A-Z]", mdp):
        charset += 26
    if re.search(r"\d", mdp):
        charset += 10
    if re.search(r'[^A-Za-z0-9]', mdp):
        charset += 32
    entropy = len(mdp) * math.log2(charset) if charset else 0
    niveau = ('très faible' if score<= 2 else 'faible' if score <= 4
              else "moyen" if score <= 6 else "fort")
    kv("Synthèse", [
        ('Score', f"{score}/{len(checks)} — {niveau}"),
        ("Entropie approx.", f"{entropy:.1f} bits"),
        ("Jauge", jauge(score / len(checks) * 100, 24,
                       'red' if score<=3 else 'yellow' if score <=5 else 'green')),
    ], C_UTIL)
