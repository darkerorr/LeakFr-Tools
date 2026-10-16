from datetime import datetime, timezone
import requests
from rich.align import Align
from rich.console import Group
from rich.layout import Layout
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich.text import Text
from core.common import (
    console, titre, ok, bad, warn, demander, attente, pause,
    BX, C_DISCORD, C_GOLD, DISCORD_EPOCH, warn_pentest
)
from modules.discord.gateway_bot import DiscordGatewayClient

STATUS_PRESETS = {
    "1": ("online", "En ligne (Online)", "bold green"),
    "2": ("idle", "Inactif (Idle / Absent)", "bold yellow"),
    "3": ("dnd", "Ne pas déranger (Do Not Disturb / DND)", "bold red"),
    "4": ("invisible", "Invisible (Offline)", "dim"),
}

ACTIVITY_PRESETS = {
    "1": (0, "Joue à (Playing)", "cyan"),
    "2": (1, "En Stream (Streaming)", "magenta"),
    "3": (2, "Écoute (Listening)", "green"),
    "4": (3, "Regarde (Watching)", "yellow"),
    "5": (5, "Participe à (Competing)", "blue"),
}


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
    try:
        r = requests.get(f"https://discord.com/api/v10/guilds/{guild_id}", headers=headers, timeout=8)
        if r.status_code == 200:
            info["guild"] = r.json()
    except Exception:
        pass

    try:
        rc = requests.get(f"https://discord.com/api/v10/guilds/{guild_id}/channels", headers=headers, timeout=8)
        if rc.status_code == 200:
            info["channels"] = rc.json()
    except Exception:
        pass

    try:
        rr = requests.get(f"https://discord.com/api/v10/guilds/{guild_id}/roles", headers=headers, timeout=8)
        if rr.status_code == 200:
            info["roles"] = rr.json()
    except Exception:
        pass

    try:
        rm = requests.get(f"https://discord.com/api/v10/guilds/{guild_id}/members?limit=100", headers=headers, timeout=8)
        if rm.status_code == 200:
            info["members"] = rm.json()
    except Exception:
        pass

    return info


def _render_bot_panel(bot_data, guilds, selected_guild_id, guild_info, gateway_client):
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="body"),
        Layout(name="footer", size=3),
    )
    layout["body"].split_row(
        Layout(name="left", ratio=50),
        Layout(name="right", ratio=50),
    )

    # 1. Header
    title_text = Text()
    title_text.append("⚡ DISCORD BOT CONTROL & AUDIT PANEL (LIVE GATEWAY) ⚡", style=f"bold {C_DISCORD}")
    layout["header"].update(Panel(Align.center(title_text), box=BX, border_style=C_DISCORD))

    # 2. Left Window: Identité du Bot & Connexion temps réel
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
    activity_txt = f"{gateway_client.activity_name}" if gateway_client and gateway_client.activity_name else "Aucune"

    conn_style = "bold green" if is_live else "bold red"
    conn_str = "🟢 EN LIGNE (Gateway Connectée)" if is_live else "🔴 HORS LIGNE (Déconnecté)"

    left_table = Table.grid(padding=(0, 1))
    left_table.add_column(style=f"bold {C_GOLD}", width=19)
    left_table.add_column()
    left_table.add_row("Connexion Gateway :", Text(conn_str, style=conn_style))
    left_table.add_row("Bot Tag :", tag)
    left_table.add_row("Bot ID :", bot_id)
    left_table.add_row("Créé le :", crea_str)
    left_table.add_row("Mode Présence :", Text(status_label.upper(), style="bold cyan"))
    left_table.add_row("Activité / Jeu :", activity_txt)
    left_table.add_row("Serveurs reliés :", f"{len(guilds)} serveur(s)")

    if guilds:
        guilds_summary = "\n".join(f"• {g.get('name', '?')[:26]} (ID: {g.get('id', '-')})" for g in guilds[:3])
        if len(guilds) > 3:
            guilds_summary += f"\n[dim]... et {len(guilds) - 3} autre(s)[/]"
        left_table.add_row("Liste Serveurs :", guilds_summary)

    # Logs récents de la Gateway
    recent_logs = gateway_client.log_messages[-5:] if gateway_client else []
    log_renderable = []
    if recent_logs:
        log_renderable.append(Text("\n[Événements & Logs Gateway Réseau] :", style="bold grey70"))
        for l in recent_logs:
            log_renderable.append(Text(f" {l}", style="dim"))

    left_panel = Panel(
        Group(left_table, *log_renderable),
        box=BX,
        border_style=C_DISCORD if is_live else "red",
        title=f"[bold {C_DISCORD}] Identité & Statut Réseau du Bot [/]",
        title_align="left",
    )
    layout["left"].update(left_panel)

    # 3. Right Window: Serveur Ciblé & Audit
    right_elements = []
    if selected_guild_id and guild_info and guild_info.get("guild"):
        g = guild_info["guild"]
        g_name = g.get("name", "Inconnu")
        owner_id = g.get("owner_id", "?")
        channels = guild_info.get("channels", [])
        roles = guild_info.get("roles", [])
        members = guild_info.get("members", [])

        g_table = Table.grid(padding=(0, 1))
        g_table.add_column(style="bold cyan", width=18)
        g_table.add_column()
        g_table.add_row("Serveur ciblé :", g_name)
        g_table.add_row("Guild ID :", selected_guild_id)
        g_table.add_row("Owner ID :", owner_id)
        g_table.add_row("Salons totaux :", f"{len(channels)} (textuels & vocaux)")
        g_table.add_row("Rôles configurés :", f"{len(roles)} rôle(s)")
        g_table.add_row("Membres audités :", f"{len(members)} membre(s) récupéré(s)")

        if channels:
            ch_list = [f"#{c.get('name', '?')}" for c in channels if c.get("type") == 0][:5]
            g_table.add_row("Salons textuels :", ", ".join(ch_list) or "-")

        right_elements.append(g_table)
    elif selected_guild_id:
        right_elements.append(Text(f"Serveur ciblé : {selected_guild_id}\n(Données restreintes par les permissions du bot)", style="yellow"))
    else:
        right_elements.append(Text("Aucun serveur ciblé.\nUtilisez l'option [2] pour analyser un serveur, inspecter ses salons et tester les permissions.", style="dim"))

    right_panel = Panel(
        Group(*right_elements),
        box=BX,
        border_style=C_GOLD,
        title=f"[bold {C_GOLD}] Audit Serveur & Recon [/]",
        title_align="left",
    )
    layout["right"].update(right_panel)

    # 4. Footer & Actions Bar
    footer_text = Text(justify="center")
    footer_text.append("[1] Démarrer/Éteindre Bot  •  [2] Cibler Serveur  •  [3] Présence/Stream  •  [4] Salons  •  [5] Rôles  •  [6] Audit Webhooks  •  [7] Message  •  [0] Quitter", style="bold white")
    layout["footer"].update(Panel(footer_text, box=BX, border_style="grey50"))

    return layout


def bot_panel():
    titre("DISCORD BOT OFFENSIVE & AUDIT PANEL", C_DISCORD)
    if not warn_pentest():
        bad("Audit annulé : autorisation requise.")
        return

    token = demander("Entrez le Token du Bot Discord").strip()
    if not token or "." not in token:
        bad("Token invalide.")
        return

    headers = {
        "Authorization": f"Bot {token}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) OSINT-Pentest-Suite",
        "Content-Type": "application/json",
    }

    with attente("Vérification des droits du Bot"):
        bot_data = _fetch_bot_info(headers)

    if not bot_data:
        bad("Impossible de se connecter : Token Bot invalide ou révoqué (HTTP 401/403).")
        return

    guilds = _fetch_bot_guilds(headers)

    # Démarrage automatique du client Gateway WebSocket
    gateway_client = DiscordGatewayClient(token)
    gateway_client.start()
    with attente("Connexion physique du Bot à la Gateway Discord (WebSocket TLS)"):
        # Laisser le temps à la Gateway d'envoyer l'opcode 10 (Hello) et Ready
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

        choix = Prompt.ask("\n[bold gold1]Panel Bot ❯[/]", default="0").strip()

        if choix in ("0", "q", "exit", "quit"):
            gateway_client.stop()
            ok("Bot déconnecté de la Gateway Discord.")
            break

        elif choix == "1":
            if gateway_client.connected:
                if Confirm.ask("Le bot est actuellement connecté. Voulez-vous l'éteindre (Offline) ?", default=True):
                    gateway_client.stop()
                    ok("Bot déconnecté de Discord.")
            else:
                ok("Tentative de reconnexion du bot à la Gateway...")
                gateway_client = DiscordGatewayClient(token)
                gateway_client.start()
                import time
                time.sleep(1.5)
            pause()

        elif choix == "2":
            if guilds:
                console.print("\n[bold]Serveurs rejoints par ce bot :[/]")
                for i, g in enumerate(guilds, 1):
                    console.print(f"  [{i}] {g.get('name')} (ID: {g.get('id')})")
            gid_input = demander("Guild ID à cibler (ou numéro de la liste)")
            if gid_input.isdigit() and 1 <= int(gid_input) <= len(guilds):
                selected_guild_id = guilds[int(gid_input) - 1].get("id")
            elif gid_input.isdigit():
                selected_guild_id = gid_input
            else:
                warn("ID invalide.")
                pause()
                continue

            with attente(f"Audit du serveur {selected_guild_id}"):
                guild_info = _fetch_guild_details(headers, selected_guild_id)
            ok("Données du serveur actualisées.")
            pause()

        elif choix == "3":
            console.print("\n[bold]Statut de présence en temps réel :[/]")
            console.print("  [1] En ligne (Online) 🟢")
            console.print("  [2] Inactif (Idle) 🟡")
            console.print("  [3] Ne pas déranger (Do Not Disturb - DND) 🔴")
            console.print("  [4] Invisible (Offline) ⚪")
            st_choice = Prompt.ask("Choisir le mode", choices=["1", "2", "3", "4"], default="1")
            status_code, status_name, _ = STATUS_PRESETS[st_choice]

            console.print("\n[bold]Type d'activité / statut :[/]")
            console.print("  [1] Joue à (Playing)")
            console.print("  [2] En Stream (Streaming Twitch/YouTube)")
            console.print("  [3] Écoute (Listening)")
            console.print("  [4] Regarde (Watching)")
            console.print("  [5] Participe à (Competing)")
            console.print("  [0] Aucune activité")
            act_choice = Prompt.ask("Type", choices=["0", "1", "2", "3", "4", "5"], default="1")

            act_name = ""
            stream_url = ""
            act_type = 0
            if act_choice != "0":
                act_type, _, _ = ACTIVITY_PRESETS[act_choice]
                act_name = demander("Texte de l'activité (ex: 'Security Audit v2' ou 'Hacking CTF')", defaut="Auditing Server")
                if act_type == 1:
                    stream_url = demander("URL du Stream (ex: https://twitch.tv/security)", defaut="https://twitch.tv/discord")

            if gateway_client.connected:
                gateway_client.update_presence(status=status_code, activity_name=act_name, activity_type=act_type, stream_url=stream_url)
                ok(f"Présence envoyée à Discord : {status_name} | {act_name or 'Sans texte'}")
            else:
                warn("Le bot est actuellement hors-ligne. Démarrez-le avec l'option [1] pour afficher la présence.")
            pause()

        elif choix == "4":
            if not selected_guild_id:
                warn("Veuillez d'abord cibler un serveur (option [2]).")
                pause()
                continue
            channels = guild_info.get("channels", [])
            if not channels:
                bad("Aucun salon accessible sur ce serveur.")
            else:
                t = Table(title=f"Architecture des Salons - {selected_guild_id}", box=BX, border_style=C_DISCORD)
                t.add_column("Type", style="bold")
                t.add_column("Nom")
                t.add_column("ID", style="dim")
                type_names = {0: "Textuel", 2: "Vocal", 4: "Catégorie", 5: "Annonces", 15: "Forum"}
                for c in channels:
                    t.add_row(type_names.get(c.get("type"), f"Type {c.get('type')}"), c.get("name", "?"), c.get("id", "-"))
                console.print(t)

                console.print("\n[bold]Options sur les salons :[/]")
                console.print("  [1] Créer un salon d'audit")
                console.print("  [0] Retour")
                c_opt = Prompt.ask("Choix", choices=["0", "1"], default="0")
                if c_opt == "1":
                    c_name = demander("Nom du nouveau salon", defaut="audit-security")
                    with attente(f"Création du salon '{c_name}'"):
                        r_ch = requests.post(
                            f"https://discord.com/api/v10/guilds/{selected_guild_id}/channels",
                            headers=headers,
                            json={"name": c_name, "type": 0},
                            timeout=8,
                        )
                    if r_ch.status_code in (200, 201):
                        ok(f"Salon '{c_name}' créé avec succès !")
                        guild_info["channels"].append(r_ch.json())
                    else:
                        bad(f"Échec ({r_ch.status_code}) : permissions de gestion des salons insuffisantes.")
            pause()

        elif choix == "5":
            if not selected_guild_id:
                warn("Veuillez d'abord cibler un serveur (option [2]).")
                pause()
                continue
            roles = guild_info.get("roles", [])
            if not roles:
                bad("Aucun rôle récupéré.")
            else:
                t = Table(title=f"Hiérarchie & Permissions des Rôles - {selected_guild_id}", box=BX, border_style=C_GOLD)
                t.add_column("Rôle", style="bold")
                t.add_column("Permissions (Brut)")
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
                warn("Veuillez d'abord cibler un serveur (option [2]).")
                pause()
                continue
            with attente("Extraction des Webhooks du serveur"):
                rw = requests.get(f"https://discord.com/api/v10/guilds/{selected_guild_id}/webhooks", headers=headers, timeout=8)
            if rw.status_code == 200:
                hooks = rw.json()
                if not hooks:
                    ok("Aucun webhook trouvé sur ce serveur.")
                else:
                    t = Table(title=f"Webhooks détectés sur le serveur ({len(hooks)})", box=BX, border_style="red")
                    t.add_column("Nom", style="bold")
                    t.add_column("ID")
                    t.add_column("Channel ID")
                    t.add_column("Token Webhook", style="dim")
                    for h in hooks:
                        t.add_row(h.get("name", "?"), h.get("id", "-"), h.get("channel_id", "-"), h.get("token", "Masqué")[:25] + "...")
                    console.print(t)
            else:
                bad(f"Échec ({rw.status_code}) : le bot ne possède pas la permission 'MANAGE_WEBHOOKS'.")
            pause()

        elif choix == "7":
            if not selected_guild_id:
                warn("Veuillez d'abord cibler un serveur (option [2]).")
                pause()
                continue
            ch_id = demander("ID du salon textuel cible")
            msg_content = demander("Message à transmettre")
            if ch_id and msg_content:
                with attente("Envoi du message"):
                    res = requests.post(
                        f"https://discord.com/api/v10/channels/{ch_id}/messages",
                        headers=headers,
                        json={"content": msg_content},
                        timeout=8,
                    )
                if res.status_code in (200, 201):
                    ok("Message transmis avec succès.")
                else:
                    bad(f"Échec ({res.status_code}) : le bot n'a pas accès en écriture dans ce salon.")
            pause()
