"""Tests de l'introduction animee, de la banniere ASCII et de sa duree."""
import sys

import main
from core.common import BANNER, BANNER_LARGEUR, BANNER_SOUS_TITRE, BANNER_TAGLINE


def _config(apparence=None):
    config = dict(main.DEFAUTS)
    config["apparence"] = dict(main.DEFAUTS["apparence"])
    config["apparence"].update(apparence or {})
    return config


def test_logo_ascii_aligne_et_assez_etroit_pour_un_terminal_standard():
    assert len({len(ligne) for ligne in BANNER}) == 1
    assert BANNER_LARGEUR == 48
    assert BANNER_LARGEUR <= 68
    assert BANNER_SOUS_TITRE and BANNER_TAGLINE


def test_duree_intro_par_defaut_longue_et_courte():
    assert main.duree_intro(_config()["apparence"]) == main.INTRO_DUREE_DEFAUT
    assert main.duree_intro({"introduction_longue": False}) == main.INTRO_DUREE_COURTE


def test_duree_intro_borne_les_valeurs_invalides():
    assert main.duree_intro({"duree_intro": 99}) == main.INTRO_DUREE_MAX
    assert main.duree_intro({"duree_intro": -5}) == 0.0
    assert main.duree_intro({"duree_intro": "abc"}) == main.INTRO_DUREE_DEFAUT
    assert main.duree_intro({"duree_intro": float("nan")}) == main.INTRO_DUREE_DEFAUT
    assert main.duree_intro({"duree_intro": "0,5"}) == main.INTRO_DUREE_DEFAUT
    assert main.duree_intro(None) == main.INTRO_DUREE_DEFAUT


def test_etapes_intro_reprend_les_vraies_valeurs_du_projet():
    etapes = dict(main.etapes_intro(_config()))
    outils = sum(len(outils) for _cat, _couleur, outils in main.CATALOGUE)
    assert etapes["Catalogue"] == f"{outils} outils / {len(main.CATALOGUE)} categories"
    assert etapes["Python"] == main.platform.python_version()
    assert etapes["Modules"] == "prets"


def test_intro_sautee_si_desactivee(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["main.py", "--no-intro"])
    main._intro_ascii(_config())
    assert capsys.readouterr().out == ""

    monkeypatch.setattr(sys, "argv", ["main.py"])
    main._intro_ascii(_config({"banniere_demarrage": False}))
    assert capsys.readouterr().out == ""


def test_intro_mode_texte_reste_lisible(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["main.py", "--text"])
    main._intro_ascii(_config())
    sortie = capsys.readouterr().out
    assert "LeakFr-Tools 2.0" in sortie
    assert BANNER_TAGLINE in sortie
    assert "█" not in sortie


def test_intro_affiche_le_logo_meme_sans_terminal_interactif(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["main.py"])
    main._intro_ascii(_config({"duree_intro": 0}))
    sortie = capsys.readouterr().out
    assert BANNER_SOUS_TITRE in sortie
    assert all(ligne.strip() in sortie for ligne in BANNER)
    assert "outils /" in sortie


def test_intro_sur_ecran_etroit_evite_les_lignes_trop_larges(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["main.py"])
    monkeypatch.setattr(main, "est_ecran_etroit", lambda: True)
    main._intro_ascii(_config({"duree_intro": 0}))
    sortie = capsys.readouterr().out
    assert "LeakFr-Tools 2.0" in sortie
    assert BANNER[0] not in sortie
    assert max(len(ligne.strip()) for ligne in sortie.splitlines()) <= 68
