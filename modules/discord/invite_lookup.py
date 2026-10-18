from datetime import datetime, timezone
import requests
from core.common import DISCORD_EPOCH, demander, titre, ok, bad, kv, attente, C_DISCORD

def invite_lookup():
    titre('DISCORD INVITE RESOLVER & OSINT', C_DISCORD)
    inv =demander("Code d'invitation ou lien (ex: discord.gg/python ou 'python')")
    code = inv.split("/")[-1].strip()
    if not code:
        bad("Code d'invitation manquant.")
        return

    try:
        with attente(f"Résolution de l'invitation '{code}'"):
            r = requests.get(f"https://discord.com/api/v10/invites/{code}?with_counts=true&with_expiration=true", timeout=8)
    except Exception as e:
        bad(f"Erreur de connexion : {e}")
        return

    if r.status_code == 404:
        bad("L'invitation est invalide, expirée ou le serveur est banni.")
        return
    elif r.status_code!=200:
        bad(f"Code HTTP {r.status_code} ({r.text})")
        return

    d = r.json()
    guild = d.get("guild", {})
    channel = d.get("channel", {})
    inviter = d.get('inviter', {})

    guild_id = guild.get("id", "?")
    date_crea_serveur ='?'
    if guild_id.isdigit():
        ts_ms = (int(guild_id) >> 22) + DISCORD_EPOCH
        dt=datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc)
        date_crea_serveur =dt.strftime("%d/%m/%Y %H:%M:%S UTC")

    features = ', '.join(guild.get('features', [])) or 'Aucune'

    lignes= [
        ('Nom du Serveur', guild.get('name', 'Inconnu')),
        ("ID du Serveur", guild_id),
        ("Date création serveur", date_crea_serveur),
        ('Description', guild.get('description') or 'Aucune'),
        ("Membres totaux", str(d.get("approximate_member_count", "Inconnu"))),
        ("Membres en ligne", str(d.get("approximate_presence_count", "Inconnu"))),
        ('Niveau de boost (Tier)', f"Tier {guild.get("premium_tier", 0)}"),
        ("Salon d'arrivée (Channel)", f"#{channel.get('name', '?')} (ID: {channel.get('id', '-')})"),
        ("Features serveur", features[:90] + ("..." if len(features) > 90 else "")),
    ]

    if inviter:
        tag_inv = f"{inviter.get("username", "?")}#{inviter.get("discriminator", "0")}"
        lignes.append(("Créateur de l'invitation", tag_inv))
        lignes.append(("ID du créateur", str(inviter.get("id", "-"))))

    expires_at = d.get("expires_at")
    lignes.append(("Expire le", expires_at if expires_at else "Invitation permanente"))

    icon = guild.get("icon")
    if icon and guild_id:
        lignes.append(('Icône URL', f"https://cdn.discordapp.com/icons/{guild_id}/{icon}.png"))

    kv("Fiche Serveur Discord", lignes, C_DISCORD)
    ok(f"Serveur détecté : {guild.get("name")}")
