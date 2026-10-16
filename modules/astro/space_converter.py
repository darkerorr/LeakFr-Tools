from rich.table import Table
from core.common import console, demander, choisir_option, titre, bad, BX, C_ASTRO

def duree_lisible(sec):
    if sec < 60:
        return f"{sec:.2f} secondes"
    if sec < 3600:
        return f"{sec / 60:.2f} minutes"
    if sec < 86400:
        return f"{sec / 3600:.2f} heures"
    if sec < 365.25 * 86400:
        return f"{sec / 86400:.2f} jours"
    return f"{sec / (365.25 * 86400):.4g} ans"

UNITES = {
    "m": ("mètre", 1.0),
    "km": ("kilomètre", 1000.0),
    "mi": ("mile", 1609.344),
    "tl": ("distance Terre-Lune", 384400000.0),
    "ua": ("unité astronomique", 149597870700.0),
    "ls": ("seconde-lumière", 299792458.0),
    "al": ("année-lumière", 9.4607304725808e15),
    "pc": ("parsec", 3.0856775814913673e16),
}

def convertisseur():
    titre("CONVERTISSEUR D'UNITÉS SPATIALES", C_ASTRO)
    console.print("[dim]Unités : " + ", ".join(f"{v[0]} ({k})" for k, v in UNITES.items())
                  + "[/]\n")
    try:
        val = float(demander("Valeur").replace(",", ".").replace(" ", ""))
    except ValueError:
        bad("Nombre invalide.")
        return
    libelles_unites = [f"{nom} ({code})" for code, (nom, _) in UNITES.items()]
    unite_choisie = choisir_option("UNITE DE DEPART", libelles_unites, selection_initiale=1)
    if unite_choisie is None:
        return
    unite = unite_choisie.rsplit("(", 1)[1].rstrip(")")
    metres = val * UNITES[unite][1]
    t = Table(box=BX, border_style=C_ASTRO, header_style=f"bold {C_ASTRO}",
              title=f"{val:g} {unite} en...", title_style=f"bold {C_ASTRO}")
    t.add_column("Unité")
    t.add_column("Valeur", justify="right", style="bold")
    for k, (nom, f) in UNITES.items():
        t.add_row(f"{nom} ({k})", f"{metres / f:,.6g}".replace(",", " "))
    console.print(t)
    console.print(f"\n[bold {C_GOLD}]Lumière :[/] cette distance est parcourue en "
                  f"{duree_lisible(metres / 299792458.0)}.")
