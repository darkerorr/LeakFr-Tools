"""Stockage local du Profile Studio.

Ce module ne contacte jamais Discord et ne modifie aucun compte. Il
prepare des images, des textes et des variantes, puis conserve l'historique
des sauvegardes locales. Toute application reelle reste manuelle.
"""
import hashlib
import json
import os
import re
import unicodedata
import uuid
from datetime import datetime, timezone
from pathlib import Path

from core.config import DATA_DIR

TAILLE_MAX_IMAGE =8 * 1024 * 1024
FORMATS_IMAGES = {"png", "jpg", "webp", "gif"}
DIMENSIONS ={"avatar": (512, 512), "banner":(960, 540)}
CHAMPS_TEXTE = {
    "display_name": (32, "Nom affiche"),
    "bio": (190, "Biographie"),
    'status_text': (128, 'Texte de statut'),
}
MAX_HISTORIQUE = 100


def maintenant():
    return datetime.now(timezone.utc).isoformat()


def detecter_format(donnees):
    if not donnees:
        return None
    if donnees[:6] in (b'GIF87a', b'GIF89a'):
        return "gif"
    if donnees[:8] == b"\x89PNG\r\n\x1a\n":
        return 'png'
    if donnees[:4] == b"RIFF" and donnees[8:12] == b"WEBP":
        return "webp"
    if donnees[:3] == b'\xff\xd8\xff':
        return "jpg"
    return None


def _slug(texte, maximum=48):
    texte = unicodedata.normalize('NFKD', str(texte or 'profil')).encode(
        "ascii", "ignore").decode("ascii")
    texte= re.sub(r"[^a-zA-Z0-9_-]+", "-", texte).strip("-").lower()
    return (texte or 'profil')[:maximum]


class ProfileStore:
    """Bibliotheque d'images preparees, variantes et historique local."""

    def __init__(self, root=None):
        self.root= Path(root or Path(DATA_DIR) / "profile_studio")
        self.images_dir=self.root / "images"
        self.prepared_dir = self.root / 'prepared'
        self.index_path = self.root / "images.json"
        self.configs_path = self.root / "configs.json"
        self.history_path = self.root / 'history.json'
        self.images_dir.mkdir(parents=True, exist_ok=True)
        self.prepared_dir.mkdir(parents=True, exist_ok=True)

    def _lire(self, path, defaut):
        try:
            donnees= json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return defaut
        return donnees if isinstance(donnees, type(defaut)) else defaut

    def _ecrire(self, path, donnees):
        self.root.mkdir(parents=True, exist_ok=True)
        temporaire = path.with_name(path.name + ".tmp")
        temporaire.write_text(json.dumps(donnees, ensure_ascii=False, indent=2) + '\n',
                              encoding="utf-8")
        os.replace(temporaire, path)

    def images(self, kind=None):
        images =self._lire(self.index_path, [])
        return [image for image in images if kind is None or image.get("kind") == kind]

    def image(self, image_id):
        for image in self.images():
            if str(image.get("id")) == str(image_id):
                return image
        return None

    def chemin_image(self, image_id):
        image= self.image(image_id)
        if not image:
            raise ValueError('Image introuvable dans la bibliotheque.')
        chemin = self.root / image["chemin"]
        if not chemin.is_file():
            raise ValueError('Fichier image manquant.')
        return chemin

    def importer_image(self, chemin, kind='avatar', nom=None):
        kind= str(kind or "avatar")
        if kind not in DIMENSIONS:
            raise ValueError("Type d'image inconnu (avatar ou banner).")
        chemin = Path(chemin)
        try:
            if chemin.stat().st_size > TAILLE_MAX_IMAGE:
                raise ValueError("Image superieure a 8 Mio.")
            donnees= chemin.read_bytes()
        except OSError as exc:
            raise ValueError(f"Image illisible : {exc}") from None
        format_ = detecter_format(donnees)
        if format_ not in FORMATS_IMAGES:
            raise ValueError("Format d'image non reconnu (PNG, JPEG, WebP ou GIF).")
        try:
            from PIL import Image, UnidentifiedImageError
        except ImportError:
            raise ValueError("Pillow est requis pour importer des images.") from None
        empreinte = hashlib.sha256(donnees).hexdigest()
        for existant in self.images():
            if existant.get("sha256") == empreinte and existant.get("kind") ==kind:
                existant = dict(existant)
                existant["doublon"] = True
                return existant
        identifiant = empreinte[:16]
        destination =self.images_dir / f"{identifiant}.{format_}"
        if not destination.is_file():
            destination.write_bytes(donnees)
        try:
            with Image.open(destination) as image:
                largeur, hauteur = image.size
                images= int(getattr(image, "n_frames", 1) or 1)
                anime = images > 1
        except (UnidentifiedImageError, OSError) as exc:
            destination.unlink(missing_ok=True)
            raise ValueError(f"Image invalide : {exc}") from None
        entree = {
            "id": identifiant,
            "sha256": empreinte,
            'kind': kind,
            "nom": _slug(nom or chemin.stem) + "." + format_,
            "format": format_,
            'largeur': largeur,
            "hauteur": hauteur,
            "images":images,
            'anime': anime,
            "taille": len(donnees),
            "source": str(chemin),
            'importe_le':maintenant(),
            "chemin":destination.relative_to(self.root).as_posix(),
        }
        images_index = self.images()
        images_index.append(entree)
        self._ecrire(self.index_path, images_index)
        entree['doublon']= False
        return entree

    def recadrer(self, image_id, kind=None, boite=None, taille=None):
        """Recadre puis redimensionne vers les dimensions Discord recommandees.

        ``boite`` vaut ``(gauche, haut, largeur, hauteur)`` en pixels de
        l'image source. Sans boite, un carre central (avatar) ou toute
        l'image (banniere) est utilise. Le resultat est une image fixe.
        """
        image = self.image(image_id)
        if not image:
            raise ValueError('Image introuvable.')
        kind = kind or image.get("kind") or "avatar"
        if kind not in DIMENSIONS:
            raise ValueError("Type d'image inconnu.")
        try:
            from PIL import Image
        except ImportError:
            raise ValueError("Pillow est requis pour recadrer.") from None
        source =self.chemin_image(image_id)
        with Image.open(source) as originale:
            originale.load()
            largeur, hauteur= originale.size
            if boite is None:
                if kind == "avatar":
                    cote =min(largeur, hauteur)
                    boite = ((largeur - cote) // 2, (hauteur - cote) // 2, cote, cote)
                else:
                    boite =(0, 0, largeur, hauteur)
            if (not isinstance(boite, (tuple, list)) or len(boite) != 4
                    or not all(isinstance(valeur, int) for valeur in boite)):
                raise ValueError("Boite de recadrage invalide.")
            gauche, haut, largeur_boite, hauteur_boite = boite
            if (gauche < 0 or haut < 0 or largeur_boite <=0 or hauteur_boite <= 0
                    or gauche + largeur_boite > largeur
                    or haut + hauteur_boite > hauteur):
                raise ValueError("La boite de recadrage depasse l'image.")
            cadre = originale.crop((gauche, haut, gauche + largeur_boite,
                                    haut + hauteur_boite)).convert('RGBA')
            dimensions =taille or DIMENSIONS[kind]
            if (not isinstance(dimensions, (tuple, list)) or len(dimensions)!=2
                    or not all(isinstance(valeur, int) and valeur > 0
                               for valeur in dimensions)):
                raise ValueError("Dimensions de sortie invalides.")
            if dimensions[0] > 2048 or dimensions[1] > 2048:
                raise ValueError("Dimensions de sortie limitees a 2048 px.")
            preparee = cadre.resize(dimensions, Image.LANCZOS)
            identifiant= uuid.uuid4().hex[:12]
            destination = self.prepared_dir / f"{identifiant}_{kind}.png"
            preparee.save(destination, format="PNG")
        entree = {
            "id": identifiant,
            "kind":kind,
            'nom': f"{Path(image["nom"]).stem}_{kind}.png",
            "format":"png",
            "largeur":dimensions[0],
            'hauteur': dimensions[1],
            "source_image": image_id,
            "recadre_le":maintenant(),
            'chemin':destination.relative_to(self.root).as_posix(),
            "fixe": True,
        }
        index= self.images()
        index.append(entree)
        self._ecrire(self.index_path, index)
        return entree

    @staticmethod
    def valider_texte(donnees):
        resultat= {}
        for champ, (maximum, libelle) in CHAMPS_TEXTE.items():
            valeur= str(donnees.get(champ) or "").strip()
            if len(valeur) > maximum:
                raise ValueError(f"{libelle} limite a {maximum} caracteres.")
            resultat[champ] = valeur
        return resultat

    def configs(self):
        return self._lire(self.configs_path, [])

    def config(self, config_id):
        for config in self.configs():
            if str(config.get('id')) == str(config_id):
                return config
        return None

    def sauvegarder_config(self, nom, donnees):
        nom = str(nom or "").strip()
        if not nom or len(nom) > 60:
            raise ValueError("Nom de variante obligatoire (60 caracteres maximum).")
        textes =self.valider_texte(donnees)
        avatar = donnees.get('avatar_id')
        banniere =donnees.get("banner_id")
        for image_id, kind, libelle in ((avatar, "avatar", "avatar"),
                                         (banniere, 'banner', 'banniere')):
            if image_id:
                image = self.image(image_id)
                if not image:
                    raise ValueError(f"Image de {libelle} introuvable.")
        configs = self.configs()
        existante= next((item for item in configs
                          if str(item.get("nom")).casefold() == nom.casefold()), None)
        entree={
            'id': (existante or {}).get('id') or uuid.uuid4().hex[:12],
            "nom": nom,
            "avatar_id": avatar or None,
            'banner_id':banniere or None,
            **textes,
            "modifie_le": maintenant(),
            'applique_sur_discord': False,
        }
        if existante:
            configs= [item for item in configs if item.get('id') != existante['id']]
        configs.append(entree)
        self._ecrire(self.configs_path, configs)
        historique = self._lire(self.history_path, [])
        historique.append({"config_id":entree["id"], "nom": nom,
                           "date": entree["modifie_le"], "action": "sauvegarde",
                           'contenu': {cle: entree.get(cle) for cle in
                                       ("avatar_id", "banner_id", "display_name",
                                        "bio", "status_text")}})
        self._ecrire(self.history_path, historique[-MAX_HISTORIQUE:])
        return entree

    def supprimer_config(self, config_id):
        configs =self.configs()
        cible= next((item for item in configs if str(item.get("id")) ==str(config_id)), None)
        if not cible:
            raise ValueError("Variante introuvable.")
        self._ecrire(self.configs_path,
                     [item for item in configs if item.get('id') != cible['id']])
        return cible

    def historique(self, limite=50):
        return self._lire(self.history_path, [])[-max(1, int(limite)):]

    def comparer(self, id_a, id_b):
        a= self.config(id_a)
        b = self.config(id_b)
        if not a or not b:
            raise ValueError("Variante introuvable.")
        champs = ("display_name", "bio", "status_text", "avatar_id", "banner_id")
        differences= {}
        for champ in champs:
            if a.get(champ) !=b.get(champ):
                differences[champ] = {'a': a.get(champ), 'b': b.get(champ)}
        return {"a": a["nom"], "b": b["nom"], "differences": differences}

    def exporter_config(self, config_id, path):
        config = self.config(config_id)
        if not config:
            raise ValueError('Variante introuvable.')
        chemin= Path(path)
        chemin.parent.mkdir(parents=True, exist_ok=True)
        donnees = dict(config)
        donnees["format"] ="leakfr-profile-variant"
        donnees["version"] = 1
        donnees['avertissement'] = (
            "Configuration preparee localement : elle n'a pas ete appliquee a Discord.")
        chemin.write_text(json.dumps(donnees, ensure_ascii=False, indent=2) + "\n",
                          encoding='utf-8')
        return chemin

    def importer_config(self, path):
        chemin = Path(path)
        try:
            donnees = json.loads(chemin.read_text(encoding='utf-8'))
        except (OSError, ValueError) as exc:
            raise ValueError(f"Configuration illisible : {exc}") from None
        if not isinstance(donnees, dict) or donnees.get('format') != 'leakfr-profile-variant':
            raise ValueError("Format de configuration non reconnu.")
        return self.sauvegarder_config(donnees.get("nom") or "Importee", donnees)
