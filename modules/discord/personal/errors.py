"""Erreurs du panel personnel Discord, sans secret dans les messages."""


class PersonalError(Exception):
    """Erreur de base du panel personnel."""


class OAuthError(PersonalError):
    """Echec du flux OAuth2 (configuration, callback, echange)."""


class ScopeError(OAuthError):
    """Scopes demandes ou accordes invalides."""


class PersonalAPIError(PersonalError):
    """Erreur lors d'un appel API autorise."""

    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


class TokenExpiredError(PersonalAPIError):
    """Le jeton OAuth2 est absent, expire ou revoque (401)."""


class StorageError(PersonalError):
    """Echec de lecture ou d'ecriture du stockage local."""
