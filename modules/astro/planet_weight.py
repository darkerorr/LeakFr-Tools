from rich.table import Table
from core.common import console, demander, titre, bad, jauge, BX, C_ASTRO, C_GOLD

GRAVITES = [("Soleil", 274.0), ("Mercure", 3.70), ("Vénus", 8.87), ("Terre", 9.81),
            ("Lune", 1.62), ("Mars", 3.71), ("Jupiter", 24.79), ("Saturne", 10.44),
            ("Uranus", 8.87), ("Neptune", 11.15), ("Pluton", 0.62)]

def poids_planetes():
    titre("TON POIDS SUR LES AUTRES ASTRES", C_ASTRO)
    try:
        m = float(demander("Ta masse en kg").replace(",", "."))
    except ValueError:
        bad("Nombre invalide.")
        return
    t = Table(box=BX, border_style=C_ASTRO, header_style=f"bold {C_ASTRO}")
    t.add_column("Astre", style="bold")
    t.add_column("Gravité (m/s²)", justify="right")
    t.add_column("Tu pèserais (kg ressentis)", justify="right", style=f"bold {C_GOLD}")
    t.add_column("Comparé à la Terre")
    for nom, g in GRAVITES:
        ressenti = m * g / 9.81
        t.add_row(nom, f"{g:g}", f"{ressenti:,.1f}".replace(",", " "),
                  jauge(min(100, g / 28 * 100), 24, C_ASTRO))
    console.print(t)
    console.print("[dim]Sur le Soleil, la barre est tronquée (gravité ~28 fois celle de la Terre).[/]")
