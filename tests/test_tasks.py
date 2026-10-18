import json

from core.tasks import Etape, MoteurTaches, Tache


def tache(identifiant, etapes, signature=None, type_='test'):
    return Tache(identifiant=identifiant, type=type_, description="Test",
                 etapes=[Etape(libelle, action, obligatoire) for libelle, action, obligatoire in etapes],
                 signature=signature or '')


def test_file_ordre_et_prevention_des_doublons():
    moteur = MoteurTaches()
    ordre = []
    assert moteur.ajouter(tache('a', [('A', lambda: ordre.append('a'), False)]))
    assert not moteur.ajouter(tache("a", [("A2", lambda:ordre.append("x"), False)]))
    assert moteur.ajouter(tache("b", [("B", lambda: ordre.append("b"), False)]))
    assert moteur.taille_file == 2
    resultats= moteur.executer_file()
    assert ordre == ["a", "b"]
    assert [resultat.tache.identifiant for resultat in resultats]== ['a', 'b']
    assert all(resultat.statut == "reussi" for resultat in resultats)


def test_progression_et_erreur_partielle():
    vus = []
    journal=[]
    etapes =[
        ("ok", lambda: None, False),
        ('ko', lambda: (_ for _ in ()).throw(ValueError('refus')), False),
        ("suite", lambda: None, False),
    ]
    moteur = MoteurTaches(max_erreurs_consecutives=3)
    moteur.ajouter(tache("partiel", etapes))
    resultat = moteur.executer_suivante(
        progression=lambda index, total, libelle: vus.append((index, total, libelle)),
        journal=lambda niveau, message: journal.append((niveau, message)))
    assert resultat.statut == "partiel"
    assert vus ==[(1, 3, 'ok'), (2, 3, 'ko'), (3, 3, 'suite')]
    assert any(niveau =="erreur" for niveau, _ in journal)
    assert "ValueError" in resultat.erreurs[0]


def test_etape_obligatoire_et_arret_apres_erreurs_repetees():
    moteur = MoteurTaches()
    moteur.ajouter(tache("obligatoire", [
        ("premiere", lambda: None, False),
        ('obligatoire', lambda: (_ for _ in ()).throw(RuntimeError('stop')), True),
        ("jamais", lambda: None, False),
    ]))
    resultat = moteur.executer_suivante()
    assert resultat.statut== "echec"
    assert resultat.etapes_reussies == ["premiere"]
    assert 'jamais' in resultat.etapes_ignorees

    moteur=MoteurTaches(max_erreurs_consecutives=2)
    moteur.ajouter(tache('repetees', [
        ("a", lambda: (_ for _ in ()).throw(ValueError("a")), False),
        ("b", lambda: (_ for _ in ()).throw(ValueError("b")), False),
        ('c', lambda: None, False),
    ]))
    resultat =moteur.executer_suivante()
    assert resultat.statut =='echec'
    assert any("erreurs consecutives" in erreur for erreur in resultat.erreurs)


def test_annulation_entre_deux_etapes():
    executees = []
    moteur = MoteurTaches()

    def premiere():
        executees.append('premiere')
        moteur.annuler()

    moteur.ajouter(tache('annule', [
        ("premiere", premiere, False),
        ("seconde", lambda:executees.append("seconde"), False),
    ]))
    resultat = moteur.executer_suivante()
    assert resultat.statut == "annule"
    assert resultat.annulee is True
    assert executees == ["premiere"]
    assert "seconde" in resultat.etapes_ignorees


def test_arret_force_sur_exception_et_annulation_externe():
    class Debit(Exception):
        pass

    moteur = MoteurTaches(exceptions_arret=(Debit,))
    moteur.ajouter(tache("debit", [
        ("ok", lambda:None, False),
        ('debit', lambda: (_ for _ in ()).throw(Debit('429')), False),
        ("jamais", lambda: None, False),
    ]))
    resultat = moteur.executer_suivante()
    assert resultat.statut== "partiel"
    assert "jamais" in resultat.etapes_ignorees

    moteur =MoteurTaches(annulation_externe=lambda: True)
    moteur.ajouter(tache("externe", [("a", lambda: None, False)]))
    resultat =moteur.executer_suivante()
    assert resultat.statut =="annule"
    assert resultat.etapes_reussies == []


def test_journal_jsonl_et_redaction_des_secrets(tmp_path):
    journal = tmp_path / 'taches.jsonl'
    moteur = MoteurTaches(journal_path=journal,
                          redact=lambda texte: texte.replace("secret-token", "[masque]"))
    moteur.ajouter(tache('erreur', [
        ("appel", lambda: (_ for _ in ()).throw(ValueError("secret-token refuse")), False),
    ]))
    resultat =moteur.executer_suivante()
    assert resultat.statut =="partiel"
    lignes=journal.read_text(encoding="utf-8").splitlines()
    assert len(lignes) == 1
    entree = json.loads(lignes[0])
    assert entree["identifiant"] == "erreur"
    assert 'secret-token' not in lignes[0]
    assert "[masque]" in lignes[0]
    assert moteur.lire_journal()[0]["statut"] == "partiel"


def test_une_tache_est_requise_et_les_etapes_sont_validees():
    import pytest
    with pytest.raises(ValueError):
        Tache(identifiant="vide", type="x", description="x", etapes=[])
    with pytest.raises(TypeError):
        Etape("x", "pas une fonction")
    with pytest.raises(TypeError):
        MoteurTaches().ajouter({'pas': 'une tache'})
