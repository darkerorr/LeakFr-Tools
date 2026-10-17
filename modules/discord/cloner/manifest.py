"""Manifeste JSON d'une structure de serveur Discord.

Le manifeste ne contient que la structure : noms, types, positions,
permissions et surcharges. Il n'embarque ni message, ni membre, ni jeton,
ni webhook. Les cibles de surcharge sont decrites symboliquement afin de
pouvoir etre remappees vers les identifiants du serveur de destination.
"""
import json
import os
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

FORMAT = "leakfr-discord-structure"
VERSION = 1
TYPES_CATEGORIE = {4}
TYPES_SALON = {0, 2, 5, 13, 15, 16}
TYPES_TEXTE = {0, 5, 13, 15, 16}
MAX_ROLES = 250
MAX_SALONS = 500
MAX_SURCHARGES = 100
MAX_MANIFESTE = 5_000_000

ROLE_PAYLOAD_FIELDS = ("name", "color", "hoist", "mentionable", "permissions")
SALON_PAYLOAD_FIELDS = (
    "name", "type", "topic", "nsfw", "bitrate", "user_limit",
    "rate_limit_per_user", "default_sort_order", "default_forum_layout",
)


def maintenant():
    return datetime.now(timezone.utc).isoformat()


def normaliser_nom(texte):
    return unicodedata.normalize("NFKD", str(texte or "").casefold()).strip()


def _entier(valeur, defaut=0):
    try:
        return int(valeur)
    except (TypeError, ValueError):
        return defaut


def _surcharge(overwrite, roles_par_id, guild_id):
    """Convertit une surcharge en reference symbolique stable."""
    cible = str(overwrite.get("id") or "")
    if cible == guild_id:
        reference = {"kind": "everyone"}
    elif cible in roles_par_id:
        role = roles_par_id[cible]
        if role.get("managed"):
            return None
        reference = {"kind": "role", "source_id": cible, "name": role.get("name")}
    elif _entier(overwrite.get("type")) == 0:
        # Role supprime ou integration non recreable : la surcharge est ignoree.
        return None
    else:
        reference = {"kind": "member", "source_id": cible}
    return {
        "target": reference,
        "type": _entier(overwrite.get("type")),
        "allow": str(overwrite.get("allow") or "0"),
        "deny": str(overwrite.get("deny") or "0"),
    }


def construire_manifeste(guild, channels, roles, exported_at=None):
    """Construit un manifeste valide a partir des reponses brutes de l'API."""
    guild = guild or {}
    guild_id = str(guild.get("id") or "")
    if not guild_id:
        raise ValueError("Serveur source sans identifiant.")
    roles = [role for role in (roles or []) if isinstance(role, dict)]
    roles_par_id = {str(role.get("id")): role for role in roles}
    roles_structure = []
    for role in sorted(roles, key=lambda item: _entier(item.get("position"))):
        role_id = str(role.get("id") or "")
        if not role_id or role_id == guild_id:
            continue
        if role.get("managed"):
            continue
        roles_structure.append({
            "id": role_id,
            "name": str(role.get("name") or "").strip(),
            "color": _entier(role.get("color")),
            "hoist": bool(role.get("hoist")),
            "mentionable": bool(role.get("mentionable")),
            "permissions": str(role.get("permissions") or "0"),
            "position": _entier(role.get("position")),
        })

    categories = []
    salons = []
    for canal in channels or []:
        if not isinstance(canal, dict):
            continue
        type_canal = _entier(canal.get("type"))
        if type_canal not in TYPES_CATEGORIE | TYPES_SALON:
            continue
        base = {
            "id": str(canal.get("id") or ""),
            "name": str(canal.get("name") or ""),
            "type": type_canal,
            "position": _entier(canal.get("position")),
        }
        if not base["id"] or not base["name"]:
            continue
        if type_canal in TYPES_CATEGORIE:
            entree = dict(base)
            entree["permission_overwrites"] = [
                convertie
                for convertie in (
                    _surcharge(surcharge, roles_par_id, guild_id)
                    for surcharge in (canal.get("permission_overwrites") or [])
                    if isinstance(surcharge, dict)
                )
                if convertie is not None
            ][:MAX_SURCHARGES]
            categories.append(entree)
            continue
        entree = dict(base)
        for champ in ("topic", "nsfw", "bitrate", "user_limit",
                      "rate_limit_per_user", "default_sort_order",
                      "default_forum_layout"):
            if champ in canal:
                entree[champ] = canal[champ]
        if type_canal == 15:
            entree["available_tags"] = [
                {"name": str(tag.get("name") or "").strip(),
                 "moderated": bool(tag.get("moderated"))}
                for tag in canal.get("available_tags") or []
                if isinstance(tag, dict) and str(tag.get("name") or "").strip()
            ][:20]
        parent = str(canal.get("parent_id") or "")
        if parent:
            entree["parent_id"] = parent
        entree["permission_overwrites"] = [
            convertie
            for convertie in (
                _surcharge(surcharge, roles_par_id, guild_id)
                for surcharge in (canal.get("permission_overwrites") or [])
                if isinstance(surcharge, dict)
            )
            if convertie is not None
        ][:MAX_SURCHARGES]
        salons.append(entree)

    manifeste = {
        "format": FORMAT,
        "version": VERSION,
        "exported_at": exported_at or maintenant(),
        "source_guild": {"id": guild_id, "name": str(guild.get("name") or "")},
        "roles": sorted(roles_structure, key=lambda item: item["position"]),
        "categories": sorted(categories, key=lambda item: item["position"]),
        "channels": sorted(salons, key=lambda item: item["position"]),
        "counts": {
            "roles": len(roles_structure),
            "categories": len(categories),
            "channels": len(salons),
        },
        "limitations": [
            "Les membres, messages, webhooks et jetons ne sont jamais exportes.",
            "Les surcharges visant un membre sont conservees mais ignorees a l'import.",
            "Les roles geres par une integration (bots) ne sont pas recrees.",
        ],
    }
    return valider_manifeste(manifeste)


def valider_manifeste(donnees):
    """Valide et normalise un manifeste ; leve ValueError si invalide."""
    if not isinstance(donnees, dict):
        raise ValueError("Le manifeste doit etre un objet JSON.")
    if donnees.get("format") != FORMAT:
        raise ValueError("Format de manifeste non reconnu.")
    if _entier(donnees.get("version")) != VERSION:
        raise ValueError("Version de manifeste non prise en charge.")
    source = donnees.get("source_guild") or {}
    if not isinstance(source, dict) or not str(source.get("id") or "").isdigit():
        raise ValueError("Identifiant du serveur source invalide.")

    roles = donnees.get("roles") or []
    categories = donnees.get("categories") or []
    channels = donnees.get("channels") or []
    if not isinstance(roles, list) or not isinstance(categories, list) or not isinstance(channels, list):
        raise ValueError("Les listes roles/categories/channels doivent etre des tableaux.")
    if len(roles) > MAX_ROLES or len(categories) + len(channels) > MAX_SALONS:
        raise ValueError("Le manifeste depasse les limites de securite (roles ou salons).")

    roles_valides = []
    vus_roles = set()
    for role in roles:
        if not isinstance(role, dict):
            raise ValueError("Role invalide dans le manifeste.")
        nom = str(role.get("name") or "").strip()
        if not nom or len(nom) > 100:
            raise ValueError("Nom de role invalide (1 a 100 caracteres).")
        identifiant = str(role.get("id") or "")
        if identifiant and identifiant in vus_roles:
            raise ValueError("Identifiant de role duplique dans le manifeste.")
        vus_roles.add(identifiant)
        try:
            permissions = int(str(role.get("permissions") or "0"))
        except ValueError:
            raise ValueError(f"Permissions invalides pour le role {nom}.") from None
        if permissions < 0 or permissions >= 1 << 64:
            raise ValueError(f"Permissions hors limites pour le role {nom}.")
        roles_valides.append({
            "id": identifiant,
            "name": nom,
            "color": max(0, min(_entier(role.get("color")), 0xFFFFFF)),
            "hoist": bool(role.get("hoist")),
            "mentionable": bool(role.get("mentionable")),
            "permissions": str(permissions),
            "position": _entier(role.get("position")),
        })

    ids_roles = {role["id"] for role in roles_valides if role["id"]}
    categories_valides = []
    for categorie in categories:
        if not isinstance(categorie, dict) or _entier(categorie.get("type")) != 4:
            raise ValueError("Categorie invalide dans le manifeste.")
        nom = str(categorie.get("name") or "").strip()
        if not nom or len(nom) > 100:
            raise ValueError("Nom de categorie invalide.")
        categories_valides.append({
            "id": str(categorie.get("id") or ""),
            "name": nom,
            "type": 4,
            "position": _entier(categorie.get("position")),
            "permission_overwrites": _valider_surcharges(
                categorie.get("permission_overwrites") or [], ids_roles, nom),
        })

    ids_categories = {categorie["id"] for categorie in categories_valides if categorie["id"]}
    salons_valides = []
    vus_salons = set()
    for canal in channels:
        if not isinstance(canal, dict):
            raise ValueError("Salon invalide dans le manifeste.")
        type_canal = _entier(canal.get("type"))
        if type_canal not in TYPES_SALON:
            raise ValueError(f"Type de salon non pris en charge : {type_canal}.")
        nom = str(canal.get("name") or "").strip()
        if not nom or len(nom) > 100:
            raise ValueError("Nom de salon invalide.")
        identifiant = str(canal.get("id") or "")
        if identifiant and identifiant in vus_salons:
            raise ValueError("Identifiant de salon duplique dans le manifeste.")
        vus_salons.add(identifiant)
        entree = {
            "id": identifiant,
            "name": nom,
            "type": type_canal,
            "position": _entier(canal.get("position")),
        }
        parent = str(canal.get("parent_id") or "")
        if parent:
            if parent not in ids_categories:
                raise ValueError(f"Categorie parente inconnue pour le salon {nom}.")
            entree["parent_id"] = parent
        for champ in SALON_PAYLOAD_FIELDS:
            if champ in ("name", "type"):
                continue
            if champ in canal:
                entree[champ] = canal[champ]
        if entree.get("topic") is not None:
            entree["topic"] = str(entree["topic"])[:1024]
        if type_canal == 15:
            entree["available_tags"] = [
                {"name": str(tag.get("name") or "").strip()[:20],
                 "moderated": bool(tag.get("moderated"))}
                for tag in canal.get("available_tags") or []
                if isinstance(tag, dict) and str(tag.get("name") or "").strip()
            ][:20]
        entree["permission_overwrites"] = _valider_surcharges(
            canal.get("permission_overwrites") or [], ids_roles, nom)
        salons_valides.append(entree)

    return {
        "format": FORMAT,
        "version": VERSION,
        "exported_at": str(donnees.get("exported_at") or maintenant()),
        "source_guild": {"id": str(source.get("id")), "name": str(source.get("name") or "")[:100]},
        "roles": roles_valides,
        "categories": categories_valides,
        "channels": salons_valides,
        "counts": {
            "roles": len(roles_valides),
            "categories": len(categories_valides),
            "channels": len(salons_valides),
        },
        "limitations": list(donnees.get("limitations") or []),
    }


def _valider_surcharges(surcharges, ids_roles, nom):
    resultat = []
    for surcharge in list(surcharges)[:MAX_SURCHARGES]:
        if not isinstance(surcharge, dict) or not isinstance(surcharge.get("target"), dict):
            raise ValueError(f"Surcharge invalide pour {nom}.")
        cible = surcharge["target"]
        kind = cible.get("kind")
        if kind not in ("everyone", "role", "member"):
            raise ValueError("Cible de surcharge inconnue.")
        reference = {"kind": kind}
        if kind == "role":
            source_id = str(cible.get("source_id") or "")
            if source_id and source_id not in ids_roles:
                raise ValueError(f"Role de surcharge inconnu pour {nom}.")
            reference["source_id"] = source_id
            reference["name"] = str(cible.get("name") or "")[:100]
        elif kind == "member":
            reference["source_id"] = str(cible.get("source_id") or "")
        try:
            allow = int(str(surcharge.get("allow") or "0"))
            deny = int(str(surcharge.get("deny") or "0"))
        except ValueError:
            raise ValueError(f"Valeurs de surcharge invalides pour {nom}.") from None
        resultat.append({"target": reference, "type": _entier(surcharge.get("type")),
                         "allow": str(max(0, allow)), "deny": str(max(0, deny))})
    return resultat


def charger_manifeste(path):
    chemin = Path(path)
    try:
        if not chemin.is_file():
            raise ValueError(f"Manifeste introuvable : {chemin}")
        if chemin.stat().st_size > MAX_MANIFESTE:
            raise ValueError("Manifeste trop volumineux.")
        donnees = json.loads(chemin.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"Lecture du manifeste impossible : {exc}") from None
    except ValueError as exc:
        raise ValueError(f"JSON invalide : {exc}") from None
    return valider_manifeste(donnees)


def sauvegarder_manifeste(manifeste, path):
    """Ecrit un manifeste atomiquement, sans secret."""
    donnees = valider_manifeste(manifeste)
    chemin = Path(path)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    temporaire = chemin.with_name(chemin.name + ".tmp")
    temporaire.write_text(json.dumps(donnees, ensure_ascii=False, indent=2) + "\n",
                          encoding="utf-8")
    os.replace(temporaire, chemin)
    return chemin


def nom_sur(texte, maximum=100, autoriser_espaces=True):
    """Nettoie un nom de salon/role sans supprimer les accents utiles."""
    texte = re.sub(r"[\x00-\x1f\x7f]", "", str(texte or "")).strip()
    if autoriser_espaces:
        texte = re.sub(r"\s+", " ", texte)
    if len(texte) > maximum:
        texte = texte[:maximum].rstrip()
    return texte


def resoudre_conflit(nom, existants, strategie="ignorer"):
    """Retourne un nom disponible, ou None si la strategie est 'ignorer'."""
    existants = {normaliser_nom(item) for item in existants or ()}
    base = nom_sur(nom)
    if normaliser_nom(base) not in existants:
        return base
    if strategie != "renommer":
        return None
    for index in range(1, 100):
        suffixe = " - copie" if index == 1 else f" - copie {index}"
        candidat = nom_sur(base[:max(1, 100 - len(suffixe))] + suffixe)
        if normaliser_nom(candidat) not in existants:
            return candidat
    return None
