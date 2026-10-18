"""Tests de la refonte du demarrage : identite, controles reels et menus."""
import io
import subprocess
import threading
import time

import pytest
from rich.console import Console

import main
from core import branding, startup_checks
from core.startup import (
    entete_chargement, faits_controles, faits_machine, glyphe_statut, jauge,
    rendu_final, rendu_initialisation, executer_sequence,
)
from core.vcs import info_commit, ligne_commit
from core.startup_checks import (
    ARGUMENTS_VERSION, Controle, Orchestrateur, Verification,
    collecter_outils_externes, controles_par_defaut, resume_verifications,
    sonder_binaire, verifier_donnees,
)


def _console(largeur=100, hauteur=30):
    flux = io.StringIO()
    return Console(file=flux, width=largeur, height=hauteur,
                   force_terminal=False, record=True), flux


def _texte_rendu(rendu, largeur=100, hauteur=30):
    console, flux = _console(largeur, hauteur)
    console.print(rendu)
    return flux.getvalue()


def _controle(nom, fonction=lambda: Verification("X", "Test", "OK", "fini")):
    return Controle(nom, "Test", fonction)


def _ok(nom="Outil"):
    return Verification(nom, "Test", "OK", "mesure reelle")


# ---------------------------------------------------------------------------
# Identite visuelle
# ---------------------------------------------------------------------------

def test_le_logo_se_revele_progressivement_puis_est_complet():
    debut = _texte_rendu(branding.logo_revele(0.0))
    fin = _texte_rendu(branding.logo_revele(1.0))
    assert branding.STRUCTURE in debut
    assert "█" not in debut
    assert all(ligne.strip() in fin for ligne in branding.BANNER)
    assert "█╗" in fin


def test_l_en_tete_complet_garde_le_logo_et_le_sous_titre():
    sortie = _texte_rendu(branding.en_tete(largeur=100, info="v2.0 | 92 outils"))
    assert all(ligne.strip() in sortie for ligne in branding.BANNER)
    assert branding.BANNER_SOUS_TITRE in sortie
    assert branding.BANNER_TAGLINE in sortie
    assert "92 outils" in sortie


def test_l_en_tete_compact_respecte_une_largeur_etroite():
    sortie = _texte_rendu(
        branding.en_tete(largeur=40, info="v2.0 | 92 outils | Linux 7.0.0",
                         compact=True, unicode=False), largeur=40, hauteur=20)
    assert "LEAKFR" in sortie
    assert branding.BANNER[0] not in sortie
    assert max(len(ligne.rstrip()) for ligne in sortie.splitlines()) <= 40


def test_rendu_sans_unicode_utilise_des_glyphes_ascii():
    sortie = _texte_rendu(rendu_final([_ok()], {}, compact=True, unicode=False),
                          largeur=60, hauteur=24)
    assert "OK" in sortie
    assert "✔" not in sortie


def test_rendu_sans_unicode_n_utilise_aucun_caractere_de_dessin():
    orch = Orchestrateur([_controle("A")])
    orch.executer()
    sorties = [
        _texte_rendu(rendu_initialisation(orch, 0.5, None, 100, 30,
                                          _console(100, 30)[0], unicode=False)),
        _texte_rendu(rendu_final([_ok()], {}, compact=False, unicode=False)),
    ]
    for sortie in sorties:
        for glyphe in "█░▒▓▰▱✔✘─│┌┐└┘╭╮╰╯":
            assert glyphe not in sortie, glyphe


def test_jauge_reflete_le_ratio_reel_des_controles():
    assert " 50%" in _texte_rendu(jauge(0.5, 20))
    assert "100%" in _texte_rendu(jauge(1.0, 20))
    assert "  0%" in _texte_rendu(jauge(0.0, 20))


def test_l_ecran_de_chargement_ne_depasse_jamais_la_largeur():
    orch = Orchestrateur([_controle("A")])
    orch.executer()
    for largeur, hauteur in ((44, 16), (60, 20), (80, 24), (120, 42)):
        rendu = rendu_initialisation(orch, 0.5, None, largeur, hauteur,
                                     _console(largeur, hauteur)[0])
        sortie = _texte_rendu(rendu, largeur=largeur, hauteur=hauteur)
        assert max(len(ligne.rstrip()) for ligne in sortie.splitlines()) <= largeur


def test_l_ecran_de_chargement_affiche_les_controles_reels_et_la_progression():
    orch = Orchestrateur([_controle(
        "Python", lambda: Verification("Python", "Environnement", "OK", "3.14.4"))])
    orch.executer()
    sortie = _texte_rendu(rendu_initialisation(orch, 0.4, None, 100, 30,
                                               _console(100, 30)[0]), 100, 30)
    assert "VERIFICATIONS REELLES" in sortie
    assert "PROGRESSION REELLE" in sortie
    assert "3.14.4" in sortie
    assert "100%" in sortie
    assert "1/1" in sortie


def test_l_en_tete_de_chargement_montre_le_logo_ou_un_titre_court():
    large = _texte_rendu(entete_chargement(largeur=100), 100, 30)
    assert all(ligne.strip() in large for ligne in branding.BANNER)
    etroit = _texte_rendu(entete_chargement(largeur=48), 48, 20)
    assert "LEAKFR // TOOLS 2.0" in etroit
    assert branding.BANNER[0] not in etroit


def test_les_faits_de_chargement_sont_mesures_et_non_inventes():
    console, _flux = _console(100, 30)
    faits = faits_machine(console, 100)
    assert any(str(console.width) in fait for fait in faits)
    assert any("python" in fait.lower() for fait in faits)
    orch = Orchestrateur([_controle("Python", lambda: _ok("3.14.4"))])
    orch.executer()
    lignes = faits_controles(orch)
    assert any("catalogue reel" in ligne for ligne in lignes)
    assert any("controles reels" in ligne for ligne in lignes)


def test_le_menu_affiche_le_commit_reel_du_depot():
    info = info_commit()
    ligne = ligne_commit(info)
    assert info["court"] in ligne
    if info["disponible"]:
        assert len(info["court"]) >= 7
        assert info["complet"].startswith(info["court"]) or info["court"] in info["complet"]
    sortie = _texte_rendu(main.construire_menu(main.NUM_IDX["1"], "", 0.0), 120, 42)
    assert "commit" in sortie.lower()


# ---------------------------------------------------------------------------
# Sondes externes : honnetes, bornees, sans shell
# ---------------------------------------------------------------------------

def test_binaire_absent_est_signale_absent(monkeypatch):
    monkeypatch.setattr(startup_checks.shutil, "which", lambda _nom: None)
    resultat = sonder_binaire("traceroute", ["--version"])
    assert resultat["present"] is False
    assert resultat["statut"] == "MISSING"
    assert "UNKNOWN" not in resultat["detail"]


def test_timeout_de_sonde_signale_une_version_inconnue(monkeypatch):
    monkeypatch.setattr(startup_checks.shutil, "which", lambda _nom: "/usr/bin/traceroute")

    def depasse(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(cmd="traceroute", timeout=0.01)

    monkeypatch.setattr(startup_checks.subprocess, "run", depasse)
    resultat = sonder_binaire("traceroute", ["--version"], timeout=0.01)
    assert resultat["present"] is True
    assert resultat["version"] is None
    assert "délai" in resultat["detail"]


def test_sonde_utilise_une_liste_sans_shell_et_un_delai(monkeypatch):
    appels = {}

    class FauxProcessus:
        returncode = 0
        stdout = "traceroute 2.1.0\n"
        stderr = ""

    def faux_run(arguments, **kwargs):
        appels["arguments"] = arguments
        appels["kwargs"] = kwargs
        return FauxProcessus()

    monkeypatch.setattr(startup_checks.shutil, "which", lambda _nom: "/usr/bin/traceroute")
    monkeypatch.setattr(startup_checks.subprocess, "run", faux_run)
    resultat = sonder_binaire("traceroute", ["--version"], timeout=1.2)
    assert appels["arguments"] == ["/usr/bin/traceroute", "--version"]
    assert appels["kwargs"]["shell"] is False
    assert appels["kwargs"]["timeout"] == 1.2
    assert appels["kwargs"]["capture_output"] is True
    assert resultat["version"] == "2.1.0"


def test_les_arguments_de_version_sont_des_options_de_lecture():
    for arguments in ARGUMENTS_VERSION.values():
        if arguments is None:
            continue
        assert arguments and all(option.startswith("-") for option in arguments)


def test_tous_les_outils_absents_sont_listes_honnetement(monkeypatch):
    monkeypatch.setattr(startup_checks.shutil, "which", lambda _nom: None)
    resultat = collecter_outils_externes(systeme="linux")
    assert resultat.statut == "WARN"
    assert resultat.ok is False
    assert "0/" in resultat.detail and "absents" in resultat.detail


def test_versions_inconnues_ne_sont_pas_presentees_comme_ok(monkeypatch):
    monkeypatch.setattr(startup_checks.shutil, "which", lambda nom: f"/usr/bin/{nom}")
    monkeypatch.setattr(
        startup_checks, "sonder_binaire",
        lambda nom, _args=None, timeout=1.2: {
            "present": True, "version": None, "statut": "UNKNOWN",
            "detail": "FOUND — VERSION UNKNOWN"})
    resultat = collecter_outils_externes(systeme="linux")
    assert resultat.statut == "UNKNOWN"
    assert "versions inconnues" in resultat.detail


def test_outils_presents_et_absents_sont_tous_listes(monkeypatch):
    presents = {"arp", "ip", "nmcli"}
    monkeypatch.setattr(
        startup_checks.shutil, "which",
        lambda nom: f"/usr/bin/{nom}" if nom in presents else None)
    monkeypatch.setattr(
        startup_checks, "sonder_binaire",
        lambda nom, _args=None, timeout=1.2: {
            "present": True, "version": f"{nom}-9.9", "statut": "OK",
            "detail": "ok"})
    resultat = collecter_outils_externes(systeme="linux")
    assert resultat.statut == "OK"
    assert "absents" in resultat.detail
    assert "traceroute" in resultat.detail and "iwlist" in resultat.detail
    assert "ip ip-9.9" in resultat.detail


# ---------------------------------------------------------------------------
# Controles du projet
# ---------------------------------------------------------------------------

def test_les_controles_couvrent_environnement_framework_et_compatibilite():
    noms = [controle.nom for controle in controles_par_defaut({})]
    assert noms == ["Python", "Système", "Terminal", "Dépendances", "Catalogue",
                    "Modules", "Thème", "Données", "Outils externes"]
    assert noms[0] == "Python" and noms[-1] == "Outils externes"


def test_le_test_d_ecriture_ne_laisse_aucun_fichier(tmp_path):
    avant = set(tmp_path.iterdir())
    verification = verifier_donnees(tmp_path)
    assert verification.statut == "OK"
    assert set(tmp_path.iterdir()) == avant
    assert not list(tmp_path.glob(".leakfr_demarrage_*"))


def test_un_repertoire_non_inscriptible_donne_un_avertissement(monkeypatch, tmp_path):
    def refuse(*_args, **_kwargs):
        raise OSError("lecture seule")

    monkeypatch.setattr(startup_checks.tempfile, "mkstemp", refuse)
    verification = verifier_donnees(tmp_path)
    assert verification.statut == "WARN"
    assert verification.ok is False


def test_une_erreur_interne_n_est_jamais_un_succes():
    def explosion():
        raise RuntimeError("boum")

    etats = Orchestrateur([Controle("Boom", "Test", explosion, True)]).executer()
    assert etats[0].statut == "ERROR"
    assert etats[0].ok is False
    assert "échec interne" in etats[0].detail


def test_le_bilan_distingue_pret_partiel_et_critique():
    assert resume_verifications([_ok()])["niveau"] == "PRET"
    avertissement = Verification("X", "Test", "WARN", "dégradé")
    assert resume_verifications([_ok(), avertissement])["niveau"] == "PARTIEL"
    interrompu = Verification("X", "Test", "SKIPPED", "délai dépassé")
    bilan = resume_verifications([_ok(), interrompu])
    assert bilan["niveau"] == "PARTIEL"
    assert bilan["interrompus"] == 1
    erreur = Verification("X", "Test", "ERROR", "cassé", True)
    bilan = resume_verifications([_ok(), erreur])
    assert bilan["niveau"] == "CRITIQUE"
    assert bilan["label"] == "ERREUR CRITIQUE"


# ---------------------------------------------------------------------------
# Orchestrateur : progression reelle, interruption, thread
# ---------------------------------------------------------------------------

def test_la_progression_n_avance_qu_apres_la_fin_reelle_d_un_controle():
    liberer = threading.Event()

    def bloque():
        liberer.wait(2.0)
        return Verification("A", "Test", "OK", "terminé")

    orchestrateur = Orchestrateur([
        Controle("A", "Test", bloque),
        Controle("B", "Test", lambda: _ok("B")),
    ]).lancer()
    try:
        time.sleep(0.05)
        etats = orchestrateur.etats()
        assert etats[0].statut == "RUNNING"
        assert etats[1].statut == "PENDING"
        assert orchestrateur.termines == 0
        assert orchestrateur.progression == 0
        assert orchestrateur.en_cours == "A"
        liberer.set()
        assert orchestrateur.attendre(2.0) is True
        assert orchestrateur.progression == 1.0
        assert [etat.statut for etat in orchestrateur.etats()] == ["OK", "OK"]
    finally:
        liberer.set()


def test_une_interruption_marque_les_controles_restants_comme_non_executes():
    liberer = threading.Event()

    def bloque():
        liberer.wait(2.0)
        return Verification("A", "Test", "OK", "trop tard")

    orchestrateur = Orchestrateur([
        Controle("A", "Test", bloque),
        Controle("B", "Test", lambda: _ok("B")),
    ]).lancer()
    try:
        time.sleep(0.05)
        orchestrateur.interrompre("délai de test")
        assert orchestrateur.termine is True
        etats = orchestrateur.etats()
        assert etats[0].statut == "SKIPPED"
        assert etats[1].statut == "SKIPPED"
        assert all("délai de test" in etat.detail for etat in etats)
        # Une verification sautee ne compte pas comme terminee.
        assert orchestrateur.termines == 0
        assert orchestrateur.progression == 0
    finally:
        liberer.set()


# ---------------------------------------------------------------------------
# Bilan et menus
# ---------------------------------------------------------------------------

def test_le_bilan_final_montre_les_echecs_reels():
    erreur = Verification("Catalogue", "Framework", "ERROR", "catalogue incomplet", True)
    sortie = _texte_rendu(rendu_final([erreur], {}, compact=False))
    assert "ERREUR CRITIQUE" in sortie
    assert "catalogue incomplet" in sortie
    assert "✘" in sortie

    avertissement = Verification("Données", "Stockage", "WARN", "lecture seule")
    sortie = _texte_rendu(rendu_final([avertissement], {}, compact=True))
    assert "PARTIELLEMENT PRÊT" in sortie
    assert "lecture seule" in sortie


def test_la_sequence_complete_affiche_le_bilan_et_le_logo(monkeypatch):
    monkeypatch.setattr(
        "core.startup.controles_par_defaut",
        lambda _config=None: [
            Controle("Python", "Environnement", lambda: _ok("Python"), True),
            Controle("Test", "Test", lambda: Verification("Test", "Test", "WARN", "partiel")),
        ])
    console, flux = _console(100, 30)
    assert executer_sequence({}, 0.1, console) is True
    sortie = flux.getvalue()
    assert "BILAN DE DEMARRAGE" in sortie
    assert "PARTIELLEMENT PRÊT" in sortie
    assert all(ligne.strip() in sortie for ligne in branding.BANNER)


def test_la_sequence_minuscule_affiche_les_resultats_sans_scene(monkeypatch):
    monkeypatch.setattr(
        "core.startup.controles_par_defaut",
        lambda _config=None: [Controle("A", "Test", lambda: _ok("A"))])
    console, flux = _console(40, 16)
    assert executer_sequence({}, 0.2, console) is True
    sortie = flux.getvalue()
    assert "LEAKFR // TOOLS 2.0" in sortie
    assert "A" in sortie and "mesure reelle" in sortie
    assert "OK" in sortie or "✔" in sortie


def test_le_menu_numerique_affiche_le_logo(monkeypatch):
    console, flux = _console(100, 40)
    monkeypatch.setattr(main, "console", console)
    monkeypatch.setattr(main, "MODE_TEXTE", False)
    monkeypatch.setattr(main, "UNICODE", True)
    monkeypatch.setattr(main, "est_ecran_etroit", lambda: False)
    monkeypatch.setattr(main, "selectionner_option", lambda *_a, **_k: "Quitter")
    assert main.menu_simple() == "0"
    sortie = flux.getvalue()
    assert all(ligne.strip() in sortie for ligne in branding.BANNER)
    assert branding.BANNER_SOUS_TITRE in sortie


def test_le_menu_numerique_reste_compact_sur_ecran_etroit(monkeypatch):
    console, flux = _console(44, 20)
    monkeypatch.setattr(main, "console", console)
    monkeypatch.setattr(main, "est_ecran_etroit", lambda: True)
    monkeypatch.setattr(main, "selectionner_option", lambda *_a, **_k: "Quitter")
    assert main.menu_simple() == "0"
    sortie = flux.getvalue()
    assert "LEAKFR // TOOLS 2.0" in sortie
    assert branding.BANNER[0] not in sortie
    assert max(len(ligne.rstrip()) for ligne in sortie.splitlines()) <= 44


def test_le_menu_interactif_garde_le_logo_complet(monkeypatch):
    monkeypatch.setattr(main, "console", _console(100, 40)[0])
    monkeypatch.setattr(main, "UNICODE", True)
    rendu = main.construire_menu(main.NUM_IDX["1"], "", 0.0)
    sortie = _texte_rendu(rendu, largeur=100, hauteur=40)
    assert all(ligne.strip() in sortie for ligne in branding.BANNER)
    assert branding.BANNER_SOUS_TITRE in sortie
    assert "SUITE DE SECURITE & RECON" in sortie
