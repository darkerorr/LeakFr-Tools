"""Panel interactif du Server Cloner.

Le panel reste volontairement synchrone et explicite : chaque etape est
montree avant execution, les permissions sont verifiees, le mode simulation
n'ecrit rien, et un serveur partiellement recree n'est jamais annonce comme
clone.
"""
from rich.markup import escape
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from core.common import (
    BX, C_DISCORD, C_GOLD, attente, bad, barre, choisir_option, console,
    demander, kv, ok, pause, titre, warn, warn_pentest,
)
from modules.discord import permissions as perms
from modules.discord.cloner.executor import executer_plan
from modules.discord.cloner.export import (
    chemin_par_defaut, ecrire_rapport, exporter_structure,
)
from modules.discord.cloner.manifest import (
    charger_manifeste, sauvegarder_manifeste,
)
from modules.discord.cloner.planner import OptionsClonage, construire_plan
from modules.discord.discord_api import DiscordAPI, DiscordAPIError
from modules.discord.panel_journal import enregistrer as journaliser


def choisir_serveur(guilds, label, guild_id_initial=None):
    guilds = list(guilds or [])
    if not guilds:
        warn("Aucun serveur accessible pour ce bot.")
        return None
    libelles = [f"{guild.get('name', '?')} ({guild.get('id')})" for guild in guilds]
    defaut = None
    if guild_id_initial:
        for index, guild in enumerate(guilds):
            if str(guild.get("id")) == str(guild_id_initial):
                defaut = libelles[index]
    choix = choisir_option(label, libelles + ["Retour"],
                           selection_initiale=libelles.index(defaut) if defaut else 0)
    if choix in (None, "Retour"):
        return None
    return guilds[libelles.index(choix)]


def charger_destination(api, guild_id, bot_id, besoin_roles=True, besoin_salons=True):
    """Charge les donnees de destination et verifie les permissions requises."""
    guild = api.guild(guild_id)
    channels = api.guild_channels(guild_id)
    roles = api.guild_roles(guild_id)
    membre = api.guild_member(guild_id, bot_id)
    permissions = perms.effective_permissions(guild, membre, roles)
    requises = []
    if besoin_salons:
        requises.append((perms.MANAGE_CHANNELS, "Gerer les salons"))
    if besoin_roles:
        requises.append((perms.MANAGE_ROLES, "Gerer les roles"))
    manquantes = perms.missing_permissions(permissions, requises)
    bot_top = perms.position_role_le_plus_haut(membre, roles)
    return {
        "guild": guild, "channels": channels, "roles": roles,
        "member": membre, "permissions": permissions,
        "manquantes": manquantes, "bot_top": bot_top,
    }


def _demander_options():
    roles = Confirm.ask("Copier les roles (couleurs, permissions, mentionnabilité) ?",
                        default=True)
    categories = Confirm.ask("Copier les categories ?", default=True)
    salons = Confirm.ask("Copier les salons textuels et vocaux ?", default=True)
    forums = Confirm.ask("Inclure les forums et salons media ?", default=True)
    permissions_choix = Confirm.ask("Copier les surcharges de permissions des salons ?",
                                    default=True)
    strategie = choisir_option("CONFLITS DE NOMS", [
        "Ignorer les elements deja existants",
        "Creer une copie renommee des elements en conflit",
        "Retour",
    ])
    if strategie in (None, "Retour"):
        return None
    roles_exclus = demander("Roles a exclure (noms separes par des virgules, vide pour aucun)",
                            "").strip()
    salons_exclus = demander("Salons a exclure (noms separes par des virgules, vide pour aucun)",
                             "").strip()
    return OptionsClonage(
        roles=roles, categories=categories, salons=salons, forums=forums,
        permissions=permissions_choix,
        conflits="renommer" if "renommee" in strategie else "ignorer",
        roles_exclus=tuple(part.strip() for part in roles_exclus.split(",") if part.strip()),
        salons_exclus=tuple(part.strip() for part in salons_exclus.split(",") if part.strip()),
    )


def _afficher_plan(plan, destination):
    compteur = plan.compter()
    table = Table(title="Apercu du clonage (aucune ecriture effectuee)",
                  box=BX, border_style=C_GOLD)
    table.add_column("Element")
    table.add_column("A creer", justify="right")
    table.add_column("Existant", justify="right")
    table.add_column("Bloque", justify="right")
    table.add_row("Roles", str(sum(1 for a in plan.actions if a["kind"] == "role"
                                   and a["mode"] == "creer")),
                  str(sum(1 for a in plan.actions if a["kind"] == "role"
                          and a["mode"] == "ignorer")),
                  str(sum(1 for a in plan.actions if a["kind"] == "role"
                          and a["mode"] == "bloquer")))
    table.add_row("Categories", str(sum(1 for a in plan.actions if a["kind"] == "categorie"
                                       and a["mode"] == "creer")),
                  str(sum(1 for a in plan.actions if a["kind"] == "categorie"
                          and a["mode"] == "ignorer")),
                  str(sum(1 for a in plan.actions if a["kind"] == "categorie"
                          and a["mode"] == "bloquer")))
    table.add_row("Salons", str(sum(1 for a in plan.actions if a["kind"] == "salon"
                                    and a["mode"] == "creer")),
                  str(sum(1 for a in plan.actions if a["kind"] == "salon"
                          and a["mode"] == "ignorer")),
                  str(sum(1 for a in plan.actions if a["kind"] == "salon"
                          and a["mode"] == "bloquer")))
    console.print(table)
    detail = Table(title="Detail des operations", box=BX, border_style=C_DISCORD)
    detail.add_column("Mode")
    detail.add_column("Type")
    detail.add_column("Nom")
    detail.add_column("Note")
    for action in plan.actions[:200]:
        detail.add_row(action["mode"], action["kind"], action["name"],
                       action.get("raison", ""))
    console.print(detail)
    if len(plan.actions) > 200:
        warn(f"Affichage limite a 200 lignes sur {len(plan.actions)}.")
    for avertissement in plan.avertissements[:20]:
        warn(avertissement)
    for ignore in plan.ignores[:20]:
        console.print(f"[dim]- {escape(ignore)}[/]")
    if len(plan.ignores) > 20:
        console.print(f"[dim]... {len(plan.ignores) - 20} autre(s) element(s) ignore(s).[/]")
    console.print(Panel(
        f"Destination : {escape(str(destination.get('name')))} "
        f"({destination.get('id')})\n"
        "Les membres, messages, webhooks et jetons ne sont jamais copies.\n"
        "Le mode simulation n'ecrit rien : l'execution demande une confirmation.",
        title="Limites", border_style="grey50"))
    return compteur


def _executer(api, plan, etat, token):
    destination = plan.guild_destination
    nombre = len(plan.creations())
    if nombre == 0:
        ok("Rien a creer : la destination contient deja tous les elements selectionnes.")
        return None
    console.print(Panel(
        f"{nombre} creation(s) vont modifier reellement le serveur "
        f"{escape(str(destination.get('name')))}({destination.get('id')}).\n"
        "Cette operation ne supprime rien mais cree des roles et des salons.",
        title="Confirmation obligatoire", border_style="red"))
    if not Confirm.ask("Confirmer l'execution reelle du clonage ?", default=False):
        warn("Clonage annule. Aucune ecriture effectuee.")
        return None
    if not Confirm.ask("Confirmer une seconde fois (operation sensible) ?", default=False):
        warn("Clonage annule. Aucune ecriture effectuee.")
        return None

    resultat = None
    with barre() as progression:
        tache = progression.add_task("Clonage de la structure", total=nombre)

        def avancer(index, total, libelle):
            progression.update(tache, completed=index - 1, description=libelle[:70])

        try:
            resultat = executer_plan(api, plan, progression=avancer)
        except KeyboardInterrupt:
            warn("Interruption clavier : les elements deja crees sont conserves.")
            return None
        progression.update(tache, completed=nombre)

    path = ecrire_rapport(resultat)
    comptes = resultat.compter()
    if resultat.statut == "reussi":
        ok(f"Structure recreee : {comptes['roles']} role(s), "
           f"{comptes['categories']} categorie(s), {comptes['salons']} salon(s).")
    elif resultat.statut == "partiel":
        warn("Clonage PARTIEL : une partie seulement de la structure a ete recreee.")
        ok(f"Elements crees : {comptes}")
    elif resultat.statut == "annule":
        warn(f"Clonage annule apres {comptes} creation(s).")
    else:
        bad(f"Clonage en echec : {comptes} creation(s) avant l'arret.")
    if resultat.erreurs:
        table = Table(title="Erreurs reelles", box=BX, border_style="red")
        table.add_column("Erreur")
        for erreur in resultat.erreurs[:40]:
            table.add_row(escape(str(erreur)))
        console.print(table)
    if resultat.notes:
        console.print(Panel("\n".join(escape(note) for note in resultat.notes[:20]),
                            title="Notes et elements ignores", border_style="yellow"))
    ok(f"Rapport JSON : {path}")
    journaliser("clone_structure", destination.get("id"), str(destination.get("id")),
                "ok" if resultat.statut == "reussi" else "erreur",
                f"statut {resultat.statut}, {comptes}", (token,))
    return resultat


def _preparer(api, manifeste, guilds, guild_id_initial, bot_id, etat, token):
    destination = choisir_serveur(guilds, "SERVEUR DE DESTINATION", guild_id_initial)
    if destination is None:
        return None
    if str(destination.get("id")) == str(manifeste.get("source_guild", {}).get("id")):
        warn("La source et la destination sont identiques : operation refusee.")
        return None
    options = _demander_options()
    if options is None:
        return None
    try:
        with attente("Lecture de la destination et des permissions"):
            infos = charger_destination(
                api, destination["id"], bot_id,
                besoin_roles=options.roles,
                besoin_salons=options.categories or options.salons)
    except DiscordAPIError as exc:
        bad(f"Destination inaccessible : {exc}")
        return None
    if infos["manquantes"]:
        bad("Permissions manquantes a la destination : " +
            ", ".join(infos["manquantes"]) + ".")
        return None
    plan = construire_plan(manifeste, infos["guild"], infos["channels"],
                           infos["roles"], options,
                           bot_top_position=infos["bot_top"])
    _afficher_plan(plan, infos["guild"])
    resultat = _executer(api, plan, etat, token)
    if resultat is not None:
        etat["selected"] = str(destination.get("id"))
        try:
            from modules.discord.bot_panel import charger_contexte
            etat["ctx"] = charger_contexte(api, etat["selected"], bot_id)
        except DiscordAPIError:
            pass
    return resultat


def _exporter(api, guilds, guild_id_initial):
    source = choisir_serveur(guilds, "SERVEUR SOURCE A EXPORTER", guild_id_initial)
    if source is None:
        return None
    try:
        with attente("Export de la structure"):
            manifeste = exporter_structure(api, source["id"])
    except DiscordAPIError as exc:
        bad(f"Export refuse : {exc}")
        return None
    path = chemin_par_defaut("structure", source["id"])
    sauvegarder_manifeste(manifeste, path)
    ok(f"Manifeste exporte sans secret : {path}")
    kv("Contenu exporte", [
        ("Roles", str(manifeste["counts"]["roles"])),
        ("Categories", str(manifeste["counts"]["categories"])),
        ("Salons", str(manifeste["counts"]["channels"])),
    ], C_DISCORD)
    return manifeste


def menu_clonage_structure(api, etat, token):
    bot_id = str((etat.get("bot_data") or {}).get("id") or etat.get("bot_id") or "")
    guilds = etat.get("guilds") or []
    while True:
        choix = choisir_option("SERVER CLONER — STRUCTURE", [
            "Preparer un clonage depuis un serveur",
            "Importer un manifeste JSON puis cloner",
            "Exporter la structure d'un serveur",
            "Retour",
        ])
        if choix in (None, "Retour"):
            return
        if choix == "Exporter la structure d'un serveur":
            _exporter(api, guilds, etat.get("selected"))
            pause()
            continue
        if choix == "Preparer un clonage depuis un serveur":
            source = choisir_serveur(guilds, "SERVEUR SOURCE", etat.get("selected"))
            if source is None:
                continue
            try:
                with attente("Lecture de la structure source"):
                    manifeste = exporter_structure(api, source["id"])
            except DiscordAPIError as exc:
                bad(f"Structure source inaccessible : {exc}")
                pause()
                continue
            path = chemin_par_defaut("structure", source["id"])
            sauvegarder_manifeste(manifeste, path)
            ok(f"Manifeste source sauvegarde : {path}")
        else:
            chemin = demander("Chemin du manifeste JSON", "").strip()
            try:
                manifeste = charger_manifeste(chemin)
            except ValueError as exc:
                bad(str(exc))
                pause()
                continue
            ok(f"Manifeste valide : {manifeste['counts']}")
        _preparer(api, manifeste, guilds, etat.get("selected"), bot_id, etat, token)
        pause()


def server_cloner():
    """Point d'entree catalogue : connexion Bot puis panel de clonage."""
    titre("DISCORD SERVER CLONER — STRUCTURE", C_DISCORD)
    warn("Utilisez uniquement des serveurs que vous administrez et un bot autorise.")
    if not warn_pentest():
        bad("Operation annulee : autorisation requise.")
        return
    token = Prompt.ask("[bold gold1]Token du Bot Discord[/]", password=True).strip()
    if not token:
        bad("Token absent.")
        return
    api = DiscordAPI(token)
    try:
        try:
            with attente("Verification du token Bot"):
                bot_data = api.me()
                guilds = api.my_guilds()
        except DiscordAPIError as exc:
            bad(f"Connexion impossible : {exc}")
            return
        etat = {"bot_data": bot_data, "bot_id": str(bot_data.get("id") or ""),
                "guilds": guilds, "selected": None, "ctx": None}
        menu_clonage_structure(api, etat, token)
    finally:
        api.close()
