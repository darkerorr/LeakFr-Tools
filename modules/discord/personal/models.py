"""Modeles de donnees du panel personnel Discord."""
import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True)
class Profil:
    id: str
    username: str
    nom_affichage: str
    locale: str
    mfa: bool
    avatar: str

    @property
    def libelle(self):
        return self.nom_affichage or self.username


@dataclass(frozen=True)
class ServeurResume:
    id: str
    nom: str
    proprietaire: bool
    permissions: int
    icone: str
    features: tuple


def _normaliser(texte):
    texte = unicodedata.normalize("NFKD", str(texte or "").casefold())
    return "".join(car for car in texte if not unicodedata.combining(car))


def parse_profil(donnees):
    """Valide et normalise la reponse ``/users/@me``."""
    if not isinstance(donnees, dict) or not donnees.get("id"):
        raise ValueError("Profil Discord invalide : identifiant absent.")
    return Profil(
        id=str(donnees["id"]),
        username=str(donnees.get("username") or "?"),
        nom_affichage=str(donnees.get("global_name") or ""),
        locale=str(donnees.get("locale") or "?"),
        mfa=bool(donnees.get("mfa_enabled")),
        avatar=str(donnees.get("avatar") or ""),
    )


def parse_serveur(donnees):
    if not isinstance(donnees, dict) or not donnees.get("id") or not donnees.get("name"):
        return None
    try:
        permissions = int(donnees.get("permissions") or 0)
    except (TypeError, ValueError):
        permissions = 0
    features = donnees.get("features")
    return ServeurResume(
        id=str(donnees["id"]),
        nom=str(donnees["name"]),
        proprietaire=bool(donnees.get("owner")),
        permissions=permissions,
        icone=str(donnees.get("icon") or ""),
        features=tuple(str(feature) for feature in features) if isinstance(features, list) else (),
    )


def parse_serveurs(donnees):
    if not isinstance(donnees, list):
        return []
    serveurs = (parse_serveur(element) for element in donnees)
    return [serveur for serveur in serveurs if serveur is not None]


def filtrer_serveurs(serveurs, requete):
    terme = _normaliser(requete).strip()
    if not terme:
        return list(serveurs)
    return [serveur for serveur in serveurs
            if terme in _normaliser(serveur.nom) or terme in serveur.id]


def trier_serveurs(serveurs, cle="nom", inverse=False):
    if cle == "id":
        return sorted(serveurs, key=lambda serveur: int(serveur.id), reverse=inverse)
    if cle == "permissions":
        return sorted(serveurs, key=lambda serveur: serveur.permissions, reverse=inverse)
    return sorted(serveurs, key=lambda serveur: _normaliser(serveur.nom), reverse=inverse)
