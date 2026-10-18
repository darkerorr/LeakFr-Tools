"""Tests deterministes de la Gateway Discord, sans token reel ni reseau.

Le client ``discord.py`` est remplace par un faux client pilote par le test :
on verifie le decompte reel des serveurs du cache, les etats de reconnexion,
la presence par defaut et l'absence de fuite de thread a l'arret.
"""
import asyncio
import threading
import time
from types import SimpleNamespace

import discord

from modules.discord.gateway_bot import DiscordGatewayClient

JETON_TEST = "MTIzNDU2Nzg5MDEyMzQ1Njc4.abcdef.ghijklmnopqrstuvwxyz"


class FauxClient:
    """Client discord.py minimal : aucune requete, tout est controle par le test."""

    def __init__(self, guildes=2, latence=0.042):
        self.guilds = [SimpleNamespace(id=str(index)) for index in range(guildes)]
        self.latency = latence
        self.handlers = {}
        self.statuts = []
        self.activites = []
        self.token = None
        self.reconnect = None
        self.ferme = False
        # Cree dans la boucle du thread Gateway : sur Python 3.9 un Event cree
        # hors boucle reste attache a la boucle du thread appelant.
        self._fin = None
        self._boucle = None

    @property
    def user(self):
        return SimpleNamespace(id="123456789012345678", name="bot-test", discriminator="0")

    def event(self, coro):
        self.handlers[coro.__name__] = coro
        return coro

    async def start(self, token, reconnect=True):
        self.token = token
        self.reconnect = reconnect
        self._boucle = asyncio.get_running_loop()
        self._fin = asyncio.Event()
        await self.handlers["on_ready"]()
        await self._fin.wait()

    async def close(self):
        self.ferme = True
        if self._fin is not None:
            self._fin.set()

    def is_closed(self):
        return self.ferme

    async def change_presence(self, status=None, activity=None, **kwargs):
        self.statuts.append(status)
        self.activites.append(activity)


class FauxClientSansReady(FauxClient):
    """Ne declenche jamais READY : sert au test de delai depasse."""

    async def start(self, token, reconnect=True):
        self.token = token
        self._boucle = asyncio.get_running_loop()
        self._fin = asyncio.Event()
        await self._fin.wait()


class FauxClientErreur(FauxClient):
    """Echec d'authentification permanent."""

    async def start(self, token, reconnect=True):
        self.token = token
        self._boucle = asyncio.get_running_loop()
        raise discord.LoginFailure("invalid token")


class FauxClientPresenceRefusee(FauxClient):
    """READY reussi mais Discord refuse la presence."""

    async def change_presence(self, status=None, activity=None, **kwargs):
        reponse = SimpleNamespace(status=403, reason="Forbidden")
        raise discord.HTTPException(reponse, "Forbidden")


def _gateway(classe=FauxClient, **kwargs):
    faux = classe(**kwargs)
    return faux, DiscordGatewayClient(JETON_TEST, client_factory=lambda _intents: faux)


def _executer(faux, nom):
    futur = asyncio.run_coroutine_threadsafe(faux.handlers[nom](), faux._boucle)
    return futur.result(timeout=5)


def _threads_gateway():
    return [t for t in threading.enumerate()
            if t.name == "discord-gateway" and t.is_alive()]


def _attendre(predicat, timeout=5):
    fin = time.time() + timeout
    while time.time() < fin:
        if predicat():
            return True
        time.sleep(0.01)
    return False


def test_gateway_compte_les_serveurs_reels_du_cache_apres_ready():
    faux, client = _gateway(guildes=3)
    assert client.guild_count is None  # avant READY : aucune estimation
    assert client.start(timeout=5) is True
    try:
        assert client.guild_count == 3
        assert client.etat == "connectee"
        assert client.session_ouverte is True
        assert client.latency_ms == 42
        assert faux.reconnect is True
        assert faux.statuts[-1] is discord.Status.online
    finally:
        assert client.stop() is True
    assert client.guild_count is None


def test_gateway_n_impose_aucune_activite_par_defaut():
    faux, client = _gateway()
    assert client.start(timeout=5) is True
    try:
        assert faux.activites == [None]
    finally:
        assert client.stop() is True


def test_gateway_ne_remplace_pas_une_activite_choisie_a_la_reconnexion():
    faux, client = _gateway()
    assert client.start(timeout=5) is True
    try:
        assert client.update_presence("idle", "Audit", 0)[0] is True
        activite = faux.activites[-1]
        assert activite is not None and activite.name == "Audit"

        _executer(faux, "on_disconnect")
        assert client.connected is False and client.reconnecting is True
        assert client.etat == "reconnexion"
        assert client.session_ouverte is True
        assert client.uptime_seconds is not None  # l'uptime reel ne repart pas a zero

        _executer(faux, "on_resumed")
        assert client.etat == "connectee"

        _executer(faux, "on_ready")  # nouvelle session READY (reconnexion complete)
        assert faux.activites[-1] is not None
        assert faux.activites[-1].name == "Audit"
    finally:
        assert client.stop() is True


def test_gateway_signale_une_presence_refusee_sans_casser_la_session():
    faux, client = _gateway(FauxClientPresenceRefusee)
    assert client.start(timeout=5) is True
    try:
        assert client.connected is True
        assert "HTTPException" in (client.last_error or "")
        assert client.last_error and JETON_TEST not in client.last_error
    finally:
        assert client.stop() is True


def test_gateway_timeout_ferme_le_thread_sans_laisser_de_session():
    faux, client = _gateway(FauxClientSansReady)
    assert client.start(timeout=0.3) is False
    assert "Delai" in (client.last_error or "")
    assert client.stop() is True
    assert _attendre(lambda: not _threads_gateway())
    assert client.session_ouverte is False


def test_gateway_echec_de_connexion_permanent_ne_genere_pas_de_faux_succes():
    faux, client = _gateway(FauxClientErreur)
    assert client.start(timeout=5) is False
    assert "401" in (client.last_error or "")
    assert client.connected is False
    assert client.etat == "arretee"
    assert faux.token == JETON_TEST
    assert JETON_TEST not in "\n".join(client.log_messages)
    assert _attendre(lambda: not _threads_gateway())


def test_gateway_arret_manuel_pendant_reconnexion():
    faux, client = _gateway()
    assert client.start(timeout=5) is True
    _executer(faux, "on_disconnect")
    assert client.etat == "reconnexion"
    assert client.stop() is True
    assert client.connected is False
    assert client.session_ouverte is False
    assert _attendre(lambda: not _threads_gateway())
    assert client.uptime_seconds is None


def test_gateway_uptime_absent_avant_toute_connexion():
    _, client = _gateway()
    assert client.uptime_seconds is None
    assert client.etat == "arretee"
    assert client.guild_count is None
