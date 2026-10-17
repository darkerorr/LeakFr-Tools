"""Tests multiplateformes : détection, navigation numérique et écran étroit.

Ces tests s'exécutent sur l'hôte Linux de développement. Ils ne prétendent pas
valider un téléphone Android réel : la détection Termux est simulée à partir
des variables d'environnement documentées.
"""
import io
from copy import deepcopy
from pathlib import Path

import pytest
from rich.table import Table
from rich.text import Text

import core.common as common_ui
import core.compat as compat
import core.config as config_module
import core.environment as environment
import main as main_module
from core.config import DEFAUTS


# ---------------------------------------------------------------------------
# A. Détection et sélection de l'environnement
# ---------------------------------------------------------------------------

def test_detection_termux_par_variables_et_pas_uniquement_linux(monkeypatch):
    monkeypatch.setattr(environment, "est_termux", lambda env=None: True)
    detecte = environment.detecter_environnement(
        sys_platform="linux", os_name="posix",
        env={"PREFIX": "/data/data/com.termux/files/usr", "TERMUX_VERSION": "0.118"})
    assert detecte["cle"] == "termux"
    assert detecte["label"] == "Android / Termux"
    assert detecte["termux"] is True
    assert detecte["confiance"] == "haute"


def test_detection_android_sans_termux_reste_distincte(monkeypatch):
    monkeypatch.setattr(environment, "est_termux", lambda env=None: False)
    monkeypatch.setattr(environment, "est_android", lambda env=None: True)
    detecte = environment.detecter_environnement(sys_platform="linux", os_name="posix",
                                                 env={"ANDROID_ROOT": "/system"})
    assert detecte["cle"] == "termux"
    assert detecte["confiance"] == "moyenne"


def test_detection_windows_macos_et_linux(monkeypatch):
    monkeypatch.setattr(environment, "est_termux", lambda env=None: False)
    monkeypatch.setattr(environment, "est_android", lambda env=None: False)
    assert environment.detecter_environnement("win32", "nt", {})["cle"] == "windows"
    assert environment.detecter_environnement("darwin", "posix", {})["cle"] == "macos"
    assert environment.detecter_environnement("linux", "posix", {})["cle"] == "linux"


def test_normalisation_et_index_des_environnements():
    assert environment.normaliser_cle("Android/termux") == "termux"
    assert environment.normaliser_cle("Win32") == "windows"
    assert environment.normaliser_cle("inconnu") == "autre"
    assert environment.index_environnement("termux") == 3
    assert environment.libelle_environnement("macos") == "macOS"


def _capture_console():
    tampon = io.StringIO()
    capture = common_ui.ConsoleAdaptative(file=tampon, width=80)
    return tampon, lambda objet: capture.print(objet)


def test_selection_manuelle_accepte_un_numero_valide():
    tampon, ecrire = _capture_console()
    detecte = {"cle": "linux", "label": "Linux", "indices": ["test"], "confiance": "haute"}
    reponses = iter(["3"])
    assert environment.select_environment({}, entree=lambda _invite: next(reponses),
                                          sortie=ecrire) == "termux"
    assert "Android / Termux" in tampon.getvalue()


def test_selection_manuelle_refuse_une_saisie_invalide_puis_reprend():
    tampon, ecrire = _capture_console()
    detecte = {"cle": "linux", "label": "Linux", "indices": [], "confiance": "haute"}
    reponses = iter(["99", "2"])
    assert environment.select_environment({}, entree=lambda _invite: next(reponses),
                                          sortie=ecrire,
                                          detecte=detecte) == "linux"
    assert "Saisie invalide" in tampon.getvalue()


def test_selection_manuelle_vide_garde_la_detection_et_config():
    detecte = {"cle": "linux", "label": "Linux", "indices": [], "confiance": "haute"}
    assert environment.select_environment({}, entree=lambda _invite: "",
                                          sortie=lambda _ligne: None,
                                          detecte=detecte) == "linux"
    config = {"plateforme": {"environnement": "termux"}}
    assert environment.select_environment(config, entree=lambda _invite: "",
                                          sortie=lambda _ligne: None,
                                          detecte=detecte) == "termux"


def test_selection_interrompue_retourne_la_detection():
    detecte = {"cle": "macos", "label": "macOS", "indices": [], "confiance": "haute"}

    def interrompre(_invite):
        raise KeyboardInterrupt

    assert environment.select_environment({}, entree=interrompre,
                                          sortie=lambda _ligne: None,
                                          detecte=detecte) == "macos"


def test_initialisation_environnement_persiste_le_choix(monkeypatch):
    monkeypatch.setattr(main_module, "_CONFIG", deepcopy(DEFAUTS))
    enregistre = {}
    monkeypatch.setattr(main_module, "sauvegarder",
                        lambda config: enregistre.update(deepcopy(config)) or True)
    monkeypatch.setattr(main_module, "detecter_environnement",
                        lambda: {"cle": "linux", "label": "Linux", "indices": [],
                                 "confiance": "haute"})
    main_module._initialiser_environnement(force="termux")
    assert main_module._CONFIG["plateforme"]["environnement"] == "termux"
    assert enregistre["plateforme"]["environnement"] == "termux"
    assert common_ui.MODE_MOBILE is True
    # Restaure l'état global utilisé par les autres tests.
    monkeypatch.setattr(common_ui, "MODE_MOBILE", False)
    monkeypatch.setattr(common_ui, "MODE_TEXTE", False)


# ---------------------------------------------------------------------------
# B. Navigation numérique et saisies
# ---------------------------------------------------------------------------

def test_choisir_option_valide_les_numeros_et_le_retour(monkeypatch):
    reponses = iter(["abc", "2"])
    monkeypatch.setattr(common_ui.Prompt, "ask", lambda *_a, **_k: next(reponses))
    assert common_ui.choisir_option("Test", ["Un", "Deux"]) == "Deux"
    monkeypatch.setattr(common_ui.Prompt, "ask", lambda *_a, **_k: "0")
    assert common_ui.choisir_option("Test", ["Un", "Retour"]) == "Retour"


def test_commande_00_quitte_application(monkeypatch):
    monkeypatch.setattr(common_ui.Prompt, "ask", lambda *_a, **_k: "00")
    with pytest.raises(common_ui.QuitterApplication):
        common_ui.choisir_option("Test", ["Un", "Deux"])


def test_interruption_clavier_annule_proprement(monkeypatch):
    def interrompre(*_args, **_kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(common_ui.Prompt, "ask", interrompre)
    assert common_ui.choisir_option("Test", ["Un", "Deux"]) is None
    assert common_ui.ask_number("Nombre", 1, 5) is None


def test_ask_number_refuse_une_valeur_hors_limites(monkeypatch):
    reponses = iter(["0", "9", "3"])
    monkeypatch.setattr(common_ui.Prompt, "ask", lambda *_a, **_k: next(reponses))
    assert common_ui.ask_number("Nombre", 1, 5) == 3


def test_pagination_numerique_sur_ecran_etroit(monkeypatch):
    monkeypatch.setattr(common_ui, "est_ecran_etroit", lambda: True)
    reponses = iter(["98", "1"])
    monkeypatch.setattr(common_ui.Prompt, "ask", lambda *_a, **_k: next(reponses))
    options = [f"O{index}" for index in range(1, 13)]
    assert common_ui.choisir_option("Liste", options) == "O11"


# ---------------------------------------------------------------------------
# C. Interface en terminal étroit
# ---------------------------------------------------------------------------

def test_les_lignes_du_menu_ne_depassent_pas_la_largeur(monkeypatch):
    monkeypatch.setattr(common_ui.console, "width", 44, raising=False)
    monkeypatch.setattr(common_ui, "MODE_MOBILE", True)
    sortie = io.StringIO()
    petite = common_ui.ConsoleAdaptative(file=sortie, width=44)
    petite.print(common_ui.render_menu("MENU", [f"Option {i}" for i in range(1, 15)]))
    lignes = [ligne for ligne in sortie.getvalue().splitlines() if ligne.strip()]
    assert lignes
    assert max(len(ligne) for ligne in lignes) <= 44
    assert "Option 1" in sortie.getvalue()
    assert "[0] Retour" in sortie.getvalue()


def test_les_tableaux_larges_deviennent_des_fiches_verticales():
    sortie = io.StringIO()
    petite = common_ui.ConsoleAdaptative(file=sortie, width=44)
    table = Table(title="Résultats")
    table.add_column("Nom")
    table.add_column("Statut")
    table.add_column("Code")
    table.add_row("exemple.com", "accessible", "200")
    petite.print(table)
    rendu = sortie.getvalue()
    assert "Nom :" in rendu and "Statut :" in rendu and "Code :" in rendu
    assert "exemple.com" in rendu
    assert "Résultats" in rendu


def test_les_fiches_cle_valeur_restent_lisibles(monkeypatch):
    monkeypatch.setattr(common_ui, "est_ecran_etroit", lambda: True)
    monkeypatch.setattr(common_ui, "largeur_utile", lambda: 42)
    sortie = io.StringIO()
    petite = common_ui.ConsoleAdaptative(file=sortie, width=42)
    sortie_originale = common_ui.console
    try:
        common_ui.console = petite
        common_ui.kv("Résultat 1/12", [("Nom", "exemple.com"),
                                       ("Code HTTP", "200")])
    finally:
        common_ui.console = sortie_originale
    rendu = sortie.getvalue()
    assert "Nom : exemple.com" in rendu
    assert "Code HTTP : 200" in rendu


def test_pagination_resultats_en_fiches_verticales_sur_mobile(monkeypatch):
    sortie = io.StringIO()
    petite = common_ui.ConsoleAdaptative(file=sortie, width=44)
    monkeypatch.setattr(common_ui, "console", petite)
    monkeypatch.setattr(common_ui, "est_ecran_etroit", lambda: True)
    monkeypatch.setattr(common_ui.Prompt, "ask", lambda *_a, **_k: "q")
    lignes = [["exemple.com", "accessible", "200"],
              ["test.tld", "injoignable", "000"]]

    common_ui.afficher_pagine(
        "Résultats OSINT", ["Nom", "Statut", "Code HTTP"], lignes,
        lambda ligne: [str(valeur) for valeur in ligne])

    rendu = sortie.getvalue()
    assert "Résultat 1/2" in rendu
    assert "Nom : exemple.com" in rendu
    assert "Code HTTP : 200" in rendu
    assert "Nom : test.tld" in rendu


def test_mode_texte_desactive_les_sequences_ansi(monkeypatch):
    sortie = io.StringIO()
    console_texte = common_ui.ConsoleAdaptative(file=sortie, width=60, no_color=True)
    console_texte.print(Text("Texte simple"))
    assert "\x1b[" not in sortie.getvalue()
    assert "Texte simple" in sortie.getvalue()


# ---------------------------------------------------------------------------
# D. Compatibilité des outils dépendant de binaires
# ---------------------------------------------------------------------------

def test_scan_wifi_est_refuse_sur_termux_sans_root(monkeypatch):
    monkeypatch.setattr(compat, "systeme_reel", lambda: "termux")
    etat = compat.verifier_outil("Scan WiFi")
    assert etat["disponible"] is False
    assert "root" in etat["raison"].casefold()


def test_outil_externe_absent_est_refuse_avec_la_cause(monkeypatch):
    monkeypatch.setattr(compat.shutil, "which", lambda _nom: None)
    etat = compat.verifier_outil("Scan WiFi", systeme="linux")
    assert etat["disponible"] is False
    assert "nmcli" in etat["raison"]


def test_outil_indisponible_ne_simule_aucune_action(monkeypatch, capsys):
    appels = []
    monkeypatch.setattr(compat.shutil, "which", lambda _nom: None)
    monkeypatch.setattr(compat, "systeme_reel", lambda: "linux")
    action = compat.proteger_outil("Scan WiFi", lambda: appels.append("execute"))
    assert action() is None
    assert appels == []
    sortie = capsys.readouterr().out
    assert "indisponible" in sortie
    assert "Aucune action" in sortie


def test_rapport_de_compatibilite_couvre_les_outils_externes(monkeypatch):
    monkeypatch.setattr(compat, "systeme_reel", lambda: "linux")
    rapport = compat.rapport_compatibilite()
    noms = {ligne["outil"] for ligne in rapport}
    assert {"Scan WiFi", "Interfaces & routage", "Table ARP", "Traceroute"} <= noms
    assert all("disponible" in ligne for ligne in rapport)


def test_aucune_commande_windows_obligatoire_dans_les_modules_multiplateformes():
    sources = [
        Path("main.py"),
        Path("modules/pentest/interfaces_routes.py"),
        Path("modules/pentest/wifi_scanner.py"),
        Path("modules/pentest/traceroute_tool.py"),
    ]
    for source in sources:
        contenu = source.read_text(encoding="utf-8").casefold()
        assert "powershell" not in contenu
        assert "os.system" not in contenu
        assert "cmd /c" not in contenu


# ---------------------------------------------------------------------------
# E. Configuration locale et conservation des données
# ---------------------------------------------------------------------------

def test_configuration_par_defaut_contient_la_plateforme_sans_secret():
    assert set(DEFAUTS["plateforme"]) >= {"environnement", "mode_texte",
                                          "largeur_sortie", "pagination"}
    assert DEFAUTS["api_keys"] == {}


def test_configuration_sauvegardee_est_relue_sans_ecraser_les_donnees(tmp_path, monkeypatch):
    monkeypatch.setattr(config_module, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(config_module, "SETTINGS_FILE", str(tmp_path / "settings.json"))
    monkeypatch.setattr(config_module, "EXPORTS_DIR", str(tmp_path / "exports"))
    monkeypatch.setattr(config_module, "LOGS_DIR", str(tmp_path / "logs"))
    sentinelle = tmp_path / "cases.db"
    sentinelle.write_bytes(b"base-existante")

    config = config_module.charger()
    config["plateforme"]["environnement"] = "termux"
    config["plateforme"]["pagination"] = 12
    config_module.sauvegarder(config)

    relu = config_module.charger()
    assert relu["plateforme"]["environnement"] == "termux"
    assert relu["plateforme"]["pagination"] == 12
    assert sentinelle.read_bytes() == b"base-existante"
    assert "secret" not in (tmp_path / "settings.json").read_text(encoding="utf-8")


def test_restauration_des_defauts_preserve_les_fichiers_locaux(tmp_path, monkeypatch):
    monkeypatch.setattr(config_module, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(config_module, "SETTINGS_FILE", str(tmp_path / "settings.json"))
    monkeypatch.setattr(config_module, "EXPORTS_DIR", str(tmp_path / "exports"))
    monkeypatch.setattr(config_module, "LOGS_DIR", str(tmp_path / "logs"))
    dossier = tmp_path / "exports"
    dossier.mkdir(parents=True, exist_ok=True)
    export = dossier / "dossier-1.json"
    export.write_text("{}", encoding="utf-8")

    config_module.restaurer_defauts()
    assert export.read_text(encoding="utf-8") == "{}"
