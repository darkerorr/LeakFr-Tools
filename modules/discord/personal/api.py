"""Appels API Discord autorises par les scopes OAuth2 du panel personnel."""
import time
from urllib.parse import urlencode

import requests

from modules.discord.personal.errors import PersonalAPIError, TokenExpiredError

BASE_URL = "https://discord.com/api/v10"


class PersonalAPI:
    """Client Bearer limite aux scopes ``identify`` et ``guilds``."""

    def __init__(self, access_token, session=None, timeout=10, sleep=time.sleep):
        if not access_token:
            raise PersonalAPIError("Aucun jeton OAuth2 : connectez-vous d'abord.")
        self._token = access_token
        self._session = session or requests.Session()
        self.timeout = timeout
        self._sleep = sleep

    def close(self):
        try:
            self._session.close()
        except (AttributeError, OSError):
            pass

    def request(self, method, path, params=None, expected=(200,)):
        if not path.startswith("/"):
            raise ValueError("Chemin API invalide.")
        url = BASE_URL + path
        if params:
            url += "?" + urlencode(params)
        headers = {"Authorization": f"Bearer {self._token}",
                   "User-Agent": "LeakFr-Tools"}
        tentative = 0
        while True:
            try:
                reponse = self._session.request(method, url, headers=headers,
                                                timeout=self.timeout)
            except requests.RequestException as exc:
                raise PersonalAPIError(
                    f"Erreur reseau : {type(exc).__name__}") from None
            if reponse.status_code == 401:
                raise TokenExpiredError(
                    "Jeton OAuth2 expire ou revoque : reconnectez-vous.", status=401)
            if reponse.status_code == 429 and tentative < 1:
                tentative += 1
                try:
                    attente = float((reponse.json() or {}).get("retry_after", 1))
                except (ValueError, TypeError):
                    attente = 1.0
                self._sleep(min(max(attente, 0.0), 5.0))
                continue
            if reponse.status_code not in expected:
                try:
                    message = (reponse.json() or {}).get("message", "")
                except ValueError:
                    message = ""
                raise PersonalAPIError(
                    f"HTTP {reponse.status_code}"
                    + (f" : {message}" if message else ""),
                    status=reponse.status_code)
            if reponse.status_code == 204:
                return None
            try:
                return reponse.json()
            except ValueError:
                raise PersonalAPIError("Reponse API non JSON.") from None

    def me(self):
        return self.request("GET", "/users/@me")

    def guildes(self):
        return self.request("GET", "/users/@me/guilds")
