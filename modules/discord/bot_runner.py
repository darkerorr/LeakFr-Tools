"""Mode en ligne du bot Discord (`--bot`).

Ce module connecte reellement le bot a la Gateway Discord et le laisse en
ligne jusqu'a l'arret manuel (Ctrl+C). Il ne sert pas de selfbot : seul un
token de bot est accepte.

Le token n'est jamais ecrit sur le disque. Il est lu dans la variable
d'environnement ``LEAKFR_DISCORD_BOT_TOKEN`` ou demande a l'ecran (saisie
masquee). Aucun message d'erreur ne contient le token.

Le nombre de serveurs affiche vient du cache de la Gateway (``discord.py``),
seul comptage reellement disponible pour un bot : il n'est jamais deduit d'un
appel REST ni remplace par zero quand il est inconnu.
"""
import os
import sys
import time

from rich.live import Live
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text

from core.common import BX, C_DISCORD, bad, console, kv, ok, titre, warn
from modules.discord.discord_api import (
    DiscordAPI, DiscordAPIError, DiscordAuthError, DiscordForbiddenError,
    DiscordRateLimitError, conseils_jeton_bot, normaliser_jeton, redact,
)
from modules.discord.gateway_bot import DiscordGatewayClient

VARIABLE_ENV = "LEAKFR_DISCORD_BOT_TOKEN"
INTERVALLE_DEFAUT = 5.0
INTERVALLE_MIN = 1.0
INTERVALLE_MAX = 300.0
DELAI_CONNEXION =20


def lire_jeton(demander_si_absent=True):
    """Jeton depuis l'environnement, sinon saisie masquee (jamais persistee)."""
    jeton= normaliser_jeton(os.environ.get(VARIABLE_ENV, ""))
    if jeton:
        return jeton
    if not demander_si_absent:
        return ""
    if not getattr(sys.stdin, 'isatty', lambda: False)():
        return ''
    try:
        return normaliser_jeton(Prompt.ask("[bold]Token du Bot Discord[/]",
                                           password=True))
    except (EOFError, KeyboardInterrupt):
        return ''


def normaliser_intervalle(valeur, defaut=INTERVALLE_DEFAUT):
    """Borne l'intervalle d'actualisation : jamais zero ni infini."""
    try:
        valeur=float(valeur)
    except (TypeError, ValueError):
        return float(defaut)
    if valeur != valeur:
        return float(defaut)
    return max(INTERVALLE_MIN, min(INTERVALLE_MAX, valeur))


def _etat_gateway(gateway):
    """Etat lisible de la Gateway, sans inventer de connexion."""
    etat =getattr(gateway, "etat", None)
    if callable(etat):
        etat = etat()
    if etat:
        return str(etat)
    return 'connectee' if getattr(gateway, 'connected', False) else 'reconnexion'


def _session_vivante(gateway):
    """Vrai tant que la session peut encore vivre (reconnexion incluse)."""
    verif= getattr(gateway, "session_ouverte", None)
    if isinstance(verif, bool):
        return verif
    if callable(verif):
        return bool(verif())
    return bool(getattr(gateway, "connected", False))


def _libelle_serveurs(gateway):
    """Comptage reel des serveurs charges, jamais une estimation inventee."""
    compte = getattr(gateway, 'guild_count', None)
    if compte is None:
        return "indisponible (cache Gateway non pret)"
    return f"{compte} serveur(s) charge(s)"


def _ligne_etat(gateway):
    latence= getattr(gateway, "latency_ms", None)
    latence_txt = "indisponible" if latence is None else f"{latence} ms"
    uptime = getattr(gateway, 'uptime_seconds', None)
    uptime_txt="indisponible" if uptime is None else f"{uptime} s"
    return (f"{time.strftime('%H:%M:%S')}  etat : {_etat_gateway(gateway)}"
            f"  |  session : {uptime_txt}  |  latence : {latence_txt}"
            f"  |  serveurs : {_libelle_serveurs(gateway)}")


def _vue_etat(gateway):
    """Vue compacte et actualisee pour une session longue (terminal ou Termux)."""
    table = Table.grid(padding=(0, 1))
    table.add_column(style=f"bold {C_DISCORD}", width=16)
    table.add_column()
    etat = _etat_gateway(gateway)
    couleurs = {"connectee": "bold green", "reconnexion":"bold yellow",
                "demarrage":"bold cyan", "arretee": "bold red"}
    latence = getattr(gateway, 'latency_ms', None)
    uptime = getattr(gateway, "uptime_seconds", None)
    table.add_row("Etat", Text(etat, style=couleurs.get(etat, "bold white")))
    table.add_row('Uptime', 'indisponible' if uptime is None else f"{uptime} s")
    table.add_row("Latence", "indisponible" if latence is None else f"{latence} ms")
    table.add_row("Serveurs", _libelle_serveurs(gateway))
    table.add_row('Derniere erreur', str(getattr(gateway, 'last_error', None) or 'aucune'))
    return table


def _afficher_echec(exc, jeton):
    """Diagnostic adapte au type d'echec, toujours sans secret."""
    if isinstance(exc, DiscordAuthError):
        bad("Token Bot refuse par Discord (HTTP 401).")
        for conseil in conseils_jeton_bot(jeton):
            warn(conseil)
    elif isinstance(exc, DiscordForbiddenError):
        bad("Permissions insuffisantes (HTTP 403) : verifiez les droits du bot.")
    elif isinstance(exc, DiscordRateLimitError):
        bad(f"Limite de debit Discord atteinte (429) : {exc}")
    elif isinstance(exc, DiscordAPIError):
        statut= getattr(exc, 'status', None)
        if statut is None:
            bad(f"Reseau indisponible ou requete refusee : {exc}")
        else:
            bad(f"Erreur Discord (HTTP {statut}) : {exc}")
    else:
        bad(f"Erreur inattendue ({type(exc).__name__}) : {redact(str(exc), (jeton,))}")


def _afficher_echec_gateway(gateway, jeton):
    erreur = str(getattr(gateway, "last_error", None) or "Gateway non connectee.")
    bad(erreur)
    if '401' in erreur:
        for conseil in conseils_jeton_bot(jeton):
            warn(conseil)


def _boucle_session(gateway, sleep, intervalle, max_iterations):
    """Maintient la session ; retourne 0 (arret voulu) ou 1 (perte definitive).

    Une coupure temporaire n'interrompt pas la session : la Gateway discord.py
    continue de se reconnecter, l'etat affiche passe en ``reconnexion`` et la
    boucle ne s'arrete que lorsque le thread Gateway est reellement termine.
    """
    interactif = bool(getattr(console, 'is_terminal', False))
    iterations=0

    if interactif:
        with Live(_vue_etat(gateway), console=console, refresh_per_second=2,
                  transient=True) as live:
            while True:
                if max_iterations is not None and iterations>= max_iterations:
                    return 0
                iterations += 1
                sleep(intervalle)
                if not _session_vivante(gateway):
                    warn(str(getattr(gateway, 'last_error', None)
                             or "Session Gateway terminee."))
                    return 1
                live.update(_vue_etat(gateway))

    precedent = None
    while True:
        if max_iterations is not None and iterations >= max_iterations:
            return 0
        iterations += 1
        sleep(intervalle)
        if not _session_vivante(gateway):
            warn(str(getattr(gateway, "last_error", None)
                     or 'Session Gateway terminee.'))
            return 1
        etat= _etat_gateway(gateway)
        if etat != precedent:
            precedent = etat
            console.print(_ligne_etat(gateway))
            if etat == 'reconnexion':
                warn("Connexion interrompue ; reconnexion en cours (session conservee).")


def demarrer_bot(jeton=None, api_factory=DiscordAPI, gateway_factory=DiscordGatewayClient,
                 sleep=time.sleep, intervalle=INTERVALLE_DEFAUT, max_iterations=None,
                 demander_si_absent=True):
    """Connecte le bot et le garde en ligne.

    Retourne un code de sortie : 0 si la session a ete ouverte puis fermee
    proprement, 1 en cas d'echec d'authentification ou de perte definitive de
    la connexion.
    """
    titre("DISCORD BOT - MODE EN LIGNE", C_DISCORD)
    intervalle = normaliser_intervalle(intervalle)
    jeton = normaliser_jeton(jeton) or lire_jeton(demander_si_absent)
    if not jeton:
        bad(f"Aucun token. Definis {VARIABLE_ENV} ou saisis le token du bot.")
        return 1

    try:
        api = api_factory(jeton)
    except Exception as exc:
        bad(f"Client REST Discord indisponible ({type(exc).__name__}).")
        console.print(redact(str(exc), (jeton,)), style='dim')
        return 1
    try:
        donnees =api.me()
    except DiscordAuthError as exc:
        _afficher_echec(exc, jeton)
        return 1
    except DiscordForbiddenError as exc:
        _afficher_echec(exc, jeton)
        return 1
    except DiscordRateLimitError as exc:
        _afficher_echec(exc, jeton)
        return 1
    except DiscordAPIError as exc:
        _afficher_echec(exc, jeton)
        return 1
    finally:
        try:
            api.close()
        except Exception:
            pass

    try:
        gateway =gateway_factory(jeton)
    except Exception as exc:
        bad(f"Client Gateway indisponible ({type(exc).__name__}).")
        console.print(redact(str(exc), (jeton,)), style="dim")
        return 1

    code = 0
    try:
        console.print("[dim]Connexion a la Gateway Discord...[/]")
        connecte = gateway.start(timeout=DELAI_CONNEXION)
        if not connecte:
            _afficher_echec_gateway(gateway, jeton)
            return 1

        utilisateur = getattr(gateway, "user_data", None) or {}
        nom = utilisateur.get("username") or donnees.get("username") or "bot"
        identifiant=utilisateur.get('id') or donnees.get('id') or '?'
        kv("Bot en ligne", [
            ("Nom", f"{nom} ({identifiant})"),
            ('Serveurs', _libelle_serveurs(gateway)),
            ("Latence", "indisponible" if gateway.latency_ms is None
             else f"{gateway.latency_ms} ms"),
            ('Arret', 'Ctrl+C'),
        ], C_DISCORD)
        ok("Le bot est connecte a Discord et reste en ligne.")
        code = _boucle_session(gateway, sleep, intervalle, max_iterations)
    except KeyboardInterrupt:
        warn("Arret demande (Ctrl+C).")
        code = 0
    except Exception as exc:
        bad(f"Erreur inattendue pendant la session ({type(exc).__name__}).")
        console.print(redact(str(exc), (jeton,)), style='dim')
        code = 1
    finally:
        try:
            propre= gateway.stop()
        except Exception:
            propre =False
        if not propre:
            warn("La session Gateway n'a pas pu etre fermee dans le delai.")

    if code == 0:
        ok("Bot deconnecte. Session fermee.")
    return code
