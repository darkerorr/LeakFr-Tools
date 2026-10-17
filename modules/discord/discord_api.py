"""Client REST Discord partage par les panels Bot et personnel.

Le client centralise les delais, les erreurs HTTP, les limites de debit (429)
et la redaction des secrets. Il ne journalise jamais le token.
"""
import json
import re
import time
from urllib.parse import quote

import requests

BASE_URL = "https://discord.com/api/v10"
TIMEOUT_DEFAUT = 10
MAX_RETRIES_DEFAUT = 2
ATTENTE_RATE_LIMIT_MAX = 10.0


class DiscordAPIError(Exception):
    """Erreur API Discord exploitable, sans secret dans le message."""

    def __init__(self, message, status=None, code=None):
        super().__init__(message)
        self.status = status
        self.code = code


class DiscordAuthError(DiscordAPIError):
    """Token refuse ou revoque (401)."""


class DiscordForbiddenError(DiscordAPIError):
    """Permissions insuffisantes (403)."""


class DiscordNotFoundError(DiscordAPIError):
    """Ressource absente ou inaccessible (404)."""


class DiscordRateLimitError(DiscordAPIError):
    """Limite de debit persistante (429)."""


def valid_snowflake(value) -> bool:
    """Verifie la forme d'un identifiant Discord (15 a 22 chiffres)."""
    return isinstance(value, str) and value.isdigit() and 15 <= len(value) <= 22


MOTIF_JETON = re.compile(
    r"(?i)\b(?:bot|bearer)\s+[A-Za-z0-9._-]{20,}")
MOTIF_JETON_COMPOSE = re.compile(
    r"[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{20,}")


def redact(texte, secrets=()):
    """Retire les secrets connus et les formes de jetons d'un texte."""
    resultat = str(texte or "")
    resultat = MOTIF_JETON.sub("[masque]", resultat)
    resultat = MOTIF_JETON_COMPOSE.sub("[masque]", resultat)
    for secret in secrets:
        if secret and len(str(secret)) >= 8:
            resultat = resultat.replace(str(secret), "[masque]")
    return resultat


def normaliser_jeton(brut):
    """Nettoie un token colle a la main (espaces, guillemets, prefixe).

    Retourne une chaine vide si rien d'exploitable. Le resultat n'est jamais
    journalise ni ecrit sur le disque.
    """
    texte = str(brut or "").strip()
    for guillemet in ('"', "'", "`"):
        texte = texte.strip(guillemet).strip()
    while True:
        minuscule = texte.casefold()
        if minuscule.startswith("bot "):
            texte = texte[4:].strip()
        elif minuscule.startswith("bearer "):
            texte = texte[7:].strip()
        else:
            break
    return texte


def forme_jeton_discord(jeton):
    """Vrai si la valeur a la forme d'un token Discord (3 parties)."""
    parties = str(jeton or "").split(".")
    return len(parties) == 3 and all(len(partie) >= 6 for partie in parties)


def conseils_jeton_bot(jeton):
    """Pistes de diagnostic quand l'authentification ``Bot <jeton>`` echoue.

    Ne contient aucun secret : les conseils ne citent jamais le token recu.
    """
    conseils = []
    if not forme_jeton_discord(jeton):
        conseils.append("La valeur ne ressemble pas a un token Discord complet "
                        "(3 parties separees par des points).")
    conseils.extend([
        "Recopie le token depuis le portail developpeur : Applications > "
        "ton application > Bot > Reset Token.",
        "Un token de compte utilisateur ou un secret OAuth2 ne fonctionne "
        "pas ici : seul un token de bot est accepte (aucun selfbot).",
        "Un token regenere ou revoque ne fonctionne plus : si le token a ete "
        "expose (capture, depot Git, journal, message), revoque-le puis "
        "reinitialise-le depuis le portail developpeur.",
    ])
    return conseils


def formater_erreur_api(status, message):
    """Message d'erreur lisible sans exposer la requete ni le token."""
    if status == 401:
        return "Token refuse ou revoque (HTTP 401)."
    if status == 403:
        return f"Permissions insuffisantes (HTTP 403){' : ' + message if message else '.'}"
    if status == 404:
        return f"Ressource introuvable (HTTP 404){' : ' + message if message else '.'}"
    return f"HTTP {status}{' : ' + message if message else ''}"


class DiscordAPI:
    """Petit client REST synchrone, injectable pour les tests."""

    def __init__(self, token, token_type="Bot", session=None, timeout=TIMEOUT_DEFAUT,
                 max_retries=MAX_RETRIES_DEFAUT, sleep=time.sleep,
                 max_rate_limit_wait=ATTENTE_RATE_LIMIT_MAX):
        if not token or not isinstance(token, str):
            raise ValueError("Token Discord absent.")
        self._token = token.strip()
        self.token_type = token_type
        self._session = session or requests.Session()
        self.timeout = timeout
        self.max_retries = max(0, int(max_retries))
        self._sleep = sleep
        self.max_rate_limit_wait = max_rate_limit_wait

    # ------------------------------------------------------------------
    # Transport
    # ------------------------------------------------------------------
    def headers(self):
        return {
            "Authorization": f"{self.token_type} {self._token}",
            "User-Agent": "LeakFr-Tools (https://github.com/darkerorr/LeakFr-Tools)",
            "Content-Type": "application/json",
        }

    def close(self):
        try:
            self._session.close()
        except (AttributeError, OSError):
            pass

    def request(self, method, path, params=None, payload=None, reason=None,
                expected=(200,)):
        """Execute une requete bornee et retourne le JSON decode.

        Les 429 sont reessayes en respectant ``retry_after`` dans une limite
        globale ; les 5xx sont reessayes avec un court backoff. Aucun message
        d'erreur ne contient le token.
        """
        if not path.startswith("/"):
            raise ValueError("Chemin API invalide.")
        url = BASE_URL + path
        headers = self.headers()
        if reason:
            headers["X-Audit-Log-Reason"] = quote(reason[:512], safe="")
        kwargs = {"headers": headers, "timeout": self.timeout}
        if params:
            kwargs["params"] = params
        if payload is not None:
            kwargs["json"] = payload

        tentatives = 0
        attente_cumulee = 0.0
        while True:
            try:
                response = self._session.request(method, url, **kwargs)
            except requests.RequestException as exc:
                if tentatives < self.max_retries:
                    tentatives += 1
                    self._sleep(min(2 ** tentatives, 5))
                    continue
                raise DiscordAPIError(
                    f"Erreur reseau : {type(exc).__name__}") from None

            status = response.status_code
            if status == 429:
                retry_after = self._retry_after(response)
                attente_cumulee += retry_after
                if (tentatives >= self.max_retries
                        or attente_cumulee > self.max_rate_limit_wait):
                    raise DiscordRateLimitError(
                        "Limite de debit Discord atteinte (429) : "
                        f"reessayez dans {retry_after:.1f} s.", status=429)
                tentatives += 1
                self._sleep(min(retry_after, 5.0))
                continue

            if 500 <= status < 600 and tentatives < self.max_retries:
                tentatives += 1
                self._sleep(min(2 ** tentatives, 5))
                continue

            message = self._message_erreur(response)
            if status == 401:
                raise DiscordAuthError(formater_erreur_api(401, message), status=401)
            if status == 403:
                raise DiscordForbiddenError(formater_erreur_api(403, message), status=403)
            if status == 404:
                raise DiscordNotFoundError(formater_erreur_api(404, message), status=404)
            if status not in expected:
                raise DiscordAPIError(formater_erreur_api(status, message), status=status)

            if status == 204:
                return None
            try:
                return response.json()
            except (ValueError, AttributeError):
                raise DiscordAPIError(
                    f"Reponse API non JSON (HTTP {status}).", status=status) from None

    def _retry_after(self, response):
        donnees = self._json(response, defaut={})
        valeur = donnees.get("retry_after")
        if valeur is None:
            try:
                valeur = float(response.headers.get("Retry-After", "1"))
            except (TypeError, ValueError):
                valeur = 1.0
        try:
            return max(0.0, float(valeur))
        except (TypeError, ValueError):
            return 1.0

    @staticmethod
    def _json(response, defaut=None):
        try:
            return response.json()
        except (ValueError, AttributeError):
            return {} if defaut is None else defaut

    def _message_erreur(self, response):
        """Message d'erreur externe, toujours expurge avant affichage."""
        donnees = self._json(response, defaut={})
        if isinstance(donnees, dict):
            return redact(str(donnees.get("message") or ""))[:300]
        return ""

    # ------------------------------------------------------------------
    # Endpoints utilises par les panels
    # ------------------------------------------------------------------
    def me(self):
        return self.request("GET", "/users/@me")

    def my_guilds(self):
        return self.request("GET", "/users/@me/guilds")

    def guild(self, guild_id, avec_comptes=True):
        _verifier_id(guild_id, "serveur")
        return self.request("GET", f"/guilds/{guild_id}",
                            params={"with_counts": "true"} if avec_comptes else None)

    def guild_channels(self, guild_id):
        _verifier_id(guild_id, "serveur")
        return self.request("GET", f"/guilds/{guild_id}/channels")

    def guild_roles(self, guild_id):
        _verifier_id(guild_id, "serveur")
        return self.request("GET", f"/guilds/{guild_id}/roles")

    def guild_member(self, guild_id, user_id):
        _verifier_id(guild_id, "serveur")
        _verifier_id(user_id, "membre")
        return self.request("GET", f"/guilds/{guild_id}/members/{user_id}")

    def guild_members(self, guild_id, limite=100):
        _verifier_id(guild_id, "serveur")
        limite = max(1, min(int(limite), 1000))
        return self.request("GET", f"/guilds/{guild_id}/members",
                            params={"limit": limite})

    def guild_webhooks(self, guild_id):
        _verifier_id(guild_id, "serveur")
        return self.request("GET", f"/guilds/{guild_id}/webhooks")

    def creer_webhook(self, channel_id, payload, reason=None):
        _verifier_id(channel_id, "salon")
        if not isinstance(payload, dict) or not str(payload.get("name") or "").strip():
            raise ValueError("Nom de webhook obligatoire.")
        return self.request("POST", f"/channels/{channel_id}/webhooks",
                            payload=payload, reason=reason, expected=(200, 201))

    def supprimer_webhook(self, webhook_id, reason=None):
        _verifier_id(webhook_id, "webhook")
        return self.request("DELETE", f"/webhooks/{webhook_id}",
                            reason=reason, expected=(204,))

    def channel(self, channel_id):
        _verifier_id(channel_id, "salon")
        return self.request("GET", f"/channels/{channel_id}")

    def envoyer_message(self, channel_id, payload, reason=None):
        _verifier_id(channel_id, "salon")
        if not isinstance(payload, dict) or not payload:
            raise ValueError("Payload de message vide.")
        return self.request("POST", f"/channels/{channel_id}/messages",
                            payload=payload, reason=reason, expected=(200, 201))

    def creer_salon(self, guild_id, payload, reason=None):
        _verifier_id(guild_id, "serveur")
        return self.request("POST", f"/guilds/{guild_id}/channels",
                            payload=payload, reason=reason, expected=(200, 201))

    def modifier_salon(self, channel_id, payload, reason=None):
        _verifier_id(channel_id, "salon")
        return self.request("PATCH", f"/channels/{channel_id}",
                            payload=payload, reason=reason, expected=(200,))

    def creer_invitation(self, channel_id, payload=None, reason=None):
        _verifier_id(channel_id, "salon")
        return self.request("POST", f"/channels/{channel_id}/invites",
                            payload=payload or {}, reason=reason, expected=(200, 201))

    def modifier_membre(self, guild_id, user_id, payload, reason=None):
        _verifier_id(guild_id, "serveur")
        _verifier_id(user_id, "membre")
        return self.request("PATCH", f"/guilds/{guild_id}/members/{user_id}",
                            payload=payload, reason=reason, expected=(200, 204))

    def modifier_propre_membre(self, guild_id, payload, reason=None):
        _verifier_id(guild_id, "serveur")
        return self.request("PATCH", f"/guilds/{guild_id}/members/@me",
                            payload=payload, reason=reason, expected=(200, 204))

    def expulser_membre(self, guild_id, user_id, reason=None):
        _verifier_id(guild_id, "serveur")
        _verifier_id(user_id, "membre")
        return self.request("DELETE", f"/guilds/{guild_id}/members/{user_id}",
                            reason=reason, expected=(204,))

    def modifier_role(self, guild_id, role_id, payload, reason=None):
        _verifier_id(guild_id, "serveur")
        _verifier_id(role_id, "role")
        return self.request("PATCH", f"/guilds/{guild_id}/roles/{role_id}",
                            payload=payload, reason=reason, expected=(200,))

    def creer_role(self, guild_id, payload, reason=None):
        _verifier_id(guild_id, "serveur")
        if not isinstance(payload, dict) or not str(payload.get("name") or "").strip():
            raise ValueError("Nom de role obligatoire.")
        return self.request("POST", f"/guilds/{guild_id}/roles",
                            payload=payload, reason=reason, expected=(200, 201))

    def supprimer_role(self, guild_id, role_id, reason=None):
        _verifier_id(guild_id, "serveur")
        _verifier_id(role_id, "role")
        return self.request("DELETE", f"/guilds/{guild_id}/roles/{role_id}",
                            reason=reason, expected=(204,))

    def modifier_positions_roles(self, guild_id, positions, reason=None):
        _verifier_id(guild_id, "serveur")
        if not isinstance(positions, list) or not positions:
            raise ValueError("Liste de positions vide.")
        return self.request("PATCH", f"/guilds/{guild_id}/roles",
                            payload=positions, reason=reason, expected=(200, 204))

    def guild_emojis(self, guild_id):
        _verifier_id(guild_id, "serveur")
        return self.request("GET", f"/guilds/{guild_id}/emojis")

    def creer_emoji(self, guild_id, payload, reason=None):
        _verifier_id(guild_id, "serveur")
        if not isinstance(payload, dict) or not payload.get("name") or not payload.get("image"):
            raise ValueError("Nom et image d'emoji obligatoires.")
        return self.request("POST", f"/guilds/{guild_id}/emojis",
                            payload=payload, reason=reason, expected=(200, 201))

    def envoyer_fichier(self, channel_id, contenu, nom_fichier, donnees,
                        content_type="application/octet-stream", payload=None,
                        reason=None):
        """Envoie une piece jointe via multipart (upload Discord)."""
        _verifier_id(channel_id, "salon")
        if not donnees:
            raise ValueError("Fichier vide.")
        nom_fichier = str(nom_fichier or "fichier").replace("/", "_").replace("\\", "_")
        url = BASE_URL + f"/channels/{channel_id}/messages"
        corps = dict(payload or {})
        if contenu:
            corps["content"] = str(contenu)[:2000]
        headers = {"Authorization": f"{self.token_type} {self._token}",
                   "User-Agent": "LeakFr-Tools (https://github.com/darkerorr/LeakFr-Tools)"}
        if reason:
            headers["X-Audit-Log-Reason"] = quote(reason[:512], safe="")
        fichiers = {"files[0]": (nom_fichier, donnees, content_type)}
        for tentative in range(self.max_retries + 1):
            try:
                reponse = self._session.post(
                    url, headers=headers, data={"payload_json": json.dumps(corps)},
                    files=fichiers, timeout=self.timeout)
            except requests.RequestException as exc:
                if tentative < self.max_retries:
                    self._sleep(min(2 ** (tentative + 1), 5))
                    continue
                raise DiscordAPIError(
                    f"Erreur reseau : {type(exc).__name__}") from None
            if reponse.status_code == 429 and tentative < self.max_retries:
                self._sleep(min(self._retry_after(reponse), 5.0))
                continue
            message = self._message_erreur(reponse)
            if reponse.status_code == 401:
                raise DiscordAuthError(formater_erreur_api(401, message), status=401)
            if reponse.status_code == 403:
                raise DiscordForbiddenError(formater_erreur_api(403, message), status=403)
            if reponse.status_code == 404:
                raise DiscordNotFoundError(formater_erreur_api(404, message), status=404)
            if reponse.status_code == 429:
                raise DiscordRateLimitError(
                    "Limite de debit Discord atteinte (429) pour l'envoi du fichier.",
                    status=429)
            if reponse.status_code not in (200, 201):
                raise DiscordAPIError(
                    formater_erreur_api(reponse.status_code, message),
                    status=reponse.status_code)
            try:
                return reponse.json()
            except (ValueError, AttributeError):
                raise DiscordAPIError(
                    f"Reponse API non JSON (HTTP {reponse.status_code}).",
                    status=reponse.status_code) from None
        raise DiscordRateLimitError("Envoi du fichier impossible (429).", status=429)


def _verifier_id(valeur, libelle):
    if not valid_snowflake(str(valeur or "")):
        raise ValueError(f"Identifiant de {libelle} invalide.")
