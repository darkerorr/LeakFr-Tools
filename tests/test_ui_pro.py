"""Tests du design system "dashboard" : sobriete, alignement, adaptation."""
import io

from rich.console import Console
from rich.text import Text

import main
from core import ui
from core.branding import BANNER


def _texte(rendu, largeur=140, hauteur=42):
    console = Console(file=io.StringIO(), width=largeur, height=hauteur,
                      force_terminal=False, color_system=None)
    console.print(rendu)
    return console.file.getvalue()



def test_l_en_tete_tient_sur_deux_lignes_et_ne_deborde_pas():
    lignes= ui.en_tete(100, 'LEAKFR', "SUITE D'INVESTIGATION",
                        "v2.0 | 92 outils", "commit abc1234")
    assert len(lignes)==2
    assert all(ligne.cell_len ==100 for ligne in lignes)
    texte=lignes[0].plain
    assert "LEAKFR" in texte and "commit abc1234" in texte
    assert lignes[1].plain.startswith('\u2500')


def test_les_regles_et_panneaux_ont_une_largeur_exacte():
    ligne = ui.regle(64)
    assert ligne.cell_len ==64
    rendu =_texte(ui.panneau([Text('contenu')], 40, titre='CATALOGUE'),
                   largeur=60, hauteur=10)
    assert "CATALOGUE" in rendu and "contenu" in rendu
    assert max(len(ligne) for ligne in rendu.splitlines()) <= 40


def test_les_paires_libelle_valeur_restent_alignees():
    texte= ui.paire("Categorie", "OSINT", 40)
    assert texte.plain.startswith("Categorie ")
    assert texte.plain.rstrip().endswith('OSINT')


def test_tronquer_ne_depasse_jamais_la_largeur_demandee():
    assert ui.tronquer("a" * 100, 20).startswith("a")
    assert len(ui.tronquer("a" * 100, 20)) <=20
    assert ui.tronquer('court', 20) == 'court'



def test_le_menu_ne_contient_aucun_glyphe_neon(monkeypatch):
    console = Console(file=io.StringIO(), width=140, height=42,
                      force_terminal=False, color_system=None)
    monkeypatch.setattr(main, "console", console)
    sortie=_texte(main.construire_menu(main.NUM_IDX["1"], "", 0.0), 140, 42)
    for glyphe in '\u2501\u2503\u250f\u2513\u2517\u251b':
        assert glyphe not in sortie, glyphe
    assert "CATALOGUE" in sortie and "DETAILS" in sortie
    assert 'Recherche de pseudo' in sortie


def test_le_menu_tient_dans_un_petit_terminal(monkeypatch):
    console = Console(file=io.StringIO(), width=44, height=20,
                      force_terminal=False, color_system=None)
    monkeypatch.setattr(main, 'console', console)
    for selection in (0, len(main.FLAT) - 1):
        sortie =_texte(main.construire_menu(selection, "", 0.0), 44, 20)
        lignes = sortie.splitlines()
        assert len(lignes) <= 20
        assert max(len(ligne) for ligne in lignes)<=44
        assert 'PENTEST & RESEAU' in sortie


def test_le_menu_montre_le_contexte_reel_et_le_commit(monkeypatch):
    console = Console(file=io.StringIO(), width=140, height=42,
                      force_terminal=False, color_system=None)
    monkeypatch.setattr(main, 'console', console)
    sortie = _texte(main.construire_menu(main.NUM_IDX["1"], "", 0.0), 140, 42)
    assert "92 outils" in sortie
    assert 'commit' in sortie.lower()



def test_le_menu_numerote_est_sobre_et_borne_a_la_largeur(monkeypatch):
    from core import common as common_ui
    monkeypatch.setattr(common_ui, 'largeur_utile', lambda: 44)
    rendu = common_ui.render_menu("MENU", [f"Option {i}" for i in range(1, 15)])
    sortie = _texte(rendu, largeur=44, hauteur=20)
    lignes = [ligne for ligne in sortie.splitlines() if ligne.strip()]
    assert max(len(ligne) for ligne in lignes) <=44
    assert "Option 1" in sortie
    assert '[0] Retour' in sortie
