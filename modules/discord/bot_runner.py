"""Mode en ligne du bot Discord (`--bot`).

Ce module connecte reellement le bot a la Gateway Discord et le laisse en
ligne jusqu'a l'arret manuel (Ctrl+C). Il ne sert pas de selfbot : seul un
token de bot est accepte.

Le token n'est jamais ecrit sur le disque. Il est lu dans la variable
d'environnement ``LEAKFR_DISCORD_BOT_TOKEN`` ou demande a l'ecran (saisie
masquee). Aucun message d'erreur ne contient le token.
"""
import os
import time

from rich.prompt import Prompt

from core.common import C_DISCORD, bad, console, kv, ok, titre, warn
from modules.discord.discord_api import (
    DiscordAPI, DiscordAPIError, DiscordAuthError, conseils_jeton_bot,
    normaliser_jeton,
)
from modules.discord.gateway_bot import DiscordGatewayClient

VARIABLE_ENV = "LEAKFR_DISCORD_BOT_TOKEN"
INTERVALLE_DEFAUT = 5


def lire_jeton(demander_si_absent=True):
    """Jeton depuis l'environnement, sinon saisie masquee (jamais persistee)."""
    jeton = normaliser_jeton(os.environ.get(VARIABLE_ENV, ""))
    if jeton:
        return jeton
    if not demander_si_absent:
        return ""
    try:
        return normaliser_jeton(Prompt.ask("[bold]Token du Bot Discord[/]",
                                           password=True))
    except (EOFError, KeyboardInterrupt):
        # Entree fermee (pipe, CI) ou interruption : on ne bloque pas le script.
        return ""


def _ligne_etat(gateway, secondes_en_ligne):
    latence = gateway.latency_ms
    latence_txt = "?" if latence is None else f"{latence} ms"
    return (f"[dim]{time.strftime('%H:%M:%S')}[/]  en ligne depuis "
            f"[bold]{secondes_en_ligne}s[/]  |  latence {latence_txt}")


def demarrer_bot(jeton=None, api_factory=DiscordAPI, gateway_factory=DiscordGatewayClient,
                 sleep=time.sleep, intervalle=INTERVALLE_DEFAUT, max_iterations=None,
                 demander_si_absent=True):
    """Connecte le bot et le garde en ligne.

    Retourne un code de sortie : 0 si la session a ete ouverte puis fermee
    proprement, 1 en cas d'echec d'authentification ou de connexion.
    """
    titre("DISCORD BOT - MODE EN LIGNE", C_DISCORD)
    jeton = normaliser_jeton(jeton) or lire_jeton(demander_si_absent)
    if not jeton:
        bad(f"Aucun token. Definis {VARIABLE_ENV} ou saisis le token du bot.")
        return 1

    api = api_factory(jeton)
    try:
        try:
            donnees = api.me()
        except DiscordAuthError:
            bad("Token Bot refuse par Discord (HTTP 401).")
            for conseil in conseils_jeton_bot(jeton):
                warn(conseil)
            return 1
        except DiscordAPIError as exc:
            bad(f"Verification impossible : {exc}")
            return 1
        try:
            guildes = api.my_guilds()
        except DiscordAPIError as exc:
            guildes = []
            warn(f"Liste des serveurs indisponible ({exc}).")
    finally:
        api.close()

    gateway = gateway_factory(jeton)
    try:
        console.print("[dim]Connexion a la Gateway Discord...[/]")
        connecte = gateway.start(timeout=20)
        if not connecte:
            bad(gateway.last_error or "Gateway non connectee.")
            if "401" in str(gateway.last_error or ""):
                for conseil in conseils_jeton_bot(jeton):
                    warn(conseil)
            return 1

        utilisateur = gateway.user_data or {}
        nom = utilisateur.get("username") or donnees.get("username") or "bot"
        kv("Bot en ligne", [
            ("Nom", f"{nom} ({utilisateur.get('id', donnees.get('id', '?'))})"),
            ("Serveurs", f"{len(guildes)} serveur(s)"),
            ("Latence", f"{gateway.latency_ms if gateway.latency_ms is not None else '?'} ms"),
            ("Arret", "Ctrl+C"),
        ], C_DISCORD)
        ok("Le bot est connecte a Discord et reste en ligne.")

        iterations = 0
        while True:
            if max_iterations is not None and iterations >= max_iterations:
                break
            iterations += 1
            sleep(intervalle)
            if not gateway.connected:
                warn(gateway.last_error or "Connexion Gateway perdue.")
                break
            console.print(_ligne_etat(gateway, gateway.uptime_seconds or 0))
    except KeyboardInterrupt:
        warn("Arret demande (Ctrl+C).")
    finally:
        gateway.stop()
    ok("Bot deconnecte. Session fermee.")
    return 0
