"""Tests des secrets (tokens jamais ecrits) et de la coherence CI / .gitignore."""
from pathlib import Path

import pytest

from modules.discord import panel_journal
from modules.discord.discord_api import DiscordAPI, DiscordAPIError, redact

RACINE = Path(__file__).resolve().parents[1]
JETON = "MTIzNDU2Nzg5MDEyMzQ1Njc4.abcdef.ghijklmnopqrstuvwxyz"


def test_redact_masque_les_tokens_dans_les_messages_d_erreur():
    message = f"Authorization: Bot {JETON} refuse"
    resultat = redact(message)
    assert JETON not in resultat
    assert "[masque]" in resultat
    assert JETON not in redact(f"token={JETON}", (JETON,))


class FausseReponse:
    def __init__(self, statut, donnees):
        self.status_code = statut
        self.headers = {}
        self._donnees =donnees

    def json(self):
        return self._donnees


class FausseSession:
    def __init__(self, reponse):
        self.reponse = reponse
        self.fermee = False

    def request(self, *_args, **_kwargs):
        return self.reponse

    def close(self):
        self.fermee= True


def test_les_reponses_d_erreur_externes_sont_expurgees():
    session = FausseSession(FausseReponse(400, {"message": f"Invalid token {JETON}"}))
    api = DiscordAPI('jwt-placeholder', session=session, max_retries=0)
    with pytest.raises(DiscordAPIError) as erreur:
        api.me()
    message = str(erreur.value)
    assert JETON not in message
    assert "[masque]" in message
    assert erreur.value.status==400


def test_journal_du_panel_n_ecrit_aucun_token(tmp_path):
    fichier =tmp_path / "journal.json"
    panel_journal.enregistrer("gateway_start", "123", "serveur", "ok",
                              f"session ouverte avec {JETON}", secrets=(JETON,),
                              path=fichier)
    contenu =fichier.read_text(encoding="utf-8")
    assert JETON not in contenu
    entrees = panel_journal.charger_journal(fichier)
    assert entrees and JETON not in str(entrees)


def test_gitignore_ne_bloque_plus_le_workflow_ci():
    lignes= [ligne.strip() for ligne in
              (RACINE / ".gitignore").read_text(encoding="utf-8").splitlines()]
    regles =[ligne for ligne in lignes if ligne and not ligne.startswith("#")]
    assert '.github' not in regles
    assert ".github/" not in regles
    assert "data/cases.db" in regles


def test_workflow_ci_present_et_coherent_avec_les_plateformes_documentees():
    workflow = RACINE / '.github' / 'workflows' / 'ci.yml'
    assert workflow.is_file()
    texte =workflow.read_text(encoding="utf-8")
    for attendu in ('ubuntu-latest', 'windows-latest', 'macos-latest',
                    "compileall", "pytest", "--help"):
        assert attendu in texte
    assert "Termux" in texte
