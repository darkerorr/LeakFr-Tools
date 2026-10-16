from datetime import datetime, timezone
import requests
from core.common import DISCORD_EPOCH, demander, titre, bad, kv, attente, C_DISCORD, HEADERS

def discord_id_lookup():
    titre("DISCORD ID LOOKUP & SNOWFLAKE DECODER", C_DISCORD)
    user_id = demander("ID Discord / Snowflake (ex: 155149108183695360)")
    if not user_id.isdigit():
        bad("L'ID Discord doit être uniquement composé de chiffres.")
        return

    uid_int = int(user_id)
    # Décodage Snowflake
    timestamp_ms = (uid_int >> 22) + DISCORD_EPOCH
    creation_dt = datetime.fromtimestamp(timestamp_ms / 1000.0, tz=timezone.utc)
    worker_id = (uid_int & 0x3E0000) >> 17
    process_id = (uid_int & 0x1F000) >> 12
    increment = uid_int & 0xFFF

    lignes = [
        ("Snowflake ID", user_id),
        ("Date de création (UTC)", creation_dt.strftime("%d/%m/%Y %H:%M:%S UTC")),
        ("Timestamp Epoch (ms)", str(timestamp_ms)),
        ("Worker ID interne", str(worker_id)),
        ("Process ID interne", str(process_id)),
        ("Incrément", str(increment)),
    ]

    # Tentative d'interrogation de l'API publique Discord (via lookup endpoint ou bot token si dispo)
    try:
        with attente("Interrogation des données publiques Discord"):
            # Endpoint public d'invitation ou widgets
            r = requests.get(f"https://discord.com/api/v9/users/{user_id}", headers=HEADERS, timeout=5)
            if r.status_code == 200:
                data = r.json()
                username = data.get("username", "?")
                discrim = data.get("discriminator", "0")
                avatar = data.get("avatar")
                banner = data.get("banner")
                bot = "Oui" if data.get("bot") else "Non"
                tag = f"{username}#{discrim}" if discrim != "0" else username
                lignes.extend([
                    ("Tag Discord", tag),
                    ("Est un Bot ?", bot),
                    ("Avatar URL", f"https://cdn.discordapp.com/avatars/{user_id}/{avatar}.png" if avatar else "Aucun"),
                    ("Bannière URL", f"https://cdn.discordapp.com/banners/{user_id}/{banner}.png" if banner else "Aucune"),
                ])
    except Exception:
        pass

    lignes.append(("Profil Web", f"https://discord.com/users/{user_id}"))
    kv("Fiche Discord Snowflake", lignes, C_DISCORD)
