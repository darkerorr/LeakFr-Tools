"""Flux OAuth2 officiel de Discord (authorization code + PKCE).

Le panel ne demande que ``identify`` et ``guilds``. Aucun token utilisateur
copie manuellement n'est accepte : le code est obtenu par le navigateur et
echange cote application, avec un verificateur PKCE.
"""
import base64
import hashlib
import os
import secrets
import threading
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import requests

from core.config import DATA_DIR
from modules.discord.local_store import charger_json, ecrire_json
from modules.discord.personal.errors import OAuthError, ScopeError

AUTHORIZE_URL = "https://discord.com/oauth2/authorize"
TOKEN_URL = "https://discord.com/api/oauth2/token"
REVOKE_URL = "https://discord.com/api/oauth2/token/revoke"
SCOPES_AUTORISES = ("identify", "guilds")
REDIRECT_DEFAUT = "http://127.0.0.1:8765/callback"
CONFIG_FILE = Path(DATA_DIR) / "discord_oauth.json"


@dataclass
class OAuthConfig:
    client_id: str
    client_secret: str = field(default="", repr=False)
    redirect_uri: str = REDIRECT_DEFAUT
    scopes: tuple = SCOPES_AUTORISES

    def url_redirigee(self):
        analyse = urlparse(self.redirect_uri)
        if analyse.scheme != "http" or analyse.hostname not in {"127.0.0.1", "localhost"}:
            raise OAuthError("L'URI de redirection doit pointer vers la boucle locale.")
        return analyse


def pkce_pair():
    """Retourne (verificateur, challenge S256) conformes RFC 7636."""
    verificateur = secrets.token_urlsafe(64)[:96]
    digest = hashlib.sha256(verificateur.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verificateur, challenge


def nouvel_etat():
    return secrets.token_urlsafe(24)


def valider_client_id(client_id):
    client_id = str(client_id or "").strip()
    if not client_id.isdigit() or not 15 <= len(client_id) <= 22:
        raise OAuthError("Client ID Discord invalide (15 a 22 chiffres attendus).")
    return client_id


def authorization_url(config, state, code_challenge):
    """Construit l'URL d'autorisation officielle, sans secret client."""
    valider_client_id(config.client_id)
    if not state or not code_challenge:
        raise OAuthError("Etat ou challenge PKCE absent.")
    params = {
        "client_id": config.client_id,
        "response_type": "code",
        "redirect_uri": config.redirect_uri,
        "scope": " ".join(config.scopes),
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return f"{AUTHORIZE_URL}?{urlencode(params)}"


def scopes_accordes(scope):
    if isinstance(scope, (list, tuple)):
        return tuple(str(item) for item in scope)
    return tuple(part for part in str(scope or "").split() if part)


def valider_scopes(demandes, accordes):
    """Refuse un scope non prevu par le panel."""
    demandes = set(demandes)
    accordes = set(accordes)
    inconnus = demandes - set(SCOPES_AUTORISES)
    if inconnus:
        raise ScopeError("Scopes demandes non autorises : " + ", ".join(sorted(inconnus)))
    excedentaires = accordes - demandes
    if excedentaires:
        raise ScopeError("Scopes accordes non demandes : " + ", ".join(sorted(excedentaires)))
    return sorted(accordes)


def _erreur_oauth(donnees, defaut):
    description = ""
    if isinstance(donnees, dict):
        description = str(donnees.get("error_description") or donnees.get("error") or "")
    return OAuthError(description[:300] if description else defaut)


def echanger_code(config, code, verificateur, session=requests, timeout=10):
    """Echange le code d'autorisation contre un jeton, sans le journaliser."""
    if not code:
        raise OAuthError("Code d'autorisation absent.")
    donnees = {
        "client_id": config.client_id,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": config.redirect_uri,
        "code_verifier": verificateur,
    }
    if config.client_secret:
        donnees["client_secret"] = config.client_secret
    try:
        reponse = session.post(TOKEN_URL, data=donnees,
                               headers={"Content-Type": "application/x-www-form-urlencoded"},
                               timeout=timeout)
    except requests.RequestException as exc:
        raise OAuthError(f"Echange OAuth2 impossible : {type(exc).__name__}") from None
    try:
        contenu = reponse.json()
    except ValueError:
        contenu = {}
    if reponse.status_code != 200:
        raise _erreur_oauth(contenu, f"Echange OAuth2 refuse (HTTP {reponse.status_code}).")
    jeton = contenu.get("access_token")
    if not jeton:
        raise OAuthError("Reponse OAuth2 sans access_token.")
    accordes = scopes_accordes(contenu.get("scope"))
    valider_scopes(config.scopes, accordes)
    return {
        "access_token": jeton,
        "refresh_token": contenu.get("refresh_token") or "",
        "token_type": contenu.get("token_type") or "Bearer",
        "expires_in": contenu.get("expires_in"),
        "scope": accordes,
    }


def rafraichir(config, refresh_token, session=requests, timeout=10):
    if not refresh_token:
        raise OAuthError("Aucun refresh token disponible.")
    donnees = {"client_id": config.client_id, "grant_type": "refresh_token",
               "refresh_token": refresh_token}
    if config.client_secret:
        donnees["client_secret"] = config.client_secret
    try:
        reponse = session.post(TOKEN_URL, data=donnees,
                               headers={"Content-Type": "application/x-www-form-urlencoded"},
                               timeout=timeout)
    except requests.RequestException as exc:
        raise OAuthError(f"Rafraichissement OAuth2 impossible : {type(exc).__name__}") from None
    contenu = reponse.json() if reponse.status_code == 200 else {}
    if reponse.status_code != 200 or not contenu.get("access_token"):
        raise _erreur_oauth(contenu, "Rafraichissement OAuth2 refuse.")
    return {"access_token": contenu["access_token"],
            "refresh_token": contenu.get("refresh_token") or refresh_token,
            "token_type": contenu.get("token_type") or "Bearer",
            "expires_in": contenu.get("expires_in"),
            "scope": scopes_accordes(contenu.get("scope"))}


def revoquer(config, token, session=requests, timeout=10, hint="access_token"):
    """Revoque un jeton aupres de Discord ; ne leve pas pour un jeton deja invalide."""
    if not token:
        return False
    donnees = {"token": token, "token_type_hint": hint, "client_id": config.client_id}
    if config.client_secret:
        donnees["client_secret"] = config.client_secret
    try:
        reponse = session.post(REVOKE_URL, data=donnees,
                               headers={"Content-Type": "application/x-www-form-urlencoded"},
                               timeout=timeout)
    except requests.RequestException:
        return False
    return reponse.status_code in (200, 204)


class _CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        analyse = urlparse(self.path)
        if analyse.path != self.server.chemin_attendu:
            self.send_error(404)
            return
        params = parse_qs(analyse.query)
        etat = (params.get("state") or [""])[0]
        if not secrets.compare_digest(etat, self.server.etat_attendu):
            self.server.erreur = "Etat OAuth2 invalide : autorisation refusee."
        elif params.get("error"):
            self.server.erreur = "Autorisation refusee : " + (params.get("error") or [""])[0]
        else:
            self.server.code = (params.get("code") or [""])[0] or None
            if not self.server.code:
                self.server.erreur = "Aucun code d'autorisation recu."
        corps = ("<html><body><h2>LeakFr-Tools</h2><p>"
                 + ("Autorisation recue, vous pouvez fermer cet onglet."
                    if self.server.code else "Autorisation refusee.")
                 + "</p></body></html>").encode("utf-8")
        self.send_response(200 if self.server.code else 400)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(corps)))
        self.end_headers()
        self.wfile.write(corps)
        self.server.termine.set()

    def log_message(self, *_args):
        pass


def attendre_callback(config, etat, timeout=180, serveur_factory=HTTPServer):
    """Ecoute le callback loopback et retourne le code d'autorisation."""
    analyse = config.url_redirigee()
    port = analyse.port or 80
    try:
        serveur = serveur_factory((analyse.hostname, port), _CallbackHandler)
    except OSError as exc:
        raise OAuthError(f"Impossible d'ecouter sur {analyse.hostname}:{port} : {exc}") from None
    serveur.chemin_attendu = analyse.path or "/"
    serveur.etat_attendu = etat
    serveur.code = None
    serveur.erreur = None
    serveur.termine = threading.Event()
    thread = threading.Thread(target=serveur.serve_forever, daemon=True)
    thread.start()
    try:
        if not serveur.termine.wait(timeout):
            raise OAuthError("Delai d'autorisation depasse (callback non recu).")
        if serveur.erreur:
            raise OAuthError(serveur.erreur)
        if not serveur.code:
            raise OAuthError("Aucun code d'autorisation recu.")
        return serveur.code
    finally:
        serveur.shutdown()
        serveur.server_close()


# ---------------------------------------------------------------------------
# Configuration locale
# ---------------------------------------------------------------------------

def _depuis_environnement(environ=None):
    env = os.environ if environ is None else environ
    return {cle: env.get(cle) for cle in
            ("DISCORD_CLIENT_ID", "DISCORD_CLIENT_SECRET", "DISCORD_REDIRECT_URI")}


def charger_config(environ=None, path=None):
    """Charge la configuration depuis l'environnement puis le fichier local."""
    env = _depuis_environnement(environ)
    fichier = charger_json(path or CONFIG_FILE, {})
    if not isinstance(fichier, dict):
        fichier = {}
    client_id = env.get("DISCORD_CLIENT_ID") or fichier.get("client_id")
    if not client_id:
        return None
    secret = env.get("DISCORD_CLIENT_SECRET")
    if secret is None:
        secret = fichier.get("client_secret") or ""
    redirect = env.get("DISCORD_REDIRECT_URI") or fichier.get("redirect_uri") or REDIRECT_DEFAUT
    try:
        client_id = valider_client_id(client_id)
    except OAuthError:
        return None
    return OAuthConfig(client_id=client_id, client_secret=str(secret or ""),
                       redirect_uri=redirect)


def sauvegarder_config(config, path=None):
    """Ecrit la configuration (client secret inclus) avec permissions 600."""
    if not isinstance(config, OAuthConfig):
        raise OAuthError("Configuration OAuth2 invalide.")
    ecrire_json(path or CONFIG_FILE, {"client_id": config.client_id,
                                      "client_secret": config.client_secret,
                                      "redirect_uri": config.redirect_uri})
    return path or CONFIG_FILE
