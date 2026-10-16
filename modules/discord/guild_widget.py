from datetime import datetime, timezone
import requests
from core.common import DISCORD_EPOCH, demander, titre, bad, kv, attente, C_DISCORD

def guild_widget_lookup():
    titre("DISCORD GUILD WIDGET & ONLINE MEMBERS OSINT", C_DISCORD)
    guild_id = demander("ID du Serveur Discord (Guild ID)")
    if not guild_id.isdigit():
        bad("L'ID doit être composé uniquement de chiffres.")
        return

    ts_ms = (int(guild_id) >> 22) + DISCORD_EPOCH
    creation_dt = datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc)

    # Récupération du widget JSON public
    url = f"https://discord.com/api/guilds/{guild_id}/widget.json"
    try:
        with attente("Interrogation du Widget public Discord"):
            r = requests.get(url, timeout=8)
    except Exception as e:
        bad(f"Erreur de contact : {e}")
        return

    lignes = [
        ("Guild ID", guild_id),
        ("Date de création", creation_dt.strftime("%d/%m/%Y %H:%M:%S UTC")),
    ]

    if r.status_code == 200:
        d = r.json()
        lignes.append(("Widget activé", "Oui (Données en direct accessibles)"))
        lignes.append(("Nom du serveur", d.get("name", "Inconnu")))
        lignes.append(("Membres en ligne actuels", str(len(d.get("members", [])))))
        lignes.append(("Salons vocaux ouverts", str(len(d.get("channels", [])))))
        inv = d.get("instant_invite")
        if inv:
            lignes.append(("Lien d'invitation généré", inv))

        members = d.get("members", [])
        if members:
            sample_members = []
            for m in members[:8]:
                pseudo = m.get("username", "?")
                status = m.get("status", "?")
                game = (m.get("game") or {}).get("name", "")
                desc = f"{pseudo} [{status}]" + (f" (Joue à {game})" if game else "")
                sample_members.append(desc)
            lignes.append(("Aperçu des membres en ligne", "\n".join(sample_members)))
    elif r.status_code == 403:
        lignes.append(("Widget activé", "Non (Le propriétaire a désactivé le widget public)"))
    elif r.status_code == 404:
        lignes.append(("Serveur trouvé", "Non (ID inconnu ou serveur inexistant)"))
    else:
        lignes.append(("Réponse HTTP", f"Code {r.status_code}"))

    kv("Résultats Widget Serveur", lignes, C_DISCORD)
