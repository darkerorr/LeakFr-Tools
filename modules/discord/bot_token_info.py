"""Fiche d'un Bot Discord a partir de son token, sans journaliser le secret."""
from datetime import datetime, timezone

from rich.prompt import Prompt

from core.common import C_DISCORD, DISCORD_EPOCH, bad, kv, ok, titre, warn
from modules.discord.discord_api import (
    DiscordAPI, DiscordAPIError, DiscordAuthError, conseils_jeton_bot, normaliser_jeton,
)


def bot_token_info():
    titre("DISCORD BOT TOKEN INFO & CHECKER", C_DISCORD)
    token = normaliser_jeton(Prompt.ask("[bold]Token du Bot Discord[/]", password=True))
    if not token:
        bad("Token absent.")
        return

    api =DiscordAPI(token)
    try:
        try:
            data=api.me()
        except DiscordAuthError:
            bad('Token Bot invalide, revoque ou de mauvais type (HTTP 401).')
            for conseil in conseils_jeton_bot(token):
                warn(conseil)
            return
        except DiscordAPIError as exc:
            bad(f"Verification impossible : {exc}")
            return

        bot_id =str(data.get("id", ""))
        date_crea='?'
        if bot_id.isdigit():
            dt= datetime.fromtimestamp(((int(bot_id) >> 22) + DISCORD_EPOCH) / 1000.0,
                                       tz=timezone.utc)
            date_crea=dt.strftime("%d/%m/%Y %H:%M:%S UTC")

        username = data.get('username', '?')
        discrim = str(data.get("discriminator") or "0")
        tag = f"{username}#{discrim}" if discrim !="0" else username

        lignes = [
            ("Nom du Bot", tag),
            ('ID Bot', bot_id),
            ("Creation du Bot", date_crea),
            ("Bot verifie", "Oui" if data.get("verified") else "Non"),
            ('2FA / MFA', 'Activee' if data.get('mfa_enabled') else 'Desactivee'),
            ("Drapeaux publics", str(data.get("public_flags", 0))),
        ]

        try:
            guilds = api.my_guilds()
        except DiscordAPIError as exc:
            lignes.append(("Serveurs rejoints", f"indisponible ({exc})"))
        else:
            lignes.append(('Serveurs rejoints', f"{len(guilds)} serveur(s)"))
            if guilds:
                noms = ", ".join(str(guild.get("name", "?")) for guild in guilds[:5])
                if len(guilds) > 5:
                    noms += f" (+{len(guilds) - 5} autres)"
                lignes.append(("Exemples de serveurs", noms))

        lignes.append(("Lien d'invitation (Administrateur)",
                       f"https://discord.com/oauth2/authorize?client_id={bot_id}"
                       '&scope=bot&permissions=8'))
        kv("Fiche Bot Discord", lignes, C_DISCORD)
        ok("Token Bot valide.")
        if int(data.get('public_flags', 0)) & (1 << 16):
            warn("Bot verifie par Discord ; verifiez tout de meme ses permissions.")
    finally:
        api.close()
