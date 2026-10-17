"""Outils locaux du panel personnel : aucun appel reseau."""
import re
from datetime import datetime, timezone
from urllib.parse import urlencode

from core.common import DISCORD_EPOCH

SCOPES_BOT = {"bot", "applications.commands"}
HEX_COULEUR = re.compile(r"^#[0-9a-fA-F]{6}$")


def decoder_snowflake(valeur):
    """Decode un identifiant Discord sans contacter de service."""
    valeur = str(valeur or "").strip()
    if not valeur.isdigit() or not 15 <= len(valeur) <= 22:
        raise ValueError("Snowflake invalide (15 a 22 chiffres attendus).")
    entier = int(valeur)
    timestamp_ms = (entier >> 22) + DISCORD_EPOCH
    creation = datetime.fromtimestamp(timestamp_ms / 1000.0, tz=timezone.utc)
    return {
        "snowflake": valeur,
        "creation_utc": creation.isoformat(timespec="milliseconds"),
        "timestamp_ms": timestamp_ms,
        "worker": (entier & 0x3E0000) >> 17,
        "processus": (entier & 0x1F000) >> 12,
        "increment": entier & 0xFFF,
        "binaire": bin(entier)[2:].zfill(64),
    }


def lien_invitation_bot(client_id, permissions=0, scopes=("bot", "applications.commands")):
    """Construit un lien d'installation officiel pour un bot ou une application."""
    client_id = str(client_id or "").strip()
    if not client_id.isdigit() or not 15 <= len(client_id) <= 22:
        raise ValueError("Client ID invalide.")
    try:
        permissions = int(permissions)
    except (TypeError, ValueError):
        raise ValueError("Permissions invalides.") from None
    if not 0 <= permissions < 1 << 64:
        raise ValueError("Permissions hors bornes.")
    scopes = tuple(scopes)
    if not scopes or not set(scopes) <= SCOPES_BOT:
        raise ValueError("Scopes d'installation invalides.")
    params = {"client_id": client_id, "scope": " ".join(scopes),
              "permissions": str(permissions)}
    return f"https://discord.com/oauth2/authorize?{urlencode(params)}"


def lien_application(client_id):
    client_id = str(client_id or "").strip()
    if not client_id.isdigit():
        raise ValueError("Application ID invalide.")
    return f"https://discord.com/developers/applications/{client_id}"


def construire_embed(titre="", description="", couleur="", footer=""):
    """Prepare un embed local ; la couleur reste au format #RRGGBB."""
    titre = (titre or "").strip()
    description = (description or "").strip()
    if not titre and not description:
        raise ValueError("Un embed exige au moins un titre ou une description.")
    if len(titre) > 256 or len(description) > 4000:
        raise ValueError("Titre (256) ou description (4000) trop long.")
    embed = {}
    if titre:
        embed["title"] = titre
    if description:
        embed["description"] = description
    if couleur:
        if not HEX_COULEUR.fullmatch(couleur.strip()):
            raise ValueError("Couleur invalide : format #RRGGBB attendu.")
        embed["color"] = int(couleur.strip()[1:], 16)
    if footer:
        embed["footer"] = {"text": footer[:2048]}
    return embed


def valider_message(contenu):
    contenu = (contenu or "").strip()
    if not contenu:
        raise ValueError("Message vide.")
    if len(contenu) > 2000:
        raise ValueError("Message limite a 2000 caracteres.")
    return contenu
