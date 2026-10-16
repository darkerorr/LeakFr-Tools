import csv
import math
import re
import socket
import sys
import time
import webbrowser
import requests
from rich import box
from rich.console import Console
from rich.live import Live
from rich.markup import escape
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich.text import Text

console = Console()
HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}
TIMEOUT = 8

UNICODE = ("utf" in (console.encoding or "").lower()) and "--ascii" not in sys.argv
INTERACTIF = sys.stdin.isatty() and sys.stdout.isatty() and "--simple" not in sys.argv

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

def attente(label):
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
    w = min(console.width or 90, 90)
    trait = texte_arc(("━" if UNICODE else "=") * w, time.time(), 0)
    console.print()
    console.print(trait)
    console.print(Text(f" {txt} ", style=f"bold {couleur}"), justify="center")
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

def kv(titre_txt, lignes, couleur=C_RECON):
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
                    BarColumn(), TaskProgressColumn(), console=console, transient=True)

def afficher_pagine(titre_txt, colonnes, rows, rendu, lien=None, par_page=15, fichier="export.csv", couleur=C_RECON, caption=""):
    vue = rows[:]
    filtre = ""
    page = 0
    message = ""
    while True:
        pages = max(1, math.ceil(len(vue) / par_page))
        page = min(max(page, 0), pages - 1)
        debut = page * par_page
        morceau = vue[debut:debut + par_page]

        console.clear()
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
                webbrowser.open(url)
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
