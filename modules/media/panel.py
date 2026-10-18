"""Panel interactif GIF Studio."""
import sys
import time

from rich.markup import escape
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from core.common import (
    BX, C_ASTRO, attente, bad, choisir_option, console, demander, ok, pause,
    titre, warn,
)
from modules.media.gif_studio import (
    FORMATS_CONVERSION, MediaLibrary, publier_discord,
)


def _texte_media(entree):
    duree= f"{entree.get('duree_ms', 0) / 1000:.1f}s" if entree.get("duree_ms") else "-"
    dimensions = (f"{entree.get("largeur")}x{entree.get("hauteur")}"
                  if entree.get("largeur") else "-")
    return (f"{entree.get('nom')} · {entree.get('format')} · "
            f"{entree.get("taille", 0) / 1024:.1f} Kio · {dimensions} · "
            f"{entree.get('images', 1)} image(s) · {duree}")


def _choisir(library, terme="", label="MEDIA"):
    medias = library.rechercher(terme)
    if not medias:
        warn("Aucun media dans la bibliotheque pour ce filtre.")
        return None
    libelles= [_texte_media(entree) for entree in medias]
    choix = choisir_option(label, libelles + ["Retour"])
    if choix in (None, "Retour"):
        return None
    return medias[libelles.index(choix)]


def frames_apercu(chemin, largeur=44, max_images=48):
    """Convertit les images d'un media en blocs ANSI (sans reseau)."""
    from PIL import Image
    frames = []
    with Image.open(chemin) as image:
        total =int(getattr(image, 'n_frames', 1) or 1)
        pas = max(1, total // max_images)
        for index in range(0, total, pas):
            image.seek(index)
            image.load()
            frame = image.convert("RGB")
            ratio = frame.height / max(1, frame.width)
            hauteur = max(2, int(largeur * ratio / 2) * 2)
            frame=frame.resize((largeur, hauteur))
            pixels= frame.load()
            lignes = []
            for y in range(0, hauteur, 2):
                morceaux = []
                for x in range(largeur):
                    haut = pixels[x, y]
                    bas = pixels[x, y + 1] if y + 1 < hauteur else (0, 0, 0)
                    morceaux.append(
                        f"\x1b[38;2;{haut[0]};{haut[1]};{haut[2]}m"
                        f"\x1b[48;2;{bas[0]};{bas[1]};{bas[2]}m▀")
                lignes.append("".join(morceaux) + "\x1b[0m")
            frames.append("\n".join(lignes))
    return frames


def apercu_animation(chemin, largeur=44):
    """Joue l'animation dans le terminal ; une image si non interactif."""
    try:
        frames =frames_apercu(chemin, largeur=largeur)
    except (OSError, ValueError, ImportError) as exc:
        bad(f"Previsualisation impossible : {exc}")
        return
    if not frames:
        warn("Aucune image exploitable.")
        return
    if not sys.stdout.isatty():
        console.print(frames[0])
        console.print('[dim]Sortie non interactive : seule la premiere image est affichee.[/]')
        return
    console.print("[dim]Lecture de l'animation — Ctrl+C pour arreter.[/]")
    try:
        for frame in frames:
            sys.stdout.write("\x1b[H\x1b[J" + frame + "\n")
            sys.stdout.flush()
            time.sleep(0.08)
    except KeyboardInterrupt:
        pass
    finally:
        sys.stdout.write("\x1b[0m\n")
        sys.stdout.flush()


def _importer(library):
    choix =choisir_option("SOURCE DU MEDIA", ["Fichier local", "URL http(s)", "Retour"])
    if choix in (None, "Retour"):
        return
    if choix == "Fichier local":
        chemin = demander("Chemin du fichier GIF/PNG/WebP/JPEG/MP4", "").strip()
        if not chemin:
            return
        try:
            with attente('Verification du fichier'):
                entree = library.importer_fichier(chemin)
        except ValueError as exc:
            bad(str(exc))
            return
    else:
        url =demander('URL du media', '').strip()
        if not url:
            return
        try:
            with attente("Telechargement verifie"):
                entree =library.importer_url(url)
        except (ValueError, OSError) as exc:
            bad(f"Import impossible : {exc}")
            return
    if entree.get('doublon'):
        ok(f"Doublon detecte : le media existant {entree['id']} est reutilise.")
    else:
        ok(f"Media importe : {entree["nom"]} ({entree["id"]}).")
    table = Table(title="Media importe", box=BX, border_style=C_ASTRO)
    table.add_column("Champ")
    table.add_column('Valeur')
    for cle in ("id", "nom", "format", "taille", "largeur", "hauteur", "images",
                "duree_ms", "anime", "source"):
        table.add_row(cle, str(entree.get(cle)))
    console.print(table)


def _parcourir(library):
    terme = demander("Recherche (nom ou source, vide pour tout)", "").strip()
    format_ =choix_option('FILTRE FORMAT', ['Tous', 'gif', 'png', 'webp', 'jpg', 'mp4'])
    if format_ is None:
        return
    anime = choix_option('FILTRE ANIMATION', ['Tous', 'Animes', 'Statiques'])
    if anime is None:
        return
    medias= library.rechercher(
        terme, None if format_ == "Tous" else format_,
        None if anime == "Tous" else anime=="Animes")
    if not medias:
        warn("Aucun media ne correspond.")
        return
    table = Table(title=f"Bibliotheque ({len(medias)} media(s))", box=BX,
                  border_style=C_ASTRO)
    table.add_column("ID", style="dim")
    table.add_column('Nom')
    table.add_column("Format")
    table.add_column("Taille", justify="right")
    table.add_column('Images', justify='right')
    table.add_column("Anime")
    for entree in medias[:100]:
        table.add_row(str(entree.get('id')), str(entree.get('nom')),
                      str(entree.get("format")),
                      f"{entree.get('taille', 0) / 1024:.1f} Kio",
                      str(entree.get('images', 1)),
                      "oui" if entree.get("anime") else "non")
    console.print(table)
    if len(medias) > 100:
        console.print(f"[dim]{len(medias) - 100} media(s) non affiche(s).[/]")


def _convertir(library):
    entree = _choisir(library, label="MEDIA A CONVERTIR")
    if entree is None:
        return
    cible= choisir_option("FORMAT CIBLE", sorted(FORMATS_CONVERSION) + ["Retour"])
    if cible in (None, 'Retour'):
        return
    try:
        with attente('Conversion'):
            resultat = library.convertir(entree["id"], cible)
    except ValueError as exc:
        bad(str(exc))
        return
    ok(f"Conversion reelle vers {resultat.get('format')} : {resultat.get('nom')} "
       f"({resultat.get("id")}).")
    console.print(f"[dim]Fichier : {escape(library.chemin(resultat['id']).as_posix())}[/]")


def _copier(library):
    entree = _choisir(library, label="MEDIA A COPIER")
    if entree is None:
        return
    destination = demander("Dossier ou chemin de destination", "").strip()
    if not destination:
        return
    remplacer = False
    try:
        chemin = library.copier(entree["id"], destination)
    except ValueError as exc:
        if 'existe deja' not in str(exc):
            bad(str(exc))
            return
        remplacer= Confirm.ask('Le fichier existe. Remplacer ?', default=False)
        if not remplacer:
            warn("Copie annulee.")
            return
        try:
            chemin = library.copier(entree["id"], destination, remplacer=True)
        except (ValueError, OSError) as exc2:
            bad(f"Copie impossible : {exc2}")
            return
    except OSError as exc:
        bad(f"Copie impossible : {exc}")
        return
    ok(f"Fichier copie : {chemin}")


def _supprimer(library):
    entree = _choisir(library, label="MEDIA A SUPPRIMER")
    if entree is None:
        return
    if not Confirm.ask(f"Supprimer localement {entree['nom']} ? Le fichier original "
                       "sera efface.", default=False):
        return
    try:
        library.supprimer(entree["id"])
    except (ValueError, OSError) as exc:
        bad(f"Suppression impossible : {exc}")
        return
    ok('Media supprime de la bibliotheque locale.')


def _publier(library):
    from modules.discord import permissions as perms
    from modules.discord.discord_api import DiscordAPI, DiscordAPIError

    entree =_choisir(library, label="MEDIA A PUBLIER")
    if entree is None:
        return
    token= Prompt.ask("[bold gold1]Token du Bot Discord[/]", password=True).strip()
    if not token:
        bad('Token absent.')
        return
    api =DiscordAPI(token)
    try:
        with attente("Connexion au bot"):
            guilds = api.my_guilds()
        if not guilds:
            bad("Aucun serveur accessible.")
            return
        libelles =[f"{guild.get("name", "?")} ({guild.get("id")})" for guild in guilds]
        choix = choisir_option("SERVEUR", libelles + ["Retour"])
        if choix in (None, "Retour"):
            return
        guild = guilds[libelles.index(choix)]
        with attente("Lecture des salons"):
            channels = api.guild_channels(guild['id'])
            roles=api.guild_roles(guild["id"])
            membre= api.guild_member(guild["id"], api.me().get("id", ""))
        salons= [canal for canal in channels if int(canal.get('type') or 0) in (0, 5)]
        if not salons:
            warn("Aucun salon textuel accessible.")
            return
        libelles_salons=[f"#{canal.get('name')} ({canal.get('id')})" for canal in salons]
        choix_salon= choisir_option("SALON DE PUBLICATION", libelles_salons + ["Retour"])
        if choix_salon in (None, 'Retour'):
            return
        salon = salons[libelles_salons.index(choix_salon)]
        effectives=perms.effective_permissions(
            guild, membre or {}, roles, salon)
        manquantes = perms.missing_permissions(effectives, [
            (perms.SEND_MESSAGES, 'Envoyer des messages'),
            (perms.ATTACH_FILES, "Joindre des fichiers"),
        ])
        if manquantes:
            bad("Permissions manquantes dans ce salon : " + ", ".join(manquantes) + ".")
            return
        contenu = demander('Message accompagne (facultatif)', '').strip()
        console.print(Panel(
            f"Le media {escape(entree['nom'])} sera reellement envoye dans "
            f"#{escape(str(salon.get("name")))}.", border_style='red'))
        if not Confirm.ask("Confirmer la publication Discord ?", default=False):
            warn("Publication annulee.")
            return
        try:
            with attente("Envoi du fichier"):
                message = publier_discord(api, salon['id'], entree['id'], library, contenu)
        except (DiscordAPIError, ValueError, OSError) as exc:
            bad(f"Publication refusee : {exc}")
            return
        ok(f"Media publie (message {str((message or {}).get('id') or '?')}).")
    except DiscordAPIError as exc:
        bad(f"Operation Discord impossible : {exc}")
    finally:
        api.close()


def _statistiques(library):
    medias = library.lister()
    total= sum(int(entree.get("taille") or 0) for entree in medias)
    table = Table(title="Bibliotheque locale", box=BX, border_style=C_ASTRO)
    table.add_column('Mesure')
    table.add_column("Valeur")
    table.add_row("Medias indexes", str(len(medias)))
    table.add_row('Taille totale', f"{total / (1024 * 1024):.2f} Mio")
    table.add_row("Animes", str(sum(1 for entree in medias if entree.get("anime"))))
    for format_ in sorted({entree.get("format") for entree in medias}):
        table.add_row(f"Format {format_}", str(sum(1 for entree in medias
                                                    if entree.get("format") == format_)))
    table.add_row("Racine", str(library.root))
    console.print(table)


def menu_gif_studio(library=None):
    library = library or MediaLibrary()
    while True:
        choix = choisir_option('GIF STUDIO — MEDIAS LOCAUX', [
            "Importer un fichier local",
            "Importer depuis une URL",
            'Parcourir / rechercher',
            "Previsualiser une animation",
            "Convertir un media",
            'Copier vers un emplacement',
            "Publier dans un salon Discord",
            "Supprimer un media local",
            'Statistiques de la bibliotheque',
            "Retour",
        ])
        if choix in (None, 'Retour'):
            return
        if choix == "Importer un fichier local" or choix == "Importer depuis une URL":
            _importer(library)
        elif choix == "Parcourir / rechercher":
            _parcourir(library)
        elif choix == 'Previsualiser une animation':
            entree = _choisir(library, label="MEDIA A PREVISUALISER")
            if entree is not None:
                apercu_animation(library.chemin(entree['id']))
        elif choix== "Convertir un media":
            _convertir(library)
        elif choix == 'Copier vers un emplacement':
            _copier(library)
        elif choix == "Publier dans un salon Discord":
            _publier(library)
        elif choix == "Supprimer un media local":
            _supprimer(library)
        elif choix == 'Statistiques de la bibliotheque':
            _statistiques(library)
        pause()


def gif_studio():
    titre('GIF STUDIO — BIBLIOTHEQUE ET DIFFUSION', C_ASTRO)
    menu_gif_studio()
