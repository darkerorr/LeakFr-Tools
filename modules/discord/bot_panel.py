"""Panel de controle et d'audit d'un Bot Discord.

Le panel reutilise un client REST commun (limites de debit, erreurs
explicites) et discord.py pour la Gateway. Aucune action destructive n'est
executee sans confirmation, et le token n'apparait ni dans les logs ni dans
les exports.
"""
import json
import mimetypes
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

from rich.align import Align
from rich.console import Group
from rich.layout import Layout
from rich.markup import escape
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich.text import Text

from core.common import (
    BX, C_DISCORD, C_GOLD, DISCORD_EPOCH, afficher_pagine, attente, bad,
    choisir_option, clear_screen, console, demander, kv, ok, pause, titre, warn,
    warn_pentest,
)
from core.config import DATA_DIR, EXPORTS_DIR
from modules.discord import permissions as perms
from modules.discord.discord_api import (
    DiscordAPI, DiscordAPIError, DiscordAuthError, DiscordForbiddenError,
    DiscordNotFoundError, conseils_jeton_bot, normaliser_jeton, valid_snowflake,
)
from modules.discord.gateway_bot import DiscordGatewayClient
from modules.discord.local_store import charger_json, ecrire_json
from modules.discord.panel_journal import derniers as journal_derniers
from modules.discord.panel_journal import enregistrer as journaliser

TEMPLATES_FILE = Path(DATA_DIR) / "discord_panel_templates.json"
TYPES_SALON_ECRITURE = {0, 5}
TYPES_SALON_CHOIX = {"Textuel": 0, "Vocal": 2, "Categorie": 4, "Annonces": 5, "Forum": 15}
STATUTS = {"En ligne": "online", "Inactif": "idle", "Ne pas deranger": "dnd",
           "Invisible": "invisible"}
ACTIVITES = {"Joue a": 0, "En Stream": 1, "Ecoute": 2, "Regarde": 3,
             "Participe a": 5, "Aucune": None}

MENU = [
    "Serveurs & permissions", "Clonage Discord", "Communication",
    "Salons & categories", "Roles", "Moderation", "Connexion & presence",
    "Actualiser", "Quitter le panel",
]


# ---------------------------------------------------------------------------
# Validation et helpers
# ---------------------------------------------------------------------------

def _valid_snowflake(value):
    return valid_snowflake(str(value or ""))


def _normaliser(texte):
    texte = unicodedata.normalize("NFKD", str(texte or "").casefold())
    return "".join(car for car in texte if not unicodedata.combining(car))


def _slug_channel_name(value):
    normalized = unicodedata.normalize("NFKD", value.strip().lower())
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii")
    name = re.sub(r"[^a-z0-9_-]+", "-", ascii_name).strip("-")
    if not name or len(name) > 100:
        raise ValueError("Nom de salon invalide (1 a 100 caracteres autorises).")
    return name


def _date_snowflake(value):
    if not _valid_snowflake(value):
        return "?"
    try:
        dt = datetime.fromtimestamp(((int(value) >> 22) + DISCORD_EPOCH) / 1000.0,
                                   tz=timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return "?"
    return dt.strftime("%d/%m/%Y %H:%M UTC")


def _tag(utilisateur):
    nom = (utilisateur or {}).get("username") or (utilisateur or {}).get("global_name") or "?"
    discrim = str((utilisateur or {}).get("discriminator") or "0")
    return f"{nom}#{discrim}" if discrim != "0" else nom


def filtrer_guildes(guilds, requete):
    """Filtre les serveurs par nom ou identifiant (recherche insensible aux accents)."""
    terme = _normaliser(requete).strip()
    if not terme:
        return list(guilds or [])
    resultat = []
    for guild in guilds or []:
        nom = _normaliser(guild.get("name"))
        if terme in nom or terme in str(guild.get("id", "")):
            resultat.append(guild)
    return resultat


def _choisir_salon(ctx, types=TYPES_SALON_ECRITURE, label="SALON"):
    salons = [canal for canal in (ctx.get("channels") or [])
              if canal.get("type") in types]
    if not salons:
        warn("Aucun salon compatible dans les donnees chargees.")
        return None
    libelles = [f"#{canal.get('name', '?')} ({canal.get('id')})" for canal in salons]
    choix = choisir_option(label, libelles + ["Retour"])
    if choix is None or choix == "Retour":
        return None
    return salons[libelles.index(choix)]


def _choisir_role(ctx, label="ROLE"):
    roles = sorted(ctx.get("roles") or [], key=lambda role: role.get("position", 0), reverse=True)
    if not roles:
        warn("Aucun role charge.")
        return None
    libelles = [f"{role.get('name', '?')} (position {role.get('position', 0)})" for role in roles]
    choix = choisir_option(label, libelles + ["Retour"])
    if choix is None or choix == "Retour":
        return None
    return roles[libelles.index(choix)]


# ---------------------------------------------------------------------------
# Chargement et permissions
# ---------------------------------------------------------------------------

def charger_contexte(api, guild_id, bot_id=None):
    """Charge les donnees d'un serveur sans masquer les erreurs d'acces."""
    ctx = {"guild": None, "channels": [], "roles": [], "member": None,
           "webhooks": [], "errors": []}
    appels = (
        ("serveur", lambda: api.guild(guild_id), "guild"),
        ("salons", lambda: api.guild_channels(guild_id), "channels"),
        ("roles", lambda: api.guild_roles(guild_id), "roles"),
    )
    for libelle, appel, cle in appels:
        try:
            ctx[cle] = appel()
        except DiscordAPIError as exc:
            ctx["errors"].append((libelle, str(exc)))
    if bot_id:
        try:
            ctx["member"] = api.guild_member(guild_id, bot_id)
        except DiscordAPIError as exc:
            ctx["errors"].append(("membre du bot", str(exc)))
    try:
        ctx["webhooks"] = api.guild_webhooks(guild_id)
    except DiscordAPIError as exc:
        ctx["webhooks"] = []
        ctx["errors"].append(("webhooks", str(exc)))
    return ctx


def permissions_du_bot(ctx):
    """Permissions effectives du bot hors salons, ou None si indisponibles."""
    if not ctx.get("guild") or not ctx.get("member"):
        return None
    return perms.effective_permissions(ctx["guild"], ctx["member"], ctx.get("roles") or [])


def _permission_summary(api, guild_id, bot_id, roles):
    """Compatibilite : permissions de base du bot et statut HTTP."""
    member = api.guild_member(guild_id, bot_id)
    guild = {"id": str(guild_id), "owner_id": ""}
    return perms.base_permissions(guild, member, roles), 200


def verifier_permission(ctx, bit, libelle):
    permissions = permissions_du_bot(ctx)
    if permissions is None:
        warn("Permissions du bot indisponibles : impossible de verifier l'autorisation.")
        return False
    if not perms.has_permission(permissions, bit):
        warn(f"Permission manquante : {libelle}.")
        return False
    return True


def _verifier_salon(ctx, channel, bit, libelle):
    permissions = permissions_du_bot(ctx)
    if permissions is None:
        warn("Permissions du bot indisponibles.")
        return False
    effectives = perms.effective_permissions(ctx["guild"], ctx["member"],
                                            ctx.get("roles") or [], channel)
    if not perms.has_permission(effectives, bit):
        warn(f"Permission manquante dans ce salon : {libelle}.")
        return False
    return True


# ---------------------------------------------------------------------------
# Rendu du dashboard
# ---------------------------------------------------------------------------

def _render_header():
    title = Text("PANEL DE CONTROLE & AUDIT DISCORD", style=f"bold {C_DISCORD}")
    return Panel(Align.center(title), box=BX, border_style=C_DISCORD)


def _render_identite(bot_data, guilds, selected, gateway):
    table = Table.grid(padding=(0, 2))
    table.add_column(style=f"bold {C_DISCORD}", width=22)
    table.add_column()
    table.add_row("Bot", _tag(bot_data))
    table.add_row("ID", str(bot_data.get("id", "?")))
    table.add_row("Cree le", _date_snowflake(str(bot_data.get("id", ""))))
    table.add_row("Serveurs visibles (REST)", str(len(guilds)))
    table.add_row("Serveur cible", selected or "Aucun")
    return Panel(table, box=BX, border_style=C_DISCORD,
                 title=f"[bold {C_DISCORD}] Identite [/]", title_align="left")


def _render_gateway(gateway):
    latence = gateway.latency_ms
    uptime = gateway.uptime_seconds
    etat = getattr(gateway, "etat", None)
    if not isinstance(etat, str) or not etat:
        etat = "connectee" if gateway.connected else "arretee"
    libelles = {
        "connectee": ("CONNECTEE", "bold green"),
        "reconnexion": ("RECONNEXION EN COURS", "bold yellow"),
        "demarrage": ("INITIALISATION", "bold cyan"),
        "arretee": ("DECONNECTEE", "bold red"),
    }
    libelle, style = libelles.get(etat, ("DECONNECTEE", "bold red"))
    serveurs = getattr(gateway, "guild_count", None)
    table = Table.grid(padding=(0, 2))
    table.add_column(style=f"bold {C_DISCORD}", width=22)
    table.add_column()
    table.add_row("Gateway", Text(libelle, style=style))
    table.add_row("Latence", f"{latence} ms" if latence is not None else "indisponible")
    table.add_row("Session", f"{uptime} s" if uptime is not None else "indisponible")
    table.add_row("Serveurs (cache Gateway)",
                  str(serveurs) if serveurs is not None else "indisponible")
    table.add_row("Intents", "guilds : oui · members : non · message_content : non")
    table.add_row("Derniere erreur", gateway.last_error or "Aucune")

    elements = [table]
    evenements = gateway.log_messages[-5:]
    if evenements:
        elements.append(Text("\nEvenements Gateway :", style=f"bold {C_DISCORD}"))
        elements.extend(Text(event, style="dim") for event in evenements)
    return Panel(Group(*elements), box=BX, border_style=C_DISCORD,
                 title=f"[bold {C_DISCORD}] Connexion [/]", title_align="left")


def _render_permissions(ctx):
    permissions = permissions_du_bot(ctx)
    elements = []
    if permissions is None:
        elements.append(Text("Permissions indisponibles : le bot n'est pas membre "
                             "du serveur ou l'acces est refuse.", style="yellow"))
    else:
        table = Table(title="Permissions effectives du bot", box=BX,
                      border_style=C_GOLD)
        table.add_column("Permission")
        table.add_column("Etat")
        for libelle, bit in (
            ("Administrateur", perms.ADMINISTRATOR),
            ("Voir les salons", perms.VIEW_CHANNEL),
            ("Envoyer des messages", perms.SEND_MESSAGES),
            ("Gerer les salons", perms.MANAGE_CHANNELS),
            ("Gerer les roles", perms.MANAGE_ROLES),
            ("Gerer les webhooks", perms.MANAGE_WEBHOOKS),
            ("Moderer les membres", perms.MODERATE_MEMBERS),
            ("Expulser des membres", perms.KICK_MEMBERS),
        ):
            table.add_row(libelle, "Oui" if perms.has_permission(permissions, bit) else "Non")
        elements.append(table)
        elements.append(Text("Calcul base sur @everyone, les roles cumules, "
                             "Administrateur et les surcharges de salons.",
                             style="dim"))
    return Panel(Group(*elements), box=BX, border_style=C_GOLD,
                 title=f"[bold {C_GOLD}] Autorisations [/]", title_align="left")


def _render_derniers_evenements():
    entrees = journal_derniers(4)
    elements = []
    if not entrees:
        elements.append(Text("Aucune action journalisee pour le moment.", style="dim"))
    for entree in entrees:
        style = "green" if entree.get("resultat") == "ok" else "red"
        elements.append(Text(f"{entree.get('timestamp', '?')} · {entree.get('action', '?')} "
                             f"· {entree.get('resultat', '?')}", style=style))
    return Panel(Group(*elements), box=BX, border_style="grey50",
                 title="[bold] Journal local [/]", title_align="left")


def _render_dashboard(bot_data, guilds, etat, gateway):
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="body"),
        Layout(name="journal", size=7),
    )
    layout["body"].split_row(Layout(name="gauche", ratio=50),
                             Layout(name="droite", ratio=50))
    layout["header"].update(_render_header())
    layout["gauche"].update(Group(
        _render_identite(bot_data, guilds, etat.get("selected"), gateway),
        _render_gateway(gateway),
    ))
    layout["droite"].update(Group(
        _render_permissions(etat.get("ctx") or {}),
        _render_footer(),
    ))
    layout["journal"].update(_render_derniers_evenements())
    return layout


def _render_footer():
    labels = ["Serveurs", "Clonage", "Communication", "Salons", "Roles",
              "Moderation", "Gateway", "Actualiser", "Quitter"]
    return Panel(Align.center(Text(" · ".join(labels), style="bold white")),
                 box=BX, border_style="grey50")


# ---------------------------------------------------------------------------
# Serveurs
# ---------------------------------------------------------------------------

def _afficher_serveur(ctx):
    guild = ctx.get("guild") or {}
    table = Table.grid(padding=(0, 2))
    table.add_column(style="bold cyan", width=24)
    table.add_column()
    table.add_row("Nom", str(guild.get("name", "?")))
    table.add_row("ID", str(guild.get("id", "?")))
    table.add_row("Proprietaire", str(guild.get("owner_id", "?")))
    table.add_row("Cree le", _date_snowflake(str(guild.get("id", ""))))
    table.add_row("Membres (approx.)", str(guild.get("approximate_member_count", "non communique")))
    table.add_row("En ligne (approx.)", str(guild.get("approximate_presence_count", "non communique")))
    table.add_row("Salons charges", str(len(ctx.get("channels") or [])))
    table.add_row("Roles charges", str(len(ctx.get("roles") or [])))
    console.print(Panel(table, box=BX, border_style=C_DISCORD, title="Serveur cible"))
    if ctx.get("errors"):
        console.print("[bold yellow]Acces partiels ou refuses :[/]")
        for libelle, message in ctx["errors"]:
            console.print(f"  - {libelle} : {escape(message)}")


def libelle_membres(charge, maximum=100):
    """Etiquette honnete : une page de 100 membres n'est pas un audit complet."""
    texte = f"{charge} membre(s) charges (maximum {maximum}"
    if charge >= maximum:
        texte += ", liste tronquee"
    return texte + ")"


def afficher_membres(api, guild_id):
    """Liste au plus 100 membres via REST, sans pretendre a l'exhaustivite."""
    try:
        membres = api.guild_members(guild_id, 100)
    except DiscordNotFoundError:
        warn("Membres inaccessibles : intent ou permission manquante.")
        return
    except DiscordAPIError as exc:
        bad(f"Lecture des membres impossible : {exc}")
        return
    table = Table(title="Membres charges", box=BX, border_style=C_DISCORD)
    table.add_column("Utilisateur")
    table.add_column("ID", style="dim")
    table.add_column("A rejoint")
    for membre in membres:
        table.add_row(_tag(membre.get("user")), str((membre.get("user") or {}).get("id", "?")),
                      str(membre.get("joined_at") or "-"))
    console.print(table)
    console.print(f"[dim]{libelle_membres(len(membres))}[/]")


def _afficher_arborescence(ctx):
    channels = ctx.get("channels") or []
    categories = {str(c.get("id")): c.get("name", "?") for c in channels if c.get("type") == 4}
    if len(channels) > 25:
        rows = sorted(channels, key=lambda item: (item.get("position", 0), item.get("name", "")))
        afficher_pagine(
            f"Salons et categories ({len(rows)})",
            ["Type", "Nom", "Categorie", "Position", "ID"], rows,
            lambda canal: (perms.TYPES_SALON.get(canal.get("type"), f"Type {canal.get('type')}"),
                           str(canal.get("name", "?")),
                           categories.get(str(canal.get("parent_id") or ""), "-"),
                           str(canal.get("position", "-")), str(canal.get("id", "-"))),
            par_page=20, fichier="salons.csv", couleur=C_DISCORD)
        return
    table = Table(title="Salons et categories", box=BX, border_style=C_DISCORD)
    table.add_column("Type")
    table.add_column("Nom")
    table.add_column("Categorie")
    table.add_column("Position", justify="right")
    table.add_column("ID", style="dim")
    for canal in sorted(channels, key=lambda item: (item.get("position", 0), item.get("name", ""))):
        table.add_row(perms.TYPES_SALON.get(canal.get("type"), f"Type {canal.get('type')}"),
                      str(canal.get("name", "?")),
                      categories.get(str(canal.get("parent_id") or ""), "-"),
                      str(canal.get("position", "-")), str(canal.get("id", "-")))
    console.print(table)


def _afficher_roles(ctx):
    roles = sorted(ctx.get("roles") or [], key=lambda role: role.get("position", 0), reverse=True)
    if len(roles) > 25:
        def rendre(role):
            critiques = ", ".join(perms.permissions_excessives(role)) or "-"
            couleur = f"#{int(role.get('color', 0)):06x}" if role.get("color") else "-"
            return (str(role.get("name", "?")), str(role.get("position", "-")),
                    couleur, critiques, str(role.get("id", "-")))
        afficher_pagine(
            f"Roles et permissions ({len(roles)})",
            ["Role", "Position", "Couleur", "Permissions critiques", "ID"], roles,
            rendre, par_page=20, fichier="roles.csv", couleur=C_GOLD)
        return
    table = Table(title="Roles et permissions", box=BX, border_style=C_GOLD)
    table.add_column("Role")
    table.add_column("Position", justify="right")
    table.add_column("Couleur")
    table.add_column("Permissions critiques")
    table.add_column("ID", style="dim")
    for role in roles:
        critiques = ", ".join(perms.permissions_excessives(role)) or "-"
        couleur = f"#{int(role.get('color', 0)):06x}" if role.get("color") else "-"
        table.add_row(str(role.get("name", "?")), str(role.get("position", "-")),
                      couleur, critiques, str(role.get("id", "-")))
    console.print(table)


def _afficher_surcharges(ctx):
    channel = _choisir_salon(ctx, types={0, 2, 4, 5, 13, 15}, label="SALON A INSPECTER")
    if channel is None:
        return
    lignes = perms.resume_surcharges(channel)
    if not lignes:
        warn("Aucune surcharge de permissions sur ce salon.")
        return
    table = Table(title=f"Surcharges · #{channel.get('name')}", box=BX, border_style=C_GOLD)
    table.add_column("Cible")
    table.add_column("Type")
    table.add_column("Accordees")
    table.add_column("Refusees")
    for ligne in lignes:
        table.add_row(ligne["cible"], str(ligne["type"]), ligne["accordees"], ligne["refusees"])
    console.print(table)


def _afficher_webhooks(ctx):
    webhooks = ctx.get("webhooks") or []
    erreur = next((message for libelle, message in ctx.get("errors") or ()
                   if libelle == "webhooks"), None)
    if erreur:
        warn(f"Webhooks non listes : {erreur}")
    if not webhooks:
        warn("Aucun webhook retourne (serveur sans webhook ou permission MANAGE_WEBHOOKS manquante).")
        return
    table = Table(title=f"Webhooks accessibles ({len(webhooks)})", box=BX, border_style="red")
    table.add_column("Nom")
    table.add_column("ID")
    table.add_column("Salon")
    table.add_column("Jetons")
    for webhook in webhooks:
        table.add_row(str(webhook.get("name", "?")), str(webhook.get("id", "-")),
                      str(webhook.get("channel_id", "-")), "masques")
    console.print(table)


def _creer_webhook(api, etat, token):
    ctx = etat["ctx"]
    channel = _choisir_salon(ctx)
    if channel is None:
        return
    if not _verifier_salon(ctx, channel, perms.MANAGE_WEBHOOKS, "Gerer les webhooks"):
        return
    nom = demander("Nom du webhook", "leakfr-audit").strip()
    if not nom or len(nom) > 80:
        bad("Nom de webhook invalide (1 a 80 caracteres).")
        return
    if not Confirm.ask(f"Creer le webhook '{nom}' dans #{channel.get('name')} ?",
                       default=False):
        return
    try:
        webhook = api.creer_webhook(str(channel.get("id")), {"name": nom})
    except DiscordAPIError as exc:
        bad(f"Creation refusee : {exc}")
        journaliser("creation_webhook", etat["selected"], str(channel.get("id")),
                    "erreur", str(exc), (token,))
        return
    identifiant = str((webhook or {}).get("id") or "?")
    ok(f"Webhook cree (ID {identifiant}).")
    if webhook and webhook.get("url"):
        console.print(Panel(
            f"URL complete (jeton inclus, affiche une seule fois) :\n"
            f"{escape(str(webhook['url']))}\n\n"
            "Conservez-la dans un gestionnaire de secrets. Elle n'est pas journalisee.",
            title="Secret du webhook", border_style="red"))
    journaliser("creation_webhook", etat["selected"], identifiant, "ok",
                f"salon {channel.get('id')}", (token,))
    try:
        ctx["webhooks"] = api.guild_webhooks(etat["selected"])
    except DiscordAPIError:
        pass


def _supprimer_webhook(api, etat, token):
    ctx = etat["ctx"]
    webhooks = ctx.get("webhooks") or []
    if not webhooks:
        warn("Aucun webhook accessible a supprimer.")
        return
    if not verifier_permission(ctx, perms.MANAGE_WEBHOOKS, "Gerer les webhooks"):
        return
    libelles = [f"{webhook.get('name', '?')} ({webhook.get('id')})" for webhook in webhooks]
    choix = choisir_option("WEBHOOK A SUPPRIMER", libelles + ["Retour"])
    if choix in (None, "Retour"):
        return
    webhook = webhooks[libelles.index(choix)]
    if not Confirm.ask(f"Supprimer definitivement le webhook '{webhook.get('name')}' ?",
                       default=False):
        return
    if not Confirm.ask("Confirmer une seconde fois la suppression ?", default=False):
        warn("Suppression annulee.")
        return
    try:
        api.supprimer_webhook(str(webhook.get("id")))
    except DiscordAPIError as exc:
        bad(f"Suppression refusee : {exc}")
        journaliser("suppression_webhook", etat["selected"], str(webhook.get("id")),
                    "erreur", str(exc), (token,))
        return
    ok("Webhook supprime.")
    journaliser("suppression_webhook", etat["selected"], str(webhook.get("id")),
                "ok", "confirmee", (token,))
    ctx["webhooks"] = [item for item in webhooks if item.get("id") != webhook.get("id")]


def _menu_webhooks(api, etat, token):
    while True:
        choix = choisir_option("WEBHOOKS DU SERVEUR", [
            "Lister les webhooks", "Creer un webhook", "Supprimer un webhook", "Retour"])
        if choix in (None, "Retour"):
            return
        if choix == "Lister les webhooks":
            _afficher_webhooks(etat["ctx"])
        elif choix == "Creer un webhook":
            _creer_webhook(api, etat, token)
        elif choix == "Supprimer un webhook":
            _supprimer_webhook(api, etat, token)
        pause()


def _exporter_audit(guild_id, ctx):
    path = _save_guild_audit(guild_id, ctx, permissions_du_bot(ctx), ctx.get("errors"))
    ok(f"Audit exporte sans tokens ni messages : {path}")


def _save_guild_audit(guild_id, guild_info, permissions=None, erreurs=None):
    """Exporte un resume JSON sans identifiants secrets ni contenu de messages."""
    guild = guild_info.get("guild") or {}
    snapshot = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "guild": {cle: guild.get(cle) for cle in
                  ("id", "name", "owner_id", "approximate_member_count",
                   "approximate_presence_count")},
        "channels": [
            {cle: canal.get(cle) for cle in
             ("id", "name", "type", "parent_id", "position", "nsfw")}
            for canal in guild_info.get("channels", [])
        ],
        "roles": [
            {cle: role.get(cle) for cle in ("id", "name", "position", "permissions")}
            for role in guild_info.get("roles", [])
        ],
        "webhooks": [
            {cle: webhook.get(cle) for cle in ("id", "name", "channel_id")}
            for webhook in guild_info.get("webhooks", [])
        ],
        "members_loaded": len(guild_info.get("members", [])),
        "permissions": permissions,
        "permission_names": perms.permission_labels(permissions or 0),
        "access_errors": [{"endpoint": libelle, "message": message}
                          for libelle, message in (erreurs or [])],
    }
    Path(EXPORTS_DIR).mkdir(parents=True, exist_ok=True)
    path = Path(EXPORTS_DIR) / f"guild_{guild_id}_audit.json"
    path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _modifier_surnom(api, etat, token):
    ctx = etat["ctx"]
    if not verifier_permission(ctx, perms.CHANGE_NICKNAME, "Changer le surnom"):
        return
    surnom = demander("Nouveau surnom du bot (vide pour le retirer)", "").strip()
    if len(surnom) > 32:
        bad("Le surnom ne peut pas depasser 32 caracteres.")
        return
    if not Confirm.ask("Confirmer le changement de surnom du bot ?", default=False):
        return
    try:
        api.modifier_propre_membre(etat["selected"], {"nick": surnom or None})
    except DiscordAPIError as exc:
        bad(f"Changement de surnom refuse : {exc}")
        journaliser("surnom_bot", etat["selected"], "@me", "erreur", str(exc), (token,))
        return
    ok("Surnom mis a jour.")
    journaliser("surnom_bot", etat["selected"], "@me", "ok", surnom or "retire", (token,))


def _creer_invitation(api, etat, token):
    channel = _choisir_salon(etat["ctx"])
    if channel is None:
        return
    if not _verifier_salon(etat["ctx"], channel, perms.CREATE_INSTANT_INVITE,
                           "Creer une invitation"):
        return
    if not Confirm.ask("Creer une invitation valable 1 heure et 1 utilisation ?",
                       default=False):
        return
    try:
        invitation = api.creer_invitation(str(channel.get("id")),
                                          {"max_age": 3600, "max_uses": 1, "unique": True})
    except DiscordAPIError as exc:
        bad(f"Invitation refusee : {exc}")
        journaliser("invitation", etat["selected"], str(channel.get("id")),
                    "erreur", str(exc), (token,))
        return
    code = str((invitation or {}).get("code") or "")
    if not code:
        warn("Invitation creee mais aucun code retourne par l'API.")
        return
    console.print(Panel(f"https://discord.gg/{code}", title="Invitation temporaire",
                        border_style=C_DISCORD))
    ok("Invitation creee (1 heure, 1 utilisation).")
    journaliser("invitation", etat["selected"], str(channel.get("id")), "ok",
                "1h / 1 utilisation", (token,))


def menu_serveurs(api, etat, token):
    while True:
        choix = choisir_option("SERVEURS & PERMISSIONS", [
            "Rechercher / selectionner un serveur", "Details du serveur",
            "Salons et categories", "Roles", "Surcharges de permissions",
            "Webhooks (lister / creer / supprimer)", "Membres charges (max 100)", "Verifier les permissions",
            "Modifier le surnom du bot", "Creer une invitation temporaire",
            "Exporter l'audit JSON", "Retour",
        ])
        if choix in (None, "Retour"):
            return
        ctx = etat.get("ctx")
        if choix == "Rechercher / selectionner un serveur":
            requete = demander("Recherche (nom ou ID, vide pour tout)", "")
            trouves = filtrer_guildes(etat["guilds"], requete)
            if not trouves:
                warn("Aucun serveur ne correspond.")
                continue
            libelles = [f"{g.get('name', '?')} ({g.get('id')})" for g in trouves[:40]]
            cible = choisir_option("SERVEURS TROUVES", libelles + ["Retour"])
            if cible in (None, "Retour"):
                continue
            selected = trouves[libelles.index(cible)]
            etat["selected"] = str(selected.get("id"))
            with attente("Chargement du serveur"):
                etat["ctx"] = charger_contexte(api, etat["selected"], etat["bot_id"])
            ok(f"Serveur cible : {selected.get('name')}.")
        elif not ctx or not ctx.get("guild"):
            warn("Selectionnez d'abord un serveur accessible.")
        elif choix == "Details du serveur":
            _afficher_serveur(ctx)
        elif choix == "Salons et categories":
            _afficher_arborescence(ctx)
        elif choix == "Roles":
            _afficher_roles(ctx)
        elif choix == "Surcharges de permissions":
            _afficher_surcharges(ctx)
        elif choix == "Webhooks (lister / creer / supprimer)":
            _menu_webhooks(api, etat, token)
        elif choix == "Membres charges (max 100)":
            afficher_membres(api, etat["selected"])
        elif choix == "Modifier le surnom du bot":
            _modifier_surnom(api, etat, token)
        elif choix == "Creer une invitation temporaire":
            _creer_invitation(api, etat, token)
        elif choix == "Verifier les permissions":
            permissions = permissions_du_bot(ctx)
            if permissions is None:
                warn("Permissions indisponibles.")
            else:
                kv("Permissions effectives", [(nom, "Oui") for nom in
                                              perms.permission_labels(permissions)], C_DISCORD)
        elif choix == "Exporter l'audit JSON":
            if not ctx or not ctx.get("guild"):
                warn("Aucun serveur charge.")
                continue
            try:
                _exporter_audit(etat["selected"], ctx)
                journaliser("export_audit", etat["selected"], etat["selected"], "ok",
                            "export JSON sans secret", (token,))
            except OSError as exc:
                bad(f"Export impossible : {exc}")
                journaliser("export_audit", etat.get("selected"), "", "erreur", str(exc), (token,))
        pause()


# ---------------------------------------------------------------------------
# Communication
# ---------------------------------------------------------------------------

def _apercu_embed(embed):
    table = Table.grid(padding=(0, 2))
    table.add_column(style="bold", width=14)
    table.add_column()
    table.add_row("Titre", str(embed.get("title") or "—"))
    table.add_row("Description", str(embed.get("description") or "—"))
    couleur = embed.get("color")
    table.add_row("Couleur", f"#{couleur:06x}" if isinstance(couleur, int) else "—")
    table.add_row("Footer", str((embed.get("footer") or {}).get("text") or "—"))
    return Panel(table, box=BX, border_style=C_DISCORD, title="Apercu de l'embed")


def _construire_embed():
    titre_embed = demander("Titre de l'embed (vide pour aucun)", "").strip()
    description = demander("Description", "").strip()
    couleur_txt = demander("Couleur hexadecimale (ex: #5865F2, vide pour aucune)", "").strip()
    footer = demander("Pied de page (facultatif)", "").strip()
    if not titre_embed and not description:
        warn("Embed vide : titre ou description requis.")
        return None
    couleur = None
    if couleur_txt:
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", couleur_txt):
            warn("Couleur invalide : format #RRGGBB attendu.")
            return None
        couleur = int(couleur_txt[1:], 16)
    embed = {}
    if titre_embed:
        embed["title"] = titre_embed[:256]
    if description:
        embed["description"] = description[:4000]
    if couleur is not None:
        embed["color"] = couleur
    if footer:
        embed["footer"] = {"text": footer[:2048]}
    return embed


def _charger_modeles():
    donnees = charger_json(TEMPLATES_FILE, [])
    return [modele for modele in donnees if isinstance(modele, dict)
            and modele.get("nom") and modele.get("contenu")]


def _enregistrer_modele(nom, contenu):
    if not nom.strip() or not contenu.strip():
        raise ValueError("Nom et contenu obligatoires.")
    if len(contenu) > 2000:
        raise ValueError("Un message Discord est limite a 2000 caracteres.")
    modeles = _charger_modeles()
    modeles = [modele for modele in modeles if modele["nom"] != nom.strip()]
    modeles.append({"nom": nom.strip()[:60], "contenu": contenu})
    ecrire_json(TEMPLATES_FILE, modeles[-50:])


def _envoyer_fichier(api, etat, token):
    ctx = etat["ctx"]
    channel = _choisir_salon(ctx)
    if channel is None:
        return
    if not _verifier_salon(ctx, channel, perms.SEND_MESSAGES, "Envoyer des messages"):
        return
    if not _verifier_salon(ctx, channel, perms.ATTACH_FILES, "Joindre des fichiers"):
        return
    chemin_txt = demander("Chemin du fichier a envoyer", "").strip()
    if not chemin_txt:
        return
    chemin = Path(chemin_txt).expanduser()
    try:
        taille = chemin.stat().st_size
        if not chemin.is_file():
            raise OSError("ce n'est pas un fichier")
        if taille == 0:
            raise OSError("fichier vide")
        if taille > 10 * 1024 * 1024:
            raise OSError("fichier superieur a 10 Mio")
        donnees = chemin.read_bytes()
    except OSError as exc:
        bad(f"Fichier invalide : {exc}")
        return
    contenu = demander("Message accompagne (facultatif)", "").strip()
    type_mime = mimetypes.guess_type(chemin.name)[0] or "application/octet-stream"
    console.print(Panel(
        f"Fichier : {escape(chemin.name)} ({taille / 1024:.1f} Kio)\n"
        f"Type : {type_mime}\nSalon : #{escape(str(channel.get('name')))}",
        title="Apercu de l'envoi", border_style=C_DISCORD))
    if not Confirm.ask("Confirmer l'envoi du fichier ?", default=False):
        return
    try:
        message = api.envoyer_fichier(str(channel.get("id")), contenu,
                                      chemin.name, donnees, type_mime)
    except DiscordAPIError as exc:
        bad(f"Envoi refuse : {exc}")
        journaliser("envoi_fichier", etat["selected"], str(channel.get("id")),
                    "erreur", str(exc), (token,))
        return
    ok(f"Fichier envoye (message {str((message or {}).get('id') or '?')}).")
    journaliser("envoi_fichier", etat["selected"], str(channel.get("id")), "ok",
                f"{chemin.name} ({taille} octets)", (token,))


def _envoyer(api, channel_id, payload, token, libelle):
    try:
        message = api.envoyer_message(channel_id, payload)
    except DiscordForbiddenError as exc:
        bad(f"{libelle} refuse : {exc}")
        journaliser(libelle, "", channel_id, "erreur", str(exc), (token,))
        return None
    except DiscordAPIError as exc:
        bad(f"{libelle} impossible : {exc}")
        journaliser(libelle, "", channel_id, "erreur", str(exc), (token,))
        return None
    message_id = str((message or {}).get("id") or "?")
    ok(f"{libelle} envoye (message {message_id}).")
    journaliser(libelle, "", channel_id, "ok", f"message {message_id}", (token,))
    return message


def menu_communication(api, etat, token):
    while True:
        choix = choisir_option("COMMUNICATION", [
            "Envoyer un message (apercu)", "Envoyer un fichier",
            "Creer un embed (apercu)", "Preparer une annonce",
            "Creer un sondage", "Modeles de messages", "Retour",
        ])
        if choix in (None, "Retour"):
            return
        ctx = etat.get("ctx")
        if not ctx or not ctx.get("guild"):
            warn("Selectionnez d'abord un serveur.")
            continue

        if choix == "Modeles de messages":
            _menu_modeles()
            continue
        if choix == "Envoyer un fichier":
            _envoyer_fichier(api, etat, token)
            pause()
            continue

        channel = _choisir_salon(ctx)
        if channel is None:
            continue
        if not _verifier_salon(ctx, channel, perms.SEND_MESSAGES, "Envoyer des messages"):
            pause()
            continue

        if choix == "Envoyer un message (apercu)":
            contenu = demander("Message a envoyer").strip()
            if not contenu or len(contenu) > 2000:
                warn("Message vide ou superieur a 2000 caracteres.")
                pause()
                continue
            console.print(Panel(escape(contenu), title="Apercu du message",
                                border_style=C_DISCORD))
            if Confirm.ask("Confirmer l'envoi ?", default=False):
                _envoyer(api, str(channel.get("id")), {"content": contenu}, token, "envoi_message")

        elif choix == "Creer un embed (apercu)":
            embed = _construire_embed()
            if embed is None:
                pause()
                continue
            console.print(_apercu_embed(embed))
            if Confirm.ask("Confirmer l'envoi de l'embed ?", default=False):
                _envoyer(api, str(channel.get("id")), {"embeds": [embed]}, token, "envoi_embed")

        elif choix == "Preparer une annonce":
            contenu = demander("Texte de l'annonce").strip()
            if not contenu or len(contenu) > 2000:
                warn("Annonce vide ou trop longue.")
                pause()
                continue
            if re.search(r"@(everyone|here)\b", contenu, re.IGNORECASE):
                warn("Les mentions de masse @everyone/@here sont refusees par ce panel.")
                pause()
                continue
            embed = _construire_embed()
            console.print(Panel(escape(contenu), title="Apercu de l'annonce",
                                border_style=C_GOLD))
            if embed:
                console.print(_apercu_embed(embed))
            if Confirm.ask("Confirmer la publication de l'annonce ?", default=False):
                payload = {"content": contenu, "allowed_mentions": {"parse": []}}
                if embed:
                    payload["embeds"] = [embed]
                _envoyer(api, str(channel.get("id")), payload, token, "annonce")

        elif choix == "Creer un sondage":
            question = demander("Question du sondage").strip()
            reponses = []
            for index in range(1, 5):
                reponse = demander(f"Reponse {index} (vide pour terminer)", "").strip()
                if not reponse:
                    break
                reponses.append(reponse)
            if not question or len(reponses) < 2:
                warn("Un sondage exige une question et au moins deux reponses.")
                pause()
                continue
            duree_txt = demander("Duree en heures (1-768)", "24").strip()
            if not duree_txt.isdigit() or not 1 <= int(duree_txt) <= 768:
                warn("Duree invalide.")
                pause()
                continue
            payload = {"poll": {
                "question": {"text": question[:300]},
                "answers": [{"poll_media": {"text": reponse[:55]}} for reponse in reponses[:10]],
                "duration": int(duree_txt),
                "allow_multiselect": False,
            }}
            table = Table(title="Apercu du sondage", box=BX, border_style=C_DISCORD)
            table.add_column("Question")
            table.add_column("Reponses")
            table.add_column("Duree")
            table.add_row(question, " | ".join(reponses), f"{duree_txt} h")
            console.print(table)
            if Confirm.ask("Confirmer la publication du sondage ?", default=False):
                _envoyer(api, str(channel.get("id")), payload, token, "sondage")
        pause()


def _menu_modeles():
    while True:
        modeles = _charger_modeles()
        choix = choisir_option("MODELES DE MESSAGES", [
            "Lister", "Creer ou remplacer", "Supprimer", "Retour"])
        if choix in (None, "Retour"):
            return
        if choix == "Lister":
            if not modeles:
                warn("Aucun modele enregistre.")
            for modele in modeles:
                console.print(Panel(escape(modele["contenu"]),
                                    title=escape(modele["nom"]), border_style=C_DISCORD))
        elif choix == "Creer ou remplacer":
            nom = demander("Nom du modele").strip()
            contenu = demander("Contenu du modele").strip()
            try:
                _enregistrer_modele(nom, contenu)
            except (ValueError, OSError) as exc:
                bad(str(exc))
            else:
                ok("Modele enregistre localement.")
        elif choix == "Supprimer":
            if not modeles:
                warn("Aucun modele a supprimer.")
                continue
            nom = choisir_option("MODELE A SUPPRIMER",
                                 [modele["nom"] for modele in modeles] + ["Retour"])
            if nom in (None, "Retour"):
                continue
            restants = [modele for modele in modeles if modele["nom"] != nom]
            try:
                ecrire_json(TEMPLATES_FILE, restants)
            except OSError as exc:
                bad(f"Suppression impossible : {exc}")
            else:
                ok("Modele supprime.")
        pause()


# ---------------------------------------------------------------------------
# Salons
# ---------------------------------------------------------------------------

def _categories(ctx):
    return [canal for canal in ctx.get("channels") or [] if canal.get("type") == 4]


def _choisir_categorie(ctx):
    categories = _categories(ctx)
    if not categories:
        return None
    libelles = [str(categorie.get("name", "?")) for categorie in categories]
    choix = choisir_option("CATEGORIE", libelles + ["Aucune", "Retour"])
    if choix in (None, "Retour"):
        return None
    if choix == "Aucune":
        return None
    return categories[libelles.index(choix)]


def _creer_salon(api, etat, token):
    type_nom = choisir_option("TYPE DE SALON", list(TYPES_SALON_CHOIX))
    if type_nom is None:
        return
    type_id = TYPES_SALON_CHOIX[type_nom]
    nom = demander("Nom du salon", "audit-security").strip()
    try:
        nom = _slug_channel_name(nom)
    except ValueError as exc:
        bad(str(exc))
        return
    payload = {"name": nom, "type": type_id}
    if type_id in TYPES_SALON_ECRITURE:
        sujet = demander("Sujet (facultatif)", "").strip()
        if sujet:
            payload["topic"] = sujet[:1024]
        nsfw = Confirm.ask("Salon NSFW ?", default=False)
        payload["nsfw"] = nsfw
    parent = _choisir_categorie(etat["ctx"])
    if parent is not None:
        payload["parent_id"] = str(parent.get("id"))

    table = Table(title="Apercu de creation", box=BX, border_style=C_DISCORD)
    table.add_column("Champ")
    table.add_column("Valeur")
    for cle, valeur in payload.items():
        table.add_row(cle, str(valeur))
    console.print(table)
    if not Confirm.ask("Confirmer la creation de ce salon ?", default=False):
        return
    try:
        canal = api.creer_salon(etat["selected"], payload)
    except DiscordAPIError as exc:
        bad(f"Creation refusee : {exc}")
        journaliser("creation_salon", etat["selected"], nom, "erreur", str(exc), (token,))
        return
    etat["ctx"]["channels"].append(canal)
    ok(f"Salon #{canal.get('name')} cree (ID {canal.get('id')}).")
    journaliser("creation_salon", etat["selected"], str(canal.get("id")), "ok",
                f"type {type_id}", (token,))


def _modifier_salon(api, etat, token):
    channel = _choisir_salon(etat["ctx"], types={0, 2, 5, 15})
    if channel is None:
        return
    if not _verifier_salon(etat["ctx"], channel, perms.MANAGE_CHANNELS, "Gerer les salons"):
        return
    champ = choisir_option("CHAMP A MODIFIER", ["Nom", "Sujet", "NSFW", "Mode lent", "Retour"])
    if champ in (None, "Retour"):
        return
    payload = {}
    if champ == "Nom":
        try:
            payload["name"] = _slug_channel_name(demander("Nouveau nom", channel.get("name", "")))
        except ValueError as exc:
            bad(str(exc))
            return
    elif champ == "Sujet":
        payload["topic"] = demander("Nouveau sujet", channel.get("topic") or "")[:1024]
    elif champ == "NSFW":
        payload["nsfw"] = Confirm.ask("Marquer ce salon comme NSFW ?", default=False)
    elif champ == "Mode lent":
        valeur = demander("Mode lent en secondes (0-21600)", "0")
        if not valeur.isdigit() or not 0 <= int(valeur) <= 21600:
            bad("Valeur de mode lent invalide.")
            return
        payload["rate_limit_per_user"] = int(valeur)

    table = Table(title="Apercu de la modification", box=BX, border_style=C_GOLD)
    table.add_column("Champ")
    table.add_column("Avant")
    table.add_column("Apres")
    for cle, valeur in payload.items():
        avant = channel.get("rate_limit_per_user" if cle == "rate_limit_per_user" else cle, "-")
        table.add_row(cle, str(avant), str(valeur))
    console.print(table)
    if not Confirm.ask("Appliquer cette modification ?", default=False):
        return
    try:
        mis_a_jour = api.modifier_salon(str(channel.get("id")), payload)
    except DiscordAPIError as exc:
        bad(f"Modification refusee : {exc}")
        journaliser("modification_salon", etat["selected"], str(channel.get("id")),
                    "erreur", str(exc), (token,))
        return
    channel.update(mis_a_jour or payload)
    ok("Salon mis a jour.")
    journaliser("modification_salon", etat["selected"], str(channel.get("id")), "ok",
                ", ".join(payload), (token,))


def _deplacer_salon(api, etat, token):
    channel = _choisir_salon(etat["ctx"], types={0, 2, 5, 15})
    if channel is None:
        return
    if not _verifier_salon(etat["ctx"], channel, perms.MANAGE_CHANNELS, "Gerer les salons"):
        return
    parent = _choisir_categorie(etat["ctx"])
    position_txt = demander("Position (entier)", str(channel.get("position", 0)))
    if not position_txt.lstrip("-").isdigit():
        bad("Position invalide.")
        return
    payload = {"position": int(position_txt), "parent_id": str(parent.get("id")) if parent else None}
    table = Table(title="Apercu du deplacement", box=BX, border_style=C_GOLD)
    table.add_column("Champ")
    table.add_column("Avant")
    table.add_column("Apres")
    table.add_row("parent_id", str(channel.get("parent_id") or "-"), str(payload["parent_id"]))
    table.add_row("position", str(channel.get("position", "-")), str(payload["position"]))
    console.print(table)
    if not Confirm.ask("Confirmer le deplacement ?", default=False):
        return
    try:
        api.modifier_salon(str(channel.get("id")), payload)
    except DiscordAPIError as exc:
        bad(f"Deplacement refuse : {exc}")
        journaliser("deplacement_salon", etat["selected"], str(channel.get("id")),
                    "erreur", str(exc), (token,))
        return
    channel.update(payload)
    ok("Salon deplace.")
    journaliser("deplacement_salon", etat["selected"], str(channel.get("id")), "ok",
                str(payload), (token,))


def _creer_categorie(api, etat, token):
    if not verifier_permission(etat["ctx"], perms.MANAGE_CHANNELS, "Gerer les salons"):
        return
    try:
        nom = _slug_channel_name(demander("Nom de la categorie", "audit"))
    except ValueError as exc:
        bad(str(exc))
        return
    if not Confirm.ask(f"Creer la categorie '{nom}' ?", default=False):
        return
    try:
        canal = api.creer_salon(etat["selected"], {"name": nom, "type": 4})
    except DiscordAPIError as exc:
        bad(f"Creation refusee : {exc}")
        journaliser("creation_categorie", etat["selected"], nom, "erreur", str(exc), (token,))
        return
    etat["ctx"]["channels"].append(canal)
    ok("Categorie creee.")
    journaliser("creation_categorie", etat["selected"], str(canal.get("id")), "ok", nom, (token,))


def _renommer_categorie(api, etat, token):
    categories = _categories(etat["ctx"])
    if not categories:
        warn("Aucune categorie chargee.")
        return
    if not verifier_permission(etat["ctx"], perms.MANAGE_CHANNELS, "Gerer les salons"):
        return
    libelles = [str(categorie.get("name", "?")) for categorie in categories]
    choix = choisir_option("CATEGORIE A RENOMMER", libelles + ["Retour"])
    if choix in (None, "Retour"):
        return
    categorie = categories[libelles.index(choix)]
    try:
        nouveau = _slug_channel_name(demander("Nouveau nom", categorie.get("name", "")))
    except ValueError as exc:
        bad(str(exc))
        return
    table = Table(title="Apercu du renommage", box=BX, border_style=C_GOLD)
    table.add_column("Champ")
    table.add_column("Avant")
    table.add_column("Apres")
    table.add_row("name", str(categorie.get("name", "-")), nouveau)
    console.print(table)
    if not Confirm.ask("Confirmer le renommage de la categorie ?", default=False):
        return
    try:
        mis_a_jour = api.modifier_salon(str(categorie.get("id")), {"name": nouveau})
    except DiscordAPIError as exc:
        bad(f"Renommage refuse : {exc}")
        journaliser("renommage_categorie", etat["selected"], str(categorie.get("id")),
                    "erreur", str(exc), (token,))
        return
    categorie.update(mis_a_jour or {"name": nouveau})
    ok("Categorie renommee.")
    journaliser("renommage_categorie", etat["selected"], str(categorie.get("id")), "ok",
                nouveau, (token,))


def menu_salons(api, etat, token):
    while True:
        choix = choisir_option("SALONS & CATEGORIES", [
            "Lister les salons", "Creer un salon", "Creer une categorie",
            "Renommer une categorie", "Modifier un salon", "Deplacer un salon",
            "Retour"])
        if choix in (None, "Retour"):
            return
        ctx = etat.get("ctx")
        if not ctx or not ctx.get("guild"):
            warn("Selectionnez d'abord un serveur.")
            continue
        if choix == "Lister les salons":
            _afficher_arborescence(ctx)
        elif choix == "Creer un salon":
            if verifier_permission(ctx, perms.MANAGE_CHANNELS, "Gerer les salons"):
                _creer_salon(api, etat, token)
        elif choix == "Creer une categorie":
            _creer_categorie(api, etat, token)
        elif choix == "Renommer une categorie":
            _renommer_categorie(api, etat, token)
        elif choix == "Modifier un salon":
            _modifier_salon(api, etat, token)
        elif choix == "Deplacer un salon":
            _deplacer_salon(api, etat, token)
        pause()


# ---------------------------------------------------------------------------
# Roles
# ---------------------------------------------------------------------------

def _comparer_roles(ctx):
    role_a = _choisir_role(ctx, "PREMIER ROLE")
    if role_a is None:
        return
    role_b = _choisir_role(ctx, "SECOND ROLE")
    if role_b is None:
        return
    difference = perms.comparaison_roles(role_a, role_b)
    table = Table(title="Comparaison des roles", box=BX, border_style=C_GOLD)
    table.add_column("Role")
    table.add_column("Ajoutees")
    table.add_column("Retirees")
    table.add_row(f"{role_a.get('name')} -> {role_b.get('name')}",
                  ", ".join(difference["ajoutees"]) or "-",
                  ", ".join(difference["retirees"]) or "-")
    console.print(table)


def _modifier_role(api, etat, token):
    ctx = etat["ctx"]
    if not verifier_permission(ctx, perms.MANAGE_ROLES, "Gerer les roles"):
        return
    role = _choisir_role(ctx)
    if role is None:
        return
    bot_top = perms.position_role_le_plus_haut(ctx.get("member"), ctx.get("roles") or [])
    if not perms.peut_gerer_role(permissions_du_bot(ctx), bot_top, role):
        warn("Hierarchie Discord : ce role est au-dessus du role le plus haut du bot.")
        return
    payload = {}
    nom = demander("Nouveau nom (vide pour conserver)", "").strip()
    if nom:
        payload["name"] = nom[:100]
    couleur = demander("Couleur #RRGGBB (vide pour conserver)", "").strip()
    if couleur:
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", couleur):
            bad("Couleur invalide.")
            return
        payload["color"] = int(couleur[1:], 16)
    permissions_txt = demander("Permissions (decimal ou 0x..., vide pour conserver)", "").strip()
    if permissions_txt:
        try:
            valeur = int(permissions_txt, 0)
        except ValueError:
            bad("Permissions invalides : entier decimal ou hexadecimal attendu.")
            return
        if valeur < 0 or valeur >= (1 << 64):
            bad("Permissions hors limites.")
            return
        payload["permissions"] = str(valeur)
    if not payload:
        warn("Aucune modification saisie.")
        return
    table = Table(title="Apercu de la modification du role", box=BX, border_style=C_GOLD)
    table.add_column("Champ")
    table.add_column("Avant")
    table.add_column("Apres")
    for cle, valeur in payload.items():
        table.add_row(cle, str(role.get(cle, "-")), str(valeur))
    console.print(table)
    if not Confirm.ask("Appliquer cette modification ?", default=False):
        return
    try:
        mis_a_jour = api.modifier_role(etat["selected"], str(role.get("id")), payload)
    except DiscordAPIError as exc:
        bad(f"Modification refusee : {exc}")
        journaliser("modification_role", etat["selected"], str(role.get("id")),
                    "erreur", str(exc), (token,))
        return
    role.update(mis_a_jour or payload)
    ok("Role mis a jour.")
    journaliser("modification_role", etat["selected"], str(role.get("id")), "ok",
                ", ".join(payload), (token,))


def _creer_role(api, etat, token):
    ctx = etat["ctx"]
    if not verifier_permission(ctx, perms.MANAGE_ROLES, "Gerer les roles"):
        return
    nom = demander("Nom du role", "audit").strip()
    if not nom or len(nom) > 100:
        bad("Nom de role invalide (1 a 100 caracteres).")
        return
    couleur = demander("Couleur #RRGGBB (vide pour aucune)", "").strip()
    payload = {"name": nom, "hoist": Confirm.ask("Afficher separement ?", default=False),
               "mentionable": Confirm.ask("Mentionnable ?", default=False)}
    if couleur:
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", couleur):
            bad("Couleur invalide.")
            return
        payload["color"] = int(couleur[1:], 16)
    permissions_txt = demander("Permissions (decimal/hex, vide pour aucune)", "").strip()
    if permissions_txt:
        try:
            valeur = int(permissions_txt, 0)
        except ValueError:
            bad("Permissions invalides.")
            return
        if valeur < 0 or valeur >= (1 << 64):
            bad("Permissions hors limites.")
            return
        payload["permissions"] = str(valeur)
    table = Table(title="Apercu du nouveau role", box=BX, border_style=C_GOLD)
    table.add_column("Champ")
    table.add_column("Valeur")
    for cle, valeur in payload.items():
        table.add_row(cle, str(valeur))
    console.print(table)
    console.print("[dim]Le role sera cree sous la hierarchie du bot. "
                  "Discord reste l'autorite finale.[/]")
    if not Confirm.ask("Confirmer la creation du role ?", default=False):
        return
    try:
        role = api.creer_role(etat["selected"], payload)
    except DiscordAPIError as exc:
        bad(f"Creation refusee : {exc}")
        journaliser("creation_role", etat["selected"], nom, "erreur", str(exc), (token,))
        return
    if not role or not role.get("id"):
        bad("Role cree sans identifiant retourne : etat local non modifie.")
        return
    ctx.setdefault("roles", []).append(role)
    ok(f"Role {role.get('name')} cree (ID {role.get('id')}).")
    journaliser("creation_role", etat["selected"], str(role.get("id")), "ok", nom, (token,))


def _supprimer_role(api, etat, token):
    ctx = etat["ctx"]
    if not verifier_permission(ctx, perms.MANAGE_ROLES, "Gerer les roles"):
        return
    roles = [role for role in ctx.get("roles") or []
             if not role.get("managed") and str(role.get("id")) != str((ctx.get("guild") or {}).get("id"))]
    if not roles:
        warn("Aucun role supprimable charge.")
        return
    libelles = [f"{role.get('name', '?')} (position {role.get('position', 0)})" for role in roles]
    choix = choisir_option("ROLE A SUPPRIMER", libelles + ["Retour"])
    if choix in (None, "Retour"):
        return
    role = roles[libelles.index(choix)]
    bot_top = perms.position_role_le_plus_haut(ctx.get("member"), ctx.get("roles") or [])
    if not perms.peut_gerer_role(permissions_du_bot(ctx), bot_top, role):
        warn("Hierarchie Discord : ce role est au-dessus du role le plus haut du bot.")
        return
    if not Confirm.ask(f"Supprimer definitivement le role '{role.get('name')}' ?",
                       default=False):
        return
    if not Confirm.ask("Confirmer une seconde fois la suppression ?", default=False):
        warn("Suppression annulee.")
        return
    try:
        api.supprimer_role(etat["selected"], str(role.get("id")))
    except DiscordAPIError as exc:
        bad(f"Suppression refusee : {exc}")
        journaliser("suppression_role", etat["selected"], str(role.get("id")),
                    "erreur", str(exc), (token,))
        return
    ctx["roles"] = [item for item in ctx.get("roles") or []
                    if item.get("id") != role.get("id")]
    ok("Role supprime.")
    journaliser("suppression_role", etat["selected"], str(role.get("id")), "ok",
                str(role.get("name")), (token,))


def _hierarchie(ctx):
    roles = sorted(ctx.get("roles") or [], key=lambda role: role.get("position", 0), reverse=True)
    bot_top = perms.position_role_le_plus_haut(ctx.get("member"), roles)
    table = Table(title=f"Hierarchie (role le plus haut du bot : {bot_top})",
                  box=BX, border_style=C_GOLD)
    table.add_column("Role")
    table.add_column("Position", justify="right")
    table.add_column("Au-dessus du bot")
    for role in roles:
        table.add_row(str(role.get("name", "?")), str(role.get("position", "-")),
                      "Oui" if int(role.get("position", 0)) >= bot_top else "Non")
    console.print(table)


def menu_roles(api, etat, token):
    while True:
        choix = choisir_option("ROLES", [
            "Explorer les roles", "Comparer deux roles", "Permissions excessives",
            "Previsualiser / modifier un role", "Creer un role", "Supprimer un role",
            "Verifier la hierarchie", "Retour"])
        if choix in (None, "Retour"):
            return
        ctx = etat.get("ctx")
        if not ctx or not ctx.get("guild"):
            warn("Selectionnez d'abord un serveur.")
            continue
        if choix == "Explorer les roles":
            _afficher_roles(ctx)
        elif choix == "Comparer deux roles":
            _comparer_roles(ctx)
        elif choix == "Permissions excessives":
            flags = [(role.get("name"), perms.permissions_excessives(role))
                     for role in ctx.get("roles") or [] if perms.permissions_excessives(role)]
            if not flags:
                ok("Aucune permission critique detectee sur les roles charges.")
            else:
                table = Table(title="Roles a examiner", box=BX, border_style="red")
                table.add_column("Role")
                table.add_column("Permissions critiques")
                for nom, liste in flags:
                    table.add_row(str(nom), ", ".join(liste))
                console.print(table)
        elif choix == "Previsualiser / modifier un role":
            _modifier_role(api, etat, token)
        elif choix == "Creer un role":
            _creer_role(api, etat, token)
        elif choix == "Supprimer un role":
            _supprimer_role(api, etat, token)
        elif choix == "Verifier la hierarchie":
            _hierarchie(ctx)
        pause()


# ---------------------------------------------------------------------------
# Moderation
# ---------------------------------------------------------------------------

def _membre_cible(api, ctx, guild_id):
    identifiant = demander("ID du membre").strip()
    if not _valid_snowflake(identifiant):
        bad("ID de membre invalide.")
        return None
    try:
        return api.guild_member(guild_id, identifiant)
    except DiscordNotFoundError:
        warn("Membre introuvable ou non accessible.")
    except DiscordAPIError as exc:
        bad(f"Lecture impossible : {exc}")
    return None


def _afficher_membre(membre):
    utilisateur = membre.get("user") or {}
    table = Table.grid(padding=(0, 2))
    table.add_column(style="bold cyan", width=24)
    table.add_column()
    table.add_row("Utilisateur", _tag(utilisateur))
    table.add_row("ID", str(utilisateur.get("id", "?")))
    table.add_row("Compte cree", _date_snowflake(str(utilisateur.get("id", ""))))
    table.add_row("A rejoint", str(membre.get("joined_at") or "non communique"))
    table.add_row("Roles", str(len(membre.get("roles") or [])))
    table.add_row("Timeout jusqu'a", str(membre.get("communication_disabled_until") or "aucun"))
    table.add_row("Bot", "oui" if utilisateur.get("bot") else "non")
    console.print(Panel(table, box=BX, border_style=C_GOLD, title="Membre"))


def _timeout_membre(api, etat, token):
    ctx = etat["ctx"]
    if not verifier_permission(ctx, perms.MODERATE_MEMBERS, "Moderer les membres"):
        return
    membre = _membre_cible(api, ctx, etat["selected"])
    if membre is None:
        return
    utilisateur = membre.get("user") or {}
    if utilisateur.get("bot"):
        warn("Le panel refuse de moderer un bot.")
        return
    if str(utilisateur.get("id")) == str((ctx.get("guild") or {}).get("owner_id")):
        warn("Le proprietaire du serveur ne peut pas etre exclu temporairement.")
        return
    bot_top = perms.position_role_le_plus_haut(ctx.get("member"), ctx.get("roles") or [])
    cible_top = perms.position_role_le_plus_haut(membre, ctx.get("roles") or [])
    if not perms.est_admin(permissions_du_bot(ctx)) and bot_top <= cible_top:
        warn("Hierarchie Discord : la cible est au-dessus ou au meme niveau que le bot.")
        return
    minutes = demander("Duree du timeout en minutes (1-40320)", "10").strip()
    if not minutes.isdigit() or not 1 <= int(minutes) <= 40320:
        bad("Duree invalide.")
        return
    raison = demander("Raison (facultative)", "").strip()
    fin = (datetime.now(timezone.utc) + timedelta(minutes=int(minutes))).isoformat()
    if not Confirm.ask(f"Appliquer un timeout de {minutes} min a {_tag(utilisateur)} ?",
                       default=False):
        return
    try:
        api.modifier_membre(etat["selected"], str(utilisateur.get("id")),
                            {"communication_disabled_until": fin}, reason=raison or None)
    except DiscordAPIError as exc:
        bad(f"Timeout refuse : {exc}")
        journaliser("timeout", etat["selected"], str(utilisateur.get("id")),
                    "erreur", str(exc), (token,))
        return
    ok("Timeout applique.")
    journaliser("timeout", etat["selected"], str(utilisateur.get("id")), "ok",
                f"{minutes} min", (token,))


def _expulser_membre(api, etat, token):
    ctx = etat["ctx"]
    if not verifier_permission(ctx, perms.KICK_MEMBERS, "Expulser des membres"):
        return
    membre = _membre_cible(api, ctx, etat["selected"])
    if membre is None:
        return
    utilisateur = membre.get("user") or {}
    if utilisateur.get("bot"):
        warn("Le panel refuse d'expulser un bot.")
        return
    if str(utilisateur.get("id")) == str((ctx.get("guild") or {}).get("owner_id")):
        warn("Le proprietaire du serveur ne peut pas etre expulse.")
        return
    bot_top = perms.position_role_le_plus_haut(ctx.get("member"), ctx.get("roles") or [])
    cible_top = perms.position_role_le_plus_haut(membre, ctx.get("roles") or [])
    if not perms.est_admin(permissions_du_bot(ctx)) and bot_top <= cible_top:
        warn("Hierarchie Discord : la cible est au-dessus ou au meme niveau que le bot.")
        return
    raison = demander("Raison (facultative)", "").strip()
    if not Confirm.ask(f"Expulser {_tag(utilisateur)} ? Cette action est sensible.",
                       default=False):
        return
    if not Confirm.ask("Confirmer une seconde fois l'expulsion ?", default=False):
        warn("Expulsion annulee.")
        return
    try:
        api.expulser_membre(etat["selected"], str(utilisateur.get("id")),
                            reason=raison or None)
    except DiscordAPIError as exc:
        bad(f"Expulsion refusee : {exc}")
        journaliser("expulsion", etat["selected"], str(utilisateur.get("id")),
                    "erreur", str(exc), (token,))
        return
    ok("Membre expulse.")
    journaliser("expulsion", etat["selected"], str(utilisateur.get("id")), "ok",
                raison or "sans raison", (token,))


def _afficher_journal():
    entrees = journal_derniers(25)
    if not entrees:
        warn("Journal vide.")
        return
    table = Table(title="Journal local des actions", box=BX, border_style=C_GOLD)
    table.add_column("Date (UTC)")
    table.add_column("Action")
    table.add_column("Serveur")
    table.add_column("Cible")
    table.add_column("Resultat")
    for entree in entrees:
        table.add_row(str(entree.get("timestamp", "?")), str(entree.get("action", "?")),
                      str(entree.get("guild_id") or "-"), str(entree.get("cible") or "-"),
                      "ok" if entree.get("resultat") == "ok" else "erreur")
    console.print(table)


def menu_moderation(api, etat, token):
    while True:
        choix = choisir_option("MODERATION AUTORISEE", [
            "Consulter un membre", "Appliquer un timeout",
            "Expulser un membre", "Journal local", "Retour"])
        if choix in (None, "Retour"):
            return
        ctx = etat.get("ctx")
        if not ctx or not ctx.get("guild"):
            warn("Selectionnez d'abord un serveur.")
            continue
        if choix == "Consulter un membre":
            membre = _membre_cible(api, ctx, etat["selected"])
            if membre:
                _afficher_membre(membre)
        elif choix == "Appliquer un timeout":
            _timeout_membre(api, etat, token)
        elif choix == "Expulser un membre":
            _expulser_membre(api, etat, token)
        elif choix == "Journal local":
            _afficher_journal()
        pause()


# ---------------------------------------------------------------------------
# Connexion & presence
# ---------------------------------------------------------------------------

def _menu_connexion(api, etat, gateway, token):
    while True:
        choix = choisir_option("CONNEXION & PRESENCE", [
            "Demarrer la Gateway" if not gateway.connected else "Arreter la Gateway",
            "Modifier la presence", "Actualiser identite et serveurs", "Retour"])
        if choix in (None, "Retour"):
            return
        if choix in ("Demarrer la Gateway", "Arreter la Gateway"):
            if gateway.connected:
                if Confirm.ask("Fermer la session Gateway du bot ?", default=False):
                    gateway.stop()
                    journaliser("gateway_stop", "", "", "ok", "session fermee", (token,))
                    ok("Gateway fermee.")
            else:
                with attente("Connexion Gateway"):
                    connecte = gateway.start(timeout=15)
                if connecte:
                    ok("Gateway connectee.")
                else:
                    warn(gateway.last_error or "Connexion non etablie.")
                    if "401" in str(gateway.last_error or ""):
                        for conseil in conseils_jeton_bot(token):
                            warn(conseil)
        elif choix == "Modifier la presence":
            statut_nom = choisir_option("STATUT", list(STATUTS))
            if statut_nom is None:
                continue
            activite_nom = choisir_option("ACTIVITE", list(ACTIVITES))
            if activite_nom is None:
                continue
            type_activite = ACTIVITES[activite_nom]
            nom_activite = ""
            url = ""
            if type_activite is not None:
                # Aucun texte d'activite impose : laisser vide n'envoie aucune
                # activite personnalisee, seul le statut est applique.
                nom_activite = demander("Texte de l'activite (vide = aucune)", "").strip()
                if type_activite == 1:
                    url = demander("URL du stream", "https://twitch.tv/discord").strip()
            succes, message = gateway.update_presence(STATUTS[statut_nom], nom_activite,
                                                      type_activite or 0, url)
            if succes:
                ok(message)
                journaliser("presence", "", "", "ok", statut_nom, (token,))
            else:
                warn(message)
        elif choix == "Actualiser identite et serveurs":
            try:
                with attente("Actualisation"):
                    etat["bot_data"] = api.me()
                    etat["guilds"] = api.my_guilds()
                    if etat.get("selected"):
                        etat["ctx"] = charger_contexte(api, etat["selected"], etat["bot_id"])
            except DiscordAuthError:
                bad("Token refuse : impossible d'actualiser.")
            except DiscordAPIError as exc:
                bad(f"Actualisation impossible : {exc}")
            else:
                ok(f"Donnees actualisees : {len(etat['guilds'])} serveur(s).")
        pause()


# ---------------------------------------------------------------------------
# Clonage
# ---------------------------------------------------------------------------

def menu_clonage(api, etat, token):
    """Acces aux cloners depuis le panel existant, sans second panel."""
    from modules.discord.cloner.panel import menu_clonage_structure
    from modules.discord.emoji_cloner import menu_clonage_emojis

    while True:
        choix = choisir_option("CLONAGE DISCORD", [
            "Server Cloner — structure, roles, salons",
            "Emoji Cloner — export et import",
            "Retour",
        ])
        if choix in (None, "Retour"):
            return
        if choix.startswith("Server Cloner"):
            menu_clonage_structure(api, etat, token)
        elif choix.startswith("Emoji Cloner"):
            menu_clonage_emojis(api, etat, token)
        pause()


# ---------------------------------------------------------------------------
# Point d'entree
# ---------------------------------------------------------------------------

def bot_panel(guild_id_initial=None):
    titre("DISCORD BOT CONTROL & AUDIT PANEL", C_DISCORD)
    if not warn_pentest():
        bad("Audit annule : autorisation requise.")
        return
    token = normaliser_jeton(Prompt.ask("[bold gold1]Token du Bot Discord[/]",
                                        password=True))
    if not token:
        bad("Token absent.")
        return

    api = DiscordAPI(token)
    gateway = None
    try:
        with attente("Verification du token Bot"):
            try:
                bot_data = api.me()
            except DiscordAuthError:
                bad("Token Bot invalide, revoque ou de mauvais type (HTTP 401).")
                for conseil in conseils_jeton_bot(token):
                    warn(conseil)
                return
            except DiscordAPIError as exc:
                bad(f"Connexion impossible : {exc}")
                return
        try:
            guilds = api.my_guilds()
        except DiscordAPIError as exc:
            bad(f"Liste des serveurs indisponible : {exc}")
            guilds = []

        gateway = DiscordGatewayClient(token)
        with attente("Connexion Gateway (discord.py)"):
            connecte = gateway.start(timeout=15)
        if not connecte:
            warn(gateway.last_error or "Gateway non connectee : les actions REST restent disponibles.")

        etat = {"bot_data": bot_data, "bot_id": str(bot_data.get("id", "")),
                "guilds": guilds, "selected": None, "ctx": None}
        if guild_id_initial and _valid_snowflake(str(guild_id_initial)):
            etat["selected"] = str(guild_id_initial)
            with attente("Chargement du serveur demande"):
                etat["ctx"] = charger_contexte(api, etat["selected"], etat["bot_id"])

        while True:
            clear_screen()
            console.print(_render_dashboard(etat["bot_data"], etat["guilds"], etat, gateway))
            choix = choisir_option("ACTIONS DU PANEL BOT", MENU)
            if choix in (None, "Quitter le panel"):
                break
            if choix == "Serveurs & permissions":
                menu_serveurs(api, etat, token)
            elif choix == "Clonage Discord":
                menu_clonage(api, etat, token)
            elif choix == "Communication":
                menu_communication(api, etat, token)
            elif choix == "Salons & categories":
                menu_salons(api, etat, token)
            elif choix == "Roles":
                menu_roles(api, etat, token)
            elif choix == "Moderation":
                menu_moderation(api, etat, token)
            elif choix == "Connexion & presence":
                _menu_connexion(api, etat, gateway, token)
            elif choix == "Actualiser":
                try:
                    with attente("Actualisation"):
                        etat["bot_data"] = api.me()
                        etat["guilds"] = api.my_guilds()
                        if etat.get("selected"):
                            etat["ctx"] = charger_contexte(api, etat["selected"], etat["bot_id"])
                except DiscordAPIError as exc:
                    bad(f"Actualisation impossible : {exc}")
                else:
                    ok("Donnees actualisees.")
                    pause()
    finally:
        if gateway is not None:
            gateway.stop()
        api.close()
        ok("Session Bot fermee.")
