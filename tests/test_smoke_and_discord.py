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
    assert total == 85
    assert sum(1 for item in main.FLAT if item["fn"]) == total
    assert len(main.ACTIONS) == total + 2
    assert len(main.CATALOGUE) == 8
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
    assert [tool["nom"] for tool in found] == ["Certificat SSL/TLS"]
    assert found[0]["chemin_navigation"] == "CYBER"
    assert main.rechercher_outils("TLS")
    assert main.rechercher_outils("subnet")[0]["nom"] == "Calculateur CIDR"
    assert main.rechercher_outils("  ") == []
    assert main.ACTIONS[found[0]["num"]] is found[0]["fn"]
    assert "Gestion des dossiers" in [tool["nom"] for tool in main.rechercher_outils("notes sources")]


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


def test_http_edge_corpus_is_local_deterministic_and_includes_boundaries(tmp_path, monkeypatch):
    module = importlib.import_module("modules.utils.http_edge_corpus")
    corpus = module.construire_corpus_http()
    ids = {case["id"] for case in corpus["cases"]}
    assert corpus["network_requests"] is False
    assert {"duplicate-conflicting", "crlf-in-value", "oversized-value-8k",
            "conflicting-framing", "unicode-value"} <= ids
    assert corpus == module.construire_corpus_http()
    destination = tmp_path / "fixtures" / "http.json"
    monkeypatch.setattr(module, "demander", lambda *_args, **_kwargs: str(destination))
    module.generer_corpus_http()
    generated = json.loads(destination.read_text(encoding="utf-8"))
    assert generated == corpus


def test_system_audit_is_local_deterministic_and_exposes_no_secrets(monkeypatch):
    module = importlib.import_module("modules.utils.system_audit")

    def connexion_interdite(*_args, **_kwargs):
        raise AssertionError("l'audit ne doit ouvrir aucune connexion")

    monkeypatch.setattr(socket.socket, "connect", connexion_interdite)
    monkeypatch.setattr(socket.socket, "connect_ex", connexion_interdite)
    infos = module.collecter_identite()
    assert infos["network_requests"] is False
    assert infos["hwid"] == module.calculer_hwid(infos["composants"])
    assert len(infos["hwid"].replace("-", "")) == 32
    assert infos["hwid"] == module.collecter_identite()["hwid"]
    assert infos["systeme"]["hote"]
    assert not hasattr(module, "requests")
    assert module.calculer_hwid({"machine-id": "abc"}) == module.calculer_hwid({"machine-id": "abc"})
    assert module.calculer_hwid({"machine-id": "abc"}) != module.calculer_hwid({"machine-id": "def"})


def _config_generateur(tmp_path, **surcharges):
    module = importlib.import_module("modules.generators.script_builder")
    config = module.config_par_defaut()
    config.update({
        "nom_script": str(tmp_path / "rapport.py"),
        "dossier_sortie": str(tmp_path / "out"),
        "sections": ["systeme", "disques"],
        "formats": ["json", "markdown", "html"],
        "mode_sortie": "fichier",
    })
    config.update(surcharges)
    return module, config


def test_script_generator_profiles_and_section_selection(tmp_path):
    module, config = _config_generateur(tmp_path)
    assert set(module.PROFILS) == {"minimal", "standard", "detaille"}
    assert set(module.PROFILS["minimal"]) < set(module.PROFILS["detaille"])
    assert "empreinte" not in module.PROFILS["detaille"]
    for profil, attendues in module.PROFILS.items():
        config["profil"] = profil
        config["sections"] = list(attendues)
        source = module.construire_script(config)
        for cle in attendues:
            nom = module.collectors.COLLECTEURS[cle][1].__name__
            assert f"def {nom}()" in source or f"def {nom}(" in source
        assert "collecter_empreinte_machine" not in source
    config["sections"] = ["systeme"]
    sans_reseau = module.construire_script(config)
    assert "collecter_reseau()" not in sans_reseau


def test_script_generator_exports_three_formats_without_network(tmp_path):
    module, config = _config_generateur(tmp_path)
    script = tmp_path / "rapport.py"
    source = module.construire_script(config)
    assert "webhook" not in source.lower()
    assert "urllib" not in source and "requests" not in source and "urlopen" not in source
    script.write_text(source, encoding="utf-8")

    run = subprocess.run([sys.executable, str(script)], capture_output=True, text=True, timeout=120)
    assert run.returncode == 0, run.stderr
    sortie = tmp_path / "out"
    produites = sorted(sortie.iterdir())
    assert [f.suffix for f in produites] == [".html", ".json", ".md"]

    rapport = json.loads(next(f for f in produites if f.suffix == ".json").read_text(encoding="utf-8"))
    assert rapport["schema"] == "leakfr.system-report.v1"
    assert set(rapport["sections"]) == {"systeme", "disques"}
    assert rapport["synthese"]["sections_total"] == 2
    assert rapport["genere_le"] and rapport["id"]

    markdown = next(f for f in produites if f.suffix == ".md").read_text(encoding="utf-8")
    assert "## Sommaire" in markdown and "## Synthese" in markdown
    assert "## Erreurs et limites" in markdown
    html = next(f for f in produites if f.suffix == ".html").read_text(encoding="utf-8")
    assert "<script" not in html.lower()
    assert "Synthese" in html and "Stockage et volumes" in html

    subprocess.run([sys.executable, str(script)], capture_output=True, text=True, timeout=120)
    assert len(list(sortie.iterdir())) == 6


def test_collectors_handle_limits_missing_data_and_errors(tmp_path):
    module = importlib.import_module("modules.generators.runtime.collectors")
    dossier = tmp_path / "fichiers"
    dossier.mkdir()
    for index in range(4):
        (dossier / f"f{index}.txt").write_text("abc", encoding="utf-8")
    limite = module.collecter_fichiers([str(dossier)], [".txt"], limite=2, empreinte=True)
    assert len(limite["donnees"]["fichiers"]) == 2
    assert limite["statut"] == "partiel"
    assert limite["donnees"]["fichiers"][0]["sha256"]

    absent = module.collecter_fichiers([str(tmp_path / "inconnu")], None, limite=5)
    assert absent["statut"] == "indisponible"

    (tmp_path / "casse.json").write_text("{invalide", encoding="utf-8")
    historique = module.collecter_historique(str(tmp_path), limite=5)
    assert historique["erreurs"]
    assert historique["statut"] in {"partiel", "indisponible"}

    assert module.collecter_disques()["donnees"]["volumes"]
    assert module.collecter_systeme()["donnees"]["python"]


def test_saisies_centralisees_appliquent_les_defauts(monkeypatch):
    module = importlib.import_module("modules.generators.script_builder")
    monkeypatch.setattr(module, "demander",
                        lambda label, defaut=None: defaut if defaut is not None else "")
    assert module._saisie("Nom", "rapport-machine.py") == "rapport-machine.py"
    assert module._liste("Liste", " ; ; ") == []
    assert module._liste("Liste", "a ; b") == ["a", "b"]
    assert module._entier("Limite", 5, 1, 10) == 5


def test_oui_non_et_entier_repromptent_les_reponses_invalides(monkeypatch):
    module = importlib.import_module("modules.generators.script_builder")
    reponses = iter(["peut-etre", "OUI", "non"])
    monkeypatch.setattr(module, "demander", lambda *_args, **_kwargs: next(reponses))
    assert module._oui_non("Continuer ?", False) is True
    assert module._oui_non("Continuer ?", True) is False

    reponses = iter(["abc", "0", "7"])
    monkeypatch.setattr(module, "demander", lambda *_args, **_kwargs: next(reponses))
    assert module._entier("Limite", 5, 1, 10) == 7


def test_noms_et_chemins_valides_y_compris_espaces(tmp_path):
    module = importlib.import_module("modules.generators.script_builder")
    for mauvais in ("", "a/b.py", "a:b.py", "x?.py", ".."):
        with pytest.raises(ValueError):
            module.valider_nom_script(mauvais)
    assert module.valider_nom_script("mon rapport") == "mon rapport.py"
    assert module.valider_nom_script("rapport") == "rapport.py"
    assert module.valider_dossier(str(tmp_path / "Mes rapports" / "2026")).is_dir()
    with pytest.raises(ValueError):
        module.valider_dossier("")


def test_tout_selectionne_les_standards_sans_les_options_sensibles(monkeypatch):
    module = importlib.import_module("modules.generators.script_builder")
    config = module.config_par_defaut()
    config["sections"] = ["session", "empreinte"]
    monkeypatch.setattr(module, "demander", lambda *_args, **_kwargs: "tout")
    module._editer_sections(config)
    assert set(config["sections"]) == set(module.STANDARD)
    assert not set(module.OPTIONNELLES) & set(config["sections"])

    config["sections"] = ["materiel"]
    monkeypatch.setattr(module, "demander", lambda *_args, **_kwargs: "1 3")
    module._editer_sections(config)
    assert config["sections"] == ["materiel", "systeme", "disques"]
    module._editer_sections(config)
    assert config["sections"] == ["materiel"]


def test_options_sensibles_desactivees_par_defaut():
    module = importlib.import_module("modules.generators.script_builder")
    config = module.config_par_defaut()
    assert set(config["sections"]) == set(module.STANDARD)
    for cle in ("session", "fichiers", "empreinte"):
        assert cle not in config["sections"]
    assert config["empreinte"] is False
    assert config["session_compte"] is False


def test_mode_rapide_evite_l_ecrasement_et_utilise_les_defauts(tmp_path, monkeypatch):
    module = importlib.import_module("modules.generators.script_builder")
    monkeypatch.chdir(tmp_path)
    (tmp_path / "rapports").mkdir()
    existant = tmp_path / "rapports" / "rapport-machine.py"
    existant.write_text("ancien", encoding="utf-8")

    reponses = iter(["rapport-machine.py", "rapports", "oui"])
    monkeypatch.setattr(module, "demander", lambda *_args, **_kwargs: next(reponses))
    resultat = module._mode_rapide(module.config_par_defaut())

    assert resultat["ok"] is True
    assert Path(resultat["chemin"]).name == "rapport-machine-1.py"
    assert existant.read_text(encoding="utf-8") == "ancien"


def test_generation_refuse_ecrasement_et_choisit_un_nom_libre(tmp_path, monkeypatch):
    module = importlib.import_module("modules.generators.script_builder")
    config = module.config_par_defaut()
    config.update({"nom_script": str(tmp_path / "test.py"),
                   "dossier_sortie": str(tmp_path / "out")})
    original = tmp_path / "test.py"
    original.write_text("# intact", encoding="utf-8")
    monkeypatch.setattr(module, "demander", lambda *_args, **_kwargs: "non")
    resultat = module._generer(config)
    assert resultat["ok"] is True
    assert Path(resultat["chemin"]).name == "test-1.py"
    assert original.read_text(encoding="utf-8") == "# intact"


def test_verification_detecte_fichier_vide_syntaxe_et_collecteurs(tmp_path):
    module = importlib.import_module("modules.generators.script_builder")
    config = module.config_par_defaut()
    config["sections"] = ["systeme", "disques"]

    vide = tmp_path / "vide.py"
    vide.write_text("", encoding="utf-8")
    assert module.verifier_generation(vide, config)["ok"] is False

    casse = tmp_path / "casse.py"
    casse.write_text("def x(:\n", encoding="utf-8")
    resultat = module.verifier_generation(casse, config)
    assert any("syntaxe" in erreur for erreur in resultat["erreurs"])

    bon = tmp_path / "bon.py"
    bon.write_text(module.construire_script(config), encoding="utf-8")
    assert module.verifier_generation(bon, config)["ok"] is True

    bon.write_text(bon.read_text(encoding="utf-8")
                   + "\ndef collecter_session(a=1, b=2):\n    pass\n", encoding="utf-8")
    resultat = module.verifier_generation(bon, config)
    assert any("desactive" in erreur for erreur in resultat["erreurs"])


def test_mode_avance_retour_et_annulation(tmp_path, monkeypatch):
    module = importlib.import_module("modules.generators.script_builder")
    config = module.config_par_defaut()
    config["sections"] = ["systeme"]
    reponses = iter(["1", "", "", "non"])
    monkeypatch.setattr(module, "demander", lambda *_args, **_kwargs: next(reponses))
    assert module._mode_avance(config) is None
    assert config["sections"] == ["systeme"]


def test_parcours_complet_mode_rapide_dans_un_terminal_simule(tmp_path, monkeypatch):
    module = importlib.import_module("modules.generators.script_builder")
    monkeypatch.chdir(tmp_path)
    reponses = iter(["e2e.py", "sorties", "oui"])
    monkeypatch.setattr(module, "demander", lambda *_args, **_kwargs: next(reponses))
    module.generer_script()

    script = tmp_path / "sorties" / "e2e.py"
    assert script.is_file() and script.stat().st_size > 0
    contenu = script.read_text(encoding="utf-8")
    compile(contenu, str(script), "exec")
    assert "collecter_session" not in contenu
    assert "collecter_empreinte_machine" not in contenu

    run = subprocess.run([sys.executable, str(script)], capture_output=True, text=True, timeout=120)
    assert run.returncode == 0, run.stderr
    assert list((tmp_path / "sorties").glob("*.json"))
    assert list((tmp_path / "sorties").glob("*.md"))


def _rapport_synthetique():
    return {
        "schema": "leakfr.system-report.v1",
        "id": "11111111-1111-1111-1111-111111111111",
        "nom": "Rapport test",
        "genere_le": "2026-10-17T12:00:00+02:00",
        "profil": "standard",
        "plateforme": "Linux",
        "synthese": {"sections_total": 3, "ok": 3, "partiel": 0, "indisponible": 0,
                     "erreur": 0, "statut": "ok", "duree_ms": 12.5},
        "sections": {
            "systeme": {"titre": "Systeme d'exploitation", "statut": "ok",
                        "donnees": {"hote": "lab"}, "erreurs": []},
            "empreinte": {"titre": "Empreinte machine (HWID)", "statut": "ok",
                          "donnees": {"hwid": "AAAA-BBBB"}, "erreurs": []},
            "session": {"titre": "Session et compte", "statut": "ok",
                        "donnees": {"utilisateur": "moi"}, "erreurs": []},
        },
    }


def test_transmission_liste_et_retire_les_sections_sensibles(tmp_path):
    module = importlib.import_module("modules.generators.transmission")
    chemin = tmp_path / "rapport.json"
    chemin.write_text(json.dumps(_rapport_synthetique()), encoding="utf-8")

    assert module.lister_rapports(tmp_path) == [chemin]
    rapport = module.charger_rapport(chemin)
    assert module.sections_sensibles_presentes(rapport) == ["empreinte", "session"]

    reduit = module.retirer_sections(rapport, ["empreinte", "session"])
    assert list(reduit["sections"]) == ["systeme"]
    assert reduit["synthese"]["sections_total"] == 1
    assert "empreinte" in reduit["synthese"]["sections_exclues"]
    assert "empreinte" in rapport["sections"]


def test_transmission_envoie_apres_confirmation_et_expurge(tmp_path, monkeypatch):
    module = importlib.import_module("modules.generators.transmission")
    chemin = tmp_path / "rapport.json"
    contenu_initial = json.dumps(_rapport_synthetique())
    chemin.write_text(contenu_initial, encoding="utf-8")
    recu = {}

    class Recepteur(BaseHTTPRequestHandler):
        def do_POST(self):
            longueur = int(self.headers.get("Content-Length", "0"))
            recu["corps"] = json.loads(self.rfile.read(longueur))
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"ok": true}')

        def log_message(self, *_args):
            pass

    serveur = ThreadingHTTPServer(("127.0.0.1", 0), Recepteur)
    threading.Thread(target=serveur.serve_forever, daemon=True).start()
    try:
        url = f"http://127.0.0.1:{serveur.server_port}/hook"
        reponses = iter(["1", "oui", url, "", "oui"])
        monkeypatch.setattr(module, "demander", lambda *_a, **_k: next(reponses))
        resultat = module.transmettre_rapport(tmp_path)
    finally:
        serveur.shutdown()
        serveur.server_close()

    assert resultat["ok"] is True and resultat["statut"] == 200
    assert set(recu["corps"]["sections"]) == {"systeme"}
    assert "hwid" not in json.dumps(recu["corps"])
    assert chemin.read_text(encoding="utf-8") == contenu_initial


def test_transmission_sans_confirmation_n_envoie_rien(tmp_path, monkeypatch):
    module = importlib.import_module("modules.generators.transmission")
    (tmp_path / "rapport.json").write_text(json.dumps(_rapport_synthetique()), encoding="utf-8")
    appels = []
    monkeypatch.setattr(module.webhook_lab, "envoyer_payload",
                        lambda *_a, **_k: appels.append(1))
    reponses = iter(["1", "oui", "http://127.0.0.1:9/hook", "", "non"])
    monkeypatch.setattr(module, "demander", lambda *_a, **_k: next(reponses))
    assert module.transmettre_rapport(tmp_path) is None
    assert appels == []


def test_transmission_valide_l_url_avant_envoi(monkeypatch):
    module = importlib.import_module("modules.generators.transmission")
    reponses = iter(["ftp://exemple.tld/hook", "https://exemple.tld/hook"])
    monkeypatch.setattr(module, "demander", lambda *_a, **_k: next(reponses))
    assert module._demander_url() == "https://exemple.tld/hook"


def test_mode_rapide_propose_la_transmission(tmp_path, monkeypatch):
    module = importlib.import_module("modules.generators.script_builder")
    monkeypatch.chdir(tmp_path)
    appels = []
    monkeypatch.setattr(module.transmission, "transmettre_rapport",
                        lambda dossier: appels.append(dossier))
    monkeypatch.setattr(module, "_generer", lambda config: {"ok": True, "chemin": "x"})
    reponses = iter(["r.py", "out", "transmettre"])
    monkeypatch.setattr(module, "demander", lambda *_a, **_k: next(reponses))
    resultat = module._mode_rapide(module.config_par_defaut())
    assert resultat["ok"] is True
    assert appels == ["out"]


def test_mode_avance_active_et_declenche_la_transmission(monkeypatch):
    module = importlib.import_module("modules.generators.script_builder")
    config = module.config_par_defaut()
    monkeypatch.setattr(module, "demander", lambda *_a, **_k: "oui")
    module._editer_transmission(config)
    assert config["transmission"] is True

    appels = []
    monkeypatch.setattr(module, "_generer_puis_transmettre",
                        lambda cfg: appels.append(cfg["nom_script"]) or {"ok": True})
    reponses = iter(["", "oui"])
    monkeypatch.setattr(module, "demander", lambda *_a, **_k: next(reponses))
    resultat = module._mode_avance(config)
    assert resultat["ok"] is True
    assert appels


def test_compilation_integrates_pyinstaller_and_checks_artifact(tmp_path, monkeypatch):
    module = importlib.import_module("modules.generators.build")
    script = tmp_path / "rapport.py"
    script.write_text("print('ok')", encoding="utf-8")

    monkeypatch.setattr(module, "executable_pyinstaller", lambda: None)
    absent = module.compiler(script)
    assert absent["ok"] is False and "pip install" in absent["erreur"]
    with pytest.raises(ValueError):
        module.valider_nom_executable("a/b")

    monkeypatch.setattr(module, "executable_pyinstaller", lambda: "pyinstaller")

    class Resultat:
        returncode = 0
        stdout = "Building EXE"
        stderr = ""

    def runner(arguments, **_kwargs):
        dist = Path(arguments[arguments.index("--distpath") + 1])
        dist.mkdir(parents=True, exist_ok=True)
        (dist / "rapport").write_text("binaire", encoding="utf-8")
        return Resultat()

    resultat = module.compiler(script, nom="rapport", dossier=str(tmp_path / "dist"), runner=runner)
    assert resultat["ok"] is True
    assert Path(resultat["chemin"]).is_file()
    assert "--onefile" in module.construire_arguments(script, "rapport", tmp_path / "dist")

    vide = module.compiler(script, nom="rapport", dossier=str(tmp_path / "vide"),
                           runner=lambda *_args, **_kwargs: Resultat())
    assert vide["ok"] is False
    assert "sans produire" in vide["erreur"]

    class Echec(Resultat):
        returncode = 2
        stderr = "boom"

    rate = module.compiler(script, nom="rapport", dossier=str(tmp_path / "echec"),
                           runner=lambda *_args, **_kwargs: Echec())
    assert rate["ok"] is False and rate["code"] == 2


def test_webhook_lab_posts_synthetic_payload_to_local_server():
    module = importlib.import_module("modules.cyber.webhook_lab")
    recu = {}

    class Recepteur(BaseHTTPRequestHandler):
        def do_POST(self):
            longueur = int(self.headers.get("Content-Length", "0"))
            recu["corps"] = json.loads(self.rfile.read(longueur))
            self.send_response(201)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok": true}')

        def log_message(self, *_args):
            pass

    serveur = ThreadingHTTPServer(("127.0.0.1", 0), Recepteur)
    thread = threading.Thread(target=serveur.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{serveur.server_port}/hook"
        resultat = module.envoyer_payload(url, module.payload_modele())
    finally:
        serveur.shutdown()
        serveur.server_close()

    assert resultat["ok"] is True
    assert resultat["statut"] == 201
    assert resultat["duree_ms"] >= 0
    assert resultat["erreur"] is None
    assert "ok" in resultat["corps"]
    assert recu["corps"]["event"] == "leakfr.webhook.test"
    assert set(recu["corps"]) == {"event", "message", "timestamp", "reference", "donnees"}


def test_webhook_lab_validates_input_and_reports_network_errors(monkeypatch):
    module = importlib.import_module("modules.cyber.webhook_lab")
    assert module.valider_url(" http://127.0.0.1:8000/hook ") == "http://127.0.0.1:8000/hook"
    for invalide in ("", "ftp://exemple.tld/hook", "http://", "http://exemple.tld/a b"):
        with pytest.raises(ValueError):
            module.valider_url(invalide)
    assert module.valider_timeout("2,5") == 2.5
    for invalide in ("zero", "0", "-1", "500"):
        with pytest.raises(ValueError):
            module.valider_timeout(invalide)

    payload = module.payload_modele()
    assert "hostname" not in json.dumps(payload).lower()
    assert "machine-id" not in json.dumps(payload)

    vide = socket.socket()
    vide.bind(("127.0.0.1", 0))
    port = vide.getsockname()[1]
    vide.close()
    refus = module.envoyer_payload(f"http://127.0.0.1:{port}/hook", payload, timeout=2)
    assert refus["ok"] is False
    assert refus["statut"] is None
    assert refus["erreur"]

    def delai_depasse(*_args, **_kwargs):
        raise module.requests.Timeout()

    monkeypatch.setattr(module.requests, "post", delai_depasse)
    expire = module.envoyer_payload("http://127.0.0.1:9/hook", payload, timeout=1)
    assert expire["ok"] is False
    assert "delai depasse" in expire["erreur"]


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


def test_panel_snowflake_and_channel_validation():
    assert bot_panel_module._valid_snowflake("123456789012345678")
    assert not bot_panel_module._valid_snowflake("1234")
    assert not bot_panel_module._valid_snowflake("../channels")
    assert bot_panel_module._slug_channel_name("  Audit Sécurité / 2026 ") == "audit-securite-2026"
    with pytest.raises(ValueError):
        bot_panel_module._slug_channel_name(" !!! ")


def test_permission_summary_calculates_role_union(monkeypatch):
    class Response:
        status_code = 200

        @staticmethod
        def json():
            return {"roles": ["222222222222222222"]}

    monkeypatch.setattr(bot_panel_module, "_request", lambda *args, **kwargs: Response())
    roles = [
        {"id": "111111111111111111", "permissions": "8"},
        {"id": "222222222222222222", "permissions": str(0x10 | 0x2000)},
    ]
    permissions, status = bot_panel_module._permission_summary(
        {}, "333333333333333333", "444444444444444444", roles
    )
    assert status == 200
    assert permissions == 0x10 | 0x2000


def test_guild_export_does_not_include_secrets_or_message_content(tmp_path, monkeypatch):
    monkeypatch.setattr(bot_panel_module, "EXPORTS_DIR", str(tmp_path))
    path = bot_panel_module._save_guild_audit(
        "123456789012345678",
        {
            "guild": {"id": "123", "name": "Lab", "owner_id": "456"},
            "channels": [{"id": "789", "name": "general", "token": "should-not-export"}],
            "roles": [{"id": "456", "name": "@everyone", "permissions": "0"}],
            "members": [{"content": "private message"}],
        },
    )
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["guild"]["name"] == "Lab"
    assert "token" not in path.read_text(encoding="utf-8")
    assert "private message" not in path.read_text(encoding="utf-8")
    assert data["members_loaded"] == 1


def test_websocket_frame_roundtrip_with_buffered_frames():
    client_socket, server_socket = socket.socketpair()
    try:
        client = DiscordGatewayClient("test-token")
        client.sock = client_socket
        server_socket.sendall(b"\x81\x02hi\x81\x02ok")
        opcode, payload, rest = client._recv_frame()
        assert (opcode, payload) == (1, b"hi")
        opcode, payload, rest = client._recv_frame(rest)
        assert (opcode, payload) == (1, b"ok")
    finally:
        client_socket.close()
        server_socket.close()


def test_websocket_control_frame_masks_ping_payload():
    class FakeSocket:
        sent = b""

        def sendall(self, frame):
            self.sent = bytes(frame)

    client = DiscordGatewayClient("test-token")
    fake = FakeSocket()
    client.sock = fake
    client._send_control_frame(0xA, b"ping")
    frame = fake.sent
    assert frame[0] == 0x8A
    assert frame[1] & 0x80
    mask = frame[2:6]
    assert bytes(byte ^ mask[i % 4] for i, byte in enumerate(frame[6:])) == b"ping"


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


def test_arrow_selector_moves_and_confirms_without_numeric_input(monkeypatch):
    import core.common as common_ui
    import os
    import select
    import termios
    import tty

    class FakeTTY:
        def isatty(self):
            return True
        def fileno(self):
            return 73

    class FakeLive:
        def __init__(self, **_kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *_args):
            return False
        def update(self, *_args, **_kwargs):
            pass

    keyboard = iter([b"\x1b", b"[B", b"\r"])
    monkeypatch.setattr(common_ui, "INTERACTIF", True)
    monkeypatch.setattr(common_ui.sys, "stdin", FakeTTY())
    monkeypatch.setattr(common_ui.sys, "stdout", FakeTTY())
    monkeypatch.setattr(common_ui, "Live", FakeLive)
    monkeypatch.setattr(select, "select", lambda *_args, **_kwargs: ([73], [], []))
    monkeypatch.setattr(os, "read", lambda _fd, _size: next(keyboard))
    monkeypatch.setattr(termios, "tcgetattr", lambda _fd: [])
    monkeypatch.setattr(termios, "tcsetattr", lambda *_args: None)
    monkeypatch.setattr(tty, "setcbreak", lambda _fd: None)

    assert common_ui.choisir_option("Test", ["Premier", "Second"]) == "Second"


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


def test_encode_decode_tool_executes_selected_mode(monkeypatch):
    module = importlib.import_module("modules.utils.encode_decode")
    output = {}
    monkeypatch.setattr(module, "choisir_option", lambda *_args, **_kwargs: "Base64 encode")
    monkeypatch.setattr(module, "demander", lambda _label: "hello")
    monkeypatch.setattr(module, "kv", lambda _title, rows, _color: output.update(rows))
    module.encode_decode()
    assert output["Sortie"] == "aGVsbG8="


def test_date_calculator_executes_selected_mode_with_local_input(monkeypatch):
    module = importlib.import_module("modules.utils.date_calculator")
    output = {}
    answers = iter(["2026-01-01", "2026-01-12"])
    monkeypatch.setattr(module, "choisir_option", lambda _title, options: options[0])
    monkeypatch.setattr(module, "demander", lambda *_args, **_kwargs: next(answers))
    monkeypatch.setattr(module, "kv", lambda title, rows, _color: output.update({"title": title, **dict(rows)}))
    module.calculer_dates()
    assert output["Jours signes"] == 11
    assert output["Semaines completes"] == 1


def test_wordlist_generator_runs_and_writes_requested_file(monkeypatch, tmp_path):
    module = importlib.import_module("modules.pentest.wordlist_generator")
    destination = tmp_path / "wordlist.txt"
    answers = iter(["test", str(destination)])
    monkeypatch.setattr(module, "choisir_option", lambda *_args, **_kwargs: "Mutations d'un mot")
    monkeypatch.setattr(module, "demander", lambda *_args, **_kwargs: next(answers))
    module.wordlist_gen()
    generated = destination.read_text(encoding="utf-8").splitlines()
    assert "test" in generated
    assert "test123" in generated
    assert len(generated) > 10


def test_concurrent_modules_import_the_executor_explicitly():
    import ast
    import importlib

    for path in Path("modules").rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        if "concurrent.futures" not in source:
            continue
        tree = ast.parse(source)
        imports_concurrent = any(
            isinstance(node, ast.Import) and any(
                alias.name == "concurrent.futures" or alias.name == "concurrent"
                for alias in node.names
            )
            for node in ast.walk(tree)
        )
        assert imports_concurrent, f"{path} uses concurrent.futures without import"
        importlib.import_module(".".join(path.with_suffix("").parts))


def test_pseudo_search_runs_concurrently_with_mocked_responses(monkeypatch):
    from contextlib import contextmanager
    from types import SimpleNamespace
    from modules.osint import pseudo_search as search_module

    class Progress:
        def add_task(self, *args, **kwargs):
            return 1
        def advance(self, *args, **kwargs):
            pass

    @contextmanager
    def fake_barre():
        yield Progress()

    monkeypatch.setattr(search_module, "demander", lambda *_args, **_kwargs: "example_test")
    monkeypatch.setattr(search_module, "barre", fake_barre)
    monkeypatch.setattr(search_module.requests, "get", lambda *args, **kwargs: SimpleNamespace(status_code=404))
    search_module.recherche_pseudo()


def test_dns_bruteforce_runs_concurrently_with_mocked_resolver(monkeypatch, tmp_path):
    from contextlib import contextmanager
    import importlib
    dns_module = importlib.import_module("modules.pentest.dns_bruteforce")

    wordlist = tmp_path / "hosts.txt"
    wordlist.write_text("www\nmail\n", encoding="utf-8")

    class Progress:
        def add_task(self, *args, **kwargs):
            return 1
        def advance(self, *args, **kwargs):
            pass

    @contextmanager
    def fake_barre():
        yield Progress()

    monkeypatch.setattr(dns_module, "warn_pentest", lambda: True)
    answers = iter(["example.test", str(wordlist)])
    monkeypatch.setattr(dns_module, "demander", lambda *_args, **_kwargs: next(answers))
    monkeypatch.setattr(dns_module, "barre", fake_barre)
    def fake_resolve(host):
        if host.startswith("www."):
            return host, [], ["192.0.2.10"]
        raise OSError("not found")
    monkeypatch.setattr(dns_module.socket, "gethostbyname_ex", fake_resolve)
    dns_module.dns_bruteforce()


def test_directory_bruteforce_runs_concurrently_with_mocked_http(monkeypatch, tmp_path):
    from contextlib import contextmanager
    import importlib
    from types import SimpleNamespace
    dir_module = importlib.import_module("modules.pentest.dir_bruteforce")

    wordlist = tmp_path / "paths.txt"
    wordlist.write_text("admin\nrobots.txt\n", encoding="utf-8")

    class Progress:
        def add_task(self, *args, **kwargs):
            return 1
        def advance(self, *args, **kwargs):
            pass

    @contextmanager
    def fake_barre():
        yield Progress()

    monkeypatch.setattr(dir_module, "warn_pentest", lambda: True)
    answers = iter(["http://example.test", str(wordlist), "200"])
    monkeypatch.setattr(dir_module, "demander", lambda *_args, **_kwargs: next(answers))
    monkeypatch.setattr(dir_module, "barre", fake_barre)
    def fake_get(url, **_kwargs):
        status = 200 if url.endswith("/admin") else 404
        return SimpleNamespace(status_code=status, content=b"ok", headers={"Content-Type": "text/plain"})
    monkeypatch.setattr(dir_module.requests, "get", fake_get)
    dir_module.dir_bruteforce()


def test_screenshots_cover_every_module_and_readme_link():
    screenshots = Path("docs/screenshots")
    assert (screenshots / "menu-principal.svg").is_file()
    module_images = list((screenshots / "modules").rglob("*.svg"))
    assert len(module_images) == sum(len(options) for _, _, options in main.CATALOGUE)
    for readme in Path("modules").glob("*/README.md"):
        for link in re.findall(r"\]\(([^)]+\.svg)\)", readme.read_text(encoding="utf-8")):
            assert (readme.parent / link).resolve().is_file(), (readme, link)
