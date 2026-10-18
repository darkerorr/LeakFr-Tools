"""Export de structure et ecriture des rapports de clonage."""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from core.config import EXPORTS_DIR
from modules.discord.cloner.manifest import construire_manifeste


def exporter_structure(api, guild_id):
    """Recupere les donnees reelles accessibles et retourne un manifeste.

    Toute erreur API remonte : aucun manifeste partiel n'est produit en
    silence. Les roles et salons sont lus avec les endpoints officiels.
    """
    guild =api.guild(guild_id)
    channels=api.guild_channels(guild_id)
    roles = api.guild_roles(guild_id)
    return construire_manifeste(guild, channels, roles)


def chemin_par_defaut(prefixe, guild_id=None, dossier=None):
    dossier = Path(dossier or EXPORTS_DIR)
    dossier.mkdir(parents=True, exist_ok=True)
    horodatage = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    suffixe=f"_{guild_id}" if guild_id else ''
    return dossier / f"{prefixe}{suffixe}_{horodatage}.json"


def ecrire_json(path, donnees):
    """Ecrit un JSON atomique et retourne son chemin."""
    chemin = Path(path)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    temporaire= chemin.with_name(chemin.name + ".tmp")
    temporaire.write_text(json.dumps(donnees, ensure_ascii=False, indent=2) + '\n',
                          encoding="utf-8")
    os.replace(temporaire, chemin)
    return chemin


def ecrire_rapport(resultat, path=None):
    chemin = Path(path) if path else chemin_par_defaut(
        "clone_rapport", (resultat.plan.guild_destination or {}).get("id"))
    return ecrire_json(chemin, resultat.rapport())
