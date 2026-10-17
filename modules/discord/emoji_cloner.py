"""Emoji Cloner : export, verification et import d'emojis Discord.

Les fichiers sont reellement telecharges depuis le CDN officiel, verifies
par signature (PNG/GIF/JPEG/WEBP), puis importes via l'endpoint officiel
``POST /guilds/{id}/emojis``. Un emoji inaccessible, trop lourd ou refuse
n'est jamais compte comme importe.
"""
import base64
import hashlib
import io
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import requests

from core.config import EXPORTS_DIR
from core.tasks import Etape, MoteurTaches, Tache
from modules.discord.discord_api import (
    DiscordAPI, DiscordAPIError, DiscordRateLimitError,
)
from modules.discord.local_store import ecrire_json

TAILLE_MAX_EMOJI = 256 * 1024
TAILLE_MAX_TELECHARGEMENT = 2 * 1024 * 1024
NOM_EMOJI = re.compile(r"^[A-Za-z0-9_]{2,32}$")
HOTES_CDN = {"cdn.discordapp.com", "media.discordapp.net", "discord.com"}
LIMITES_EMOJIS = {0: 50, 1: 100, 2: 150, 3: 250}
FORMAT_MANIFESTE = "leakfr-discord-emojis"
VERSION_MANIFESTE = 1


def maintenant():
    return datetime.now(timezone.utc).isoformat()


def detecter_format(donnees):
    """Detecte le format par signature, sans faire confiance a l'extension."""
    if not isinstance(donnees, (bytes, bytearray)) or not donnees:
        return None
    if donnees[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    if donnees[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if donnees[:4] == b"RIFF" and donnees[8:12] == b"WEBP":
        return "webp"
    if donnees[:3] == b"\xff\xd8\xff":
        return "jpg"
    return None


def est_anime(donnees, emoji=None):
    if bool((emoji or {}).get("animated")):
        return True
    return detecter_format(donnees) == "gif"


def url_emoji(emoji):
    identifiant = str((emoji or {}).get("id") or "")
    if not identifiant.isdigit():
        raise ValueError("Identifiant d'emoji invalide.")
    extension = "gif" if (emoji or {}).get("animated") else "png"
    return f"https://cdn.discordapp.com/emojis/{identifiant}.{extension}"


def verifier_url(url):
    """Refuse tout telechargement hors du CDN Discord officiel."""
    from urllib.parse import urlparse
    analyse = urlparse(str(url or ""))
    if analyse.scheme != "https" or analyse.hostname not in HOTES_CDN:
        raise ValueError("URL d'emoji hors du CDN Discord refuse.")
    return url


def telecharger_emoji(session, emoji, limite=TAILLE_MAX_TELECHARGEMENT):
    """Telecharge un emoji borne ; retourne (donnees, format, url)."""
    url = verifier_url(url_emoji(emoji))
    try:
        reponse = session.get(url, timeout=15, stream=True)
    except requests.RequestException as exc:
        raise ValueError(f"Telechargement impossible : {type(exc).__name__}") from None
    if reponse.status_code != 200:
        raise ValueError(f"CDN Discord : HTTP {reponse.status_code}")
    longueur = reponse.headers.get("Content-Length")
    if longueur and str(longueur).isdigit() and int(longueur) > limite:
        raise ValueError(f"Emoji trop lourd (>{limite} octets).")
    contenu = bytearray()
    for morceau in reponse.iter_content(8192):
        if not morceau:
            continue
        contenu.extend(morceau)
        if len(contenu) > limite:
            raise ValueError(f"Emoji trop lourd (>{limite} octets).")
    donnees = bytes(contenu)
    format_ = detecter_format(donnees)
    if format_ not in ("png", "gif", "jpg", "webp"):
        raise ValueError("Format d'image non reconnu ou non pris en charge.")
    if format_ == "webp":
        raise ValueError("Le format WebP n'est pas accepte par l'import d'emojis Discord.")
    if len(donnees) > TAILLE_MAX_EMOJI:
        raise ValueError("Emoji superieur a la limite Discord de 256 Kio.")
    return donnees, format_, url


def verifier_permission_import(api, guild_id, bot_id):
    """Retourne les permissions manquantes pour creer des emojis."""
    from modules.discord import permissions as perms
    guild = api.guild(guild_id)
    roles = api.guild_roles(guild_id)
    membre = api.guild_member(guild_id, bot_id)
    effectives = perms.effective_permissions(guild, membre, roles)
    return perms.missing_permissions(effectives, [
        (perms.MANAGE_GUILD_EXPRESSIONS, "Gerer les emojis et autocollants"),
    ])


def nom_valide(texte):
    return bool(NOM_EMOJI.match(str(texte or "")))


def normaliser_nom(nom):
    """Produit un nom conforme (2 a 32 caracteres alphanumeriques/underscore)."""
    propre = re.sub(r"[^A-Za-z0-9_]", "_", str(nom or "")).strip("_")
    propre = re.sub(r"_{2,}", "_", propre)
    if len(propre) > 32:
        propre = propre[:32].rstrip("_")
    if not propre:
        propre = "emoji"
    elif len(propre) < 2:
        propre = (propre + "_emoji")[:32]
    return propre


def resoudre_nom(nom, existants, strategie="ignorer", prefixe=""):
    base = normaliser_nom((prefixe or "") + nom)
    existants = {str(item).casefold() for item in existants or ()}
    if base.casefold() not in existants:
        return base
    if strategie != "renommer":
        return None
    for index in range(2, 100):
        suffixe = f"_{index}"
        candidat = base[:32 - len(suffixe)] + suffixe
        if candidat.casefold() not in existants:
            return candidat
    return None


def limite_emojis(premium_tier, anime):
    """Capacite par type selon le niveau de boost (documentation Discord)."""
    tier = max(0, min(int(premium_tier or 0), 3))
    return LIMITES_EMOJIS[tier]


@dataclass
class OptionsEmoji:
    conserver_noms: bool = True
    prefixe: str = ""
    conflits: str = "ignorer"  # ignorer | renommer
    limite_lot: int = 20

    def __post_init__(self):
        if self.conflits not in ("ignorer", "renommer"):
            raise ValueError("Strategie de conflit inconnue.")
        if not 1 <= int(self.limite_lot) <= 50:
            raise ValueError("La taille du lot doit etre comprise entre 1 et 50.")
        if len(self.prefixe or "") > 12:
            raise ValueError("Prefixe trop long (12 caracteres maximum).")


@dataclass
class EntreeEmoji:
    emoji: dict
    nom_source: str
    nom_cible: str = ""
    statut: str = "en_attente"  # pret | ignore | erreur | importe
    raison: str = ""
    format: str = ""
    taille: int = 0
    anime: bool = False
    sha256: str = ""
    fichier: str = ""
    destination_id: str = ""
    donnees: bytes = field(default=b"", repr=False)

    def manifeste(self):
        return {
            "source_id": str(self.emoji.get("id") or ""),
            "nom_source": self.nom_source,
            "nom_cible": self.nom_cible,
            "anime": self.anime,
            "format": self.format,
            "taille": self.taille,
            "sha256": self.sha256,
            "fichier": self.fichier,
            "statut": self.statut,
            "raison": self.raison,
            "destination_id": self.destination_id,
        }


def planifier_import(source_emojis, destination_emojis, telecharger, options=None,
                    premium_tier=0):
    """Prepare l'import : noms, doublons, capacite, taille et format."""
    options = options or OptionsEmoji()
    destination_emojis = [emoji for emoji in (destination_emojis or [])
                          if isinstance(emoji, dict)]
    existants = {str(emoji.get("name") or "").casefold() for emoji in destination_emojis}
    statiques = sum(1 for emoji in destination_emojis if not emoji.get("animated"))
    animes = sum(1 for emoji in destination_emojis if emoji.get("animated"))
    capacite = limite_emojis(premium_tier, True)
    entrees = []
    for emoji in source_emojis or []:
        if not isinstance(emoji, dict):
            continue
        nom_source = str(emoji.get("name") or "")
        entree = EntreeEmoji(emoji=emoji, nom_source=nom_source,
                             anime=bool(emoji.get("animated")))
        entrees.append(entree)
        try:
            donnees, format_, _url = telecharger(emoji)
        except (ValueError, OSError) as exc:
            entree.statut = "erreur"
            entree.raison = str(exc)
            continue
        entree.donnees = donnees
        entree.format = format_
        entree.taille = len(donnees)
        entree.anime = est_anime(donnees, emoji)
        entree.sha256 = hashlib.sha256(donnees).hexdigest()
        if not options.conserver_noms and not options.prefixe:
            entree.statut = "ignore"
            entree.raison = "modification de nom demandee sans prefixe"
            continue
        entree.nom_cible = resoudre_nom(
            nom_source, existants, options.conflits, options.prefixe)
        if not entree.nom_cible:
            entree.statut = "ignore"
            entree.raison = "nom deja utilise a la destination"
            continue
        if entree.anime:
            if animes >= capacite:
                entree.statut = "ignore"
                entree.raison = "capacite d'emojis animes atteinte"
                continue
            animes += 1
        else:
            if statiques >= capacite:
                entree.statut = "ignore"
                entree.raison = "capacite d'emojis statiques atteinte"
                continue
            statiques += 1
        existants.add(entree.nom_cible.casefold())
        entree.statut = "pret"
    return entrees


def exporter_emojis(api, session, guild_id, dossier=None, options=None):
    """Telecharge les emojis accessibles et ecrit un manifeste local."""
    options = options or OptionsEmoji()
    emojis = api.guild_emojis(guild_id)
    if not isinstance(emojis, list):
        raise DiscordAPIError("Reponse inattendue pour la liste des emojis.")
    dossier = Path(dossier or Path(EXPORTS_DIR) / "emojis" / str(guild_id))
    dossier.mkdir(parents=True, exist_ok=True)
    entrees = []
    for emoji in emojis:
        entree = EntreeEmoji(emoji=emoji, nom_source=str(emoji.get("name") or ""))
        entrees.append(entree)
        try:
            donnees, format_, _url = telecharger_emoji(session, emoji)
        except (ValueError, OSError) as exc:
            entree.statut = "erreur"
            entree.raison = str(exc)
            continue
        entree.donnees = b""
        entree.format = format_
        entree.taille = len(donnees)
        entree.anime = est_anime(donnees, emoji)
        entree.sha256 = hashlib.sha256(donnees).hexdigest()
        entree.nom_cible = normaliser_nom(entree.nom_source)
        fichier = dossier / f"{entree.nom_cible}_{entree.sha256[:8]}.{format_}"
        fichier.write_bytes(donnees)
        entree.fichier = str(fichier)
        entree.statut = "telecharge"
    manifeste = {
        "format": FORMAT_MANIFESTE,
        "version": VERSION_MANIFESTE,
        "exported_at": maintenant(),
        "source_guild": str(guild_id),
        "options": vars(options),
        "emojis": [entree.manifeste() for entree in entrees],
        "counts": {
            "total": len(entrees),
            "telecharges": sum(1 for entree in entrees if entree.statut == "telecharge"),
            "erreurs": sum(1 for entree in entrees if entree.statut == "erreur"),
        },
        "limitations": [
            "Seuls les emojis accessibles au bot sont exportes.",
            "Les fichiers restent soumis aux droits de leur serveur d'origine.",
        ],
    }
    chemin = dossier / f"manifeste_{guild_id}.json"
    ecrire_json(chemin, manifeste)
    return manifeste, chemin


def importer_entrees(api, guild_id, entrees, progression=None, annulation=None):
    """Importe les entrees pretes via le moteur commun, sans masquer les refus."""
    resultat = {"importes": [], "erreurs": [], "ignores": []}
    pretes = [entree for entree in entrees if entree.statut == "pret" and entree.donnees]
    if not pretes:
        resultat["ignores"] = [
            {"nom": entree.nom_source, "raison": entree.raison}
            for entree in entrees if entree.statut in ("ignore", "erreur")
        ]
        return resultat
    etat = {"debit": False}
    moteur = MoteurTaches(exceptions_arret=(DiscordRateLimitError,),
                          annulation_externe=annulation)

    def etape_import(entree):
        def importer():
            mime = {"png": "image/png", "gif": "image/gif",
                    "jpg": "image/jpeg"}[entree.format]
            image = (f"data:{mime};base64,"
                     + base64.b64encode(entree.donnees).decode("ascii"))
            try:
                cree = api.creer_emoji(
                    guild_id, {"name": entree.nom_cible, "image": image},
                    reason="LeakFr-Tools import d'emojis")
            except DiscordRateLimitError as exc:
                entree.statut = "erreur"
                entree.raison = str(exc)
                etat["debit"] = True
                raise
            except (DiscordAPIError, ValueError) as exc:
                entree.statut = "erreur"
                entree.raison = str(exc)
                raise
            except Exception as exc:  # noqa: BLE001 - l'echec reste visible
                entree.statut = "erreur"
                entree.raison = f"{type(exc).__name__} - {exc}"
                raise
            identifiant = str((cree or {}).get("id") or "")
            if not identifiant:
                entree.statut = "erreur"
                entree.raison = "l'API n'a pas retourne d'identifiant"
                raise DiscordAPIError(entree.raison)
            entree.statut = "importe"
            entree.destination_id = identifiant

        return importer

    moteur.ajouter(Tache(
        identifiant=f"emojis->{guild_id}", type="import_emojis",
        description="Import d'emojis Discord",
        etapes=[Etape(f"emoji {entree.nom_cible}", etape_import(entree))
                for entree in pretes],
        destructive=False))
    resultat_tache = moteur.executer_suivante(progression=progression)
    for entree in pretes:
        if entree.statut == "pret":
            entree.statut = "ignore"
            entree.raison = ("non execute apres annulation"
                             if resultat_tache.statut == "annule"
                             else "non execute apres arret sur erreurs")
    for entree in entrees:
        if entree.statut == "importe":
            resultat["importes"].append(
                {"nom": entree.nom_cible, "id": entree.destination_id})
        elif entree.statut == "erreur":
            resultat["erreurs"].append(
                {"nom": entree.nom_cible, "erreur": entree.raison})
    if etat["debit"]:
        resultat["interrompu"] = "limite de debit Discord"
    if resultat_tache.statut == "annule":
        resultat["annule"] = True
    resultat["ignores"] = [
        {"nom": entree.nom_source, "raison": entree.raison}
        for entree in entrees if entree.statut in ("ignore", "erreur")
    ]
    return resultat


def importer_manifeste(api, manifeste, guild_id, options=None, premium_tier=0):
    """Recharge les fichiers d'un manifeste exporte, sans pretendre reussir."""
    if not isinstance(manifeste, dict) or manifeste.get("format") != FORMAT_MANIFESTE:
        raise ValueError("Manifeste d'emojis non reconnu.")
    if int(manifeste.get("version") or 0) != VERSION_MANIFESTE:
        raise ValueError("Version de manifeste d'emojis non prise en charge.")
    options = options or OptionsEmoji()
    destination = api.guild_emojis(guild_id)
    existants = {str(emoji.get("name") or "").casefold()
                 for emoji in destination if isinstance(emoji, dict)}
    capacite = limite_emojis(premium_tier, True)
    statiques = sum(1 for emoji in destination
                    if isinstance(emoji, dict) and not emoji.get("animated"))
    animes = sum(1 for emoji in destination
                 if isinstance(emoji, dict) and emoji.get("animated"))
    entrees = []
    for item in manifeste.get("emojis") or []:
        if not isinstance(item, dict):
            continue
        entree = EntreeEmoji(emoji={"id": item.get("source_id"),
                                    "animated": bool(item.get("anime"))},
                             nom_source=str(item.get("nom_source") or ""),
                             anime=bool(item.get("anime")))
        entrees.append(entree)
        chemin = Path(str(item.get("fichier") or ""))
        try:
            racine = (Path(EXPORTS_DIR) / "emojis").resolve()
            resolu = chemin.resolve()
            if not resolu.is_relative_to(racine):
                raise ValueError("fichier hors du dossier d'export autorise")
            chemin = resolu
            if not chemin.is_file():
                raise ValueError("fichier exporte introuvable")
            if chemin.stat().st_size > TAILLE_MAX_EMOJI:
                raise ValueError("fichier superieur a 256 Kio")
            donnees = chemin.read_bytes()
            format_ = detecter_format(donnees)
            if format_ not in ("png", "gif", "jpg"):
                raise ValueError("format de fichier invalide")
        except (OSError, ValueError) as exc:
            entree.statut = "erreur"
            entree.raison = str(exc)
            continue
        entree.donnees = donnees
        entree.format = format_
        entree.taille = len(donnees)
        entree.sha256 = hashlib.sha256(donnees).hexdigest()
        entree.fichier = str(chemin)
        entree.nom_cible = resoudre_nom(entree.nom_source, existants,
                                       options.conflits, options.prefixe)
        if not entree.nom_cible:
            entree.statut = "ignore"
            entree.raison = "nom deja utilise a la destination"
            continue
        if entree.anime:
            if animes >= capacite:
                entree.statut = "ignore"
                entree.raison = "capacite d'emojis animes atteinte"
                continue
            animes += 1
        else:
            if statiques >= capacite:
                entree.statut = "ignore"
                entree.raison = "capacite d'emojis statiques atteinte"
                continue
            statiques += 1
        existants.add(entree.nom_cible.casefold())
        entree.statut = "pret"
    return entrees


def ecrire_manifeste_import(resultat, entrees, guild_id, chemin=None):
    manifeste = {
        "format": FORMAT_MANIFESTE,
        "version": VERSION_MANIFESTE,
        "exported_at": maintenant(),
        "destination_guild": str(guild_id),
        "emojis": [entree.manifeste() for entree in entrees],
        "counts": {
            "total": len(entrees),
            "importes": len(resultat.get("importes") or []),
            "erreurs": len(resultat.get("erreurs") or []),
            "ignores": sum(1 for entree in entrees if entree.statut == "ignore"),
        },
    }
    chemin = Path(chemin or Path(EXPORTS_DIR) / f"emojis_import_{guild_id}.json")
    ecrire_json(chemin, manifeste)
    return chemin, manifeste


# ---------------------------------------------------------------------------
# Panel interactif
# ---------------------------------------------------------------------------

def _choisir_serveur(guilds, label, initial=None):
    from core.common import choisir_option, warn
    guilds = list(guilds or [])
    if not guilds:
        warn("Aucun serveur accessible.")
        return None
    libelles = [f"{guild.get('name', '?')} ({guild.get('id')})" for guild in guilds]
    choix = choisir_option(label, libelles + ["Retour"])
    if choix in (None, "Retour"):
        return None
    return guilds[libelles.index(choix)]


def _options_panel():
    from core.common import Confirm, choisir_option, demander
    conserver = Confirm.ask("Conserver les noms d'origine ?", default=True)
    prefixe = demander("Prefixe a ajouter aux noms (vide pour aucun)", "").strip()
    if not prefixe:
        prefixe = ""
    if not conserver and not prefixe:
        prefixe = demander("Un prefixe est requis pour modifier les noms", "").strip()
        if not prefixe:
            from core.common import warn
            warn("Modification de nom sans prefixe : import annule.")
            return None
    conflits = choisir_option("CONFLITS DE NOMS", [
        "Ignorer les emojis dont le nom existe deja",
        "Renommer avec un suffixe numerique",
        "Retour",
    ])
    if conflits in (None, "Retour"):
        return None
    return OptionsEmoji(conserver_noms=conserver, prefixe=prefixe,
                        conflits="renommer" if "Renommer" in conflits else "ignorer")


def _previsualiser_emoji(entrees):
    """Affiche une image reelle d'emoji deja telechargee, sans reseau."""
    from core.common import C_DISCORD, choisir_option, console, warn
    from rich.panel import Panel
    from rich.prompt import Confirm
    libelles = [
        f"{entree.nom_cible or entree.nom_source} · "
        f"{'anime' if entree.anime else 'statique'} · {entree.taille / 1024:.1f} Kio"
        for entree in entrees if entree.donnees
    ]
    candidats = [entree for entree in entrees if entree.donnees]
    if not candidats:
        warn("Aucune image telechargee a previsualiser.")
        return
    try:
        from modules.media.panel import frames_apercu
    except ImportError:
        warn("Pillow est requis pour previsualiser les emojis.")
        return
    while True:
        choix = choisir_option("EMOJI A PREVISUALISER", libelles + ["Terminer"])
        if choix in (None, "Terminer"):
            return
        entree = candidats[libelles.index(choix)]
        try:
            frames = frames_apercu(io.BytesIO(entree.donnees), largeur=24,
                                   max_images=1)
        except (OSError, ValueError) as exc:
            warn(f"Previsualisation impossible : {exc}")
            continue
        if frames:
            console.print(Panel(frames[0], title=entree.nom_cible,
                                border_style=C_DISCORD))
        if entree.anime:
            warn("Emoji anime : seule la premiere image est affichee.")
        if not Confirm.ask("Voir un autre emoji ?", default=False):
            return


def _afficher_entrees(entrees):
    from rich.table import Table
    from core.common import BX, C_DISCORD, console
    table = Table(title="Emojis analyses", box=BX, border_style=C_DISCORD)
    table.add_column("Nom source")
    table.add_column("Nom cible")
    table.add_column("Type")
    table.add_column("Taille", justify="right")
    table.add_column("Statut")
    table.add_column("Note")
    for entree in entrees[:100]:
        table.add_row(entree.nom_source, entree.nom_cible or "-",
                      "anime" if entree.anime else "statique",
                      f"{entree.taille / 1024:.1f} Kio" if entree.taille else "-",
                      entree.statut, entree.raison)
    console.print(table)
    if len(entrees) > 100:
        console.print(f"[dim]{len(entrees) - 100} entree(s) non affichee(s).[/]")


def menu_clonage_emojis(api, etat, token, session=None):
    """Menu d'import/export d'emojis, reutilise par le panel Bot."""
    from rich.panel import Panel
    from core.common import (
        Confirm, attente, bad, barre, choisir_option, console, demander, ok,
        pause, warn,
    )
    from modules.discord.panel_journal import enregistrer as journaliser
    session = session or requests.Session()
    guilds = etat.get("guilds") or []
    try:
        while True:
            choix = choisir_option("EMOJI CLONER", [
                "Importer depuis un serveur source",
                "Exporter les emojis d'un serveur (fichiers + manifeste)",
                "Importer un manifeste exporte",
                "Retour",
            ])
            if choix in (None, "Retour"):
                return
            if choix == "Exporter les emojis d'un serveur (fichiers + manifeste)":
                source = _choisir_serveur(guilds, "SERVEUR SOURCE")
                if source is None:
                    continue
                try:
                    with attente("Telechargement des emojis"):
                        manifeste, chemin = exporter_emojis(api, session, source["id"])
                except (DiscordAPIError, ValueError, OSError) as exc:
                    bad(f"Export impossible : {exc}")
                    pause()
                    continue
                ok(f"{manifeste['counts']['telecharges']} emoji(s) telecharge(s), "
                   f"{manifeste['counts']['erreurs']} erreur(s).")
                ok(f"Manifeste : {chemin}")
                journaliser("export_emojis", source["id"], source["id"], "ok",
                            str(manifeste["counts"]), (token,))
                pause()
                continue
            if choix == "Importer un manifeste exporte":
                chemin = demander("Chemin du manifeste JSON", "").strip()
                try:
                    from modules.discord.local_store import charger_json
                    manifeste = charger_json(chemin, None)
                    if not manifeste:
                        raise ValueError("Manifeste absent ou JSON invalide.")
                except (ValueError, OSError) as exc:
                    bad(str(exc))
                    pause()
                    continue
                destination = _choisir_serveur(guilds, "SERVEUR DE DESTINATION")
                if destination is None:
                    continue
                try:
                    manquantes = verifier_permission_import(
                        api, destination["id"], etat.get("bot_id"))
                except DiscordAPIError as exc:
                    bad(f"Verification des permissions impossible : {exc}")
                    pause()
                    continue
                if manquantes:
                    bad("Permissions manquantes a la destination : "
                        + ", ".join(manquantes) + ".")
                    pause()
                    continue
                options = _options_panel()
                if options is None:
                    continue
                try:
                    guild = api.guild(destination["id"])
                    entrees = importer_manifeste(
                        api, manifeste, destination["id"], options,
                        premium_tier=guild.get("premium_tier", 0))
                except (ValueError, DiscordAPIError) as exc:
                    bad(f"Manifeste refuse : {exc}")
                    pause()
                    continue
            else:
                source = _choisir_serveur(guilds, "SERVEUR SOURCE")
                if source is None:
                    continue
                destination = _choisir_serveur(guilds, "SERVEUR DE DESTINATION")
                if destination is None:
                    continue
                if str(source["id"]) == str(destination["id"]):
                    warn("Source et destination identiques : import refuse.")
                    pause()
                    continue
                try:
                    manquantes = verifier_permission_import(
                        api, destination["id"], etat.get("bot_id"))
                except DiscordAPIError as exc:
                    bad(f"Verification des permissions impossible : {exc}")
                    pause()
                    continue
                if manquantes:
                    bad("Permissions manquantes a la destination : "
                        + ", ".join(manquantes) + ".")
                    pause()
                    continue
                options = _options_panel()
                if options is None:
                    continue
                try:
                    with attente("Lecture et verification des emojis"):
                        emojis = api.guild_emojis(source["id"])
                        dest_emojis = api.guild_emojis(destination["id"])
                        guild = api.guild(destination["id"])
                        entrees = planifier_import(
                            emojis, dest_emojis,
                            lambda emoji: telecharger_emoji(session, emoji),
                            options, premium_tier=guild.get("premium_tier", 0))
                except (DiscordAPIError, ValueError) as exc:
                    bad(f"Preparation impossible : {exc}")
                    pause()
                    continue
            _afficher_entrees(entrees)
            if Confirm.ask("Previsualiser un emoji avant import ?", default=False):
                _previsualiser_emoji(entrees)
            pretes = [entree for entree in entrees if entree.statut == "pret"]
            if not pretes:
                warn("Aucun emoji importable apres verification.")
                pause()
                continue
            console.print(Panel(
                f"{len(pretes)} emoji(s) seront reellement importes sur "
                f"{destination.get('name')} ({destination.get('id')}).\n"
                "Un refus Discord sera affiche et compte comme echec.",
                title="Confirmation", border_style="red"))
            if not Confirm.ask("Confirmer l'import des emojis ?", default=False):
                warn("Import annule.")
                pause()
                continue
            with barre() as progression:
                tache = progression.add_task("Import des emojis", total=len(pretes))

                def avancer(index, total, nom):
                    progression.update(tache, completed=index - 1,
                                       description=nom[:50])

                resultat = importer_entrees(api, destination["id"], entrees, avancer)
                progression.update(tache, completed=len(pretes))
            chemin, manifeste = ecrire_manifeste_import(resultat, entrees,
                                                        destination["id"])
            if resultat.get("importes"):
                ok(f"{len(resultat['importes'])} emoji(s) importe(s) et confirmes par l'API.")
            if resultat.get("erreurs"):
                bad(f"{len(resultat['erreurs'])} echec(s) :")
                for erreur in resultat["erreurs"][:20]:
                    console.print(f"  - {erreur['nom']} : {erreur['erreur']}")
            if resultat.get("interrompu"):
                warn(f"Import interrompu : {resultat['interrompu']}.")
            ok(f"Manifeste de resultat : {chemin}")
            journaliser("import_emojis", destination["id"], destination["id"],
                        "ok" if not resultat.get("erreurs") else "erreur",
                        str(manifeste["counts"]), (token,))
            pause()
    finally:
        if session is not None and hasattr(session, "close"):
            try:
                session.close()
            except OSError:
                pass


def emoji_cloner():
    """Point d'entree catalogue : connexion Bot puis panel Emoji Cloner."""
    from rich.prompt import Prompt
    from core.common import bad, titre, attente, warn, warn_pentest
    titre("DISCORD EMOJI CLONER", "#5865F2")
    warn("Importez uniquement des emojis dont la copie est autorisee.")
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
        menu_clonage_emojis(api, etat, token)
    finally:
        api.close()
