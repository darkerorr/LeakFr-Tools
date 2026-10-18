"""Sequence de demarrage animee de LeakFr-Tools.

Quatre phases distinctes, rendues avec Rich ``Live`` (aucune ligne empilee) :

A. activation : contexte local **mesure en direct** (systeme, Python,
   taille et encodage du terminal) avec trame de scan ;
B. revelation du logo adossee au catalogue reel et a l'etat des controles
   en cours (aucune phase purement decorative) ;
C. initialisation technique : panneau de controle pilote par les
   verifications **reellement executees** en arriere-plan ;
D. bilan et transition : statut honnete, logo final, ouverture du menu.

La progression affichee est le rapport ``controles termines / total`` et
chaque phase affiche des valeurs reellement lues. Un terminal etroit ou bas
recoit une composition compacte ; une erreur de rendu renvoie ``False`` et
la banniere statique est utilisee a la place.
"""
import platform
import time

from rich import box
from rich.align import Align
from rich.console import Group
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from core import ui
from core.branding import (
    BANNER_TAGLINE, SEGMENT_PLEIN, SEGMENT_VIDE, SPINNER, STRUCTURE,
    couleurs_logo, en_tete, logo_final, logo_revele, melange, sous_titre_revele,
)
from core.common import obtenir_theme
from core.startup_checks import (
    Orchestrateur, controles_par_defaut, resume_verifications,
)

GLYPHES = {
    "OK": "\u2714",
    'WARN': '!',
    "ERROR": "\u2718",
    "OPTIONAL": "\u25cb",
    'UNKNOWN': '?',
    "MISSING": "-",
    "PENDING": "\u00b7",
    'SKIPPED': '-',
    "RUNNING":"",
}
GLYPHES_ASCII = {'OK': 'OK', 'WARN':'!!', 'ERROR':'XX', 'OPTIONAL': 'o',
                 "UNKNOWN":"?", "MISSING": "-", "PENDING": ".", "SKIPPED": "-",
                 "RUNNING": ""}

COULEURS_STATUT ={
    "OK": "bold #4ade80",
    'WARN': 'bold #ffb020',
    "ERROR": "bold #ff5c7a",
    "OPTIONAL": "#7d9188",
    'UNKNOWN': 'bold #ffd166',
    "MISSING": "#888888",
    "PENDING": "grey42",
    'SKIPPED': 'grey50',
    "RUNNING":"bold #36d1ff",
}


def _couleurs(palette=None):
    palette = palette or obtenir_theme()
    vert, cyan= couleurs_logo(palette)
    return palette, vert, cyan


def _tronquer(texte, largeur):
    texte= ' '.join(str(texte or '').split())
    if largeur <= 0:
        return ""
    if len(texte)<= largeur:
        return texte
    if largeur<= 1:
        return texte[:largeur]
    return texte[:largeur - 1].rstrip() + "\u2026"


def _spinner(t, unicode=True):
    if unicode:
        return SPINNER[int(t * 14) % len(SPINNER)]
    return "|/-\\"[int(t * 14) % 4]


def glyphe_statut(statut, t=0.0, unicode=True, palette=None):
    """Glyphe et style d'un statut, sans jamais masquer un echec."""
    _palette, _vert, cyan =_couleurs(palette)
    if statut== "RUNNING":
        return (_spinner(t, unicode), f"bold {cyan}")
    if unicode:
        return GLYPHES.get(statut, "?"), COULEURS_STATUT.get(statut, "white")
    return GLYPHES_ASCII.get(statut, "?"), COULEURS_STATUT.get(statut, "white")



def faits_machine(flux, largeur):
    """Mesures reelles affichees pendant la phase A (aucune valeur inventee)."""
    systeme = f"{platform.system() or '?'} {platform.release() or ''}".strip()
    encodage = (getattr(flux, 'encoding', None) or 'ascii').upper()
    couleurs =getattr(flux, "color_system", None) or "auto"
    hauteur=getattr(flux, "height", None) or "?"
    return [
        f"systeme : {systeme} · python {platform.python_version()}",
        f"terminal : {largeur}x{hauteur} · {encodage} · couleurs {couleurs}",
    ]


def faits_controles(orch, maximum=3):
    """Lignes reelles sur le catalogue et les controles en cours."""
    from core.catalogue import CATALOGUE, FLAT
    outils = sum(1 for entree in FLAT if entree['fn'])
    lignes = [f"catalogue reel : {outils} outils · {len(CATALOGUE)} categories",
              f"controles reels : {orch.termines}/{orch.total} termines"]
    for etat in orch.etats():
        if etat.terminee and etat.statut in ("OK", "WARN", "ERROR", "OPTIONAL"):
            lignes.append(f"{etat.nom} : {etat.detail}")
        if len(lignes)>=maximum + 2:
            break
    return lignes



def entete_chargement(palette=None, unicode=True, largeur=80, t=0.0):
    """En-tete de l'ecran de chargement (logo si la place le permet)."""
    palette, vert, cyan =_couleurs(palette)
    if unicode and largeur>= 74:
        elements = list(logo_final(t, palette, unicode))
        elements.append(Align.center(sous_titre_revele(1.0, palette)))
        elements.append(Align.center(Text(
            BANNER_TAGLINE,
            style=f"dim {palette.get('texte_secondaire', '#888888')}")))
        return Group(*elements)
    marque = Text(justify="center")
    marque.append("LEAKFR", style=f"bold {vert}")
    marque.append(' // TOOLS 2.0', style=f"bold {cyan}")
    return Group(marque)

def _ligne_controle(etat, t, palette, largeur, unicode=True):
    glyphe, style =glyphe_statut(etat.statut, t, unicode, palette)
    texte = Text()
    texte.append(f"{glyphe:<2}", style=style)
    texte.append(" ")
    nom = f"{etat.nom:<16}"
    texte.append(nom, style='bold white' if etat.terminee else 'grey50')
    reste = max(6, largeur - len(nom) - 3)
    detail_style= "dim" if etat.statut != "ERROR" else "bold #ff8fa3"
    if etat.statut == 'RUNNING':
        detail_style ="italic #36d1ff"
    texte.append(_tronquer(etat.detail, reste), style=detail_style)
    texte.no_wrap = True
    texte.overflow = "ellipsis"
    return texte


def jauge(progression, largeur=30, unicode=True, palette=None):
    """Jauge segmentee dont le remplissage suit la progression reelle."""
    palette, vert, cyan =_couleurs(palette)
    progression = max(0.0, min(1.0, float(progression)))
    largeur = max(8, int(largeur))
    pleins= int(round(largeur * progression))
    texte = Text()
    for index in range(largeur):
        if index < pleins:
            couleur= melange(vert, cyan, index / max(1, largeur - 1))
            texte.append(SEGMENT_PLEIN if unicode else '#', style=f"bold {couleur}")
        else:
            texte.append(SEGMENT_VIDE if unicode else "-", style="grey27")
    texte.append(f" {int(round(progression * 100)):3d}%", style='bold white')
    return texte


def _ligne_systeme(label, valeur, palette=None, largeur=13, accent=None):
    _palette, _vert, cyan = _couleurs(palette)
    texte= Text(no_wrap=True, overflow='ellipsis')
    texte.append(f"{label:<9}", style="grey50")
    texte.append(_tronquer(valeur, largeur), style=accent or "white")
    return texte


def _panneau_systeme(t, palette, flux, unicode=True):
    palette, vert, cyan =_couleurs(palette)
    systeme = f"{platform.system() or '?'} {platform.release() or ''}".strip()
    encodage = (getattr(flux, 'encoding', None) or 'ascii').upper()
    couleurs =getattr(flux, "color_system", None) or "auto"
    lignes= [
        _ligne_systeme('SYSTEME', systeme, palette),
        _ligne_systeme("PYTHON", platform.python_version(), palette),
        _ligne_systeme("TERMINAL", encodage, palette),
        _ligne_systeme('COULEURS', couleurs, palette),
        Text(""),
        _ligne_systeme("DUREE", f"{t:4.1f} s", palette, accent=f"bold {cyan}"),
        Text(''),
        Text("Controles locaux.", style="dim", no_wrap=True),
        Text("Aucun scan de cible.", style="dim", no_wrap=True),
    ]
    return Panel(Group(*lignes), box=box.SQUARE if unicode else box.ASCII,
                 border_style=palette.get("bordures", "#4a5a52"),
                 title=f"[bold {vert}] SYSTEME [/]", title_align='left',
                 padding=(0, 1))


def _pied_initialisation(orch, palette, largeur, unicode=True, t=0.0):
    """Lignes de progression (le cadre est dessine par ``core.ui``)."""
    palette, vert, cyan = _couleurs(palette)
    interne =max(20, int(largeur) - 4)
    jauge_largeur = max(10, min(40, interne - 16))
    texte =Text(no_wrap=True, overflow='ellipsis')
    texte.append_text(jauge(orch.progression, jauge_largeur, unicode, palette))
    suffixe =" controles" if interne >= 48 else ""
    texte.append(f"   {orch.termines}/{orch.total}{suffixe}", style='bold white')
    if orch.en_cours:
        texte.append(f"   {_spinner(time.monotonic() * 1.6)} {orch.en_cours}",
                     style=f"italic {cyan}")
    if orch.termine:
        sautes = sum(1 for etat in orch.etats() if etat.statut == "SKIPPED")
        if sautes:
            note = Text(f"{sautes} verification(s) interrompue(s) · poursuite",
                        style="bold #ffb020")
        else:
            note =Text("controles termines · ouverture du catalogue", style="dim")
    else:
        note= Text("verifications locales en cours d'execution", style='dim')
    note= Text(_tronquer(note.plain, interne), style=note.style or "dim")
    texte.no_wrap = True
    note.no_wrap = True
    return [texte, note]


def rendu_initialisation(orch, t=0.0, palette=None, largeur=80, hauteur=30,
                         flux=None, unicode=True):
    """Ecran de chargement : en-tete, controles reels et progression reelle.

    Composition compacte (Group) : pas de Layout plein ecran, donc aucun
    espace vide entre le titre et les resultats.
    """
    palette, vert, cyan = _couleurs(palette)
    flux = flux or _console_defaut()
    largeur_panneau = max(30, min(int(largeur) - 2, 100))

    parts = []
    if hauteur >=22 and largeur >= 58:
        parts.append(entete_chargement(palette, unicode, largeur, t))
        parts.append(Text(''))

    entete= Text(no_wrap=True, overflow="ellipsis")
    entete.append('LEAKFR', style=f"bold {vert}")
    entete.append("  //  BOOT" if largeur_panneau < 62 else "  //  CHARGEMENT",
                  style=f"dim {cyan}")
    if largeur_panneau >=62:
        entete.append(f"   {orch.termines}/{orch.total} controles", style="bold white")
        entete.append(f"   {t:4.1f} s", style="dim")
    parts.append(entete)

    controles = [_ligne_controle(etat, t, palette, max(24, largeur_panneau - 6),
                                 unicode) for etat in orch.etats()]
    parts.append(ui.panneau(controles, largeur_panneau,
                            titre="VERIFICATIONS REELLES",
                            pied=f"{orch.termines}/{orch.total}",
                            unicode=unicode))
    parts.append(ui.panneau(
        _pied_initialisation(orch, palette, largeur_panneau, unicode, t),
        largeur_panneau, titre="PROGRESSION REELLE", unicode=unicode))
    return Group(*parts)


def _console_defaut():
    from core.common import console
    return console



def _contexte(config):
    from core.catalogue import CATALOGUE, FLAT
    outils =sum(1 for entree in FLAT if entree["fn"])
    return {
        'outils':outils,
        "categories": len(CATALOGUE),
        "systeme": f"{platform.system()} {platform.release()}".strip(),
    }


def rendu_final(resultats, config=None, t=0.0, palette=None, largeur=80,
                unicode=True, duree=0.0, compact=False):
    """Composition finale : logo, bilan honnete et contexte du projet."""
    palette, vert, cyan =_couleurs(palette)
    bilan = resume_verifications(resultats)
    couleur = {"PRET": "bold #4ade80", "PARTIEL": "bold #ffb020",
               'CRITIQUE': 'bold #ff5c7a'}[bilan['niveau']]
    contexte = _contexte(config)
    infos = (f"v2.0  |  {contexte['outils']} outils  |  "
             f"{contexte["categories"]} categories  |  {contexte["systeme"]}")

    elements = [Text("")]
    if compact:
        elements.append(en_tete(largeur, palette, infos, compact=True,
                                unicode=unicode))
    else:
        elements.append(en_tete(largeur, palette, infos, compact=False,
                                unicode=unicode, t=t))
    elements.append(Text(''))

    lignes =[]
    for etat in resultats:
        lignes.append(_ligne_controle(etat, t, palette, max(24, largeur - 20),
                                      unicode))
    synthese = Text()
    synthese.append(f" {bilan['label']} ", style=f"bold black on {couleur.split()[-1]}")
    synthese.append(f"   {bilan['ok']} OK", style="bold #4ade80")
    if bilan['optionnels']:
        synthese.append(f"  |  {bilan['optionnels']} optionnel(s)", style="dim")
    if bilan["avertissements"]:
        synthese.append(f"  |  {bilan["avertissements"]} avertissement(s)",
                        style="bold #ffb020")
    if bilan["erreurs"]:
        synthese.append(f"  |  {bilan["erreurs"]} erreur(s)", style='bold #ff5c7a')
    if bilan["inconnus"]:
        synthese.append(f"  |  {bilan['inconnus']} inconnu(s)", style="dim")
    if bilan['interrompus']:
        synthese.append(f"  |  {bilan['interrompus']} interrompu(s)", style="dim")
    synthese.append(f"   {duree:.1f} s", style="dim")

    panneau = Panel(
        Group(*lignes, Text(""), synthese),
        box=box.SQUARE if unicode else box.ASCII,
        border_style=couleur.split()[-1], padding=(0, 1),
        title=f"[bold] BILAN DE DEMARRAGE [/]",
        subtitle=f"[{couleur}] {bilan["label"]} [/]", subtitle_align='right')
    elements.append(Align.center(panneau))
    elements.append(Text(""))
    elements.append(Align.center(Text(
        "Aucun scan, aucune cible distante : le demarrage reste local.",
        style="dim")))
    elements.append(Text(''))
    return Group(*elements)



def executer_sequence(config=None, duree=3.2, flux=None):
    """Affiche l'ecran de chargement reel puis le bilan.

    ``True`` indique que l'ecran final a ete affiche ; une exception de rendu
    remonte a l'appelant, qui retombe sur la banniere statique : le demarrage
    ne depend jamais de l'affichage.
    """
    from core.common import MODE_TEXTE, UNICODE as UNICODE_DISPO
    config =config or {}
    flux = flux or _console_defaut()
    palette = obtenir_theme()
    _palette, vert, _cyan = _couleurs(palette)
    largeur = max(30, int(flux.width or 80))
    hauteur= max(16, int(flux.height or 30))
    unicode = bool(UNICODE_DISPO) and not MODE_TEXTE

    controles = controles_par_defaut(config)
    orchestrateur =Orchestrateur(controles)
    orchestrateur.lancer()

    budget =max(1.6, min(float(duree or 0.0), 4.5))
    minimum = min(0.6, max(0.25, budget * 0.35))
    limite= time.monotonic() + budget + 4.0

    def temps():
        return orchestrateur.ecoule

    if largeur < 52 or hauteur < 18:
        orchestrateur.attendre(timeout=budget + 4.0)
        if not orchestrateur.termine:
            orchestrateur.interrompre()
        flux.print(Text('LEAKFR // TOOLS 2.0', style=f"bold {vert}"))
        for etat in orchestrateur.etats():
            flux.print(_ligne_controle(etat, 0.0, palette,
                                       max(24, largeur - 2), unicode))
        return True

    with Live(console=flux, refresh_per_second=12, transient=True,
              auto_refresh=True) as live:
        fin_minimum =time.monotonic() + minimum
        while True:
            if not orchestrateur.termine and time.monotonic() > limite:
                orchestrateur.interrompre()
            live.update(
                rendu_initialisation(orchestrateur, temps(), palette, largeur,
                                     hauteur, flux, unicode),
                refresh=True)
            if orchestrateur.termine and time.monotonic() >= fin_minimum:
                break
            time.sleep(0.05)

    resultats = orchestrateur.etats()
    flux.clear()
    flux.print(rendu_final(resultats, config, temps(), palette, largeur,
                           unicode, temps(), largeur < 84 or hauteur < 26))
    return True
