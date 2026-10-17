#!/usr/bin/env python3
"""Génère des captures statiques des menus Rich, sans réseau ni données de compte.

Usage : python3 scripts/generate_screenshots.py
Les SVG produits montrent l'interface de navigation, pas l'exécution des outils.
"""
from pathlib import Path
import io
import re
import sys
import unicodedata

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import main

OUT = ROOT / "docs" / "screenshots"
MODULE_DIRS = {
    "OSINT": "osint", "RECONNAISSANCE": "recon", "CYBER": "cyber",
    "PENTEST & RESEAU": "pentest", "DISCORD OSINT": "discord",
    "UTILITAIRES": "utils", "ASTRONOMIE": "astro",
}


def slug(text):
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def write_svg(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(line.rstrip() for line in content.splitlines()) + "\n", encoding="utf-8")


def save_renderable(renderable, path, title):
    terminal = Console(record=True, file=io.StringIO(), width=124, height=42,
                       force_terminal=True, color_system="truecolor", legacy_windows=False)
    terminal.print(renderable)
    write_svg(path, terminal.export_svg(title=title))


def main_menu():
    terminal = Console(record=True, file=io.StringIO(), width=124, height=42,
                       force_terminal=True, color_system="truecolor", legacy_windows=False)
    terminal.print(main.construire_menu(-1, "", 0, tout=True))
    write_svg(OUT / "menu-principal.svg", terminal.export_svg(title="LeakFr-Tools — menu principal"))

    overview = Console(record=True, file=io.StringIO(), width=100, force_terminal=True,
                       color_system="truecolor", legacy_windows=False)
    table = Table(title="LeakFr-Tools — domaines de navigation", border_style="cyan")
    table.add_column("Domaine", style="bold")
    table.add_column("Sous-catégories", justify="right")
    table.add_column("Usage")
    for category, _, description, sections in main.NAV_GROUPS:
        table.add_row(category, str(len(sections)), description)
    table.add_row("Recherche globale", "—", "Recherche par nom, catégorie et fonction")
    table.add_row("Configuration", "—", "Thèmes et préférences")
    table.add_row("Quitter", "—", "Fermer l'application")
    overview.print(table)
    write_svg(OUT / "categories.svg", overview.export_svg(title="LeakFr-Tools — aperçu des catégories"))


def generate():
    if OUT.exists():
        for old_image in OUT.rglob("*.svg"):
            old_image.unlink()
    OUT.mkdir(parents=True, exist_ok=True)
    main_menu()
    for category, color, description, sections in main.NAV_GROUPS:
        table = Table(title=f"LeakFr-Tools — {category}", border_style=color)
        table.add_column("Sous-catégorie", style="bold")
        table.add_column("Outil")
        table.add_column("Usage")
        for section, section_description, names in sections:
            if names:
                for name in names:
                    tool = main._OUTILS_PAR_NOM[name]
                    table.add_row(section, name, tool["desc"])
            else:
                table.add_row(section, "Gestion des dossiers / Historique", section_description)
        save_renderable(table, OUT / "categories" / f"{slug(category)}.svg",
                        f"LeakFr-Tools — {category}")

    for category_name, _, tools in main.CATALOGUE:
        table = Table(title=f"LeakFr-Tools — {category_name}", border_style="cyan")
        table.add_column("Outil", style="bold")
        table.add_column("Chemin")
        table.add_column("Description")
        for name, description, _function in tools:
            tool = main._OUTILS_PAR_NOM[name]
            table.add_row(name, tool["chemin_navigation"], description)
            module_slug = slug(name)
            preview = Panel(
                Text(f"{tool['chemin_navigation']}\\n\\n{description}\\n\\nAction : lancement direct depuis la sélection."),
                title=f"{name} · aperçu de navigation", border_style=tool["couleur"],
            )
            save_renderable(
                preview,
                OUT / "modules" / MODULE_DIRS[category_name] / f"{module_slug}.svg",
                f"LeakFr-Tools — {name}",
            )
    count = sum(len(options) for _, _, options in main.CATALOGUE)
    assert len(list((OUT / "modules").rglob("*.svg"))) == count
    assert len(main._ROUTE_PAR_NOM) == count
    aliases = {"securite-web": "cyber", "reseau-laboratoire": "pentest-reseau",
               "analyse-utilitaires": "utilitaires"}
    for source_slug, target_slug in aliases.items():
        source = OUT / "categories" / f"{source_slug}.svg"
        target = OUT / "categories" / f"{target_slug}.svg"
        write_svg(target, source.read_text(encoding="utf-8"))
    return sum(1 for _ in OUT.rglob("*.svg"))


if __name__ == "__main__":
    print(f"Captures générées : {generate()} fichiers SVG dans {OUT.relative_to(ROOT)}")
