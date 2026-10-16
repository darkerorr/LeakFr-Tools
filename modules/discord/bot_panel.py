"""Panel de controle et d'audit pour Bot Discord.

Ameliore: organisation visuelle, hierarchie, lisibilite, messages d'erreur.
Preserve toutes les commandes et interactions existantes.
"""
from datetime import datetime, timezone
import json
import re
import unicodedata
from pathlib import Path

import requests
from rich.align import Align
from rich.console import Group
from rich.layout import Layout
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich.text import Text
from core.common import (
    console, titre, ok, bad, warn, demander, attente, pause, kv,
    BX, C_DISCORD, C_GOLD, DISCORD_EPOCH, warn_pentest
)
from core.config import EXPORTS_DIR
from modules.discord.gateway_bot import DiscordGatewayClient

STATUS_PRESETS = {
    "1": ("online", "En ligne (Online)", "bold green"),
    "2": ("idle", "Inactif (Idle / Absent)", "bold yellow"),
    "3": ("dnd", "Ne pas deranger (DND)", "bold red"),
    "4": ("invisible", "Invisible (Offline)", "dim"),
}

ACTIVITY_PRESETS = {
    "1": (0, "Joue a (Playing)", "cyan"),
    "2": (1, "En Stream (Streaming)", "magenta"),
    "3": (2, "Ecoute (Listening)", "green"),
    "4": (3, "Regarde (Watching)", "yellow"),
    "5": (5, "Participe a (Competing)", "blue"),
}


# ---------------------------------------------------------------------------
# Helpers reseau
# ---------------------------------------------------------------------------

def _fetch_bot_info(headers):
    try:
        r = requests.get("https://discord.com/api/v10/users/@me", headers=headers, timeout=8)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


def _fetch_bot_guilds(headers):
    try:
        r = requests.get("https://discord.com/api/v10/users/@me/guilds", headers=headers, timeout=8)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return []


def _fetch_guild_details(headers, guild_id):
    info = {"channels": [], "roles": [], "members": [], "guild": None}
    endpoints = [
        ("guild", f"https://discord.com/api/v10/guilds/{guild_id}", "guild"),
        ("channels", f"https://discord.com/api/v10/guilds/{guild_id}/channels", "channels"),
        ("roles", f"https://discord.com/api/v10/guilds/{guild_id}/roles", "roles"),
        ("members", f"https://discord.com/api/v10/guilds/{guild_id}/members?limit=100", "members"),
    ]
    for key, url, target in endpoints:
        try:
            r = requests.get(url, headers=headers, timeout=8)
            if r.status_code == 200:
                info[target] = r.json()
        except Exception:
            pass
    return info


# ---------------------------------------------------------------------------
# Rendu du panel (decoupe en sous-fonctions)
# ---------------------------------------------------------------------------

def _render_header():
    title = Text(f"PANEL DE CONTROLE & AUDIT DISCORD", style=f"bold {C_DISCORD}")
    return Panel(Align.center(title), box=BX, border_style=C_DISCORD)


def _render_left_panel(bot_data, guilds, gateway_client):
    """Panneau gauche : identite du bot et statut Gateway."""
    bot_id = bot_data.get("id", "?")
    tag = bot_data.get("username", "?")
    if bot_data.get("discriminator", "0") != "0":
        tag += f"#{bot_data.get('discriminator')}"

    crea_str = "?"
    if bot_id.isdigit():
        dt = datetime.fromtimestamp(((int(bot_id) >> 22) + DISCORD_EPOCH) / 1000.0, tz=timezone.utc)
        crea_str = dt.strftime("%d/%m/%Y %H:%M UTC")

    is_live = gateway_client and gateway_client.connected
    status_label = gateway_client.presence_status if gateway_client else "offline"
    activity_txt = gateway_client.activity_name if (gateway_client and gateway_client.activity_name) else "Aucune"

    conn_style = "bold green" if is_live else "bold red"
    conn_badge = "EN LIGNE (Gateway)" if is_live else "HORS LIGNE"

    # Tableau principal
    t = Table.grid(padding=(0, 2))
    t.add_column(style=f"bold {C_DISCORD}", width=20)
    t.add_column()
    t.add_row("Connexion Gateway:", Text(conn_badge, style=conn_style))
    t.add_row("Tag du bot:", tag)
    t.add_row("ID du bot:", bot_id)
    t.add_row("Cree le:", crea_str)
    t.add_row("Presence:", Text(status_label.upper(), style="bold cyan"))
    t.add_row("Activite:", activity_txt)
    t.add_row("Serveurs:", f"{len(guilds)} serveur(s)")



    # Liste des serveurs (max 3)
    if guilds:
        lines = [f"  {g.get('name', '?')[:28]} (ID: {g.get('id', '-')})" for g in guilds[:4]]
        if len(guilds) > 4:
            lines.append(f"  ... et {len(guilds) - 4} autre(s)")
        t.add_row("Serveurs:", "\n".join(lines))

    # Logs Gateway
    logs = gateway_client.log_messages[-6:] if gateway_client else []
    elements = [t]
    if logs:
        elements.append(Text("\nEvenements Gateway recents:", style=f"bold {C_DISCORD}"))
        for l in logs:
            elements.append(Text(f"  {l}", style="dim"))

    return Panel(
        Group(*elements),
        box=BX,
        border_style=C_DISCORD if is_live else "red",
        title=f"[bold {C_DISCORD}] Identite & Connexion [/]",
        title_align="left",
    )


def _render_right_panel(selected_guild_id, guild_info):
    """Panneau droit : audit du serveur cible."""
    elements = []

    if selected_guild_id and guild_info and guild_info.get("guild"):
        g = guild_info["guild"]
        channels = guild_info.get("channels", [])
        roles = guild_info.get("roles", [])
        members = guild_info.get("members", [])

        t = Table.grid(padding=(0, 2))
        t.add_column(style="bold cyan", width=20)
        t.add_column()
        t.add_row("Serveur cible:", g.get("name", "Inconnu"))
        t.add_row("Guild ID:", selected_guild_id)
        t.add_row("Proprietaire ID:", g.get("owner_id", "?"))
        t.add_row("Salons:", f"{len(channels)} (textuels + vocaux)")
        t.add_row("Roles:", f"{len(roles)} role(s)")
        t.add_row("Membres audites:", f"{len(members)} membre(s)")

        if channels:
            text_channels = [c for c in channels if c.get("type") == 0][:6]
            ch_names = ", ".join(f"#{c.get('name', '?')}" for c in text_channels) or "-"
            t.add_row("Salons textes:", ch_names)
            if len(text_channels) < len([c for c in channels if c.get("type") == 0]):
                t.add_row("", Text("(liste tronquee)", style="dim"))

        elements.append(t)
    elif selected_guild_id:
        elements.append(
            Text(
                f"Serveur cible : {selected_guild_id}\n"
                "(Donnees restreintes par les permissions du bot)",
                style="yellow",
            )
        )
    else:
        elements.append(
            Text(
                "Aucun serveur cible.\n\n"
                "Utilisez [2] pour analyser un serveur,\n"
                "inspecter ses salons et tester les permissions.",
                style="dim",
            )
        )

    return Panel(
        Group(*elements),
        box=BX,
        border_style=C_GOLD,
        title=f"[bold {C_GOLD}] Audit Serveur [/]",
        title_align="left",
    )


def _render_footer():
    """Barre d'actions en bas du panel."""
    actions = [
        ("1", "Gateway"), ("2", "Cible"), ("3", "Presence"),
        ("4", "Salons"), ("5", "Roles"), ("6", "Webhooks"),
        ("7", "Message"), ("8", "Actualiser"), ("9", "Permissions"),
        ("10", "Pseudo"), ("11", "Invitation"), ("12", "Export JSON"),
        ("0", "Quitter"),
    ]
    parts = [Text.assemble((f"[{key}]", f"bold {C_DISCORD}"), (f" {label}", "bold white"))
             for key, label in actions]
    return Panel(Align.center(Group(*parts)), box=BX, border_style="grey50")


def _request(method, url, headers, **kwargs):
    """Effectue une requete API avec un delai borne et une erreur exploitable."""
    return requests.request(method, url, headers=headers, timeout=8, **kwargs)


def _valid_snowflake(value):
    return isinstance(value, str) and value.isdigit() and 15 <= len(value) <= 22


def _permission_summary(headers, guild_id, bot_id, roles):
    """Calcule les permissions de base du bot a partir de ses roles de serveur."""
    if not (_valid_snowflake(guild_id) and _valid_snowflake(bot_id)):
        raise ValueError("Identifiant de serveur ou de bot invalide.")
    response = _request(
        "GET",
        f"https://discord.com/api/v10/guilds/{guild_id}/members/{bot_id}",
        headers,
    )
    if response.status_code != 200:
        return None, response.status_code
    member = response.json()
    role_ids = set(member.get("roles", [])) | {guild_id}
    permissions = 0
    for role in roles:
        if role.get("id") in role_ids:
            permissions |= int(role.get("permissions", 0))
    return permissions, response.status_code


def _permission_rows(permissions):
    checks = [
        ("Administrateur", 0x8), ("Gerer les salons", 0x10),
        ("Voir les journaux d'audit", 0x80), ("Gerer les messages", 0x2000),
        ("Gerer les roles", 0x10000000), ("Gerer les webhooks", 0x20000000),
    ]
    return [(label, "Oui" if permissions & 0x8 or permissions & bit else "Non")
            for label, bit in checks]


def _save_guild_audit(guild_id, guild_info):
    """Exporte un resume JSON sans identifiants secrets ni contenu de messages."""
    guild = guild_info.get("guild") or {}
    snapshot = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "guild": {key: guild.get(key) for key in ("id", "name", "owner_id", "approximate_member_count")},
        "channels": [
            {key: channel.get(key) for key in ("id", "name", "type", "nsfw")}
            for channel in guild_info.get("channels", [])
        ],
        "roles": [
            {key: role.get(key) for key in ("id", "name", "position", "permissions")}
            for role in guild_info.get("roles", [])
        ],
        "members_loaded": len(guild_info.get("members", [])),
    }
    Path(EXPORTS_DIR).mkdir(parents=True, exist_ok=True)
    path = Path(EXPORTS_DIR) / f"guild_{guild_id}_audit.json"
    path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _slug_channel_name(value):
    normalized = unicodedata.normalize("NFKD", value.strip().lower())
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii")
    name = re.sub(r"[^a-z0-9_-]+", "-", ascii_name).strip("-")
    if not name or len(name) > 100:
        raise ValueError("Nom de salon invalide (1 a 100 caracteres autorises).")
    return name


def _api_error(response):
    try:
        data = response.json()
        message = data.get("message", "")
    except (ValueError, AttributeError):
        message = ""
    return f"HTTP {response.status_code}" + (f" : {message}" if message else "")


def _render_bot_panel(bot_data, guilds, selected_guild_id, guild_info, gateway_client):
    """Construit le layout complet du panel."""
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="body"),
        Layout(name="footer", size=5),
    )
    layout["body"].split_row(
        Layout(name="left", ratio=50),
        Layout(name="right", ratio=50),
    )

    layout["header"].update(_render_header())
    layout["left"].update(_render_left_panel(bot_data, guilds, gateway_client))
    layout["right"].update(_render_right_panel(selected_guild_id, guild_info))
    layout["footer"].update(_render_footer())

    return layout


# ---------------------------------------------------------------------------
# Point d'entree principal
# ---------------------------------------------------------------------------

def bot_panel():
    titre("DISCORD BOT CONTROL & AUDIT PANEL", C_DISCORD)
    if not warn_pentest():
        bad("Audit annule : autorisation requise.")
        return

    token = Prompt.ask("[bold gold1]Entrez le Token du Bot Discord[/]", password=True).strip()
    if not token or "." not in token:
        bad("Token invalide.")
        return

    headers = {
        "Authorization": f"Bot {token}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) OSINT-Pentest-Suite",
        "Content-Type": "application/json",
    }

    with attente("Verification des droits du Bot"):
        bot_data = _fetch_bot_info(headers)

    if not bot_data:
        bad("Impossible de se connecter : Token Bot invalide ou revoque (HTTP 401/403).")
        return

    guilds = _fetch_bot_guilds(headers)

    # Demarrage automatique du client Gateway WebSocket
    gateway_client = DiscordGatewayClient(token)
    gateway_client.start()
    with attente("Connexion du Bot a la Gateway Discord (WebSocket TLS)"):
        import time
        t_start = time.time()
        while time.time() - t_start < 4:
            if gateway_client.connected:
                break
            time.sleep(0.2)

    selected_guild_id = ""
    guild_info = {"channels": [], "roles": [], "members": [], "guild": None}

    while True:
        console.clear()
        panel_layout = _render_bot_panel(bot_data, guilds, selected_guild_id, guild_info, gateway_client)
        console.print(panel_layout)

        choix = Prompt.ask("\n[bold gold1]Panel Bot >[/]", default="0").strip()

        if choix in ("0", "q", "exit", "quit"):
            gateway_client.stop()
            ok("Bot deconnecte de la Gateway Discord.")
            break

        elif choix == "1":
            if gateway_client.connected:
                if Confirm.ask("Le bot est connecte. Voulez-vous l'eteindre ?", default=True):
                    gateway_client.stop()
                    ok("Bot deconnecte de Discord.")
            else:
                ok("Tentative de reconnexion du bot a la Gateway...")
                gateway_client = DiscordGatewayClient(token)
                gateway_client.start()
                import time
                time.sleep(1.5)
                if gateway_client.connected:
                    ok("Connexion Gateway etablie.")
                else:
                    warn("La connexion n'a pas abouti. Consultez les evenements Gateway dans le panneau.")
            pause()

        elif choix == "2":
            if guilds:
                console.print("\n[bold]Serveurs rejoints par ce bot :[/]")
                for i, g in enumerate(guilds, 1):
                    console.print(f"  [{i}] {g.get('name')} (ID: {g.get('id')})")
            gid_input = demander("Guild ID a cibler (ou numero de la liste)")
            if gid_input.isdigit() and 1 <= int(gid_input) <= len(guilds):
                selected_guild_id = guilds[int(gid_input) - 1].get("id")
            elif _valid_snowflake(gid_input):
                selected_guild_id = gid_input
            else:
                warn("ID invalide.")
                pause()
                continue

            with attente(f"Audit du serveur {selected_guild_id}"):
                guild_info = _fetch_guild_details(headers, selected_guild_id)
            ok("Donnees du serveur actualisees.")
            pause()

        elif choix == "3":
            console.print("\n[bold]Statut de presence :[/]")
            console.print("  [1] En ligne (Online)")
            console.print("  [2] Inactif (Idle)")
            console.print("  [3] Ne pas deranger (DND)")
            console.print("  [4] Invisible (Offline)")
            st_choice = Prompt.ask("Choix", choices=["1", "2", "3", "4"], default="1")
            status_code, status_name, _ = STATUS_PRESETS[st_choice]

            console.print("\n[bold]Type d'activite :[/]")
            console.print("  [1] Joue a (Playing)")
            console.print("  [2] En Stream (Streaming)")
            console.print("  [3] Ecoute (Listening)")
            console.print("  [4] Regarde (Watching)")
            console.print("  [5] Participe a (Competing)")
            console.print("  [0] Aucune activite")
            act_choice = Prompt.ask("Type", choices=["0", "1", "2", "3", "4", "5"], default="1")

            act_name = ""
            stream_url = ""
            act_type = 0
            if act_choice != "0":
                act_type, _, _ = ACTIVITY_PRESETS[act_choice]
                act_name = demander("Texte de l'activite", defaut="Auditing Server")
                if act_type == 1:
                    stream_url = demander("URL du Stream", defaut="https://twitch.tv/discord")

            if gateway_client.connected:
                gateway_client.update_presence(status=status_code, activity_name=act_name, activity_type=act_type, stream_url=stream_url)
                ok(f"Presence envoyee : {status_name} | {act_name or 'Sans texte'}")
            else:
                warn("Le bot est hors-ligne. Demarrez-le avec [1] pour modifier la presence.")
            pause()

        elif choix == "4":
            if not selected_guild_id:
                warn("Ciblez d'abord un serveur (option [2]).")
                pause()
                continue
            channels = guild_info.get("channels", [])
            if not channels:
                bad("Aucun salon accessible sur ce serveur.")
            else:
                t = Table(title=f"Salons de {selected_guild_id}", box=BX, border_style=C_DISCORD)
                t.add_column("Type", style="bold")
                t.add_column("Nom")
                t.add_column("ID", style="dim")
                type_names = {0: "Textuel", 2: "Vocal", 4: "Categorie", 5: "Annonces", 15: "Forum"}
                for c in channels:
                    t.add_row(type_names.get(c.get("type"), f"Type {c.get('type')}"), c.get("name", "?"), c.get("id", "-"))
                console.print(t)

                console.print("\n[bold]Options :[/]")
                console.print("  [1] Creer un salon d'audit")
                console.print("  [0] Retour")
                c_opt = Prompt.ask("Choix", choices=["0", "1"], default="0")
                if c_opt == "1":
                    try:
                        c_name = _slug_channel_name(demander("Nom du nouveau salon", defaut="audit-security"))
                        if Confirm.ask(f"Confirmer la creation du salon '{c_name}' ?", default=False):
                            with attente(f"Creation du salon '{c_name}'"):
                                r_ch = _request(
                                    "POST",
                                    f"https://discord.com/api/v10/guilds/{selected_guild_id}/channels",
                                    headers,
                                    json={"name": c_name, "type": 0},
                                )
                            if r_ch.status_code in (200, 201):
                                ok(f"Salon '{c_name}' cree avec succes !")
                                guild_info["channels"].append(r_ch.json())
                            else:
                                bad(_api_error(r_ch))
                    except (ValueError, requests.RequestException) as exc:
                        bad(f"Creation impossible : {exc}")
            pause()

        elif choix == "5":
            if not selected_guild_id:
                warn("Ciblez d'abord un serveur (option [2]).")
                pause()
                continue
            roles = guild_info.get("roles", [])
            if not roles:
                bad("Aucun role recupere.")
            else:
                t = Table(title=f"Roles de {selected_guild_id}", box=BX, border_style=C_GOLD)
                t.add_column("Role", style="bold")
                t.add_column("Permissions")
                t.add_column("Position")
                t.add_column("ID", style="dim")
                for r in sorted(roles, key=lambda x: x.get("position", 0), reverse=True):
                    perm_val = int(r.get("permissions", 0))
                    admin_tag = " [bold red][ADMIN][/]" if (perm_val & 0x8) else ""
                    t.add_row(r.get("name", "?") + admin_tag, str(perm_val), str(r.get("position", "-")), r.get("id", "-"))
                console.print(t)
            pause()

        elif choix == "6":
            if not selected_guild_id:
                warn("Ciblez d'abord un serveur (option [2]).")
                pause()
                continue
            try:
                with attente("Extraction des Webhooks du serveur"):
                    rw = _request("GET", f"https://discord.com/api/v10/guilds/{selected_guild_id}/webhooks", headers)
            except requests.RequestException as exc:
                bad(f"Erreur reseau : {exc}")
                pause()
                continue
            if rw.status_code == 200:
                hooks = rw.json()
                if not hooks:
                    ok("Aucun webhook trouve sur ce serveur.")
                else:
                    t = Table(title=f"Webhooks detectes ({len(hooks)})", box=BX, border_style="red")
                    t.add_column("Nom", style="bold")
                    t.add_column("ID")
                    t.add_column("Channel ID")
                    t.add_column("Token", style="dim")
                    for h in hooks:
                        t.add_row(h.get("name", "?"), h.get("id", "-"), h.get("channel_id", "-"), "[masque]")

                    console.print(t)
            else:
                bad(f"Echec ({rw.status_code}) : permission 'MANAGE_WEBHOOKS' requise.")
            pause()

        elif choix == "7":

            if not selected_guild_id:
                warn("Ciblez d'abord un serveur (option [2]).")
                pause()
                continue
            ch_id = demander("ID du salon textuel cible")
            if ch_id not in {str(channel.get("id")) for channel in guild_info.get("channels", [])}:
                bad("Le salon doit appartenir a la liste des salons charges pour le serveur cible.")
                pause()
                continue
            msg_content = demander("Message a transmettre")
            if not _valid_snowflake(ch_id) or not msg_content:
                bad("ID de salon ou message invalide.")
            elif Confirm.ask("Confirmer l'envoi de ce message ?", default=False):
                try:
                    with attente("Envoi du message"):
                        res = _request("POST", f"https://discord.com/api/v10/channels/{ch_id}/messages",
                                       headers, json={"content": msg_content})
                    if res.status_code in (200, 201):
                        ok("Message transmis avec succes.")
                    else:
                        bad(_api_error(res))
                except requests.RequestException as exc:
                    bad(f"Erreur reseau : {exc}")
            pause()

        elif choix == "8":
            try:
                with attente("Actualisation des donnees Discord"):
                    guilds = _fetch_bot_guilds(headers)
                    if selected_guild_id:
                        guild_info = _fetch_guild_details(headers, selected_guild_id)
                ok(f"Donnees actualisees : {len(guilds)} serveur(s) accessible(s).")
            except requests.RequestException as exc:
                bad(f"Actualisation impossible : {exc}")
            pause()

        elif choix == "9":
            if not selected_guild_id:
                warn("Ciblez d'abord un serveur (option [2]).")
                pause()
                continue
            try:
                permissions, status = _permission_summary(
                    headers, selected_guild_id, str(bot_data.get("id", "")),
                    guild_info.get("roles", []),
                )
                if permissions is None:
                    bad(f"Impossible de lire les permissions ({status}) : membre introuvable ou acces refuse.")
                else:
                    rows = _permission_rows(permissions)
                    kv("Permissions effectives du bot (roles cumules)", rows, C_DISCORD)
                    if permissions & 0x8:
                        warn("Le bot possede Administrateur : reduis ses permissions si ce droit n'est pas necessaire.")
            except (ValueError, requests.RequestException) as exc:
                bad(f"Audit des permissions impossible : {exc}")
            pause()

        elif choix == "10":
            if not selected_guild_id:
                warn("Ciblez d'abord un serveur (option [2]).")
                pause()
                continue
            nickname = demander("Nouveau surnom du bot (vide pour le retirer)", defaut="")
            if len(nickname) > 32:
                bad("Le surnom ne peut pas depasser 32 caracteres.")
            elif Confirm.ask("Confirmer le changement de surnom du bot ?", default=False):
                try:
                    with attente("Mise a jour du surnom"):
                        res = _request("PATCH", f"https://discord.com/api/v10/guilds/{selected_guild_id}/members/@me",
                                       headers, json={"nick": nickname or None})
                    if res.status_code in (200, 204):
                        ok("Surnom mis a jour.")
                    else:
                        bad(_api_error(res))
                except requests.RequestException as exc:
                    bad(f"Erreur reseau : {exc}")
            pause()

        elif choix == "11":
            if not selected_guild_id:
                warn("Ciblez d'abord un serveur (option [2]).")
                pause()
                continue
            channel_id = demander("ID du salon textuel pour l'invitation")
            if channel_id not in {str(channel.get("id")) for channel in guild_info.get("channels", [])}:
                bad("Le salon doit appartenir a la liste des salons charges pour le serveur cible.")
            elif not _valid_snowflake(channel_id):
                bad("ID de salon invalide.")
            elif Confirm.ask("Creer une invitation partageable pour ce salon ?", default=False):
                try:
                    with attente("Creation de l'invitation"):
                        res = _request("POST", f"https://discord.com/api/v10/channels/{channel_id}/invites",
                                       headers, json={"max_age": 3600, "max_uses": 1, "unique": True})
                    if res.status_code in (200, 201):
                        code = res.json().get("code")
                        ok(f"Invitation creee (valable 1 heure, 1 utilisation) : https://discord.gg/{code}")
                    else:
                        bad(_api_error(res))
                except (requests.RequestException, ValueError) as exc:
                    bad(f"Creation impossible : {exc}")
            pause()

        elif choix == "12":
            if not selected_guild_id or not guild_info.get("guild"):
                warn("Ciblez et chargez d'abord un serveur (option [2]).")
                pause()
                continue
            try:
                path = _save_guild_audit(selected_guild_id, guild_info)
                ok(f"Audit exporte sans tokens ni messages : {path}")
            except OSError as exc:
                bad(f"Export impossible : {exc}")
            pause()
