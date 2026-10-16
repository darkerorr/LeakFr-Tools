from datetime import datetime, timezone
import requests
from core.common import DISCORD_EPOCH, demander, titre, bad, kv, attente, C_DISCORD

def webhook_info():
    titre("DISCORD WEBHOOK INSPECTOR", C_DISCORD)
    webhook_url = demander("URL du Webhook Discord")
    if not webhook_url.startswith("https://discord.com/api/webhooks/") and not webhook_url.startswith("https://discordapp.com/api/webhooks/"):
        bad("Format d'URL de webhook Discord invalide.")
        return

    try:
        with attente("Interrogation de l'API Discord Webhook"):
            r = requests.get(webhook_url, timeout=8)
    except Exception as e:
        bad(f"Erreur de connexion : {e}")
        return

    if r.status_code == 404:
        bad("Le Webhook est introuvable ou a été supprimé.")
        return
    elif r.status_code != 200:
        bad(f"Code HTTP inattendu : {r.status_code} ({r.text})")
        return

    try:
        d = r.json()
    except Exception:
        bad("Impossible de décoder la réponse JSON.")
        return

    hook_id = d.get("id", "?")
    date_crea = "?"
    if hook_id.isdigit():
        ts_ms = (int(hook_id) >> 22) + DISCORD_EPOCH
        dt = datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc)
        date_crea = dt.strftime("%d/%m/%Y %H:%M:%S UTC")

    user_data = d.get("user", {})
    creator_tag = f"{user_data.get('username', '?')}#{user_data.get('discriminator', '0')}" if user_data else "Non disponible"

    lignes = [
        ("Nom du Webhook", d.get("name", "Sans nom")),
        ("ID Webhook", hook_id),
        ("Date de création", date_crea),
        ("Guild / Serveur ID", str(d.get("guild_id", "Aucun (DM/Inconnu)"))),
        ("Salon / Channel ID", str(d.get("channel_id", "Inconnu"))),
        ("Avatar Hash", str(d.get("avatar", "Par défaut"))),
        ("Type", "Incoming Webhook" if d.get("type") == 1 else f"Type {d.get('type')}"),
        ("Créateur du Webhook", creator_tag),
        ("ID du Créateur", str(user_data.get("id", "-"))),
        ("Token présent", "Oui (valide et actif)"),
    ]
    kv("Détails du Webhook", lignes, C_DISCORD)
