"""Construction du plan de clonage sans aucune ecriture sur Discord.

Le plan est deterministe : il compare le manifeste source aux salons et
roles deja presents, applique la strategie de conflit choisie et produit la
liste exacte des creations, ignorés et blocages. L'executeur consomme ce
plan ; le mode simulation s'arrete ici.
"""
from dataclasses import dataclass, field

from modules.discord.cloner.manifest import normaliser_nom, resoudre_conflit

TYPES_SALON_LIBELLES = {
    0: "textuel", 2: "vocal", 5: "annonces", 13: "stage", 15: "forum", 16: "media",
}


@dataclass
class OptionsClonage:
    roles: bool = True
    categories: bool = True
    salons: bool = True
    permissions: bool = True
    forums: bool = True
    conflits: str = "ignorer"  # ignorer | renommer
    salons_exclus: tuple = ()
    roles_exclus: tuple = ()

    def __post_init__(self):
        if self.conflits not in ("ignorer", "renommer"):
            raise ValueError("Strategie de conflit inconnue.")
        self.salons_exclus = tuple(str(nom).strip() for nom in self.salons_exclus
                                   if str(nom).strip())
        self.roles_exclus = tuple(str(nom).strip() for nom in self.roles_exclus
                                  if str(nom).strip())


@dataclass
class Plan:
    manifeste: dict
    guild_destination: dict
    options: OptionsClonage
    actions: list = field(default_factory=list)
    correspondances: dict = field(default_factory=dict)
    avertissements: list = field(default_factory=list)
    ignores: list = field(default_factory=list)
    permissions_requises: list = field(default_factory=list)

    def compter(self):
        compteur = {"creer": 0, "ignorer": 0, "bloquer": 0, "role": 0,
                    "categorie": 0, "salon": 0}
        for action in self.actions:
            compteur[action["mode"]] = compteur.get(action["mode"], 0) + 1
            compteur[action["kind"]] = compteur.get(action["kind"], 0) + 1
        return compteur

    def creations(self):
        return [action for action in self.actions if action["mode"] == "creer"]


def _index_roles(roles):
    index = {}
    for role in roles or []:
        if isinstance(role, dict):
            index.setdefault(normaliser_nom(role.get("name")), role)
    return index


def _index_salons(channels):
    index = {}
    for canal in channels or []:
        if not isinstance(canal, dict):
            continue
        cle = (int(canal.get("type") or 0), str(canal.get("parent_id") or ""),
               normaliser_nom(canal.get("name")))
        index.setdefault(cle, canal)
    return index


def _payload_role(role):
    return {
        "name": role["name"],
        "color": role.get("color", 0),
        "hoist": bool(role.get("hoist")),
        "mentionable": bool(role.get("mentionable")),
        "permissions": str(role.get("permissions") or "0"),
    }


def _payload_salon(canal, parent_dest, overwrites):
    payload = {"name": canal["name"], "type": int(canal["type"])}
    for champ in ("topic", "nsfw", "bitrate", "user_limit",
                  "rate_limit_per_user", "default_sort_order",
                  "default_forum_layout"):
        if champ in canal:
            payload[champ] = canal[champ]
    if parent_dest:
        payload["parent_id"] = parent_dest
    if canal.get("available_tags"):
        payload["available_tags"] = canal["available_tags"]
    if overwrites:
        payload["permission_overwrites"] = overwrites
    return payload


def construire_plan(manifeste, guild_destination, channels_destination, roles_destination,
                    options=None, bot_top_position=None):
    """Compare le manifeste a la destination et retourne un plan complet."""
    options = options or OptionsClonage()
    guild_destination = guild_destination or {}
    guild_id = str(guild_destination.get("id") or "")
    if not guild_id:
        raise ValueError("Serveur de destination sans identifiant.")
    plan = Plan(manifeste=manifeste, guild_destination=guild_destination, options=options)
    roles_dest = _index_roles(roles_destination)
    salons_dest = _index_salons(channels_destination)

    # -- Roles ---------------------------------------------------------
    role_map = {}
    noms_roles_dest = list(roles_dest)
    roles_exclus = {normaliser_nom(nom) for nom in options.roles_exclus}
    salons_exclus = {normaliser_nom(nom) for nom in options.salons_exclus}
    for role in manifeste.get("roles") or []:
        source_id = str(role.get("id") or "")
        nom = role["name"]
        if normaliser_nom(nom) in roles_exclus:
            plan.ignores.append(f"Role exclu par selection : {nom}")
            continue
        existant = roles_dest.get(normaliser_nom(nom))
        if existant:
            role_map[source_id] = str(existant.get("id"))
            plan.actions.append({
                "kind": "role", "source_id": source_id, "name": nom,
                "mode": "ignorer", "raison": "role deja present",
                "destination_id": str(existant.get("id")),
            })
            continue
        if not options.roles:
            plan.ignores.append(f"Role ignore (option desactivee) : {nom}")
            continue
        if bot_top_position is not None and int(bot_top_position) <= 1:
            plan.actions.append({
                "kind": "role", "source_id": source_id, "name": nom,
                "mode": "bloquer", "payload": None,
                "raison": "hierarchie : aucun role disponible sous le bot",
            })
            plan.avertissements.append(
                f"Role {nom} non recreable : le bot n'a pas de role au-dessus.")
            continue
        plan.actions.append({
            "kind": "role", "source_id": source_id, "name": nom,
            "mode": "creer", "payload": _payload_role(role),
        })
        # Placeholder resolu par l'executeur une fois le role cree ; il permet
        # aux surcharges des salons de designer les nouveaux roles.
        role_map[source_id] = f"role:{source_id}"
        noms_roles_dest.append(normaliser_nom(nom))

    # -- Categories ----------------------------------------------------
    categorie_map = {}
    noms_categories = {}
    for canal in channels_destination or []:
        if isinstance(canal, dict) and int(canal.get("type") or 0) == 4:
            noms_categories.setdefault(normaliser_nom(canal.get("name")), canal)
    for categorie in manifeste.get("categories") or []:
        source_id = str(categorie.get("id") or "")
        existante = noms_categories.get(normaliser_nom(categorie["name"]))
        if existante:
            categorie_map[source_id] = str(existante.get("id"))
            plan.actions.append({
                "kind": "categorie", "source_id": source_id, "name": categorie["name"],
                "mode": "ignorer", "raison": "categorie deja presente",
                "destination_id": str(existante.get("id")),
            })
            continue
        if not options.categories:
            plan.ignores.append(f"Categorie ignoree (option desactivee) : {categorie['name']}")
            continue
        surcharges, ignorees = _mapper_surcharges(
            categorie.get("permission_overwrites") or [], guild_id, role_map,
            roles_dest, options.permissions)
        plan.ignores.extend(ignorees)
        payload = {"name": categorie["name"], "type": 4}
        if surcharges:
            payload["permission_overwrites"] = surcharges
        plan.actions.append({
            "kind": "categorie", "source_id": source_id, "name": categorie["name"],
            "mode": "creer", "payload": payload,
        })

    # -- Salons --------------------------------------------------------
    for canal in manifeste.get("channels") or []:
        if normaliser_nom(canal["name"]) in salons_exclus:
            plan.ignores.append(f"Salon exclu par selection : {canal['name']}")
            continue
        if int(canal["type"]) == 15 and not options.forums:
            plan.ignores.append(f"Forum ignore (option desactivee) : {canal['name']}")
            continue
        if not options.salons:
            plan.ignores.append(f"Salon ignore (option desactivee) : {canal['name']}")
            continue
        parent_source = str(canal.get("parent_id") or "")
        parent_dest = categorie_map.get(parent_source, "")
        parent_cle = parent_dest
        if parent_source and not parent_dest and options.categories:
            # La categorie sera creee : aucun salon existant ne peut deja
            # se trouver sous cet identifiant inexistant.
            parent_cle = ""
        existant = salons_dest.get((int(canal["type"]), parent_cle,
                                    normaliser_nom(canal["name"])))
        nom_cible = canal["name"]
        if existant:
            if options.conflits == "ignorer":
                plan.actions.append({
                    "kind": "salon", "source_id": canal["id"], "name": canal["name"],
                    "mode": "ignorer", "raison": "salon deja present",
                    "destination_id": str(existant.get("id")),
                })
                continue
            existants = [item["name"] for item in (channels_destination or [])
                         if isinstance(item, dict)
                         and int(item.get("type") or 0) == int(canal["type"])
                         and str(item.get("parent_id") or "") == parent_cle]
            nom_cible = resoudre_conflit(canal["name"], existants, "renommer")
            if not nom_cible:
                plan.actions.append({
                    "kind": "salon", "source_id": canal["id"], "name": canal["name"],
                    "mode": "bloquer", "raison": "aucun nom libre apres 99 essais",
                })
                continue

        surcharges, ignorees = _mapper_surcharges(
            canal.get("permission_overwrites") or [], guild_id, role_map,
            roles_dest, options.permissions)
        plan.ignores.extend(ignorees)
        source_copie = dict(canal)
        source_copie["name"] = nom_cible
        plan.actions.append({
            "kind": "salon", "source_id": canal["id"], "name": nom_cible,
            "mode": "creer", "payload": _payload_salon(source_copie, parent_dest, surcharges),
            "parent_source_id": parent_source or None,
            "type": int(canal["type"]),
            "libelle_type": TYPES_SALON_LIBELLES.get(int(canal["type"]), "inconnu"),
        })

    plan.correspondances = {"roles": role_map, "categories": categorie_map}
    plan.permissions_requises = ["Gerer les salons"]
    if options.roles:
        plan.permissions_requises.append("Gerer les roles")
    return plan


def _mapper_surcharges(surcharges, guild_id, role_map, roles_dest, actives):
    if not actives:
        return [], []
    resultat = []
    ignores = []
    for surcharge in surcharges or []:
        cible = surcharge.get("target") or {}
        kind = cible.get("kind")
        if kind == "everyone":
            destination = guild_id
        elif kind == "role":
            source_id = str(cible.get("source_id") or "")
            destination = role_map.get(source_id)
            if not destination:
                role = roles_dest.get(normaliser_nom(cible.get("name")))
                destination = str((role or {}).get("id") or "")
            if not destination:
                ignores.append(
                    f"Surcharge ignoree : role source absent a la destination "
                    f"({cible.get('name') or source_id}).")
                continue
        elif kind == "member":
            ignores.append("Surcharge de membre ignoree : les comptes ne sont pas copies.")
            continue
        else:
            continue
        resultat.append({
            "id": destination,
            "type": int(surcharge.get("type") or 0),
            "allow": str(surcharge.get("allow") or "0"),
            "deny": str(surcharge.get("deny") or "0"),
        })
    return resultat, ignores


def resume_lignes(plan):
    """Representation textuelle stable pour l'apercu interactif."""
    lignes = []
    for action in plan.actions:
        detail = f"{action['mode']:7} {action['kind']:9} {action['name']}"
        if action.get("raison"):
            detail += f" ({action['raison']})"
        lignes.append(detail)
    return lignes
