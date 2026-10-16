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

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import main

OUT = ROOT / "docs" / "screenshots"
CATEGORY_SLUGS = {
    "OSINT": "osint",
    "RECONNAISSANCE": "reconnaissance",
    "CYBER": "cyber",
    "PENTEST & RESEAU": "pentest-reseau",
    "DISCORD OSINT": "discord",
    "UTILITAIRES": "utilitaires",
    "ASTRONOMIE": "astronomie",
}
MODULE_DIRS = {
    "OSINT": "osint", "RECONNAISSANCE": "recon", "CYBER": "cyber",
    "PENTEST & RESEAU": "pentest", "DISCORD OSINT": "discord",
    "UTILITAIRES": "utils", "ASTRONOMIE": "astro",
}


def slug(text):
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def save_renderable(renderable, path, title):
    terminal = Console(record=True, file=io.StringIO(), width=124, height=42,
                       force_terminal=True, color_system="truecolor", legacy_windows=False)
    terminal.print(renderable)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(terminal.export_svg(title=title), encoding="utf-8")


def main_menu():
    terminal = Console(record=True, file=io.StringIO(), width=124, height=42,
                       force_terminal=True, color_system="truecolor", legacy_windows=False)
    terminal.print(main.construire_menu(-1, "", 0, tout=True))
    (OUT / "menu-principal.svg").write_text(terminal.export_svg(title="LeakFr-Tools — menu principal"), encoding="utf-8")

    from rich.table import Table
    overview = Console(record=True, file=io.StringIO(), width=100, force_terminal=True,
                       color_system="truecolor", legacy_windows=False)
    table = Table(title="LeakFr-Tools — catégories", border_style="cyan")
    table.add_column("Catégorie", style="bold")
    table.add_column("Outils", justify="right")
    table.add_column("Domaines")
    for category, _, tools in main.CATALOGUE:
        table.add_row(category, str(len(tools)), ", ".join(name for name, _, _ in tools[:3]) + ("…" if len(tools) > 3 else ""))
    overview.print(table)
    (OUT / "categories.svg").write_text(overview.export_svg(title="LeakFr-Tools — aperçu des catégories"), encoding="utf-8")


def generate():
    if OUT.exists():
        for old_image in OUT.rglob("*.svg"):
            old_image.unlink()
    OUT.mkdir(parents=True, exist_ok=True)
    main_menu()
    for category_index, (category_name, _, tools) in enumerate(main.CATALOGUE):
        cat_slug = CATEGORY_SLUGS[category_name]
        first_tool_index = next(i for i, item in enumerate(main.FLAT)
                                if item["cat"] == category_index)
        cat_render = main.construire_menu(first_tool_index, "", 0, tout=False)
        save_renderable(cat_render, OUT / "categories" / f"{cat_slug}.svg",
                        f"LeakFr-Tools — {category_name}")
        for name, description, _function in tools:
            index = next(i for i, item in enumerate(main.FLAT) if item["nom"] == name)
            renderable = main.construire_menu(index, "", 0, tout=False)
            module_slug = slug(name)
            save_renderable(
                renderable,
                OUT / "modules" / MODULE_DIRS[category_name] / f"{module_slug}.svg",
                f"LeakFr-Tools — {name}",
            )
    return sum(1 for _ in OUT.rglob("*.svg"))


if __name__ == "__main__":
    print(f"Captures générées : {generate()} fichiers SVG dans {OUT.relative_to(ROOT)}")
