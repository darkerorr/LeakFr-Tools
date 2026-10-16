from datetime import datetime, timezone
import requests
from core.common import DISCORD_EPOCH, demander, titre, ok, bad, kv, attente, C_DISCORD

def bot_token_info():
    titre("DISCORD BOT TOKEN INFO & CHECKER", C_DISCORD)
    token = demander("Token du Bot Discord")
    if not token or "." not in token:
        bad("Format de token Bot invalide (doit contenir des points).")
        return

    headers = {
        "Authorization": f"Bot {token.strip()}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }

    try:
        with attente("Interrogation de l'API Discord Bot"):
            r = requests.get("https://discord.com/api/v10/users/@me", headers=headers, timeout=8)
    except Exception as e:
        bad(f"Erreur de connexion : {e}")
        return

    if r.status_code == 401:
        bad("Token Bot invalide ou révoqué (HTTP 401 Unauthorized).")
        return
    elif r.status_code != 200:
        bad(f"Réponse inattendue de Discord : HTTP {r.status_code} ({r.text})")
        return

    data = r.json()
    bot_id = data.get("id", "?")
    date_crea = "?"
    if bot_id.isdigit():
        ts_ms = (int(bot_id) >> 22) + DISCORD_EPOCH
        dt = datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc)
        date_crea = dt.strftime("%d/%m/%Y %H:%M:%S UTC")

    username = data.get("username", "?")
    discrim = data.get("discriminator", "0")
    tag = f"{username}#{discrim}" if discrim != "0" else username
    mfa = "Activée" if data.get("mfa_enabled") else "Désactivée"
    verified = "Oui" if data.get("verified") else "Non"

    lignes = [
        ("Nom du Bot", tag),
        ("ID Bot", bot_id),
        ("Création du Bot", date_crea),
        ("Bot vérifié", verified),
        ("2FA / MFA", mfa),
        ("Drapeaux publics (Flags)", str(data.get("public_flags", 0))),
        ("Lien d'invitation Admin", f"https://discord.com/oauth2/authorize?client_id={bot_id}&scope=bot&permissions=8"),
    ]

    # Nombre de serveurs où se trouve le bot
    try:
        guilds_res = requests.get("https://discord.com/api/v10/users/@me/guilds", headers=headers, timeout=6)
        if guilds_res.status_code == 200:
            guilds = guilds_res.json()
            lignes.append(("Serveurs rejoints", f"{len(guilds)} serveur(s)"))
            if guilds:
                noms_guilds = ", ".join([g.get("name", "?") for g in guilds[:5]])
                if len(guilds) > 5:
                    noms_guilds += f" (+{len(guilds)-5} autres)"
                lignes.append(("Exemples de serveurs", noms_guilds))
    except Exception:
        pass

    kv("Fiche Bot Discord", lignes, C_DISCORD)
    ok("Token Bot valide et fonctionnel !")
