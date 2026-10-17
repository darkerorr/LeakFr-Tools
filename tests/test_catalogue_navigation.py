from copy import deepcopy
import importlib
import io
import json
import re
import socket
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

import main
from modules.discord.gateway_bot import DiscordGatewayClient

bot_panel_module = importlib.import_module("modules.discord.bot_panel")


def test_catalogue_contains_all_modules_and_maps_actions():
    total = sum(len(options) for _, _, options in main.CATALOGUE)
    assert total == 92
    assert sum(1 for item in main.FLAT if item["fn"]) == total
    assert len(main.ACTIONS) == total + 4
    assert len(main.CATALOGUE) == 7
    assert len(main.NAV_GROUPS) == 8  # recherches et alias fonctionnels restent disponibles
    assert main.SEL == main.NUM_IDX["1"]
    assert main.FLAT[main.SEL]["nom"] == "Recherche de pseudo"
    routed_names = set(main._ROUTE_PAR_NOM)
    catalogue_names = {name for _, _, options in main.CATALOGUE for name, _, _ in options}
    assert routed_names == catalogue_names
    assert len(routed_names) == len(catalogue_names)
    utility_names = {name for name, _, _ in main.CATALOGUE[5][2]}
    assert {"Generateur de mot de passe", "Formateur JSON", "Analyseur de texte",
            "Generateur UUID", "Convertisseur de bases", "Calculateur de dates",
            "Corpus cas limites HTTP", "Audit de la machine"} <= utility_names


def test_global_search_finds_function_aliases_and_direct_routing():
    found = main.rechercher_outils("certificat tls")
    noms = [tool["nom"] for tool in found]
    assert noms[0] == "Certificat SSL/TLS"
    assert "TLS Policy Diff" in noms
    assert found[0]["chemin_navigation"] == "SECURITE WEB > TLS & identité"
    assert main.rechercher_outils("TLS")
    assert main.rechercher_outils("subnet")[0]["nom"] == "Calculateur CIDR"
    assert main.rechercher_outils("  ") == []
    assert main.ACTIONS[found[0]["num"]] is found[0]["fn"]
    assert "Gestion des dossiers" in [tool["nom"] for tool in main.rechercher_outils("notes sources")]
    assert main.rechercher_outils("preuve integrite")[0]["nom"] == "Evidence Chain Ledger"
    assert main.rechercher_outils("correlation entites")[0]["nom"] == "Finding Correlator"
    assert main.ACTIONS["evidence"] is main._ouvrir_preuves
    assert main.ACTIONS["correlation"] is main._ouvrir_correlation


def test_search_shortcuts_open_case_workflows(monkeypatch):
    dossier = {"id": 1, "title": "Enquete"}
    appels = []
    monkeypatch.setattr(main, "_selectionner_dossier", lambda _titre: dossier)
    monkeypatch.setattr(main, "_gestion_preuves", lambda case: appels.append(("preuves", case)))
    monkeypatch.setattr(main, "_correler_dossier", lambda case: appels.append(("correlation", case)))

    main._ouvrir_preuves()
    main._ouvrir_correlation()
    assert appels == [("preuves", dossier), ("correlation", dossier)]

    monkeypatch.setattr(main, "_selectionner_dossier", lambda _titre: None)
    main._ouvrir_preuves()
    main._ouvrir_correlation()
    assert len(appels) == 2


def test_global_search_selection_returns_action_key(monkeypatch):
    tool = main.rechercher_outils("certificat tls")[0]
    monkeypatch.setattr(main.Prompt, "ask", lambda *_args, **_kwargs: "certificat tls")
    monkeypatch.setattr(main, "selectionner_option", lambda _title, choices: choices[0])
    assert main.recherche_globale() == tool["num"]


def test_navigation_routes_every_catalogue_tool_through_its_path(monkeypatch):
    monkeypatch.setattr(main.console, "clear", lambda: None)
    monkeypatch.setattr(main.console, "print", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(main, "titre", lambda *_args, **_kwargs: None)
    for tool in main.FLAT:
        if not tool["fn"]:
            continue
        category_name = main.CATALOGUE[tool["cat"]][0]
        choices = iter([category_name, tool["nom"]])
        monkeypatch.setattr(main, "selectionner_option", lambda *_args, _choices=choices, **_kwargs: next(_choices))
        assert main.menu_simple() == tool["num"], tool["nom"]


def test_original_menu_cancel_and_category_back(monkeypatch):
    choices = iter(["OSINT", "Retour", None])
    monkeypatch.setattr(main, "selectionner_option", lambda *_args, **_kwargs: next(choices))
    assert main.menu_simple() == "0"


def test_original_menu_search_shortcut_opens_result_directly(monkeypatch):
    choices = iter(["Recherche globale"])
    monkeypatch.setattr(main, "selectionner_option", lambda *_args, **_kwargs: next(choices))
    monkeypatch.setattr(main, "recherche_globale", lambda: "42")
    assert main.menu_simple() == "42"


def test_help_and_version_cli(capsys, monkeypatch):
    monkeypatch.setattr("sys.argv", ["main.py", "--help"])
    with pytest.raises(SystemExit) as help_exit:
        main.main()
    assert help_exit.value.code == 0
    assert "--simple" in capsys.readouterr().out

    monkeypatch.setattr("sys.argv", ["main.py", "--version"])
    with pytest.raises(SystemExit) as version_exit:
        main.main()
    assert version_exit.value.code == 0
    assert "LeakFr-Tools 2.0" in capsys.readouterr().out


def test_visual_settings_are_persistent_and_apply_to_rendered_menu(monkeypatch):
    from core.config import DEFAUTS
    from core.common import obtenir_config_ui, obtenir_theme

    config = deepcopy(DEFAUTS)
    config["apparence"].update({
        "theme_actif": "bleu_electrique",
        "style_interface": "compact",
        "couleur_accent": "#12abef",
        "afficher_badges_categories": False,
        "afficher_panneau_lateral": False,
    })
    monkeypatch.setattr(main, "_CONFIG", config)
    main._appliquer_configuration_visuelle()
    assert obtenir_config_ui()["style_interface"] == "compact"
    assert obtenir_theme()["principale"] == "#12abef"
    rendered = main.construire_menu(main.NUM_IDX["1"], "", 0)
    from rich.console import Console
    terminal = Console(file=io.StringIO(), width=100, force_terminal=False, record=True)

    terminal.print(rendered)
    output = terminal.file.getvalue()
    assert "INSPECTEUR" not in output
    assert "SUITE DE SECURITE & RECON" in output
    assert "PENTEST & RESEAU" in output
    assert "s : parametres" in output
    assert "recherche" in output.lower()
    monkeypatch.setattr(main, "_CONFIG", deepcopy(DEFAUTS))
    main._appliquer_configuration_visuelle()


def test_menu_settings_route_opens_settings_then_returns_to_main(monkeypatch):
    choices = iter(["Parametres", "Quitter"])
    transitions = []
    monkeypatch.setattr(main, "selectionner_option", lambda *_args, **_kwargs: next(choices))
    monkeypatch.setattr(main, "_ecran_parametres", lambda: transitions.append("settings-open"))
    monkeypatch.setattr(main.console, "clear", lambda: None)
    assert main.menu_simple() == "0"
    assert transitions == ["settings-open"]


def test_numeric_selector_uses_touch_keyboard_numbers(monkeypatch):
    """Le menu commun se pilote au numéro, sans flèches ni souris."""
    import core.common as common_ui

    reponses = iter(["3", "2"])
    monkeypatch.setattr(common_ui.Prompt, "ask",
                        lambda *_args, **_kwargs: next(reponses))
    assert common_ui.choisir_option("Test", ["Premier", "Second"]) == "Second"

    monkeypatch.setattr(common_ui.Prompt, "ask", lambda *_args, **_kwargs: "0")
    assert common_ui.choisir_option("Test", ["Premier", "Retour"]) == "Retour"

    monkeypatch.setattr(common_ui.Prompt, "ask", lambda *_args, **_kwargs: "00")
    with pytest.raises(common_ui.QuitterApplication):
        common_ui.choisir_option("Test", ["Premier", "Second"])


def test_settings_screen_opens_submenu_and_applies_selection(monkeypatch):
    import core.common as common_ui
    from core.config import DEFAUTS

    monkeypatch.setattr(main, "_CONFIG", deepcopy(DEFAUTS))
    monkeypatch.setattr(main.console, "clear", lambda: None)
    monkeypatch.setattr(main, "sauvegarder", lambda _config: None)
    monkeypatch.setattr(main, "pause", lambda: None)
    choices = iter(["Style d'interface", "Compact", "Retour au menu principal"])
    seen_menus = []
    def choose(label, options, **_kwargs):
        seen_menus.append((label, list(options)))
        return next(choices)
    monkeypatch.setattr(main, "selectionner_option", choose)
    main._ecran_parametres()

    assert main._CONFIG["apparence"]["style_interface"] == "compact"
    assert common_ui.obtenir_config_ui()["style_interface"] == "compact"
    assert seen_menus[0][0] == "PARAMETRES"
    assert "Style d'interface" in seen_menus[0][1]
    assert seen_menus[1] == ("STYLE D'INTERFACE", ["Dashboard split", "Classique", "Compact"])


def test_screenshots_cover_every_module_and_readme_link():
    screenshots = Path("docs/screenshots")
    assert (screenshots / "menu-principal.svg").is_file()
    module_images = list((screenshots / "modules").rglob("*.svg"))
    assert len(module_images) == sum(len(options) for _, _, options in main.CATALOGUE)
    for readme in Path("modules").glob("*/README.md"):
        for link in re.findall(r"\]\(([^)]+\.svg)\)", readme.read_text(encoding="utf-8")):
            assert (readme.parent / link).resolve().is_file(), (readme, link)
