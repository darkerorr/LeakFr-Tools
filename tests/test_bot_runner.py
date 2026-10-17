"""Tests du mode en ligne du bot Discord (`--bot`) et des diagnostics de token.

Aucun test ne contacte Discord : le REST et la Gateway sont des faux clients
injectes. Le nombre de serveurs vient du cache Gateway, jamais d'un appel REST.
"""
import sys

import pytest

from modules.discord import bot_runner
from modules.discord.discord_api import (
    DiscordAPIError, DiscordAuthError, DiscordForbiddenError, DiscordRateLimitError,
    conseils_jeton_bot, forme_jeton_discord, normaliser_jeton,
)

JETON_VALIDE = "MTIzNDU2Nzg5MDEyMzQ1Njc4.abcdef.ghijklmnopqrstuvwxyz"


@pytest.fixture(autouse=True)
def _console_non_interactive(monkeypatch):
    """Rend l'affichage de session deterministe (jamais de Live en test)."""
    monkeypatch.setattr(bot_runner.console, "_force_terminal", False, raising=False)


class FausseApi:
    """Client REST minimal, injectable, sans reseau.

    Il n'expose volontairement pas ``my_guilds`` : le comptage des serveurs ne
    doit plus dependre d'un endpoint REST.
    """

    def __init__(self, me=None):
        self._me = me if me is not None else {"id": "123456789012345678",
                                              "username": "bot-test"}
        self.ferme = False

    def me(self):
        if isinstance(self._me, Exception):
            raise self._me
        return self._me

    def close(self):
        self.ferme = True


class FausseGateway:
    """Gateway simulee : aucun appel reseau, etat controle par le test."""

    def __init__(self, connecte=True, erreur=None, serveurs=2, fermeture_propre=True):
        self.connected = connecte
        self.reconnecting = False
        self.last_error = erreur
        self.user_data = {"id": "123456789012345678", "username": "bot-test"}
        self.latency_ms = 42
        self.uptime_seconds = 3
        self.guild_count = serveurs
        self.session_ouverte = True
        self.etat = "connectee" if connecte else "arretee"
        self.fermeture_propre = fermeture_propre
        self.demarree = False
        self.arretee = False

    def start(self, timeout=20):
        self.demarree = True
        return self.connected

    def stop(self, timeout=5):
        self.arretee = True
        self.connected = False
        self.session_ouverte = False
        self.etat = "arretee"
        return self.fermeture_propre


def api_factory(api):
    return lambda _jeton: api


def gateway_factory(gateway):
    return lambda _jeton: gateway


def _lancer(gateway=None, api=None, sleep=lambda _s: None, **kwargs):
    gateway = gateway or FausseGateway()
    api = api or FausseApi()
    kwargs.setdefault("max_iterations", 1)
    code = bot_runner.demarrer_bot(jeton=JETON_VALIDE,
                                   api_factory=api_factory(api),
                                   gateway_factory=gateway_factory(gateway),
                                   sleep=sleep, demander_si_absent=False, **kwargs)
    return code, gateway, api


def test_normaliser_jeton_nettoie_les_saisies_reelles():
    assert normaliser_jeton("  Bot MTIz.NDU2.abc  ") == "MTIz.NDU2.abc"
    assert normaliser_jeton('"MTIz.NDU2.abc"') == "MTIz.NDU2.abc"
    assert normaliser_jeton("Bearer MTIz.NDU2.abc") == "MTIz.NDU2.abc"
    assert normaliser_jeton("") == ""
    assert normaliser_jeton(None) == ""


def test_forme_jeton_et_conseils_sans_secret():
    assert forme_jeton_discord(JETON_VALIDE)
    assert not forme_jeton_discord("token-bidon")
    conseils = conseils_jeton_bot("token-bidon")
    assert any("3 parties" in conseil for conseil in conseils)
    assert any("token de bot" in conseil for conseil in conseils)
    assert not any("token-bidon" in conseil for conseil in conseils)
    # Le partage d'un token n'entraine pas une revocation automatique : le
    # conseil doit demander une revocation manuelle.
    assert not any("automatiquement" in conseil.lower() for conseil in conseils)
    assert any("revoque" in conseil for conseil in conseils)


def test_normaliser_intervalle_borne_les_valeurs():
    assert bot_runner.normaliser_intervalle(None) == bot_runner.INTERVALLE_DEFAUT
    assert bot_runner.normaliser_intervalle("abc") == bot_runner.INTERVALLE_DEFAUT
    assert bot_runner.normaliser_intervalle(0) == bot_runner.INTERVALLE_MIN
    assert bot_runner.normaliser_intervalle(-12) == bot_runner.INTERVALLE_MIN
    assert bot_runner.normaliser_intervalle(99999) == bot_runner.INTERVALLE_MAX
    assert bot_runner.normaliser_intervalle("30") == 30.0


def test_mode_bot_refuse_un_token_absent(monkeypatch, capsys):
    monkeypatch.delenv(bot_runner.VARIABLE_ENV, raising=False)
    code = bot_runner.demarrer_bot(jeton="", demander_si_absent=False)
    sortie = capsys.readouterr().out
    assert code == 1
    assert "Aucun token" in sortie
    assert bot_runner.VARIABLE_ENV in sortie


def test_mode_bot_utilise_la_variable_d_environnement(monkeypatch, capsys):
    monkeypatch.setenv(bot_runner.VARIABLE_ENV, JETON_VALIDE)
    code, gateway, api = _lancer()
    sortie = capsys.readouterr().out
    assert code == 0
    assert api.ferme is True
    assert gateway.demarree and gateway.arretee
    assert "en ligne" in sortie
    assert JETON_VALIDE not in sortie


def test_mode_bot_compte_les_serveurs_via_la_gateway(capsys):
    gateway = FausseGateway(serveurs=4)
    code, gateway, _api = _lancer(gateway)
    sortie = capsys.readouterr().out
    assert code == 0
    assert "4 serveur(s)" in sortie


def test_mode_bot_signale_des_serveurs_indisponibles_sans_inventer(capsys):
    gateway = FausseGateway(serveurs=None)
    code, _gateway, _api = _lancer(gateway)
    sortie = capsys.readouterr().out
    assert code == 0
    assert "indisponible" in sortie


def test_mode_bot_explique_un_token_refuse(capsys):
    api = FausseApi(me=DiscordAuthError("Token refuse ou revoque (HTTP 401).", status=401))
    code, _gateway, api = _lancer(api=api)
    sortie = capsys.readouterr().out
    assert code == 1
    assert api.ferme is True
    assert "401" in sortie
    assert "portail developpeur" in sortie
    assert JETON_VALIDE not in sortie


def test_mode_bot_signale_une_gateway_non_connectee(capsys):
    gateway = FausseGateway(connecte=False,
                            erreur="Token Bot refuse par Discord (401).")
    code, gateway, _api = _lancer(gateway)
    sortie = capsys.readouterr().out
    assert code == 1
    assert gateway.arretee is True
    assert "401" in sortie
    assert JETON_VALIDE not in sortie


def test_mode_bot_ne_masque_pas_une_erreur_api(capsys):
    api = FausseApi(me=DiscordAPIError("HTTP 500", status=500))
    code, _gateway, _api = _lancer(api=api)
    sortie = capsys.readouterr().out
    assert code == 1
    assert "HTTP 500" in sortie


@pytest.mark.parametrize("erreur, attendu", [
    (DiscordForbiddenError("Permissions insuffisantes (HTTP 403).", status=403), "403"),
    (DiscordRateLimitError("Limite de debit Discord atteinte (429).", status=429), "429"),
    (DiscordAPIError("Erreur reseau : ConnectionError", status=None), "Reseau"),
    (DiscordAPIError("Reponse API non JSON (HTTP 200).", status=200), "non JSON"),
])
def test_mode_bot_distingue_les_types_d_erreur(capsys, erreur, attendu):
    api = FausseApi(me=erreur)
    code, _gateway, _api = _lancer(api=api)
    sortie = capsys.readouterr().out
    assert code == 1
    assert attendu in sortie
    assert JETON_VALIDE not in sortie


def test_mode_bot_survit_a_une_reconnexion_temporaire(capsys):
    gateway = FausseGateway()
    appels = {"n": 0}

    def sommeil(_secondes):
        appels["n"] += 1
        if appels["n"] == 1:  # coupure temporaire, la session reste ouverte
            gateway.connected = False
            gateway.reconnecting = True
            gateway.etat = "reconnexion"
            gateway.last_error = "Connexion perdue."
        else:  # discord.py a repris la session
            gateway.connected = True
            gateway.reconnecting = False
            gateway.etat = "connectee"

    code = bot_runner.demarrer_bot(jeton=JETON_VALIDE,
                                   api_factory=api_factory(FausseApi()),
                                   gateway_factory=gateway_factory(gateway),
                                   sleep=sommeil, max_iterations=3,
                                   demander_si_absent=False)
    sortie = capsys.readouterr().out
    assert code == 0
    assert gateway.arretee is True
    assert "reconnexion" in sortie


def test_mode_bot_quitte_sur_perte_definitive(capsys):
    gateway = FausseGateway()

    def sommeil(_secondes):
        gateway.connected = False
        gateway.reconnecting = False
        gateway.session_ouverte = False
        gateway.etat = "arretee"
        gateway.last_error = "Session Gateway terminee."

    code = bot_runner.demarrer_bot(jeton=JETON_VALIDE,
                                   api_factory=api_factory(FausseApi()),
                                   gateway_factory=gateway_factory(gateway),
                                   sleep=sommeil, max_iterations=5,
                                   demander_si_absent=False)
    sortie = capsys.readouterr().out
    assert code == 1
    assert "Session Gateway terminee." in sortie
    assert gateway.arretee is True


def test_mode_bot_arret_manuel_pendant_la_session(capsys):
    def sommeil(_secondes):
        raise KeyboardInterrupt

    code, gateway, _api = _lancer(sleep=sommeil)
    sortie = capsys.readouterr().out
    assert code == 0
    assert "Ctrl+C" in sortie
    assert gateway.arretee is True


def test_mode_bot_signale_une_fermeture_incomplete(capsys):
    gateway = FausseGateway(fermeture_propre=False)
    code, _gateway, _api = _lancer(gateway)
    sortie = capsys.readouterr().out
    assert code == 0
    assert "n'a pas pu etre fermee" in sortie


def test_mode_bot_masque_un_token_dans_une_erreur_de_fabrique(capsys):
    def factory_en_erreur(_jeton):
        raise ValueError(f"configuration invalide : {JETON_VALIDE}")

    code = bot_runner.demarrer_bot(jeton=JETON_VALIDE, api_factory=factory_en_erreur,
                                   gateway_factory=gateway_factory(FausseGateway()),
                                   demander_si_absent=False)
    sortie = capsys.readouterr().out
    assert code == 1
    assert "ValueError" in sortie
    assert JETON_VALIDE not in sortie


def test_mode_bot_masque_un_token_dans_une_erreur_de_gateway(capsys):
    def factory_en_erreur(_jeton):
        raise RuntimeError(f"echec gateway avec {JETON_VALIDE}")

    code = bot_runner.demarrer_bot(jeton=JETON_VALIDE,
                                   api_factory=api_factory(FausseApi()),
                                   gateway_factory=factory_en_erreur,
                                   demander_si_absent=False)
    sortie = capsys.readouterr().out
    assert code == 1
    assert "RuntimeError" in sortie
    assert JETON_VALIDE not in sortie


def test_option_bot_du_cli_declenche_le_mode_bot(monkeypatch):
    appels = []
    monkeypatch.setattr(bot_runner, "demarrer_bot",
                        lambda **kwargs: appels.append(kwargs) or 0)
    monkeypatch.setattr(sys, "argv", ["main.py", "--bot"])
    import main as module_main
    code = module_main.main()
    assert len(appels) == 1
    assert appels[0]["intervalle"] == bot_runner.INTERVALLE_DEFAUT
    assert code == 0


def test_option_intervalle_du_bot_est_transmise(monkeypatch):
    appels = []
    monkeypatch.setattr(bot_runner, "demarrer_bot",
                        lambda **kwargs: appels.append(kwargs) or 0)
    monkeypatch.setattr(sys, "argv", ["main.py", "--bot", "--bot-interval", "30"])
    import main as module_main
    module_main.main()
    assert appels[0]["intervalle"] == 30.0


def test_lire_jeton_ne_demande_rien_sans_terminal(monkeypatch, capsys):
    monkeypatch.delenv(bot_runner.VARIABLE_ENV, raising=False)

    class EntreeFermee:
        def isatty(self):
            return False

    monkeypatch.setattr(bot_runner.sys, "stdin", EntreeFermee())
    assert bot_runner.lire_jeton() == ""
    assert "Token du Bot" not in capsys.readouterr().out


def test_variable_d_environnement_exposee():
    assert bot_runner.VARIABLE_ENV == "LEAKFR_DISCORD_BOT_TOKEN"
