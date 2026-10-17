"""Tests du mode en ligne du bot Discord (`--bot`) et des diagnostics de token."""
import sys

from modules.discord import bot_runner
from modules.discord.discord_api import (
    DiscordAPIError, DiscordAuthError, conseils_jeton_bot, forme_jeton_discord,
    normaliser_jeton,
)

JETON_VALIDE = "MTIzNDU2Nzg5MDEyMzQ1Njc4.abcdef.ghijklmnopqrstuvwxyz"


class FausseApi:
    """Client REST minimal, injectable, sans reseau."""

    def __init__(self, me=None, guildes=None):
        self._me = me if me is not None else {"id": "123456789012345678",
                                              "username": "bot-test"}
        self._guildes = guildes if guildes is not None else [{"id": "1"}, {"id": "2"}]
        self.ferme = False

    def me(self):
        if isinstance(self._me, Exception):
            raise self._me
        return self._me

    def my_guilds(self):
        if isinstance(self._guildes, Exception):
            raise self._guildes
        return self._guildes

    def close(self):
        self.ferme = True


class FausseGateway:
    """Gateway simulee : aucun appel reseau, etat controle par le test."""

    def __init__(self, connecte=True, erreur=None):
        self.connected = connecte
        self.last_error = erreur
        self.user_data = {"id": "123456789012345678", "username": "bot-test"}
        self.latency_ms = 42
        self.uptime_seconds = 3
        self.demarree = False
        self.arretee = False

    def start(self, timeout=20):
        self.demarree = True
        return self.connected

    def stop(self, timeout=5):
        self.arretee = True
        self.connected = False


def api_factory(api):
    return lambda _jeton: api


def gateway_factory(gateway):
    return lambda _jeton: gateway


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


def test_mode_bot_refuse_un_token_absent(monkeypatch, capsys):
    monkeypatch.delenv(bot_runner.VARIABLE_ENV, raising=False)
    code = bot_runner.demarrer_bot(jeton="", demander_si_absent=False)
    sortie = capsys.readouterr().out
    assert code == 1
    assert "Aucun token" in sortie
    assert bot_runner.VARIABLE_ENV in sortie


def test_mode_bot_utilise_la_variable_d_environnement(monkeypatch, capsys):
    monkeypatch.setenv(bot_runner.VARIABLE_ENV, JETON_VALIDE)
    api = FausseApi()
    gateway = FausseGateway()
    code = bot_runner.demarrer_bot(api_factory=api_factory(api),
                                   gateway_factory=gateway_factory(gateway),
                                   sleep=lambda _secondes: None, max_iterations=1,
                                   demander_si_absent=False)
    sortie = capsys.readouterr().out
    assert code == 0
    assert api.ferme is True
    assert gateway.demarree and gateway.arretee
    assert "en ligne" in sortie
    assert JETON_VALIDE not in sortie


def test_mode_bot_explique_un_token_refuse(capsys):
    api = FausseApi(me=DiscordAuthError("Token refuse ou revoque (HTTP 401).", status=401))
    code = bot_runner.demarrer_bot(jeton=JETON_VALIDE, api_factory=api_factory(api),
                                   gateway_factory=gateway_factory(FausseGateway()),
                                   demander_si_absent=False)
    sortie = capsys.readouterr().out
    assert code == 1
    assert "401" in sortie
    assert "portail developpeur" in sortie
    assert JETON_VALIDE not in sortie


def test_mode_bot_signale_une_gateway_non_connectee(capsys):
    gateway = FausseGateway(connecte=False,
                            erreur="Token Bot refuse par Discord (401).")
    code = bot_runner.demarrer_bot(jeton=JETON_VALIDE,
                                   api_factory=api_factory(FausseApi()),
                                   gateway_factory=gateway_factory(gateway),
                                   demander_si_absent=False)
    sortie = capsys.readouterr().out
    assert code == 1
    assert gateway.arretee is True
    assert "401" in sortie
    assert JETON_VALIDE not in sortie


def test_mode_bot_ne_masque_pas_une_erreur_api(capsys):
    api = FausseApi(me=DiscordAPIError("HTTP 500", status=500))
    code = bot_runner.demarrer_bot(jeton=JETON_VALIDE, api_factory=api_factory(api),
                                   gateway_factory=gateway_factory(FausseGateway()),
                                   demander_si_absent=False)
    sortie = capsys.readouterr().out
    assert code == 1
    assert "HTTP 500" in sortie


def test_mode_bot_signe_un_serveur_indisponible_sans_abandonner(capsys):
    api = FausseApi(guildes=DiscordAPIError("HTTP 503", status=503))
    gateway = FausseGateway()
    code = bot_runner.demarrer_bot(jeton=JETON_VALIDE, api_factory=api_factory(api),
                                   gateway_factory=gateway_factory(gateway),
                                   sleep=lambda _secondes: None, max_iterations=1,
                                   demander_si_absent=False)
    sortie = capsys.readouterr().out
    assert code == 0
    assert "indisponible" in sortie


def test_option_bot_du_cli_declenche_le_mode_bot(monkeypatch):
    appels = []
    monkeypatch.setattr(bot_runner, "demarrer_bot", lambda: appels.append("bot") or 0)
    monkeypatch.setattr(sys, "argv", ["main.py", "--bot"])
    import main as module_main
    code = module_main.main()
    assert appels == ["bot"]
    assert code == 0


def test_variable_d_environnement_exposee():
    assert bot_runner.VARIABLE_ENV == "LEAKFR_DISCORD_BOT_TOKEN"
