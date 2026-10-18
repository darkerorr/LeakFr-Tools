"""Identite visuelle LEAKFR : logo ASCII et en-tete reutilisable.

Ce module ne depend pas de ``core.common`` au niveau module (seulement de
Rich) afin que ``core.common`` puisse en importer le logo sans cycle. Les
memes lignes servent a l'introduction animee, au menu interactif et au menu
numerique : il n'existe qu'une seule definition du logo.
"""
from rich import box
from rich.align import Align
from rich.console import Group
from rich.panel import Panel
from rich.text import Text

NOM = "LEAKFR"
NOM_COMPLET = "LeakFr-Tools"
VERSION = "2.0"

# Logo ASCII du projet : six lignes de largeur identique (48 colonnes).
BANNER = [
    "██╗     ███████╗ █████╗ ██╗  ██╗███████╗██████╗ ",
    "██║     ██╔════╝██╔══██╗██║ ██╔╝██╔════╝██╔══██╗",
    "██║     █████╗  ███████║█████╔╝ █████╗  ██████╔╝",
    "██║     ██╔══╝  ██╔══██║██╔═██╗ ██╔══╝  ██╔══██╗",
    "███████╗███████╗██║  ██║██║  ██╗██║     ██║  ██║",
    "╚══════╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝     ╚═╝  ╚═╝",
]
BANNER_LARGEUR = max(len(ligne) for ligne in BANNER)
BANNER_HAUTEUR = len(BANNER)
BANNER_SOUS_TITRE = "T O O L S   2 . 0"
BANNER_TAGLINE = "OSINT  |  RECONNAISSANCE  |  CYBER  |  RESEAU  |  DISCORD"

# Glyphes de structure et de balayage (ASCII si Unicode indisponible).
STRUCTURE = "\u2591"      # ░
BALAYAGE = "\u2588"       # █
SEGMENT_PLEIN = "\u25b0"  # ▰
SEGMENT_VIDE = "\u25b1"   # ▱
SPINNER = "\u280b\u2819\u2839\u2838\u283c\u2834\u2826\u2827\u2807\u280f"


def _hex_vers_rgb(valeur):
    valeur = str(valeur or "").lstrip("#")
    if len(valeur) == 3:
        valeur = "".join(c * 2 for c in valeur)
    if len(valeur) != 6:
        return (74, 222, 128)
    try:
        return tuple(int(valeur[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return (74, 222, 128)


def melange(couleur_a, couleur_b, ratio):
    """Interpole deux couleurs hexadecimale (0 = a, 1 = b)."""
    ratio = max(0.0, min(1.0, float(ratio)))
    a = _hex_vers_rgb(couleur_a)
    b = _hex_vers_rgb(couleur_b)
    return "#" + "".join(f"{round(x + (y - x) * ratio):02x}" for x, y in zip(a, b))


def couleurs_logo(palette=None):
    """Couple (vert neon, cyan) deduit du theme actif.

    ``succes`` et ``secondaire`` sont verts/cyan dans toutes les palettes
    fournies : le logo garde donc l'identite cyber sans ignorer le theme.
    """
    palette = palette or {}
    return (palette.get("succes", "#4ade80"),
            palette.get("secondaire", "#36d1ff"))


def couleur_logo(x, y, palette=None, largeur=None, t=0.0):
    """Couleur d'un caractere du logo (degrade horizontal + pulsation)."""
    vert, cyan = couleurs_logo(palette)
    largeur = max(1, int(largeur or BANNER_LARGEUR))
    base = (x / largeur) * 0.82 + (y / max(1, BANNER_HAUTEUR)) * 0.18
    if t:
        base += 0.04 * ((t * 0.6) % 1.0 - 0.5)
    return melange(vert, cyan, base)


def logo_structure(unicode=True, palette=None):
    """Silhouette du logo avant revelation (caracteres de structure)."""
    palette = palette or {}
    couleur = palette.get("texte_secondaire", "#3a4a40")
    lignes = []
    for ligne in BANNER:
        texte = Text()
        for caractere in ligne:
            if caractere == " ":
                texte.append(" ")
            elif unicode:
                texte.append(STRUCTURE, style=f"dim {couleur}")
            else:
                texte.append(".", style=f"dim {couleur}")
        lignes.append(Align.center(texte))
    return lignes


def logo_revele(progression=1.0, t=0.0, palette=None, unicode=True,
                balayage=True):
    """Logo revele par un balayage diagonal, avec ligne de scan lumineuse.

    La progression pilote seulement la revelation graphique : elle ne mesure
    aucun travail technique. A 0, seule la structure est visible ; a 1, tous
    les caracteres sont affiches avec le degrade du theme.
    """
    progression = max(0.0, min(1.0, float(progression)))
    palette = palette or {}
    scan = progression * (BANNER_LARGEUR + 8) - 4
    lignes = []
    for y, ligne in enumerate(BANNER):
        texte = Text()
        for x, caractere in enumerate(ligne):
            if caractere == " ":
                texte.append(" ")
                continue
            seuil = (x / BANNER_LARGEUR) * 0.72 + (y / max(1, BANNER_HAUTEUR - 1)) * 0.28
            if progression <= 0 or seuil > progression:
                texte.append(STRUCTURE if unicode else ".", style="grey23")
                continue
            couleur = couleur_logo(x, y, palette, BANNER_LARGEUR, t)
            if balayage and abs(x - scan) <= 2:
                texte.append(caractere, style="bold white")
            else:
                texte.append(caractere, style=f"bold {couleur}")
        lignes.append(Align.center(texte))
    return lignes


def logo_final(t=0.0, palette=None, unicode=True):
    """Logo pleinement revele, utilise par le menu principal."""
    return logo_revele(1.0, t, palette, unicode, balayage=False)


def sous_titre_revele(progression=1.0, palette=None):
    """Sous-titre saisi progressivement (effet machine a ecrire)."""
    palette = palette or {}
    progression = max(0.0, min(1.0, float(progression)))
    visible = int(round(len(BANNER_SOUS_TITRE) * progression))
    texte = BANNER_SOUS_TITRE[:visible]
    curseur = "" if visible >= len(BANNER_SOUS_TITRE) else "_"
    return Text(texte + curseur,
                style=f"bold {palette.get('titres', '#e6fff2')}")


def _couper(texte, largeur):
    texte = " ".join(str(texte or "").split())
    if largeur <= 0:
        return ""
    if len(texte) <= largeur:
        return texte
    return texte[:max(1, largeur - 1)].rstrip() + "\u2026"


def entete_compact(largeur=None, palette=None, info="", unicode=True):
    """En-tete d'une ou deux lignes pour les terminaux etroits ou bas."""
    palette = palette or {}
    _vert, cyan = couleurs_logo(palette)
    largeur = max(24, min(int(largeur or 78), 100))
    contenu = Group(Text(_couper(info, largeur - 8), style="dim")) if info else Text("")
    return Panel(contenu, box=box.ROUNDED if unicode else box.ASCII,
                 border_style=cyan, padding=(0, 1),
                 title=f"[bold {cyan}] LEAKFR // TOOLS {VERSION} [/]",
                 title_align="left")


def entete_bandeau(largeur=None, palette=None, info="", commit="", unicode=True):
    """Bandeau du menu : toujours rempli (nom, info, commit), jamais vide.

    Utilise quand le grand logo ne tient pas dans le terminal : le panneau
    garde l'identite LEAKFR et affiche le commit reel du depot.
    """
    palette = palette or {}
    vert, cyan = couleurs_logo(palette)
    largeur = max(28, min(int(largeur or 78), 100))
    boite = box.ROUNDED if unicode else box.ASCII
    lignes = [Align.center(Text(_couper(info, largeur - 6), style="white"))]
    if commit:
        lignes.append(Align.center(Text(
            _couper(commit, largeur - 6),
            style=f"dim {palette.get('texte_secondaire', '#888888')}")))
    return Panel(
        Group(*lignes), box=boite, border_style=cyan, padding=(0, 1),
        title=f"[bold {vert}] LEAKFR [/][dim {cyan}]//[/] [bold {cyan}]TOOLS {VERSION}[/]",
        title_align="left")


def en_tete(largeur=None, palette=None, info="", compact=False, unicode=True,
            t=0.0, logo=None):
    """En-tete reutilisable : logo complet ou bandeau compact.

    ``logo`` permet de fournir des lignes deja rendues (animation) ; sinon le
    logo final est utilise. Le rendu n'ecrit rien : il retourne un renderable
    Rich, ce qui le rend testable sans terminal.
    """
    palette = palette or {}
    largeur = int(largeur or 78)
    # Sans Unicode, l'art en blocs du logo n'est pas affichable : le bandeau
    # compact reste lisible et garde l'identite LEAKFR.
    if compact or not unicode:
        return entete_compact(largeur, palette, info, unicode)
    lignes = list(logo) if logo is not None else logo_final(t, palette, unicode)
    elements = list(lignes)
    elements.append(Align.center(sous_titre_revele(1.0, palette)))
    elements.append(Align.center(Text(
        BANNER_TAGLINE, style=f"dim {palette.get('texte_secondaire', '#888888')}")))
    if info:
        elements.append(Align.center(Text(info, style="dim")))
    return Group(*elements)
