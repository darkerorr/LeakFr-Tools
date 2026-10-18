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

from core.branding import (
    BANNER_TAGLINE, SEGMENT_PLEIN, SEGMENT_VIDE, SPINNER, STRUCTURE,
    couleurs_logo, en_tete, logo_revele, melange, sous_titre_revele,
)
from core.common import obtenir_theme
from core.startup_checks import (
    Orchestrateur, controles_par_defaut, resume_verifications,
)

GLYPHES = {
    "OK": "\u2714",       # ✔
    "WARN": "!",
    "ERROR": "\u2718",    # ✘
    "OPTIONAL": "\u25cb",  # ○
    "UNKNOWN": "?",
    "MISSING": "-",
    "PENDING": "\u00b7",  # ·
    "SKIPPED": "-",
    "RUNNING": "",
}
GLYPHES_ASCII = {"OK": "OK", "WARN": "!!", "ERROR": "XX", "OPTIONAL": "o",
                 "UNKNOWN": "?", "MISSING": "-", "PENDING": ".", "SKIPPED": "-",
                 "RUNNING": ""}

COULEURS_STATUT = {
    "OK": "bold #4ade80",
    "WARN": "bold #ffb020",
    "ERROR": "bold #ff5c7a",
    "OPTIONAL": "#7d9188",
    "UNKNOWN": "bold #ffd166",
    "MISSING": "#888888",
    "PENDING": "grey42",
    "SKIPPED": "grey50",
    "RUNNING": "bold #36d1ff",
}


def _couleurs(palette=None):
    palette = palette or obtenir_theme()
    vert, cyan = couleurs_logo(palette)
    return palette, vert, cyan


def _tronquer(texte, largeur):
    texte = " ".join(str(texte or "").split())
    if largeur <= 0:
        return ""
    if len(texte) <= largeur:
        return texte
    if largeur <= 1:
        return texte[:largeur]
    return texte[:largeur - 1].rstrip() + "\u2026"


def _spinner(t, unicode=True):
    if unicode:
        return SPINNER[int(t * 14) % len(SPINNER)]
    return "|/-\\"[int(t * 14) % 4]


def glyphe_statut(statut, t=0.0, unicode=True, palette=None):
    """Glyphe et style d'un statut, sans jamais masquer un echec."""
    _palette, _vert, cyan = _couleurs(palette)
    if statut == "RUNNING":
        return (_spinner(t, unicode), f"bold {cyan}")
    if unicode:
        return GLYPHES.get(statut, "?"), COULEURS_STATUT.get(statut, "white")
    return GLYPHES_ASCII.get(statut, "?"), COULEURS_STATUT.get(statut, "white")


# ---------------------------------------------------------------------------
# PHASE A - activation visuelle
# ---------------------------------------------------------------------------

def mot_decode(mot, progression, t=0.0, palette=None, unicode=True):
    """Mot dont les lettres se resolvent de gauche a droite."""
    palette, vert, cyan = _couleurs(palette)
    bruit = "\u2593\u2592\u2591#%&" if unicode else "#%@"
    resolus = int(max(0.0, min(1.0, progression)) * (len(mot) + 2))
    texte = Text()
    for index, caractere in enumerate(mot):
        if caractere == " ":
            texte.append(" ")
            continue
        if index < resolus:
            couleur = melange(vert, cyan, index / max(1, len(mot) - 1))
            texte.append(caractere, style=f"bold {couleur}")
        else:
            texte.append(bruit[int(index * 7 + t * 12) % len(bruit)],
                         style="grey30")
    return texte


def _bande_scan(largeur, position, palette=None, unicode=True):
    palette, vert, cyan = _couleurs(palette)
    bande = Text()
    for x in range(largeur):
        distance = abs(x - position)
        if distance <= 1:
            bande.append("\u2588" if unicode else "#", style="bold white")
        elif distance <= 4:
            bande.append("\u2593" if unicode else "=", style=f"bold {cyan}")
        elif distance <= 8:
            bande.append("\u2592" if unicode else "+", style=f"dim {vert}")
        else:
            bande.append(STRUCTURE if unicode else "-", style="grey19")
    return bande


def faits_machine(flux, largeur):
    """Mesures reelles affichees pendant la phase A (aucune valeur inventee)."""
    systeme = f"{platform.system() or '?'} {platform.release() or ''}".strip()
    encodage = (getattr(flux, "encoding", None) or "ascii").upper()
    couleurs = getattr(flux, "color_system", None) or "auto"
    hauteur = getattr(flux, "height", None) or "?"
    return [
        f"systeme : {systeme} · python {platform.python_version()}",
        f"terminal : {largeur}x{hauteur} · {encodage} · couleurs {couleurs}",
    ]


def faits_controles(orch, maximum=3):
    """Lignes reelles sur le catalogue et les controles en cours."""
    from core.catalogue import CATALOGUE, FLAT
    outils = sum(1 for entree in FLAT if entree["fn"])
    lignes = [f"catalogue reel : {outils} outils · {len(CATALOGUE)} categories",
              f"controles reels : {orch.termines}/{orch.total} termines"]
    for etat in orch.etats():
        if etat.terminee and etat.statut in ("OK", "WARN", "ERROR", "OPTIONAL"):
            lignes.append(f"{etat.nom} : {etat.detail}")
        if len(lignes) >= maximum + 2:
            break
    return lignes


def rendu_activation(progression=0.0, t=0.0, palette=None, unicode=True,
                     largeur=48, message="initialisation du terminal", faits=()):
    """Phase A : cadre, trame, mot-marque et mesures locales reelles."""
    palette, vert, cyan = _couleurs(palette)
    position = progression * (largeur + 10) - 5
    marque = Text()
    marque.append("\u25e4 " if unicode else "[ ", style=f"dim {cyan}")
    marque.append_text(mot_decode("LEAKFR", progression, t, palette, unicode))
    marque.append(" // TOOLS 2.0", style="dim")
    marque.append(" \u25e5" if unicode else " ]", style=f"dim {cyan}")

    regle = Text()
    curseur = int(max(0, min(largeur - 1, position)))
    regle.append("\u2501" * curseur, style=f"dim {vert}")
    regle.append("\u25c6" if unicode else "+", style="bold white")
    regle.append("\u2501" * max(0, largeur - curseur - 1), style=f"dim {vert}")

    elements = [
        Text(""),
        Align.center(Text("[ ACTIVATION ]", style=f"bold {cyan}")),
        Align.center(_bande_scan(largeur, position, palette, unicode)),
        Align.center(regle),
        Align.center(marque),
        Align.center(Text(message, style="dim")),
    ]
    for fait in faits:
        elements.append(Align.center(Text(fait, style="dim")))
    elements.append(Text(""))
    return Group(*elements)


# ---------------------------------------------------------------------------
# PHASE B - revelation du logo
# ---------------------------------------------------------------------------

def rendu_revelation(progression=0.0, t=0.0, palette=None, unicode=True,
                     largeur=48, faits=()):
    """Phase B : logo, sous-titre saisi et etat reel des controles."""
    palette, vert, cyan = _couleurs(palette)
    elements = [Text("")]
    elements.extend(logo_revele(progression, t, palette, unicode))
    elements.append(Align.center(sous_titre_revele(progression, palette)))
    if progression >= 0.72:
        elements.append(Align.center(Text(
            BANNER_TAGLINE,
            style=f"dim {palette.get('texte_secondaire', '#888888')}")))
    else:
        elements.append(Text(""))
    for fait in faits:
        elements.append(Align.center(Text(fait, style="dim")))
    elements.append(Text(""))
    return Group(*elements)


# ---------------------------------------------------------------------------
# PHASE C - initialisation technique liee aux controles reels
# ---------------------------------------------------------------------------

def _ligne_controle(etat, t, palette, largeur, unicode=True):
    glyphe, style = glyphe_statut(etat.statut, t, unicode, palette)
    texte = Text()
    texte.append(f"{glyphe:<2}", style=style)
    texte.append(" ")
    nom = f"{etat.nom:<16}"
    texte.append(nom, style="bold white" if etat.terminee else "grey50")
    reste = max(6, largeur - len(nom) - 3)
    detail_style = "dim" if etat.statut != "ERROR" else "bold #ff8fa3"
    if etat.statut == "RUNNING":
        detail_style = "italic #36d1ff"
    texte.append(_tronquer(etat.detail, reste), style=detail_style)
    texte.no_wrap = True
    texte.overflow = "ellipsis"
    return texte


def jauge(progression, largeur=30, unicode=True, palette=None):
    """Jauge segmentee dont le remplissage suit la progression reelle."""
    palette, vert, cyan = _couleurs(palette)
    progression = max(0.0, min(1.0, float(progression)))
    largeur = max(8, int(largeur))
    pleins = int(round(largeur * progression))
    texte = Text()
    for index in range(largeur):
        if index < pleins:
            couleur = melange(vert, cyan, index / max(1, largeur - 1))
            texte.append(SEGMENT_PLEIN if unicode else "#", style=f"bold {couleur}")
        else:
            texte.append(SEGMENT_VIDE if unicode else "-", style="grey27")
    texte.append(f" {int(round(progression * 100)):3d}%", style="bold white")
    return texte


def _ligne_systeme(label, valeur, palette=None, largeur=13, accent=None):
    _palette, _vert, cyan = _couleurs(palette)
    texte = Text(no_wrap=True, overflow="ellipsis")
    texte.append(f"{label:<9}", style="grey50")
    texte.append(_tronquer(valeur, largeur), style=accent or "white")
    return texte


def _panneau_systeme(t, palette, flux, unicode=True):
    palette, vert, cyan = _couleurs(palette)
    systeme = f"{platform.system() or '?'} {platform.release() or ''}".strip()
    encodage = (getattr(flux, "encoding", None) or "ascii").upper()
    couleurs = getattr(flux, "color_system", None) or "auto"
    lignes = [
        _ligne_systeme("SYSTEME", systeme, palette),
        _ligne_systeme("PYTHON", platform.python_version(), palette),
        _ligne_systeme("TERMINAL", encodage, palette),
        _ligne_systeme("COULEURS", couleurs, palette),
        Text(""),
        _ligne_systeme("DUREE", f"{t:4.1f} s", palette, accent=f"bold {cyan}"),
        Text(""),
        Text("Controles locaux.", style="dim", no_wrap=True),
        Text("Aucun scan de cible.", style="dim", no_wrap=True),
    ]
    return Panel(Group(*lignes), box=box.SQUARE if unicode else box.ASCII,
                 border_style=palette.get("bordures", "#4a5a52"),
                 title=f"[bold {vert}] SYSTEME [/]", title_align="left",
                 padding=(0, 1))


def _pied_initialisation(orch, palette, largeur, unicode=True):
    palette, vert, cyan = _couleurs(palette)
    jauge_largeur = max(12, min(40, largeur // 2))
    texte = Text()
    texte.append_text(jauge(orch.progression, jauge_largeur, unicode, palette))
    texte.append(f"   {orch.termines}/{orch.total} controles", style="bold white")
    if orch.en_cours:
        texte.append(f"   {_spinner(time.monotonic() * 1.6)} {orch.en_cours}",
                     style=f"italic {cyan}")
    if orch.termine:
        sautes = sum(1 for etat in orch.etats() if etat.statut == "SKIPPED")
        if sautes:
            note = Text(f"{sautes} verification(s) interrompue(s) · poursuite",
                        style="bold #ffb020")
        else:
            note = Text("controles termines · ouverture du catalogue", style="dim")
    else:
        note = Text("verifications locales en cours d'execution", style="dim")
    texte.no_wrap = True
    note.no_wrap = True
    return Panel(Group(texte, note), box=box.SQUARE if unicode else box.ASCII,
                 border_style=palette.get("bordures", "#4a5a52"),
                 padding=(0, 1), title="[dim]PROGRESSION REELLE[/]",
                 title_align="left")


def rendu_initialisation(orch, t=0.0, palette=None, largeur=80, hauteur=30,
                         flux=None, unicode=True):
    """Phase C : composition large (Layout) ou compacte selon le terminal."""
    palette, vert, cyan = _couleurs(palette)
    flux = flux or _console_defaut()
    compact = largeur < 84 or hauteur < 26
    if compact:
        entete = Text()
        entete.append("LEAKFR", style=f"bold {vert}")
        entete.append(" // INITIALISATION", style=f"dim {cyan}")
        entete.append(f"   {orch.termines}/{orch.total}", style="bold white")
        entete.append(f"   {t:4.1f}s", style="dim")
        lignes = [entete, Text("")]
        for etat in orch.etats():
            lignes.append(_ligne_controle(etat, t, palette,
                                          max(24, largeur - 4), unicode))
        lignes.append(Text(""))
        lignes.append(jauge(orch.progression, max(10, min(28, largeur - 12)),
                            unicode, palette))
        if orch.en_cours:
            lignes.append(Text(f"{_spinner(t * 1.6, unicode)} {orch.en_cours}",
                               style=f"italic {cyan}"))
        return Group(*lignes)

    marque = Text()
    marque.append("LEAKFR", style=f"bold {vert}")
    marque.append("  //  INITIALISATION", style=f"dim {cyan}")
    compteurs = Text(f"{orch.termines}/{orch.total} controles", style="bold white")
    compteurs.append(f"  |  {t:4.1f} s", style="dim")
    entete_table = Table.grid(expand=True)
    entete_table.add_column(justify="left")
    entete_table.add_column(justify="right")
    entete_table.add_row(marque, compteurs)
    boite = box.SQUARE if unicode else box.ASCII
    panneau_entete = Panel(entete_table, box=boite, border_style=cyan,
                           padding=(0, 1), title="[dim]BOOT SEQUENCE[/]",
                           title_align="right")

    controles = [_ligne_controle(etat, t, palette, max(24, largeur - 34), unicode)
                 for etat in orch.etats()]
    panneau_controles = Panel(
        Group(*controles), box=boite, border_style=vert, padding=(0, 1),
        title=f"[bold {vert}] VERIFICATIONS REELLES [/]", title_align="left")
    panneau_systeme = _panneau_systeme(t, palette, flux, unicode)

    corps = Table.grid(expand=True, padding=(0, 1))
    corps.add_column(ratio=3)
    corps.add_column(ratio=1)
    corps.add_row(panneau_controles, panneau_systeme)

    layout = Layout()
    layout.split_column(
        Layout(panneau_entete, size=3),
        Layout(corps),
        Layout(_pied_initialisation(orch, palette, largeur, unicode), size=4),
    )
    return layout


def _console_defaut():
    from core.common import console
    return console


def rendu_fermeture(progression=0.0, palette=None, unicode=True, largeur=48):
    """Phase D : dernier balayage avant l'ouverture du menu."""
    palette, vert, cyan = _couleurs(palette)
    position = progression * (largeur + 12) - 6
    lignes = [Text("")]
    lignes.append(Align.center(Text(
        "[ TRANSITION // OUVERTURE DU CATALOGUE ]", style=f"dim {cyan}")))
    lignes.append(Align.center(_bande_scan(largeur, position, palette, unicode)))
    lignes.append(Text(""))
    return Group(*lignes)


# ---------------------------------------------------------------------------
# Bilan final
# ---------------------------------------------------------------------------

def _contexte(config):
    from core.catalogue import CATALOGUE, FLAT
    outils = sum(1 for entree in FLAT if entree["fn"])
    return {
        "outils": outils,
        "categories": len(CATALOGUE),
        "systeme": f"{platform.system()} {platform.release()}".strip(),
    }


def rendu_final(resultats, config=None, t=0.0, palette=None, largeur=80,
                unicode=True, duree=0.0, compact=False):
    """Composition finale : logo, bilan honnete et contexte du projet."""
    palette, vert, cyan = _couleurs(palette)
    bilan = resume_verifications(resultats)
    couleur = {"PRET": "bold #4ade80", "PARTIEL": "bold #ffb020",
               "CRITIQUE": "bold #ff5c7a"}[bilan["niveau"]]
    contexte = _contexte(config)
    infos = (f"v2.0  |  {contexte['outils']} outils  |  "
             f"{contexte['categories']} categories  |  {contexte['systeme']}")

    elements = [Text("")]
    if compact:
        elements.append(en_tete(largeur, palette, infos, compact=True,
                                unicode=unicode))
    else:
        elements.append(en_tete(largeur, palette, infos, compact=False,
                                unicode=unicode, t=t))
    elements.append(Text(""))

    lignes = []
    for etat in resultats:
        lignes.append(_ligne_controle(etat, t, palette, max(24, largeur - 20),
                                      unicode))
    synthese = Text()
    synthese.append(f" {bilan['label']} ", style=f"bold black on {couleur.split()[-1]}")
    synthese.append(f"   {bilan['ok']} OK", style="bold #4ade80")
    if bilan["optionnels"]:
        synthese.append(f"  |  {bilan['optionnels']} optionnel(s)", style="dim")
    if bilan["avertissements"]:
        synthese.append(f"  |  {bilan['avertissements']} avertissement(s)",
                        style="bold #ffb020")
    if bilan["erreurs"]:
        synthese.append(f"  |  {bilan['erreurs']} erreur(s)", style="bold #ff5c7a")
    if bilan["inconnus"]:
        synthese.append(f"  |  {bilan['inconnus']} inconnu(s)", style="dim")
    if bilan["interrompus"]:
        synthese.append(f"  |  {bilan['interrompus']} interrompu(s)", style="dim")
    synthese.append(f"   {duree:.1f} s", style="dim")

    panneau = Panel(
        Group(*lignes, Text(""), synthese),
        box=box.SQUARE if unicode else box.ASCII,
        border_style=couleur.split()[-1], padding=(0, 1),
        title=f"[bold] BILAN DE DEMARRAGE [/]",
        subtitle=f"[{couleur}] {bilan['label']} [/]", subtitle_align="right")
    elements.append(Align.center(panneau))
    elements.append(Text(""))
    elements.append(Align.center(Text(
        "Aucun scan, aucune cible distante : le demarrage reste local.",
        style="dim")))
    elements.append(Text(""))
    return Group(*elements)


# ---------------------------------------------------------------------------
# Orchestration des phases
# ---------------------------------------------------------------------------

def _attendre_image(live, rendu, fin, intervalle=0.035):
    while True:
        maintenant = time.monotonic()
        reste = fin - maintenant
        if reste <= 0:
            return
        live.update(rendu(), refresh=True)
        time.sleep(min(intervalle, max(0.005, reste)))


def executer_sequence(config=None, duree=3.2, flux=None):
    """Joue la sequence complete ; retourne les verifications reelles.

    ``True`` (implicite) indique que l'ecran final a ete affiche. Toute
    exception de rendu remonte a l'appelant, qui retombe sur la banniere
    statique : le demarrage ne depend jamais de l'animation.
    """
    from core.common import MODE_TEXTE, UNICODE as UNICODE_DISPO
    config = config or {}
    flux = flux or _console_defaut()
    palette = obtenir_theme()
    _palette, vert, _cyan = _couleurs(palette)
    largeur = max(30, int(flux.width or 80))
    hauteur = max(16, int(flux.height or 30))
    unicode = bool(UNICODE_DISPO) and not MODE_TEXTE
    compact = largeur < 84 or hauteur < 26

    controles = controles_par_defaut(config)
    orchestrateur = Orchestrateur(controles)
    orchestrateur.lancer()

    budget = max(1.6, min(float(duree or 0.0), 4.5))
    t_a = min(0.40, budget * 0.16)
    t_b = min(0.95, budget * 0.30)
    minimum_c = max(0.70, budget - t_a - t_b - 0.30)
    limite = time.monotonic() + budget + 4.0
    debut = time.monotonic()

    def temps():
        return orchestrateur.ecoule

    if largeur < 52 or hauteur < 18:
        # Terminal minuscule : pas de scene plein cadre, mais des resultats
        # reels et lisibles.
        orchestrateur.attendre(timeout=budget + 4.0)
        if not orchestrateur.termine:
            orchestrateur.interrompre()
        flux.print(Text("LEAKFR // TOOLS 2.0", style=f"bold {vert}"))
        for etat in orchestrateur.etats():
            flux.print(_ligne_controle(etat, 0.0, palette,
                                       max(24, largeur - 2), unicode))
        return True

    with Live(console=flux, refresh_per_second=20, transient=True,
              auto_refresh=True) as live:
        # PHASE A - activation
        fin_a = time.monotonic() + t_a
        _attendre_image(
            live,
            lambda: rendu_activation(
                min(1.0, max(0.0, 1.0 - (fin_a - time.monotonic()) / max(0.01, t_a))),
                temps(), palette, unicode, min(48, largeur - 8),
                faits=faits_machine(flux, largeur)),
            fin_a)

        # PHASE B - revelation du logo
        fin_b = time.monotonic() + t_b
        _attendre_image(
            live,
            lambda: rendu_revelation(
                min(1.0, max(0.0, 1.0 - (fin_b - time.monotonic()) / max(0.01, t_b))),
                temps(), palette, unicode,
                faits=faits_controles(orchestrateur)),
            fin_b)

        # PHASE C - initialisation technique reelle
        fin_minimum = time.monotonic() + minimum_c
        while True:
            if not orchestrateur.termine and time.monotonic() > limite:
                orchestrateur.interrompre()
            live.update(
                rendu_initialisation(orchestrateur, temps(), palette, largeur,
                                     hauteur, flux, unicode),
                refresh=True)
            if orchestrateur.termine and time.monotonic() >= fin_minimum:
                break
            time.sleep(0.04)

        # PHASE D - dernier balayage
        fin_d = time.monotonic() + 0.26
        _attendre_image(
            live,
            lambda: rendu_fermeture(
                min(1.0, max(0.0, 1.0 - (fin_d - time.monotonic()) / 0.26)),
                palette, unicode, min(48, largeur - 8)),
            fin_d, intervalle=0.028)

    resultats = orchestrateur.etats()
    flux.clear()
    flux.print(rendu_final(resultats, config, temps(), palette, largeur,
                           unicode, temps(), compact))
    return True
