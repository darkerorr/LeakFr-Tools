import json

import pytest

import core.cases as cases
import core.correlate as correlate


@pytest.fixture
def entrepot(tmp_path, monkeypatch):
    monkeypatch.setattr(cases, "CASES_DB", str(tmp_path / "cases.db"))
    monkeypatch.setattr(cases, "HISTORY_FILE", str(tmp_path / "history.json"))
    monkeypatch.setattr(cases, "DATA_DIR", str(tmp_path))
    return cases


def test_registre_de_preuves_detecte_une_modification(tmp_path, entrepot):
    dossier = entrepot.creer_case("Enquete test", "laboratoire")
    preuve = tmp_path / "preuve.txt"
    preuve.write_text("contenu original", encoding="utf-8")

    preuve_id = entrepot.ajouter_preuve(dossier, preuve, source="collecte locale", note="test")
    entrees = entrepot.lister_preuves(dossier)
    assert len(entrees) == 1
    assert entrees[0]["sha256"] and entrees[0]["size"] == len("contenu original")

    etat = entrepot.verifier_preuve(preuve_id)
    assert etat["intact"] is True

    preuve.write_text("contenu modifie", encoding="utf-8")
    etat = entrepot.verifier_preuve(preuve_id)
    assert etat["intact"] is False
    assert "change" in etat["motif"]

    controles = entrepot.lister_verifications(preuve_id)
    assert len(controles) == 2
    assert controles[0]["intact"] == 0
    assert controles[1]["intact"] == 1

    autre = entrepot.creer_case("Autre dossier", "")
    autre_fichier = tmp_path / "autre.txt"
    autre_fichier.write_text("autre contenu", encoding="utf-8")
    autre_preuve = entrepot.ajouter_preuve(autre, autre_fichier)
    entrepot.verifier_preuve(autre_preuve)
    assert {c["evidence_id"] for c in entrepot.lister_verifications(case_id=dossier)} == {preuve_id}
    assert {c["evidence_id"] for c in entrepot.exporter_preuves_json(dossier)["verifications"]} == {preuve_id}

    chaine = entrepot.verifier_chaine(dossier)
    assert chaine["valide"] is True
    assert chaine["entrees"] == 1


def test_chaine_detecte_une_entree_alteree(tmp_path, entrepot):
    dossier = entrepot.creer_case("Chaine", "")
    for index in range(3):
        fichier = tmp_path / f"p{index}.txt"
        fichier.write_text(f"contenu {index}", encoding="utf-8")
        entrepot.ajouter_preuve(dossier, fichier, note=f"note {index}")

    assert entrepot.verifier_chaine(dossier)["valide"] is True

    connexion = entrepot._connect()
    connexion.execute("UPDATE evidence SET note='alteree' WHERE id=2")
    connexion.commit()
    connexion.close()

    chaine = entrepot.verifier_chaine(dossier)
    assert chaine["valide"] is False
    assert chaine["anomalies"]

    journal = entrepot.exporter_preuves_markdown(dossier)
    assert "Registre de preuves" in journal
    assert "Limites" in journal
    assert "pas une preuve" not in journal.lower()
    export = entrepot.exporter_preuves_json(dossier)
    assert export["chaine"]["valide"] is False
    assert "verifications" in export


def test_ajout_preuve_refuse_un_fichier_absent(tmp_path, entrepot):
    dossier = entrepot.creer_case("Absent", "")
    with pytest.raises(ValueError):
        entrepot.ajouter_preuve(dossier, tmp_path / "inconnu.bin")


def test_correlateur_regroupe_les_valeurs_avec_provenance(tmp_path, entrepot):
    dossier = entrepot.creer_case("Correlation", "")
    entrepot.ajouter_source(dossier, data_type="domaine", value="example.tld",
                            tool_name="whois")
    entrepot.ajouter_source(dossier, data_type="url", value="https://example.tld/login",
                            tool_name="sonde")
    entrepot.ajouter_note(dossier, "observation", "Contact: alice@example.tld et @alice")

    resultat = correlate.correler_case(dossier)
    valeurs = {(entite["type"], entite["valeur"]) for entite in resultat["entites"]}
    assert ("domaine", "example.tld") in valeurs
    assert ("email", "alice@example.tld") in valeurs
    assert ("pseudo", "alice") in valeurs

    domaines = [entite for entite in resultat["correspondances_exactes"]
                if entite["type"] == "domaine"]
    assert domaines and len(domaines[0]["provenances"]) >= 2
    assert "n'etablit pas l'identite" in resultat["avertissement"]

    markdown = correlate.exporter_markdown(resultat)
    assert "Provenance detaillee" in markdown
    assert "source #" in markdown or "note #" in markdown
    json.dumps(correlate.exporter_json(resultat))


def test_correlateur_refuse_un_dossier_inconnu(entrepot):
    with pytest.raises(ValueError):
        correlate.correler_case(99999)
