"""Journal local des operations du panel Bot.

Chaque entree est redigee avant ecriture : le token et les valeurs sensibles
fournies par l'appelant sont masques. Le journal ne contient ni message envoye
ni secret.
"""
from datetime import datetime, timezone
from pathlib import Path

from core.config import DATA_DIR
from modules.discord.discord_api import redact
from modules.discord.local_store import charger_json, ecrire_json

JOURNAL_FILE = Path(DATA_DIR) / "discord_panel_journal.json"
MAX_ENTREES = 300


def chemin_journal():
    return Path(JOURNAL_FILE)


def charger_journal(path=None):
    donnees = charger_json(path or chemin_journal(), [])
    if not isinstance(donnees, list):
        return []
    entrees = []
    for entree in donnees:
        if not isinstance(entree, dict):
            continue
        entrees.append({
            "timestamp": entree.get("timestamp"),
            "action": redact(entree.get("action"))[:120],
            "guild_id": str(entree.get("guild_id") or ""),
            "cible": redact(entree.get("cible"))[:80],
            "resultat": entree.get("resultat"),
            "detail": redact(entree.get("detail"))[:400],
        })
    return entrees[-MAX_ENTREES:]


def enregistrer(action, guild_id=None, cible=None, resultat="ok", detail="",
                secrets=(), path=None):
    """Ajoute une entree d'action, sans secret ni contenu de message brut."""
    entrees = charger_journal(path)
    entrees.append({
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "action": redact(action, secrets)[:120],
        "guild_id": str(guild_id or ""),
        "cible": redact(cible, secrets)[:80],
        "resultat": "ok" if resultat == "ok" else "erreur",
        "detail": redact(detail, secrets)[:400],
    })
    ecrire_json(path or chemin_journal(), entrees[-MAX_ENTREES:])
    return entrees[-1]


def derniers(limite=10, path=None):
    return list(reversed(charger_journal(path)))[:max(1, int(limite))]


def effacer(path=None):
    ecrire_json(path or chemin_journal(), [])
