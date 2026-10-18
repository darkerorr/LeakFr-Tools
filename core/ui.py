"""Design system "dashboard" de LeakFr-Tools.

Interface professionnelle et sobre : filets fins, colonnes alignées, aucun
dégradé ni animation. Le menu principal, les sous-menus numérotés, les
paramètres et les listes passent tous par ces primitives pour rester
cohérents, du grand écran au téléphone.

Règle de largeur : chaque fonction reçoit une largeur *exacte* et ne renvoie
jamais une ligne plus longue (le texte est tronqué proprement).
"""
from rich import box
from rich.cells import cell_len
from rich.console import Group
from rich.panel import Panel
from rich.text import Text

BORDURE = "grey35"
TEXTE = 'white'
SECONDAIRE = "grey58"
FAIBLE ="grey42"
FOND_SELECTION = 'grey27'
TITRE_STYLE= "bold white"


def tronquer(texte, largeur):
    """Tronque une chaîne à *largeur* cellules (jamais de repli)."""
    texte = ' '.join(str(texte if texte is not None else '').split())
    largeur = max(0, int(largeur))
    if cell_len(texte) <= largeur:
        return texte
    if largeur <=1:
        return texte[:largeur]
    return texte[:largeur - 1].rstrip() + '\u2026'


def ajuster(ligne, largeur):
    """Force une ligne ``Text`` à exactement *largeur* cellules."""
    if not isinstance(ligne, Text):
        ligne= Text(str(ligne if ligne is not None else ''))
    largeur = max(0, int(largeur))
    ligne =ligne.copy()
    if ligne.cell_len > largeur:
        ligne.truncate(largeur, overflow="ellipsis")
    reste = largeur - ligne.cell_len
    if reste > 0:
        ligne.append(" " * reste)
    return ligne


def regle(largeur, style=BORDURE, unicode=True):
    """Filet horizontal fin, utilisé sous les en-têtes et en pied d'écran."""
    largeur= max(1, int(largeur))
    return Text("\u2500" * largeur if unicode else "-" * largeur, style=style)


def deux_colonnes(gauche, droite, largeur, style_gauche=TEXTE,
                  style_droite=SECONDAIRE):
    """Ligne à deux colonnes : libellé à gauche, valeur alignée à droite."""
    largeur =max(1, int(largeur))
    droite =tronquer(droite, max(0, largeur // 2))
    dispo =max(1, largeur - len(droite) - 1) if droite else largeur
    gauche = tronquer(gauche, dispo)
    ligne = Text(no_wrap=True)
    ligne.append(gauche, style=style_gauche)
    reste=largeur - len(gauche) - len(droite)
    ligne.append(' ' * max(0, reste))
    if droite:
        ligne.append(droite, style=style_droite)
    return ligne


def paire(label, valeur, largeur, style_valeur=TEXTE):
    """Ligne ``LIBELLE   valeur`` : libelle discret, valeur lisible."""
    largeur = max(1, int(largeur))
    label= tronquer(label, max(5, min(14, largeur // 3)))
    colonne = max(len(label) + 1, 10)
    texte =Text(no_wrap=True)
    texte.append(f"{label:<{colonne}}", style=FAIBLE)
    texte.append(tronquer(valeur, max(1, largeur - colonne)),
                 style=style_valeur)
    return texte


def en_tete(largeur, marque, tagline='', details='', contexte='',
            unicode=True, style_marque="bold white", style_details=SECONDAIRE):
    """En-tête d'écran : marque à gauche, contexte à droite, puis un filet."""
    largeur=max(20, int(largeur))
    separateur ="  \u00b7  " if unicode else " | "
    gauche = marque + (f"{separateur}{tagline}" if tagline else "")
    morceaux =[part for part in (details, contexte) if part]
    droite= separateur.join(morceaux)
    if droite:
        dispo =largeur - len(gauche) - 2
        if dispo < 24:
            gauche = tronquer(gauche, max(10, largeur // 2))
            dispo = largeur - len(gauche) - 2
        droite = tronquer(droite, max(8, dispo))
    ligne = Text(no_wrap=True)
    ligne.append(gauche, style=style_marque)
    if droite:
        ligne.append(" " * max(1, largeur - len(gauche) - len(droite)))
        ligne.append(droite, style=style_details)
    return [ajuster(ligne, largeur), regle(largeur, BORDURE, unicode)]


def panneau(lignes, largeur, titre="", pied="", unicode=True,
            couleur_titre=TITRE_STYLE, couleur_bordure=BORDURE):
    """Panneau à filet fin, titre discret, pied de panneau aligné à droite."""
    boite =box.SQUARE if unicode else box.ASCII
    return Panel(
        Group(*lignes),
        box=boite,
        border_style=couleur_bordure,
        padding=(0, 1),
        width=max(8, int(largeur)),
        title=f"[{couleur_titre}] {titre} [/]" if titre else None,
        title_align='left',
        subtitle=f"[{FAIBLE}] {pied} [/]" if pied else None,
        subtitle_align="right",
    )


def barre_etat(raccourcis, largeur, msg='', unicode=True):
    """Ligne de raccourcis en pied d'écran (une seule ligne, tronquée)."""
    largeur = max(20, int(largeur))
    ligne = Text(no_wrap=True, overflow='ellipsis')
    for index, (touche, libelle) in enumerate(raccourcis or []):
        if index:
            ligne.append('   ')
        ligne.append(touche, style="bold white")
        ligne.append(" ", style=FAIBLE)
        ligne.append(libelle, style=SECONDAIRE)
    if not unicode:
        ligne= Text(" ".join(f"{t} {lib}" for t, lib in (raccourcis or [])),
                     style='bold white', no_wrap=True, overflow='ellipsis')
    if msg:
        ligne.append(f"   ! {msg}", style="bold red")
    return ajuster(ligne, largeur)


def grille(gauche, droite, espace=2):
    """Deux renderables cote a cote (panneau catalogue / details)."""
    from rich.table import Table
    table = Table.grid(padding=(0, espace))
    table.add_column()
    table.add_column()
    table.add_row(gauche, droite)
    return table
