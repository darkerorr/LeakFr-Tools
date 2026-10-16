from datetime import datetime, timezone
import requests
from core.common import DISCORD_EPOCH, demander, titre, ok, bad, kv, attente, C_DISCORD

def bot_invite_generator():
    titre("GÉNÉRATEUR D'INVITATION & OSINT APPLICATION DISCORD", C_DISCORD)
    app_id = demander("Client ID / Application ID du Bot")
    if not app_id.isdigit():
        bad("L'ID doit être composé uniquement de chiffres.")
        return

    uid_int = int(app_id)
    creation_dt = datetime.fromtimestamp(((uid_int >> 22) + DISCORD_EPOCH) / 1000.0, tz=timezone.utc)

    # Récupération données RPC / Application publique
    app_name = "Inconnu"
    app_desc = "-"
    icon_url = "-"
    try:
        with attente("Recherche des métadonnées de l'application"):
            r = requests.get(f"https://discord.com/api/v10/applications/{app_id}/rpc", timeout=5)
            if r.status_code == 200:
                data = r.json()
                app_name = data.get("name", "Inconnu")
                app_desc = data.get("description", "-")
                icon = data.get("icon")
                if icon:
                    icon_url = f"https://cdn.discordapp.com/app-icons/{app_id}/{icon}.png"
    except Exception:
        pass

    lignes = [
        ("Application ID", app_id),
        ("Nom de l'App", app_name),
        ("Description", app_desc or "Aucune"),
        ("Date de création", creation_dt.strftime("%d/%m/%Y %H:%M:%S UTC")),
        ("Icône de l'App", icon_url),
        ("Lien Invité Administrateur (perm 8)", f"https://discord.com/oauth2/authorize?client_id={app_id}&scope=bot&permissions=8"),
        ("Lien Invité Standard (perm 0)", f"https://discord.com/oauth2/authorize?client_id={app_id}&scope=bot&permissions=0"),
        ("Lien Slash Commands uniquement", f"https://discord.com/oauth2/authorize?client_id={app_id}&scope=applications.commands"),
        ("Lien Bot + Slash Commands", f"https://discord.com/oauth2/authorize?client_id={app_id}&scope=bot%20applications.commands&permissions=8"),
    ]

    kv("Liens OAuth2 & Fiche Application", lignes, C_DISCORD)
    ok("Liens d'invitations générés avec succès !")
