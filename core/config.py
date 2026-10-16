"""Configuration persistante de LeakFr-Tools.

Stocke les préférences utilisateur dans un fichier JSON sous data/.
Fournit des valeurs par défaut validées et une restauration propre.
"""
import json
import os
import sys

# Répertoire de données local (dans le dépôt)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")

# Chemins importants
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")
CASES_DB = os.path.join(DATA_DIR, "cases.db")
HISTORY_FILE = os.path.join(DATA_DIR, "history.json")
EXPORTS_DIR = os.path.join(DATA_DIR, "exports")
LOGS_DIR = os.path.join(DATA_DIR, "logs")

# ---------------------------------------------------------------------------
# Valeurs par défaut – chaque catégorie avec ses clés
# ---------------------------------------------------------------------------
DEFAUTS = {
    # Apparence
    "apparence": {
        "theme_actif": "original",
        "banniere_demarrage": True,
        "animations": True,
        "introduction_longue": True,
    },
    # Démarrage
    "demarrage": {
        "verifier_dependances": True,
        "afficher_version": True,
    },
    # Fonctionnement
    "fonctionnement": {
        "confirmation_sensible": True,
        "niveau_details": "normal",         # minimal / normal / verbose
        "effets_visuels": True,
    },
    # Réseau
    "reseau": {
        "timeout": 8,
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "max_redirects": 5,
        "dns_timeout": 3,
    },
    # Stockage
    "stockage": {
        "data_dir": DATA_DIR,
        "max_historique": 500,
        "sauvegarder_resultats": True,
    },
    # Journalisation
    "journalisation": {
        "niveau": "info",                  # debug / info / warning / error
        "fichier_log": os.path.join(LOGS_DIR, "leakfr.log"),
        "log_dans_terminal": True,
    },
    # Modules (paramètres spécifiques)
    "modules": {
        "osint": {},
        "recon": {},
        "cyber": {},
        "pentest": {},
        "discord": {},
        "utils": {},
        "astro": {},
    },
    # Clés API (jamais dans les logs)
    "api_keys": {},
    # Thème personnalisé (écrase theme_actif si "personnalise")
    "theme_personnalise": {
        "principale": "#ff5fd2",
        "secondaire": "#36d1ff",
        "titres": "#ffd166",
        "texte_principal": "#ffffff",
        "texte_secondaire": "#888888",
        "selection": "#ffffff",
        "bordures": "#888888",
        "accents": "#ff5fd2",
        "succes": "#4ade80",
        "avertissements": "#ffd166",
        "erreurs": "#ff5c7a",
        "panneaux": "#1a1a2e",
    },
}


def _assurer_repertoires():
    """Crée data/ et ses sous-dossiers si absents."""
    for d in (DATA_DIR, EXPORTS_DIR, LOGS_DIR):
        os.makedirs(d, exist_ok=True)


def charger() -> dict:
    """Charge les réglages depuis settings.json.

    Retourne un dictionnaire complet : les clés manquantes ou la totalité
    du fichier sont remplacées par les valeurs par défaut.
    """
    _assurer_repertoires()
    if not os.path.isfile(SETTINGS_FILE):
        return _deep_copy(DEFAUTS)

    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return _deep_copy(DEFAUTS)

    if not isinstance(data, dict):
        return _deep_copy(DEFAUTS)

    # Fusion récursive avec les défauts
    fusion = _deep_copy(DEFAUTS)
    _fusionner(fusion, data)
    return fusion


def sauvegarder(config: dict) -> bool:
    """Écrit la configuration dans settings.json."""
    _assurer_repertoires()
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return True
    except OSError:
        return False


def restaurer_defauts() -> dict:
    """Réinitialise et retourne la configuration par défaut."""
    config = _deep_copy(DEFAUTS)
    sauvegarder(config)
    return config


def obtenir(config: dict, cle: str, defaut=None):
    """Accès par points : config, 'apparence.theme_actif'."""
    parts = cle.split(".")
    val = config
    for p in parts:
        if isinstance(val, dict) and p in val:
            val = val[p]
        else:
            return defaut
    return val


def definir(config: dict, cle: str, valeur) -> dict:
    """Définit une valeur par chemin pointé."""
    parts = cle.split(".")
    target = config
    for p in parts[:-1]:
        target = target.setdefault(p, {})
    target[parts[-1]] = valeur
    return config


# ---------------------------------------------------------------------------
# Helpers internes
# ---------------------------------------------------------------------------

def _deep_copy(d):
    """Copie simple pour dicts imbriqués (JSON‑compatible)."""
    return json.loads(json.dumps(d))


def _fusionner(base, ajouts):
    """Fusion récursive : les valeurs de *ajouts* surchargent *base*."""
    for k, v in ajouts.items():
        if k in base and isinstance(base[k], dict) and isinstance(v, dict):
            _fusionner(base[k], v)
        else:
            base[k] = v