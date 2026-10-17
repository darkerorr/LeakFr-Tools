import csv
import math
import os
import re
import shutil
import socket
import subprocess
import sys
import time
import webbrowser
import requests
from rich import box
from rich.console import Console, Group
from rich.theme import Theme
from rich.style import Style
from rich.live import Live
from rich.markup import escape
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich.text import Text

class QuitterApplication(Exception):
    """Demande explicite de sortie (commande 00 ou Ctrl-C géré par le menu)."""


class ConsoleAdaptative(Console):
    """Console Rich qui transforme les tableaux larges en fiches verticales.

    Sur un téléphone ou dans un terminal de 40 à 60 colonnes, un tableau à
    six colonnes devient illisible. Les tableaux avec en-têtes sont rendus
    en blocs « champ : valeur » ; les grilles de mise en page sans en-tête
    restent inchangées.
    """

    def print(self, *objects, **kwargs):
        width = self.width or 80
        if width <= 68:
            objects = tuple(self._adapter_table(obj) if isinstance(obj, Table) else obj
                            for obj in objects)
        return super().print(*objects, **kwargs)

    @staticmethod
    def _texte_cellule(cellule):
        if isinstance(cellule, Text):
            return cellule.copy()
        if isinstance(cellule, str):
            try:
                return Text.from_markup(cellule)
            except Exception:
                return Text(cellule)
        return Text(str(cellule))

    def _adapter_table(self, table):
        if not table.show_header or len(table.columns) <= 1 or not table.rows:
            return table
        elements = []
        if table.title:
            elements.append(Text(str(table.title), style="bold"))
        titre_carte = escape(str(table.title)) if table.title else "Élément"
        total = len(table.rows)
        colonnes = [(colonne, list(colonne.cells)) for colonne in table.columns]
        for index, _ligne in enumerate(table.rows):
            champs = []
            for colonne, cellules in colonnes:
                cellule = cellules[index] if index < len(cellules) else ""
                entete = str(colonne.header or "").strip()
                valeur = self._texte_cellule(cellule)
                texte = Text()
                if entete:
                    texte.append(f"{entete} : ", style="bold")
                texte.append_text(valeur)
                champs.append(texte)
            elements.append(Panel(Group(*champs), title=f"{titre_carte} {index + 1}/{total}",
                                  border_style="grey42", box=box.ROUNDED))
        if table.caption:
            elements.append(Text(str(table.caption), style="dim"))
        return Group(*elements)


console = ConsoleAdaptative()
HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}
TIMEOUT = 8

UNICODE = ("utf" in (console.encoding or "").lower()) and "--ascii" not in sys.argv
INTERACTIF = sys.stdin.isatty() and sys.stdout.isatty() and "--simple" not in sys.argv
MODE_TEXTE = "--text" in sys.argv or "--no-color" in sys.argv
MODE_MOBILE = "--phone" in sys.argv
ANIMATIONS = not MODE_TEXTE
PAGINATION_DEFAUT = 15
LARGEUR_MENU = "auto"

BX = box.ROUNDED if UNICODE else box.ASCII
OKC, KOC = ("✔", "✘") if UNICODE else ("OK", "KO")
FULL, EMPTY = ("█", "░") if UNICODE else ("#", "-")
ARROW = "❯" if UNICODE else ">"
SEP = "•" if UNICODE else "|"
CONN_T, CONN_L, PIPE = (("├── ", "└── ", "│   ") if UNICODE else ("|-- ", "`-- ", "|   "))

C_OSINT = "#ff5fd2"
C_RECON = "#36d1ff"
C_CYBER = "#ff5c7a"
C_UTIL = "#4ade80"
C_ASTRO = "#9d8cff"
C_GOLD = "#ffd166"
C_PENTEST = "#ff9500"
C_DISCORD = "#5865F2"

def configurer_affichage(config=None, environnement=None):
    """Applique les préférences d'affichage et le mode mobile.

    Le mode texte désactive couleurs et animations ; il reste entièrement
    fonctionnel. Le mode mobile réduit les menus et la pagination mais ne
    change jamais le système d'exploitation.
    """
    global MODE_TEXTE, MODE_MOBILE, ANIMATIONS, PAGINATION_DEFAUT, LARGEUR_MENU
    config = config or {}
    plateforme = config.get("plateforme") or {}
    apparence = config.get("apparence") or {}
    env = str(environnement or plateforme.get("environnement") or "").casefold()
    if not env or env == "auto":
        try:
            from core.environment import detecter_environnement
            env = str(detecter_environnement().get("cle") or "")
        except Exception:
            env = ""
    mobile = env in {"termux", "android"}
    if "--phone" in sys.argv:
        mobile = True
    if "--text" in sys.argv or "--no-color" in sys.argv:
        MODE_TEXTE = True
    else:
        MODE_TEXTE = bool(plateforme.get("mode_texte", False))
    MODE_MOBILE = mobile
    ANIMATIONS = (not MODE_TEXTE and not mobile
                  and bool(apparence.get("animations", True)))
    try:
        PAGINATION_DEFAUT = max(5, min(50, int(plateforme.get("pagination", 15))))
    except (TypeError, ValueError):
        PAGINATION_DEFAUT = 15
    LARGEUR_MENU = str(plateforme.get("largeur_sortie")
                       or apparence.get("largeur_menu") or "auto")
    console.no_color = MODE_TEXTE


def clear_screen():
    """Efface l'écran avec Rich, sans commande shell propre à un OS."""
    try:
        if MODE_TEXTE:
            console.print("\n" * 2, end="")
        else:
            console.clear()
    except Exception:
        pass


def largeur_utile():
    largeur = console.width or 80
    if LARGEUR_MENU == "etroit":
        return min(largeur, 60)
    if LARGEUR_MENU == "large":
        return max(largeur, 100)
    return largeur


def est_ecran_etroit():
    return largeur_utile() <= 68 or MODE_MOBILE


def ask_number(label, minimum, maximum, defaut=None):
    """Saisie numérique validée, commune à tous les menus."""
    minimum = int(minimum)
    maximum = int(maximum)
    while True:
        try:
            if defaut is None:
                brut = Prompt.ask(f"[bold {C_GOLD}]{label}[/]")
            else:
                brut = Prompt.ask(f"[bold {C_GOLD}]{label}[/]", default=str(defaut),
                                  show_default=True)
        except (KeyboardInterrupt, EOFError):
            return None
        brut = str(brut).strip()
        if brut.isdigit() and minimum <= int(brut) <= maximum:
            return int(brut)
        bad(f"Entrée invalide : choisis un nombre entre {minimum} et {maximum}.")


def ask_text(label, defaut=None):
    return demander(label, defaut)


def confirm_action(message, defaut=False):
    try:
        return bool(Confirm.ask(message, default=defaut))
    except (KeyboardInterrupt, EOFError):
        return False


def show_error(message):
    bad(message)


def show_result_details(titre_txt, champs, couleur=C_RECON):
    kv(titre_txt, champs, couleur)


def render_menu(titre_menu, options, page=0, par_page=None, largeur=None, retour=True):
    """Construit un menu numéroté réutilisable (interface et captures)."""
    options = [str(option) for option in options]
    par_page = int(par_page or (10 if est_ecran_etroit() else 18))
    par_page = max(3, par_page)
    pages = max(1, math.ceil(len(options) / par_page))
    page = max(0, min(int(page), pages - 1))
    debut = page * par_page
    morceau = options[debut:debut + par_page]
    lignes = []
    for index, option in enumerate(morceau, start=1):
        ligne = Text(f"[{index}] ", style=f"bold {C_GOLD}")
        ligne.append(escape(option), style="white")
        lignes.append(ligne)
    if retour:
        lignes.append(Text("[0] Retour / annuler", style="bold yellow"))
    else:
        lignes.append(Text("[0] Annuler", style="bold yellow"))
    if pages > 1:
        lignes.append(Text(f"Page {page + 1}/{pages} · [98] suivante · [99] précédente",
                           style="dim"))
    largeur_panneau = min(largeur or largeur_utile(), 90)
    if MODE_TEXTE or largeur_panneau < 44:
        entete = Text(str(titre_menu), style=f"bold {C_GOLD}")
        return Group(entete, *lignes)
    return Panel(Group(*lignes), title=str(titre_menu), border_style=C_GOLD, box=BX,
                 width=largeur_panneau)


def show_menu(titre_menu, options, selection_initiale=0):
    return choisir_option(titre_menu, options, selection_initiale)


# Configuration et thème (import différé)
_CONFIG = None
_THEME = None
_UI_CONFIG = {}
_CUSTOM_THEME_ACTIVE = False


def initialiser_theme(config: dict):
    global C_OSINT, C_RECON, C_CYBER, C_UTIL, C_ASTRO, C_GOLD, C_PENTEST, C_DISCORD
    global _CONFIG, _THEME, _UI_CONFIG, _CUSTOM_THEME_ACTIVE
    from core.theme import appliquer_theme
    _CONFIG = config
    _UI_CONFIG = dict(config.get("apparence", {}))
    palette = appliquer_theme(config)
    _THEME = palette
    C_OSINT = palette.get("principale", C_OSINT)
    C_RECON = palette.get("secondaire", C_RECON)
    C_CYBER = palette.get("erreurs", C_CYBER)
    C_UTIL = palette.get("succes", C_UTIL)
    C_ASTRO = palette.get("secondaire", C_ASTRO)
    C_GOLD = palette.get("titres", C_GOLD)
    C_PENTEST = palette.get("avertissements", C_PENTEST)
    C_DISCORD = palette.get("accents", C_DISCORD)
    app = config.get("apparence", {})
    foreground = app.get("couleur_shell_texte", "#ffffff")
    background = app.get("couleur_shell_fond", "#10131c")
    if not isinstance(foreground, str) or not foreground.startswith("#"):
        foreground = "#ffffff"
    if not isinstance(background, str):
        background = "#10131c"
    try:
        console.style = Style(color=foreground, bgcolor=background)
    except (ValueError, TypeError):
        console.style = Style(color="#ffffff", bgcolor="#10131c")
        foreground, background = "#ffffff", "#10131c"
    if _CUSTOM_THEME_ACTIVE:
        console.pop_theme()
    console.push_theme(Theme({"prompt": palette.get("titres", C_GOLD),
                              "repr.number": palette.get("secondaire", C_RECON),
                              "shell.text": foreground,
                              "shell.background": background}), inherit=True)
    _CUSTOM_THEME_ACTIVE = True


def obtenir_theme() -> dict:
    return _THEME or {}


def obtenir_config_ui() -> dict:
    """Retourne une copie des réglages visuels actuellement actifs."""
    return dict(_UI_CONFIG)


DISCORD_EPOCH = 1420070400000

BANNER = [
    " ██████╗ ███████╗██╗███╗   ██╗████████╗",
    "██╔═══██╗██╔════╝██║████╗  ██║╚══██╔══╝",
    "██║   ██║███████╗██║██╔██╗ ██║   ██║   ",
    "██║   ██║╚════██║██║██║╚██╗██║   ██║   ",
    "╚██████╔╝███████║██║██║ ╚████║   ██║   ",
    " ╚═════╝ ╚══════╝╚═╝╚═╝  ╚═══╝   ╚═╝   ",
]

def warn_pentest() -> bool:
    console.print(
        Panel(
            Text.from_markup(
                "[bold red]⚠ AVERTISSEMENT LÉGAL[/]\n\n"
                "Ces outils sont réservés à des fins d'audit légitime sur des systèmes\n"
                "dont vous êtes le propriétaire ou explicitement autorisé."
            ),
            border_style="red",
            box=BX,
        )
    )
    return Confirm.ask("Confirmer l'autorisation d'audit", default=False)

def arc(x, t, vitesse=0.2, echelle=0.02):
    import colorsys
    h = (x * echelle - t * vitesse) % 1.0
    r, g, b = colorsys.hsv_to_rgb(h, 0.75, 1.0)
    return f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}"

def texte_arc(txt, t=0.0, decalage=0, gras=True):
    out = Text()
    base = "bold " if gras else ""
    for i, ch in enumerate(txt):
        out.append(ch, style=base + arc(i + decalage, t))
    return out

class _AttenteSimple:
    def __init__(self, label):
        self.label = label

    def __enter__(self):
        console.print(f"[dim]{escape(str(self.label))}...[/]")
        return self

    def __exit__(self, *_args):
        return False


def attente(label):
    """Animation discrète ou simple ligne selon le mode texte/mobile."""
    if MODE_TEXTE or not ANIMATIONS:
        return _AttenteSimple(label)
    t0 = time.time()
    frames = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏" if UNICODE else "|/-\\"

    def rendu():
        t = time.time() - t0
        ligne = Text()
        ligne.append(frames[int(t * 12) % len(frames)] + " ", style="bold " + arc(0, t, 0.5))
        ligne.append(label + "  ", style="bold white")
        ligne.append_text(texte_arc(FULL * 22, t * 3, 0))
        return ligne

    return Live(get_renderable=rendu, console=console, refresh_per_second=20, transient=True)

def titre(txt, couleur=C_RECON):
    w = max(12, min(largeur_utile(), 90))
    texte_titre = str(txt)
    if len(texte_titre) > w - 4:
        texte_titre = texte_titre[:max(1, w - 7)].rstrip() + "..."
    if MODE_TEXTE or w < 44:
        console.print(Text(texte_titre, style=f"bold {couleur}"))
        console.print(Text("-" * min(w, len(texte_titre) + 2), style="dim"))
        return
    trait = texte_arc(("━" if UNICODE else "=") * w, time.time(), 0)
    console.print()
    console.print(trait)
    console.print(Text(f" {texte_titre} ", style=f"bold {couleur}"), justify="center")
    console.print(trait)
    console.print()

def ok(txt):
    console.print(f"[bold green][+][/] {escape(str(txt))}")

def bad(txt):
    console.print(f"[bold red][-][/] {escape(str(txt))}")

def warn(txt):
    console.print(f"[bold yellow][!][/] {escape(str(txt))}")

def demander(label, defaut=None):
    if defaut is None:
        return Prompt.ask(f"[bold {C_GOLD}]{label}[/]").strip()
    return Prompt.ask(f"[bold {C_GOLD}]{label}[/]", default=defaut, show_default=False).strip()


RETOURS = {"retour", "retour au menu principal", "quitter", "quitter le panel",
           "terminer", "annuler", "retour au catalogue"}


def choisir_option(titre_menu, options, selection_initiale=0):
    """Sélection entièrement numérique, utilisable au clavier tactile.

    Les entrées vides répètent le menu ; ``0`` choisit l'option de retour
    quand elle existe, sinon annule. ``98``/``99`` paginent les longues
    listes sans imposer de flèches directionnelles.
    """
    options = [str(option) for option in options]
    if not options:
        return None
    dernier = options[-1]
    retour_label = dernier if dernier.casefold().strip() in RETOURS else None
    normal = options[:-1] if retour_label else options
    if not normal:
        return retour_label
    par_page = 10 if est_ecran_etroit() else 18
    pages = max(1, math.ceil(len(normal) / par_page))
    try:
        page = max(0, min(int(selection_initiale) // par_page, pages - 1))
    except (TypeError, ValueError):
        page = 0
    while True:
        morceau = normal[page * par_page:(page + 1) * par_page]
        console.print(render_menu(titre_menu, normal, page=page,
                                  par_page=par_page, retour=bool(retour_label)))
        if pages > 1:
            console.print(f"[dim]Page {page + 1}/{pages}. 98 = suivante, 99 = précédente.[/]")
        try:
            index_defaut = max(0, min(int(selection_initiale), len(normal) - 1))
        except (TypeError, ValueError):
            index_defaut = 0
        defaut_num = index_defaut - page * par_page + 1
        if not 1 <= defaut_num <= len(morceau):
            defaut_num = 1 if morceau else 0
        try:
            brut = Prompt.ask(f"[bold {C_GOLD}]Choisis une option[/]",
                              default=str(defaut_num), show_default=True).strip()
        except (KeyboardInterrupt, EOFError):
            return None
        if brut == "00":
            raise QuitterApplication()
        if brut == "":
            brut = "0"
        if not brut.isdigit():
            bad(f"Entrée invalide : saisis un numéro entre 1 et {len(morceau)}, "
                "0 pour retour/annuler, 98/99 pour paginer.")
            continue
        nombre = int(brut)
        if nombre == 0:
            return retour_label
        if nombre == 98:
            page = (page + 1) % pages
            continue
        if nombre == 99:
            page = (page - 1) % pages
            continue
        if 1 <= nombre <= len(morceau):
            return morceau[nombre - 1]
        bad(f"Numéro hors limites (1-{len(morceau)}).")
        if pages > 1:
            bad("98 = page suivante, 99 = page précédente, 0 = retour.")

def kv(titre_txt, lignes, couleur=C_RECON):
    lignes = list(lignes)
    if est_ecran_etroit():
        elements = []
        for k, v in lignes:
            ligne = Text(f"{k} : ", style=f"bold {couleur}")
            ligne.append_text(v if isinstance(v, Text) else Text(str(v)))
            elements.append(ligne)
        console.print(Panel(Group(*elements), title=str(titre_txt), box=BX,
                            border_style=couleur, width=min(largeur_utile(), 90)))
        return
    t = Table(title=titre_txt, box=BX, border_style=couleur, title_style=f"bold {couleur}", show_header=False, padding=(0, 1))
    t.add_column(style=f"bold {couleur}", no_wrap=True)
    t.add_column()
    for k, v in lignes:
        t.add_row(escape(str(k)), v if isinstance(v, Text) else escape(str(v)))
    console.print(t)

def jauge(pct, largeur=30, couleur=C_GOLD):
    n = max(0, min(largeur, round(pct / 100 * largeur)))
    return Text.from_markup(f"[{couleur}]{FULL * n}[/][dim]{EMPTY * (largeur - n)}[/]")

def pause():
    Prompt.ask("\n[dim]Entrée pour revenir au menu[/]", default="", show_default=False)

def barre():
    return Progress(SpinnerColumn(style="cyan"), TextColumn("[bold]{task.description}"),
                    BarColumn(), TaskProgressColumn(), console=console, transient=True,
                    disable=MODE_TEXTE or not ANIMATIONS)

def afficher_pagine(titre_txt, colonnes, rows, rendu, lien=None, par_page=None, fichier="export.csv", couleur=C_RECON, caption=""):
    vue = rows[:]
    filtre = ""
    page = 0
    message = ""
    par_page = int(par_page or PAGINATION_DEFAUT)
    par_page = max(1, par_page)
    while True:
        pages = max(1, math.ceil(len(vue) / par_page))
        page = min(max(page, 0), pages - 1)
        debut = page * par_page
        morceau = vue[debut:debut + par_page]

        clear_screen()
        if est_ecran_etroit() and len(colonnes) > 2:
            elements = [Text(str(titre_txt), style=f"bold {couleur}")]
            for i, row in enumerate(morceau):
                valeurs = rendu(row)
                champs = []
                for libelle, valeur in zip(colonnes, valeurs):
                    ligne = Text(f"{libelle} : ", style=f"bold {couleur}")
                    if isinstance(valeur, Text):
                        ligne.append_text(valeur)
                    else:
                        ligne.append(str(valeur))
                    champs.append(ligne)
                elements.append(Panel(Group(*champs),
                                      title=f"Résultat {debut + i + 1}/{len(vue)}",
                                      border_style="grey42", box=BX))
            if not morceau:
                elements.append(Text("[dim]Aucun résultat.[/]"))
            console.print(Group(*elements))
        else:
            t = Table(title=titre_txt, title_style=f"bold {couleur}", box=BX, border_style=couleur,
                      header_style=f"bold {couleur}", caption=caption, caption_style="dim")
            t.add_column("#", justify="right", style=f"bold {C_GOLD}")
            for c in colonnes:
                t.add_column(c)
            for i, row in enumerate(morceau):
                t.add_row(str(debut + i + 1), *rendu(row))
            if not morceau:
                t.add_row("-", *["[dim]aucun résultat[/]"] + [""] * (len(colonnes) - 1))
            console.print(t)

        etat = f"Page [bold]{page + 1}[/]/[bold]{pages}[/]   |   [bold]{len(vue)}[/] résultat(s)"
        if filtre:
            etat += f"   |   filtre : [bold {C_OSINT}]{escape(filtre)}[/]"
        aide = (f"[bold {couleur}]n[/] suivant   [bold {couleur}]p[/] précédent   "
                f"[bold {couleur}]<numéro>[/] aller à la page   "
                f"[bold {couleur}]f texte[/] filtrer   [bold {couleur}]f[/] reset")
        if lien:
            aide += f"   [bold {couleur}]o N[/] ouvrir"
        aide += f"   [bold {couleur}]e[/] export CSV   [bold {couleur}]q[/] quitter"
        if est_ecran_etroit():
            console.print(Panel(etat + "\n" + "\n".join(part.strip() for part in aide.split("   ")),
                                border_style="grey50", box=BX))
        else:
            console.print(Panel(etat + "\n" + aide, border_style="grey50", box=BX))
        if message:
            console.print(message)
            message = ""

        cmd = Prompt.ask(f"[bold {couleur}]{ARROW}[/] Commande", default="n").strip()
        low = cmd.lower()

        if low in ("q", "quit", "exit"):
            return
        elif low in ("n", ""):
            if page >= pages - 1:
                message = "[yellow]Tu es déjà sur la dernière page.[/]"
            page += 1
        elif low in ("p", "b"):
            if page == 0:
                message = "[yellow]Tu es déjà sur la première page.[/]"
            page -= 1
        elif low.isdigit():
            page = int(low) - 1
        elif low.startswith("f"):
            filtre = cmd[1:].strip()
            vue = [r for r in rows if filtre.lower() in " ".join(map(str, r)).lower()] if filtre else rows[:]
            page = 0
        elif low.startswith("o") and lien:
            m = re.match(r"o\s*(\d+)", low)
            if m and 1 <= int(m.group(1)) <= len(vue):
                url = lien(vue[int(m.group(1)) - 1])
                ouvrir_url(url)
                message = f"[green]Ouverture :[/] {escape(url)}"
            else:
                message = "[red]Numéro invalide. Exemple : o 12[/]"
        elif low == "e":
            try:
                with open(fichier, "w", newline="", encoding="utf-8-sig") as f:
                    w = csv.writer(f, delimiter=";")
                    w.writerow(list(colonnes) + (["lien"] if lien else []))
                    for r in vue:
                        w.writerow(list(r) + ([lien(r)] if lien else []))
                message = f"[green]Exporté dans[/] [bold]{fichier}[/] ({len(vue)} lignes)"
            except Exception as e:
                message = f"[red]Export impossible : {escape(str(e))}[/]"
        else:
            message = "[red]Commande inconnue.[/]"

def ouvrir_url(url):
    """Ouvre une URL avec le navigateur du système si possible.

    Sur Android/Termux, le module webbrowser peut échouer : la commande
    `termux-open-url` est alors utilisée quand elle existe. Sinon l'URL est
    affichée pour permettre une copie manuelle ; aucun échec silencieux.
    """
    try:
        if webbrowser.open(url):
            return True
    except Exception:
        pass
    for commande in ("termux-open-url", "xdg-open", "open"):
        chemin = shutil.which(commande)
        if not chemin:
            continue
        try:
            subprocess.run([chemin, url], timeout=10, check=False,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except (OSError, subprocess.SubprocessError):
            continue
    console.print(f"[yellow]Ouverture automatique impossible. URL :[/] {escape(str(url))}")
    return False


def resoudre(cible):
    try:
        return socket.gethostbyname(cible)
    except socket.gaierror:
        return None

def doh(nom, type_):
    try:
        r = requests.get("https://dns.google/resolve", params={"name": nom, "type": type_}, headers=HEADERS, timeout=TIMEOUT)
        return [a["data"] for a in r.json().get("Answer", [])]
    except Exception:
        return []

def nettoyer_cible(c):
    return re.sub(r"^https?://", "", c.strip()).rstrip("/")