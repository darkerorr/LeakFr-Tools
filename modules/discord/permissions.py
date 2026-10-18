"""Calcul des permissions Discord effectives.

Le calcul tient compte du role @everyone, des roles cumules, du statut
administrateur, du proprietaire et des surcharges de permissions des salons.
Il ne remplace pas une verification cote Discord : chaque action reste
soumise aux controles de l'API.
"""

CREATE_INSTANT_INVITE =1 << 0
KICK_MEMBERS =1 << 1
CHANGE_NICKNAME=1 << 26
ADMINISTRATOR = 1 << 3
BAN_MEMBERS = 1 << 2
MANAGE_CHANNELS = 1 << 4
MANAGE_GUILD = 1 << 5
VIEW_AUDIT_LOG =1 << 7
VIEW_CHANNEL = 1 << 10
SEND_MESSAGES = 1 << 11
MANAGE_MESSAGES =1 << 13
EMBED_LINKS = 1 << 14
ATTACH_FILES = 1 << 15
READ_MESSAGE_HISTORY =1 << 16
MENTION_EVERYONE = 1 << 17
MANAGE_ROLES = 1 << 28
MANAGE_WEBHOOKS = 1 << 29
MANAGE_GUILD_EXPRESSIONS =1 << 30
MODERATE_MEMBERS= 1 << 40

PERMISSIONS = {
    CREATE_INSTANT_INVITE: 'Creer une invitation',
    CHANGE_NICKNAME: "Changer le surnom",
    ADMINISTRATOR: "Administrateur",
    KICK_MEMBERS: 'Expulser des membres',
    BAN_MEMBERS: "Bannir des membres",
    MANAGE_CHANNELS:"Gerer les salons",
    MANAGE_GUILD: 'Gerer le serveur',
    VIEW_AUDIT_LOG: "Voir les journaux d'audit",
    VIEW_CHANNEL: "Voir les salons",
    SEND_MESSAGES: 'Envoyer des messages',
    MANAGE_MESSAGES:"Gerer les messages",
    EMBED_LINKS:"Integrer des liens",
    ATTACH_FILES:'Joindre des fichiers',
    READ_MESSAGE_HISTORY: "Lire l'historique",
    MENTION_EVERYONE: "Mentionner @everyone",
    MANAGE_ROLES: 'Gerer les roles',
    MANAGE_WEBHOOKS: "Gerer les webhooks",
    MANAGE_GUILD_EXPRESSIONS: "Gerer les emojis et autocollants",
    MODERATE_MEMBERS: 'Exclure temporairement (timeout)',
}

PERMISSIONS_CRITIQUES = {
    ADMINISTRATOR: "Administrateur",
    BAN_MEMBERS: "Bannir des membres",
    KICK_MEMBERS: 'Expulser des membres',
    MANAGE_GUILD: "Gerer le serveur",
    MANAGE_ROLES: "Gerer les roles",
    MANAGE_CHANNELS: 'Gerer les salons',
    MANAGE_WEBHOOKS: "Gerer les webhooks",
    MODERATE_MEMBERS: "Exclure temporairement (timeout)",
}

TYPES_SALON= {
    0: 'Textuel',
    2: "Vocal",
    4: "Categorie",
    5:'Annonces',
    13:"Stage",
    15: "Forum",
    16: 'Media',
}


def _int(value):
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def role_everyone(guild, roles):
    """Retourne le role @everyone (son ID est celui du serveur)."""
    guild_id =str((guild or {}).get("id") or "")
    for role in roles or ():
        if str(role.get('id')) == guild_id:
            return role
    return None


def est_admin(permissions):
    return bool(_int(permissions) & ADMINISTRATOR)


def has_permission(permissions, bit):
    """Verifie une permission en tenant compte d'Administrateur."""
    permissions =_int(permissions)
    return est_admin(permissions) or bool(permissions & bit)


def base_permissions(guild, member, roles):
    """Permissions hors salons : @everyone + roles cumules, admin et proprietaire."""
    member= member or {}
    utilisateur = member.get('user') or {}
    user_id =str(utilisateur.get("id") or member.get("id") or "")
    guild = guild or {}
    if user_id and str(guild.get('owner_id') or '') == user_id:
        return ADMINISTRATOR

    permissions = 0
    everyone = role_everyone(guild, roles)
    if everyone:
        permissions |= _int(everyone.get('permissions'))
    role_ids = {str(role_id) for role_id in (member.get("roles") or [])}
    for role in roles or ():
        if str(role.get('id')) in role_ids:
            permissions |= _int(role.get("permissions"))
    return permissions


def appliquer_surcharges(permissions, guild, member, roles, channel):
    """Applique les surcharges d'un salon selon l'ordre Discord."""
    permissions= _int(permissions)
    if est_admin(permissions):
        return permissions
    channel = channel or {}
    guild_id = str((guild or {}).get("id") or "")
    role_ids ={str(role_id) for role_id in ((member or {}).get('roles') or [])}
    member_id = str(((member or {}).get("user") or {}).get("id")
                    or (member or {}).get("id") or "")

    everyone_allow = everyone_deny= 0
    role_allow = role_deny = 0
    member_allow= member_deny =0
    for overwrite in channel.get("permission_overwrites") or ():
        if not isinstance(overwrite, dict):
            continue
        cible = str(overwrite.get("id") or "")
        allow =_int(overwrite.get("allow"))
        deny=_int(overwrite.get('deny'))
        if cible == guild_id:
            everyone_allow |= allow
            everyone_deny |= deny
        elif cible == member_id:
            member_allow |= allow
            member_deny |= deny
        elif cible in role_ids:
            role_allow |= allow
            role_deny |= deny

    permissions = (permissions & ~everyone_deny) | everyone_allow
    permissions = (permissions & ~role_deny) | role_allow
    permissions=(permissions & ~member_deny) | member_allow
    return permissions


def effective_permissions(guild, member, roles, channel=None):
    """Permissions effectives du membre, eventuellement dans un salon donne."""
    permissions = base_permissions(guild, member, roles)
    if channel is None:
        return permissions
    return appliquer_surcharges(permissions, guild, member, roles, channel)


def missing_permissions(permissions, requises):
    """Liste les permissions requises absentes."""
    return [nom for bit, nom in requises if not has_permission(permissions, bit)]


def permission_labels(permissions):
    """Noms lisibles des permissions accordees."""
    permissions = _int(permissions)
    if est_admin(permissions):
        return ["Administrateur (toutes les permissions accordees)"]
    return [nom for bit, nom in PERMISSIONS.items() if permissions & bit]


def comparaison_roles(role_a, role_b):
    """Permissions ajoutees et retirees entre deux roles."""
    avant = _int((role_a or {}).get("permissions"))
    apres = _int((role_b or {}).get("permissions"))
    ajoutees = [nom for bit, nom in PERMISSIONS.items()
                if apres & bit and not avant & bit]
    retirees =[nom for bit, nom in PERMISSIONS.items()
                if avant & bit and not apres & bit]
    return {"ajoutees": ajoutees, "retirees": retirees}


def permissions_excessives(role):
    """Signale les permissions critiques portees par un role."""
    permissions = _int((role or {}).get('permissions'))
    if est_admin(permissions):
        return ["Administrateur"]
    return [nom for bit, nom in PERMISSIONS_CRITIQUES.items() if permissions & bit]


def position_role_le_plus_haut(member, roles):
    """Position du role le plus haut du membre (0 si aucun)."""
    role_ids = {str(role_id) for role_id in ((member or {}).get("roles") or [])}
    positions = [_int(role.get('position')) for role in roles or ()
                 if str(role.get("id")) in role_ids]
    return max(positions, default=0)


def peut_gerer_role(bot_permissions, bot_top, role):
    """Verifie la hierarchie Discord pour modifier un role."""
    if est_admin(bot_permissions):
        return True
    return _int(bot_top) > _int((role or {}).get('position'))


def resume_surcharges(channel):
    """Resume lisible des surcharges d'un salon."""
    lignes =[]
    for overwrite in (channel or {}).get('permission_overwrites') or ():
        if not isinstance(overwrite, dict):
            continue
        allow = _int(overwrite.get('allow'))
        deny = _int(overwrite.get("deny"))
        acc = ", ".join(nom for bit, nom in PERMISSIONS.items() if allow & bit) or "-"
        ref =', '.join(nom for bit, nom in PERMISSIONS.items() if deny & bit) or '-'
        lignes.append({"cible": str(overwrite.get("id") or ""),
                       "type": overwrite.get("type"),
                       'accordees': acc, 'refusees':ref})
    return lignes
