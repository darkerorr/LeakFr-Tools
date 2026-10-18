"""Clé API NASA réellement utilisée par les outils d'astronomie.

Ordre de priorité : variable d'environnement ``NASA_API_KEY``, réglage local
``api_keys.nasa_api_key`` (Paramètres → Clé API NASA), puis la clé publique
``DEMO_KEY`` fournie par la NASA. La source réellement utilisée est retournée
pour être affichée : aucune clé n'est inventée ni mise en cache.
"""
import os

CLE_PUBLIQUE ="DEMO_KEY"
CLE_REGLAGE ="nasa_api_key"


def cle_api():
    """Retourne ``(clé, source lisible)`` pour l'API NASA."""
    env = (os.environ.get("NASA_API_KEY") or "").strip()
    if env:
        return env, "variable d'environnement NASA_API_KEY"
    try:
        from core.config import charger
        config = charger()
        cle= str((config.get("api_keys") or {}).get(CLE_REGLAGE) or "").strip()
    except Exception:
        cle = ''
    if cle:
        return cle, "réglage local api_keys.nasa_api_key"
    return CLE_PUBLIQUE, 'clé publique DEMO_KEY (limitée à quelques requêtes)'


def params_nasa(supplement=None):
    """Paramètres de requête avec la clé réellement disponible."""
    cle, source = cle_api()
    params = {'api_key': cle}
    if supplement:
        params.update(supplement)
    return params, source


def avertir_si_publique(source) -> bool:
    """Vrai si la clé publique est utilisée (message affiché par l'appelant)."""
    return CLE_PUBLIQUE in source
