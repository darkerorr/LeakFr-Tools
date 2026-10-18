"""Tests de l'introduction animee, de la banniere ASCII et de sa duree."""
import io
import sys

import pytest

import main
from core.common import BANNER, BANNER_LARGEUR, BANNER_SOUS_TITRE, BANNER_TAGLINE


def _config(apparence=None):
    config =dict(main.DEFAUTS)
    config["apparence"] = dict(main.DEFAUTS["apparence"])
    config["apparence"].update(apparence or {})
    return config


class FauxTerminal(io.StringIO):
    """Sortie interactive simulee (l'animation ne se lance qu'avec un TTY)."""

    def isatty(self):
        return True


def test_logo_ascii_aligne_et_assez_etroit_pour_un_terminal_standard():
    assert len({len(ligne) for ligne in BANNER}) == 1
    assert BANNER_LARGEUR == 35
    assert BANNER_LARGEUR <=68
    assert BANNER_SOUS_TITRE and BANNER_TAGLINE


def test_duree_intro_par_defaut_longue_et_courte():
    assert main.duree_intro(_config()['apparence']) == main.INTRO_DUREE_DEFAUT
    assert main.duree_intro({"introduction_longue": False}) ==main.INTRO_DUREE_COURTE


def test_duree_intro_borne_les_valeurs_invalides():
    assert main.duree_intro({"duree_intro":99}) == main.INTRO_DUREE_MAX
    assert main.duree_intro({'duree_intro': -5})== 0.0
    assert main.duree_intro({"duree_intro": "abc"}) == main.INTRO_DUREE_DEFAUT
    assert main.duree_intro({"duree_intro": float("nan")}) == main.INTRO_DUREE_DEFAUT
    assert main.duree_intro({'duree_intro': '0,5'})==main.INTRO_DUREE_DEFAUT
    assert main.duree_intro(None) == main.INTRO_DUREE_DEFAUT


def test_etapes_intro_reprend_les_vraies_valeurs_du_projet():
    etapes = dict(main.etapes_intro(_config()))
    outils =sum(len(outils) for _cat, _couleur, outils in main.CATALOGUE)
    assert etapes["Catalogue"] == f"{outils} outils / {len(main.CATALOGUE)} categories"
    assert etapes["Python"] ==main.platform.python_version()
    assert etapes['Environnement'] and etapes['Environnement'] !='inconnu'
    assert "modules importables" in etapes["Modules"]


def test_verifications_intro_portent_leur_resultat_reel():
    for verification in main.verifications_intro(_config()):
        assert set(verification) =={'nom', 'ok', 'detail'}
        assert isinstance(verification["ok"], bool)
        assert verification["nom"]
        assert verification['detail']
    assert all(verification["ok"] for verification in main.verifications_intro(_config()))


def test_verifications_intro_detectent_un_catalogue_casse(monkeypatch):
    monkeypatch.setattr(main, "_outils_du_catalogue", lambda: [None])
    catalogue = next(verification for verification in main.verifications_intro(_config())
                     if verification["nom"] == "Catalogue")
    assert catalogue["ok"] is False
    assert 'incomplet' in catalogue['detail']


def test_verifications_intro_detectent_un_module_indisponible(monkeypatch):
    def faux(_config=None):
        return ""

    faux.__module__ = "module.inexistant.totalement"
    monkeypatch.setattr(main, "_outils_du_catalogue", lambda: [faux])
    modules = next(verification for verification in main.verifications_intro(_config())
                   if verification["nom"] == "Modules")
    assert modules["ok"] is False
    assert 'indisponible' in modules['detail']


def test_animations_relues_apres_application_de_la_configuration():
    import core.common as common_ui
    try:
        common_ui.configurer_affichage(_config({'animations': False}))
        assert common_ui.ANIMATIONS is False
        assert main.animations_actives() is False
    finally:
        common_ui.configurer_affichage(main._CONFIG)
    assert main.animations_actives() is True


def test_intro_sautee_si_desactivee(monkeypatch, capsys):
    monkeypatch.setattr(sys, 'argv', ['main.py', '--no-intro'])
    main._intro_ascii(_config())
    assert capsys.readouterr().out == ""

    monkeypatch.setattr(sys, "argv", ["main.py"])
    main._intro_ascii(_config({"banniere_demarrage": False}))
    assert capsys.readouterr().out == ''


def test_intro_mode_texte_reste_lisible(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["main.py", "--text"])
    main._intro_ascii(_config())
    sortie =capsys.readouterr().out
    assert "LeakFr-Tools 2.0" in sortie
    assert BANNER_TAGLINE in sortie
    assert '█' not in sortie


def test_intro_no_color_reste_lisible(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["main.py", "--no-color"])
    main._intro_ascii(_config())
    sortie = capsys.readouterr().out
    assert "LeakFr-Tools 2.0" in sortie
    assert "█" not in sortie


def test_intro_phone_reduit_l_affichage(monkeypatch, capsys):
    monkeypatch.setattr(sys, 'argv', ['main.py', '--phone'])
    try:
        main._appliquer_configuration_visuelle()
        assert main.est_ecran_etroit() is True
        main._intro_ascii(_config({"duree_intro": 0}))
    finally:
        monkeypatch.setattr(sys, 'argv', ['main.py'])
        main._appliquer_configuration_visuelle()
    sortie= capsys.readouterr().out
    assert 'LeakFr-Tools 2.0' in sortie
    assert BANNER[0] not in sortie


def test_intro_affiche_le_logo_meme_sans_terminal_interactif(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["main.py"])
    main._intro_ascii(_config({'duree_intro': 0}))
    sortie = capsys.readouterr().out
    assert BANNER_SOUS_TITRE in sortie
    assert all(ligne.strip() in sortie for ligne in BANNER)
    assert "outils /" in sortie


def test_intro_sur_ecran_etroit_evite_les_lignes_trop_larges(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["main.py"])
    monkeypatch.setattr(main, 'est_ecran_etroit', lambda:True)
    main._intro_ascii(_config({"duree_intro": 0}))
    sortie = capsys.readouterr().out
    assert 'LeakFr-Tools 2.0' in sortie
    assert BANNER[0] not in sortie
    assert max(len(ligne.strip()) for ligne in sortie.splitlines()) <= 68


def test_duree_nulle_n_anime_pas_mais_affiche_la_banniere(monkeypatch):
    appels=[]
    monkeypatch.setattr(sys, "argv", ["main.py"])
    monkeypatch.setattr(main, "_animer_intro", lambda *_args: appels.append(1))
    monkeypatch.setattr(sys, 'stdout', FauxTerminal())
    main._intro_ascii(_config({"duree_intro":0}))
    assert appels == []
    assert BANNER_SOUS_TITRE in sys.stdout.getvalue()


def test_animation_lancee_seulement_sur_terminal_interactif(monkeypatch):
    appels= []
    monkeypatch.setattr(sys, "argv", ["main.py"])
    monkeypatch.setattr(main, '_animer_intro', lambda *_args: appels.append(1))

    monkeypatch.setattr(sys, "stdout", FauxTerminal())
    main._intro_ascii(_config({'duree_intro': 3}))

    class NonInteractif(io.StringIO):
        def isatty(self):
            return False

    monkeypatch.setattr(sys, 'stdout', NonInteractif())
    main._intro_ascii(_config({"duree_intro": 3}))
    assert appels == [1]


def test_interruption_pendant_l_animation_sort_proprement(monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['main.py'])
    monkeypatch.setattr(sys, "stdout", FauxTerminal())

    def interruption(_config, _duree):
        raise KeyboardInterrupt

    monkeypatch.setattr(main, '_animer_intro', interruption)
    with pytest.raises(main.QuitterApplication):
        main._intro_ascii(_config({"duree_intro": 3}))


def test_une_erreur_d_animation_n_empeche_pas_le_demarrage(monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['main.py'])
    monkeypatch.setattr(sys, "stdout", FauxTerminal())

    def explosion(_config, _duree):
        raise RuntimeError("rendu impossible")

    monkeypatch.setattr(main, '_animer_intro', explosion)
    main._intro_ascii(_config({"duree_intro": 3}))
    assert BANNER_SOUS_TITRE in sys.stdout.getvalue()
