"""GIF Studio : bibliotheque locale de medias animes.

Chaque import est verifie (signature, taille, decodage), stocke sous son
empreinte SHA-256 et indexe localement. La conversion repose sur Pillow et
ne promet que les formats reellement pris en charge. La publication Discord
est une operation distincte de l'enregistrement local.
"""
import hashlib
import ipaddress
import json
import os
import socket
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

from core.config import DATA_DIR

TAILLE_MAX = 10 * 1024 * 1024
FORMATS_IMPORT = {"gif", "png", "webp", "jpg", "mp4"}
FORMATS_DISCORD = {"gif", "png", "webp", "jpg", "mp4"}
FORMATS_CONVERSION = {"gif", "webp", "png"}
EXTENSIONS = {"gif": ".gif", "png": ".png", "webp": ".webp", "jpg": ".jpg",
              "mp4": ".mp4"}
MIME = {"gif": "image/gif", "png": "image/png", "webp": "image/webp",
        "jpg": "image/jpeg", "mp4": "video/mp4"}


def maintenant():
    return datetime.now(timezone.utc).isoformat()


def detecter_format(donnees):
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
    if len(donnees) >= 12 and donnees[4:8] == b"ftyp":
        return "mp4"
    return None


def _est_ip_privee(adresse):
    try:
        ip = ipaddress.ip_address(adresse)
    except ValueError:
        return True
    return (ip.is_private or ip.is_loopback or ip.is_link_local
            or ip.is_reserved or ip.is_multicast or ip.is_unspecified)


def valider_url(url):
    """Valide une URL http(s) publique et bloque les cibles internes."""
    analyse = urlparse(str(url or ""))
    if analyse.scheme not in ("http", "https"):
        raise ValueError("Seules les URL http(s) sont acceptees.")
    if analyse.username or analyse.password:
        raise ValueError("URL avec identifiants refusee.")
    hote = analyse.hostname
    if not hote:
        raise ValueError("URL sans hote.")
    try:
        infos = socket.getaddrinfo(hote, analyse.port or (443 if analyse.scheme == "https" else 80),
                                   proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        raise ValueError("Hote introuvable.") from None
    adresses = {info[4][0] for info in infos}
    if not adresses:
        raise ValueError("Hote sans adresse resolvable.")
    for adresse in adresses:
        if _est_ip_privee(adresse):
            raise ValueError("Les adresses privees, locales ou reservees sont refusees.")
    return url


def analyser_media(chemin):
    """Analyse un fichier local ; retourne les metadonnees reelles."""
    chemin = Path(chemin)
    try:
        taille = chemin.stat().st_size
    except OSError as exc:
        raise ValueError(f"Fichier illisible : {exc}") from None
    if taille <= 0:
        raise ValueError("Fichier vide.")
    if taille > TAILLE_MAX:
        raise ValueError(f"Fichier superieur a {TAILLE_MAX // (1024 * 1024)} Mio.")
    with chemin.open("rb") as fichier:
        entete = fichier.read(32)
    format_ = detecter_format(entete)
    if format_ not in FORMATS_IMPORT:
        raise ValueError("Format non reconnu (GIF, PNG, WebP, JPEG ou MP4 attendu).")
    meta = {"format": format_, "taille": taille, "largeur": None, "hauteur": None,
            "images": 1, "duree_ms": 0, "anime": format_ == "gif"}
    if format_ == "mp4":
        meta["note"] = "Metadonnees video limitees (aucun decodeur video embarque)."
        return meta
    try:
        from PIL import Image, UnidentifiedImageError
    except ImportError:
        raise ValueError("Pillow est requis pour analyser les images.") from None
    try:
        with Image.open(chemin) as image:
            meta["largeur"], meta["hauteur"] = image.size
            meta["images"] = int(getattr(image, "n_frames", 1) or 1)
            duree = 0
            for index in range(meta["images"]):
                try:
                    image.seek(index)
                except EOFError:
                    break
                duree += int(image.info.get("duration") or 0)
            meta["duree_ms"] = duree
            meta["anime"] = meta["images"] > 1 or bool(getattr(image, "is_animated", False))
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError(f"Image invalide ou corrompue : {exc}") from None
    return meta


def _slug(texte, maximum=60):
    import re
    import unicodedata
    texte = unicodedata.normalize("NFKD", str(texte or "media")).encode(
        "ascii", "ignore").decode("ascii")
    texte = re.sub(r"[^a-zA-Z0-9_-]+", "-", texte).strip("-").lower()
    return (texte or "media")[:maximum]


class MediaLibrary:
    """Index JSON local et fichiers originaux, sans dependance a Discord."""

    def __init__(self, root=None):
        self.root = Path(root or Path(DATA_DIR) / "media")
        self.originals = self.root / "originals"
        self.index_path = self.root / "index.json"
        self.originals.mkdir(parents=True, exist_ok=True)

    # -- index ---------------------------------------------------------
    def _charger(self):
        try:
            donnees = json.loads(self.index_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        return donnees if isinstance(donnees, list) else []

    def _ecrire(self, entrees):
        self.root.mkdir(parents=True, exist_ok=True)
        temporaire = self.index_path.with_name(self.index_path.name + ".tmp")
        temporaire.write_text(json.dumps(entrees, ensure_ascii=False, indent=2) + "\n",
                              encoding="utf-8")
        os.replace(temporaire, self.index_path)

    def lister(self):
        return self._charger()

    def obtenir(self, media_id):
        for entree in self._charger():
            if str(entree.get("id")) == str(media_id):
                return entree
        return None

    def chemin(self, media_id):
        entree = self.obtenir(media_id)
        if not entree:
            raise ValueError("Media introuvable dans la bibliotheque.")
        chemin = self.root / entree["chemin"]
        if not chemin.is_file():
            raise ValueError("Fichier original manquant : l'index est incoherent.")
        return chemin

    def _ajouter(self, donnees, nom, source, format_, conversion_de=None):
        empreinte = hashlib.sha256(donnees).hexdigest()
        entrees = self._charger()
        for existant in entrees:
            if existant.get("sha256") == empreinte:
                existant = dict(existant)
                existant["doublon"] = True
                return existant
        identifiant = empreinte[:16]
        chemin = self.originals / f"{identifiant}{EXTENSIONS[format_]}"
        if not chemin.is_file():
            chemin.write_bytes(donnees)
        try:
            meta = analyser_media(chemin)
        except ValueError:
            chemin.unlink(missing_ok=True)
            raise
        entree = {
            "id": identifiant,
            "sha256": empreinte,
            "nom": _slug(nom) + EXTENSIONS[format_],
            "format": format_,
            "taille": meta["taille"],
            "largeur": meta["largeur"],
            "hauteur": meta["hauteur"],
            "images": meta["images"],
            "duree_ms": meta["duree_ms"],
            "anime": meta["anime"],
            "source": str(source),
            "importe_le": maintenant(),
            "chemin": chemin.relative_to(self.root).as_posix(),
        }
        if conversion_de:
            entree["conversion_de"] = conversion_de
        entrees.append(entree)
        self._ecrire(entrees)
        entree["doublon"] = False
        return entree

    # -- imports -------------------------------------------------------
    def importer_fichier(self, chemin, nom=None):
        chemin = Path(chemin)
        try:
            taille = chemin.stat().st_size
        except OSError as exc:
            raise ValueError(f"Fichier illisible : {exc}") from None
        if taille > TAILLE_MAX:
            raise ValueError(f"Fichier superieur a {TAILLE_MAX // (1024 * 1024)} Mio.")
        donnees = chemin.read_bytes()
        format_ = detecter_format(donnees)
        if format_ not in FORMATS_IMPORT:
            raise ValueError("Format non reconnu (GIF, PNG, WebP, JPEG ou MP4 attendu).")
        return self._ajouter(donnees, nom or chemin.stem, chemin, format_)

    def importer_url(self, url, session=None, nom=None):
        import requests
        valider_url(url)
        session = session or requests.Session()
        courant = url
        for _redirection in range(3):
            try:
                reponse = session.get(courant, timeout=15, stream=True,
                                      allow_redirects=False)
            except requests.RequestException as exc:
                raise ValueError(f"Telechargement impossible : {type(exc).__name__}") from None
            if reponse.status_code in (301, 302, 303, 307, 308):
                cible = reponse.headers.get("Location")
                if not cible:
                    raise ValueError("Redirection sans destination.")
                courant = valider_url(urljoin(courant, cible))
                continue
            if reponse.status_code != 200:
                raise ValueError(f"Telechargement refuse : HTTP {reponse.status_code}")
            longueur = reponse.headers.get("Content-Length")
            if longueur and str(longueur).isdigit() and int(longueur) > TAILLE_MAX:
                raise ValueError("Fichier trop volumineux.")
            contenu = bytearray()
            for morceau in reponse.iter_content(16384):
                contenu.extend(morceau)
                if len(contenu) > TAILLE_MAX:
                    raise ValueError("Fichier trop volumineux.")
            donnees = bytes(contenu)
            format_ = detecter_format(donnees)
            if format_ not in FORMATS_IMPORT:
                raise ValueError("Le fichier telecharge n'est pas un media reconnu.")
            return self._ajouter(donnees, nom or Path(urlparse(courant).path).stem,
                                 courant, format_)
        raise ValueError("Trop de redirections.")

    # -- operations ----------------------------------------------------
    def rechercher(self, terme="", format_=None, anime=None):
        terme = str(terme or "").casefold()
        resultat = []
        for entree in self._charger():
            if terme and terme not in (str(entree.get("nom", "")) + " " +
                                       str(entree.get("source", ""))).casefold():
                continue
            if format_ and entree.get("format") != format_:
                continue
            if anime is not None and bool(entree.get("anime")) != bool(anime):
                continue
            resultat.append(entree)
        return resultat

    def convertir(self, media_id, cible):
        cible = str(cible or "").lower()
        if cible not in FORMATS_CONVERSION:
            raise ValueError("Conversion prise en charge : gif, webp ou png (APNG).")
        entree = self.obtenir(media_id)
        if not entree:
            raise ValueError("Media introuvable.")
        if entree.get("format") == "mp4":
            raise ValueError("Conversion video non prise en charge : aucun decodeur "
                             "video n'est embarque.")
        if entree.get("format") == cible:
            raise ValueError("Le media est deja dans ce format.")
        try:
            from PIL import Image
        except ImportError:
            raise ValueError("Pillow est requis pour convertir les medias.") from None
        source = self.chemin(media_id)
        images = []
        durees = []
        try:
            with Image.open(source) as image:
                frames = int(getattr(image, "n_frames", 1) or 1)
                for index in range(frames):
                    image.seek(index)
                    image.load()
                    images.append(image.convert("RGBA" if cible != "jpg" else "RGB"))
                    durees.append(int(image.info.get("duration") or 80))
        except OSError as exc:
            raise ValueError(f"Decodage impossible : {exc}") from None
        sortie = self.originals / (
            f"{hashlib.sha256((media_id + cible).encode()).hexdigest()[:16]}"
            f"{EXTENSIONS[cible]}")
        try:
            if cible == "gif":
                images[0].save(sortie, save_all=True, append_images=images[1:],
                               duration=durees, loop=0, disposal=2, optimize=False)
            elif cible == "webp":
                images[0].save(sortie, format="WEBP", save_all=True,
                               append_images=images[1:], duration=durees, loop=0,
                               quality=90)
            else:
                images[0].save(sortie, format="PNG", save_all=len(images) > 1,
                               append_images=images[1:], duration=durees, loop=0)
        except (OSError, ValueError) as exc:
            sortie.unlink(missing_ok=True)
            raise ValueError(f"Conversion impossible : {exc}") from None
        donnees = sortie.read_bytes()
        resultat = self._ajouter(donnees, Path(entree["nom"]).stem, source, cible,
                                 conversion_de=media_id)
        sortie.unlink(missing_ok=True)
        return resultat

    def copier(self, media_id, destination, remplacer=False):
        source = self.chemin(media_id)
        destination = Path(destination)
        if destination.is_dir():
            destination = destination / source.name
        if destination.exists() and not remplacer:
            raise ValueError("Le fichier de destination existe deja.")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes())
        return destination

    def supprimer(self, media_id):
        entree = self.obtenir(media_id)
        if not entree:
            raise ValueError("Media introuvable.")
        chemin = self.root / entree["chemin"]
        chemin.unlink(missing_ok=True)
        entrees = [item for item in self._charger() if item.get("id") != media_id]
        self._ecrire(entrees)
        return entree


def publier_discord(api, channel_id, media_id, library, contenu=""):
    """Publie un media dans un salon ; retourne le message cree par l'API."""
    entree = library.obtenir(media_id)
    if not entree:
        raise ValueError("Media introuvable.")
    if entree.get("format") not in FORMATS_DISCORD:
        raise ValueError("Ce format ne peut pas etre publie sur Discord.")
    chemin = library.chemin(media_id)
    donnees = chemin.read_bytes()
    if len(donnees) > TAILLE_MAX:
        raise ValueError("Fichier superieur a la limite d'upload de 10 Mio.")
    return api.envoyer_fichier(str(channel_id), contenu or "", chemin.name, donnees,
                               MIME.get(entree["format"], "application/octet-stream"),
                               reason="LeakFr-Tools GIF Studio")
