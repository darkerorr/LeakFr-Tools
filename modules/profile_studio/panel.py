"""Panel Profile Studio : preparation locale, application manuelle.

Aucun bouton « Appliquer » : l'API officielle ne permet pas a une
application de modifier le profil d'un compte utilisateur. Les actions
proposées ouvrent les paramètres officiels de Discord et conservent les
variantes localement.
"""
from rich.markup import escape
from rich.panel import Panel
from rich.prompt import Confirm
from rich.table import Table

from core.common import (
    BX, C_ASTRO, bad, choisir_option, console, demander, ok, ouvrir_url, pause,
    titre, warn,
)
from modules.profile_studio.store import ProfileStore
from modules.profile_studio.templates import appliquer_modele, lister_modeles, placeholders

LIENS_OFFICIELS = [
    ("Profil (avatar, banniere, bio)", "https://discord.com/settings/profile"),
    ("Compte (nom, e-mail, mot de passe)", "https://discord.com/settings/account"),
    ("Apparence (theme, statut)", "https://discord.com/settings/appearance"),
    ("Connexions", "https://discord.com/settings/connections"),
]


def _image_label(image):
    return (f"{image.get('nom')} · {image.get('largeur')}x{image.get('hauteur')} · "
            f"{image.get('kind')} · id {image.get('id')}")


def _choisir_image(store, kind=None, label="IMAGE"):
    images = store.images(kind)
    if not images:
        warn("Aucune image preparee pour ce type.")
        return None
    libelles = [_image_label(image) for image in images]
    choix = choisir_option(label, libelles + ["Retour"])
    if choix in (None, "Retour"):
        return None
    return images[libelles.index(choix)]


def _lister_images(store):
    images = store.images()
    if not images:
        warn("Bibliotheque d'images vide.")
        return
    table = Table(title="Avatars et bannieres prepares", box=BX, border_style=C_ASTRO)
    table.add_column("ID", style="dim")
    table.add_column("Nom")
    table.add_column("Type")
    table.add_column("Dimensions")
    table.add_column("Format")
    table.add_column("Origine")
    for image in images:
        table.add_row(str(image.get("id")), str(image.get("nom")),
                      str(image.get("kind")),
                      f"{image.get('largeur')}x{image.get('hauteur')}",
                      str(image.get("format")), str(image.get("chemin")))
    console.print(table)


def _previsualiser(store):
    image = _choisir_image(store, label="IMAGE A PREVISUALISER")
    if image is None:
        return
    try:
        from modules.media.panel import frames_apercu
        frames = frames_apercu(store.chemin_image(image["id"]), largeur=40,
                               max_images=1)
    except (OSError, ValueError, ImportError) as exc:
        bad(f"Previsualisation impossible : {exc}")
        return
    if frames:
        console.print(frames[0])
    console.print("[dim]Apercu local de la premiere image ; aucune modification Discord.[/]")


def _importer(store):
    chemin = demander("Chemin de l'image (PNG, JPEG, WebP ou GIF)", "").strip()
    if not chemin:
        return
    kind = choisir_option("TYPE D'IMAGE", ["Avatar", "Banniere", "Retour"])
    if kind in (None, "Retour"):
        return
    try:
        image = store.importer_image(chemin, "avatar" if kind == "Avatar" else "banner")
    except ValueError as exc:
        bad(str(exc))
        return
    if image.get("doublon"):
        ok(f"Image deja presente : {image['id']} (reutilisee).")
    else:
        ok(f"Image importee localement : {image['id']}.")
    console.print(Panel(
        f"{image.get('nom')} · {image.get('largeur')}x{image.get('hauteur')} · "
        f"{image.get('taille', 0) / 1024:.1f} Kio\n"
        "L'original est conserve. L'image n'a pas ete envoyee a Discord.",
        title="Import local", border_style=C_ASTRO))


def _recadrer(store):
    image = _choisir_image(store, label="IMAGE A RECADRER")
    if image is None:
        return
    kind = choisir_option("TYPE DE SORTIE", ["Avatar 512x512", "Banniere 960x540", "Retour"])
    if kind in (None, "Retour"):
        return
    kind_code = "avatar" if "Avatar" in kind else "banner"
    mode = choisir_option("CADRAGE", [
        "Automatique (carre centre / image entiere)",
        "Boite personnalisee en pixels",
        "Retour",
    ])
    if mode in (None, "Retour"):
        return
    boite = None
    if mode == "Boite personnalisee en pixels":
        try:
            boite = tuple(int(demander(champ).strip()) for champ in
                          ("Gauche (px)", "Haut (px)", "Largeur (px)", "Hauteur (px)"))
        except ValueError:
            bad("Les quatre valeurs doivent etre des entiers.")
            return
    try:
        preparee = store.recadrer(image["id"], kind_code, boite)
    except ValueError as exc:
        bad(str(exc))
        return
    ok(f"Image preparee localement : {preparee['id']} "
       f"({preparee['largeur']}x{preparee['hauteur']}).")
    console.print(f"[dim]Fichier : {escape(preparee['chemin'])}[/]")
    if image.get("anime"):
        warn("La source etait animee ; le recadrage produit une image fixe.")


def _modeles(store):
    modeles = lister_modeles()
    libelles = [f"{modele['nom']} — {modele['description']}" for modele in modeles]
    choix = choisir_option("MODELES DE BIOGRAPHIE", libelles + ["Retour"])
    if choix in (None, "Retour"):
        return None
    modele = modeles[libelles.index(choix)]
    valeurs = {}
    for cle in placeholders(modele):
        valeurs[cle] = demander(f"Valeur pour {{{cle}}} (facultatif)", "").strip()
    texte = appliquer_modele(modele, valeurs)
    console.print(Panel(escape(texte), title=f"Modele · {modele['nom']}",
                        border_style=C_ASTRO))
    console.print("[dim]Texte local, non applique a Discord.[/]")
    return texte


def _editer_variante(store):
    configs = store.configs()
    choix = "Nouvelle variante"
    existante = None
    if configs:
        libelles = [f"{config['nom']} ({config['id']})" for config in configs]
        choix = choisir_option("VARIANTE A MODIFIER", libelles + ["Nouvelle variante", "Retour"])
        if choix in (None, "Retour"):
            return
        if choix != "Nouvelle variante":
            existante = configs[libelles.index(choix)]
    nom = demander("Nom de la variante", (existante or {}).get("nom") or "").strip()
    if not nom:
        warn("Nom obligatoire.")
        return
    display_name = demander("Nom affiche (32 caracteres max)",
                            (existante or {}).get("display_name") or "").strip()
    bio = (existante or {}).get("bio") or ""
    if Confirm.ask("Utiliser un modele de biographie ?", default=False):
        texte = _modeles(store)
        if texte:
            bio = texte
    bio = demander("Biographie (190 caracteres max)", bio).strip()
    statut = demander("Texte de statut (128 caracteres max)",
                      (existante or {}).get("status_text") or "").strip()

    avatar = None
    if Confirm.ask("Choisir un avatar prepare ?", default=False):
        image = _choisir_image(store, "avatar", "AVATAR")
        avatar = image["id"] if image else (existante or {}).get("avatar_id")
    else:
        avatar = (existante or {}).get("avatar_id")
    banniere = None
    if Confirm.ask("Choisir une banniere preparee ?", default=False):
        image = _choisir_image(store, "banner", "BANNIERE")
        banniere = image["id"] if image else (existante or {}).get("banner_id")
    else:
        banniere = (existante or {}).get("banner_id")

    donnees = {"display_name": display_name, "bio": bio, "status_text": statut,
               "avatar_id": avatar, "banner_id": banniere}
    try:
        config = store.sauvegarder_config(nom, donnees)
    except ValueError as exc:
        bad(str(exc))
        return
    table = Table(title="Variante enregistree LOCALEMENT", box=BX, border_style=C_ASTRO)
    table.add_column("Champ")
    table.add_column("Valeur")
    for champ, libelle in (("display_name", "Nom affiche"), ("bio", "Biographie"),
                           ("status_text", "Statut"), ("avatar_id", "Avatar"),
                           ("banner_id", "Banniere")):
        table.add_row(libelle, str(config.get(champ) or "-"))
    console.print(table)
    ok("Configuration enregistree localement — elle n'est PAS appliquee sur Discord.")
    console.print("[dim]Pour l'appliquer, utilisez les parametres officiels Discord "
                  "(menu Guide & liens).[/]")


def _lister_variantes(store):
    configs = store.configs()
    if not configs:
        warn("Aucune variante enregistree.")
        return
    table = Table(title="Variantes locales", box=BX, border_style=C_ASTRO)
    table.add_column("ID", style="dim")
    table.add_column("Nom")
    table.add_column("Nom affiche")
    table.add_column("Statut")
    table.add_column("Avatar")
    table.add_column("Banniere")
    table.add_column("Applique ?")
    for config in configs:
        table.add_row(str(config.get("id")), str(config.get("nom")),
                      str(config.get("display_name") or "-"),
                      str(config.get("status_text") or "-"),
                      "oui" if config.get("avatar_id") else "non",
                      "oui" if config.get("banner_id") else "non",
                      "non (local)")
    console.print(table)


def _comparer(store):
    configs = store.configs()
    if len(configs) < 2:
        warn("Deux variantes sont necessaires pour comparer.")
        return
    libelles = [f"{config['nom']} ({config['id']})" for config in configs]
    choix_a = choisir_option("PREMIERE VARIANTE", libelles + ["Retour"])
    if choix_a in (None, "Retour"):
        return
    choix_b = choisir_option("SECONDE VARIANTE", libelles + ["Retour"])
    if choix_b in (None, "Retour"):
        return
    try:
        comparaison = store.comparer(configs[libelles.index(choix_a)]["id"],
                                    configs[libelles.index(choix_b)]["id"])
    except ValueError as exc:
        bad(str(exc))
        return
    table = Table(title=f"Comparaison · {comparaison['a']} / {comparaison['b']}",
                  box=BX, border_style=C_ASTRO)
    table.add_column("Champ")
    table.add_column(comparaison["a"])
    table.add_column(comparaison["b"])
    if not comparaison["differences"]:
        table.add_row("Aucune difference", "-", "-")
    for champ, valeurs in comparaison["differences"].items():
        table.add_row(champ, str(valeurs["a"] or "-"), str(valeurs["b"] or "-"))
    console.print(table)


def _historique(store):
    entrees = store.historique()
    if not entrees:
        warn("Historique vide.")
        return
    table = Table(title="Historique local des configurations", box=BX,
                  border_style=C_ASTRO)
    table.add_column("Date")
    table.add_column("Variante")
    table.add_column("Action")
    for entree in reversed(entrees):
        table.add_row(str(entree.get("date")), str(entree.get("nom")),
                      str(entree.get("action")))
    console.print(table)
    console.print("[dim]Historique local uniquement : aucune modification Discord.[/]")


def _exporter(store):
    configs = store.configs()
    if not configs:
        warn("Aucune variante a exporter.")
        return
    libelles = [f"{config['nom']} ({config['id']})" for config in configs]
    choix = choisir_option("VARIANTE A EXPORTER", libelles + ["Retour"])
    if choix in (None, "Retour"):
        return
    chemin = demander("Chemin du fichier JSON", "data/exports/profil_variante.json").strip()
    try:
        path = store.exporter_config(configs[libelles.index(choix)]["id"], chemin)
    except (ValueError, OSError) as exc:
        bad(f"Export impossible : {exc}")
        return
    ok(f"Configuration exportee localement : {path}")


def _importer(store):
    chemin = demander("Chemin du fichier JSON a importer", "").strip()
    if not chemin:
        return
    try:
        config = store.importer_config(chemin)
    except ValueError as exc:
        bad(str(exc))
        return
    ok(f"Variante importee localement : {config['nom']} ({config['id']}).")


def _guide():
    table = Table(title="Parametres officiels Discord", box=BX, border_style=C_ASTRO)
    table.add_column("Reglage")
    table.add_column("Lien officiel")
    for libelle, lien in LIENS_OFFICIELS:
        table.add_row(libelle, lien)
    console.print(table)
    console.print(Panel(
        "1. Ouvrez le lien officiel correspondant dans votre navigateur.\n"
        "2. Utilisez l'image preparee dans data/profile_studio/prepared/.\n"
        "3. Copiez le nom affiche, la bio et le statut depuis votre variante.\n"
        "4. Validez manuellement dans Discord.\n\n"
        "LIMITE REELLE : l'API officielle Discord ne permet pas a une application\n"
        "de modifier le profil d'un compte utilisateur. Le Profile Studio ne\n"
        "demande aucun jeton de compte, n'utilise pas de selfbot et n'automatise\n"
        "aucune modification de compte. Un bot ne peut modifier que son propre profil.",
        title="Guide d'application manuelle", border_style="yellow"))
    choix = choisir_option("OUVRIR UN LIEN OFFICIEL", [libelle for libelle, _ in LIENS_OFFICIELS]
                           + ["Retour"])
    if choix in (None, "Retour"):
        return
    lien = dict(LIENS_OFFICIELS)[choix]
    ouvrir_url(lien)
    ok(f"Ouverture demandee : {lien}")


def menu_profile_studio(store=None):
    store = store or ProfileStore()
    while True:
        choix = choisir_option("PROFILE STUDIO — PREPARATION LOCALE", [
            "Lister les avatars et bannieres",
            "Previsualiser une image",
            "Importer une image",
            "Recadrer / preparer une image",
            "Modeles de biographie",
            "Creer ou modifier une variante",
            "Lister les variantes",
            "Comparer deux variantes",
            "Historique local",
            "Exporter une variante",
            "Importer une variante",
            "Guide & parametres officiels Discord",
            "Retour",
        ])
        if choix in (None, "Retour"):
            return
        if choix == "Lister les avatars et bannieres":
            _lister_images(store)
        elif choix == "Previsualiser une image":
            _previsualiser(store)
        elif choix == "Importer une image":
            _importer(store)
        elif choix == "Recadrer / preparer une image":
            _recadrer(store)
        elif choix == "Modeles de biographie":
            _modeles(store)
        elif choix == "Creer ou modifier une variante":
            _editer_variante(store)
        elif choix == "Lister les variantes":
            _lister_variantes(store)
        elif choix == "Comparer deux variantes":
            _comparer(store)
        elif choix == "Historique local":
            _historique(store)
        elif choix == "Exporter une variante":
            _exporter(store)
        elif choix == "Importer une variante":
            _importer(store)
        elif choix == "Guide & parametres officiels Discord":
            _guide()
        pause()


def profile_studio():
    titre("PROFILE STUDIO — AVATAR, BANNIERE ET BIO", C_ASTRO)
    console.print(Panel(
        "Tout est prepare LOCALEMENT. Aucune modification de compte Discord\n"
        "n'est effectuee par cet outil : l'API officielle ne le permet pas.",
        title="Limite explicite", border_style="yellow"))
    menu_profile_studio()
