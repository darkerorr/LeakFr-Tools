"""Preferences, modeles et historique local du panel personnel.

Aucun jeton OAuth2 ni secret client n'est ecrit ici : les cles sensibles sont
supprimees avant sauvegarde, et les details d'historique sont rediges.
"""
from datetime import datetime, timezone
from pathlib import Path

from core.config import DATA_DIR
from modules.discord.discord_api import redact
from modules.discord.local_store import charger_json, ecrire_json
from modules.discord.personal.errors import StorageError

CHEMIN_DEFAUT= Path(DATA_DIR) / "discord_personal.json"
CLES_INTERDITES =('token', 'secret', 'password', 'authorization')


def _assainir(valeur):
    if isinstance(valeur, dict):
        propre={}
        for cle, contenu in valeur.items():
            if any(motif in str(cle).casefold() for motif in CLES_INTERDITES):
                continue
            propre[str(cle)]= _assainir(contenu)
        return propre
    if isinstance(valeur, list):
        return [_assainir(element) for element in valeur]
    return valeur


class PersonalStore:
    """Petit magasin JSON, tolerant aux fichiers absents ou corrompus."""

    def __init__(self, path=None):
        self.path = Path(path or CHEMIN_DEFAUT)
        self._donnees = self._charger()

    def _charger(self):
        donnees =charger_json(self.path, {})
        if not isinstance(donnees, dict):
            donnees = {}
        return {
            "preferences": _assainir(donnees.get("preferences") or {}),
            "templates":[modele for modele in donnees.get("templates") or []
                          if isinstance(modele, dict) and modele.get('nom')
                          and modele.get("contenu")],
            "history":[{"timestamp":entree.get("timestamp"),
                         'action': redact(entree.get('action')),
                         "detail":redact(entree.get("detail"))}
                        for entree in donnees.get("history") or []
                        if isinstance(entree, dict)][-200:],
        }

    def _sauvegarder(self):
        try:
            ecrire_json(self.path, _assainir(self._donnees))
        except OSError as exc:
            raise StorageError(f"Ecriture locale impossible : {exc}") from None

    def preference(self, cle, defaut=None):
        return self._donnees["preferences"].get(cle, defaut)

    def definir_preference(self, cle, valeur):
        self._donnees["preferences"][str(cle)] = _assainir(valeur)
        self._sauvegarder()

    def modeles(self):
        return list(self._donnees["templates"])

    def ajouter_modele(self, nom, contenu):
        nom = (nom or "").strip()
        contenu = (contenu or "").strip()
        if not nom or not contenu:
            raise ValueError("Nom et contenu obligatoires.")
        if len(contenu) > 2000:
            raise ValueError('Un message Discord est limite a 2000 caracteres.')
        self._donnees["templates"] = [modele for modele in self.modeles()
                                      if modele["nom"]!= nom]
        self._donnees['templates'].append({'nom': nom[:60], 'contenu': contenu})
        self._donnees["templates"] = self._donnees["templates"][-50:]
        self._sauvegarder()

    def supprimer_modele(self, nom):
        avant = len(self.modeles())
        self._donnees['templates'] = [modele for modele in self.modeles()
                                      if modele["nom"] != nom]
        if len(self.modeles()) == avant:
            return False
        self._sauvegarder()
        return True

    def enregistrer(self, action, detail="", secrets=()):
        self._donnees['history'].append({
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "action": redact(action, secrets)[:120],
            'detail': redact(detail, secrets)[:300],
        })
        self._donnees["history"] = self._donnees["history"][-200:]
        self._sauvegarder()

    def historique(self, limite=25):
        return list(reversed(self._donnees['history']))[:max(1, int(limite))]
