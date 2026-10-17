"""Execution d'un plan de clonage sur un serveur de destination.

Les creations passent par le moteur de taches commun (`core.tasks`) : file,
progression par action, annulation entre deux actions, erreurs partielles,
arret sur limite de debit et journal exploitable. Un element n'est compte
comme cree que si l'API a retourne un identifiant.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone

from core.tasks import Etape, MoteurTaches, Tache
from modules.discord.discord_api import DiscordAPIError, DiscordRateLimitError


def _maintenant():
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ResultatClonage:
    plan: object
    statut: str = "en_cours"
    crees: dict = field(default_factory=lambda: {"roles": [], "categories": [], "salons": []})
    ignores: list = field(default_factory=list)
    erreurs: list = field(default_factory=list)
    notes: list = field(default_factory=list)
    correspondances: dict = field(default_factory=lambda: {
        "roles": {}, "categories": {}, "salons": {}})
    debut: str = field(default_factory=_maintenant)
    fin: str = ""

    def compter(self):
        return {cle: len(valeur) for cle, valeur in self.crees.items()}

    def terminer(self):
        self.fin = _maintenant()
        if self.erreurs and self.crees["roles"] + self.crees["categories"] + self.crees["salons"]:
            self.statut = "partiel"
        elif self.erreurs:
            self.statut = "echec"
        else:
            self.statut = "reussi"
        return self

    def rapport(self):
        return {
            "statut": self.statut,
            "debut": self.debut,
            "fin": self.fin,
            "source": self.plan.manifeste.get("source_guild"),
            "destination": {
                "id": self.plan.guild_destination.get("id"),
                "name": self.plan.guild_destination.get("name"),
            },
            "options": vars(self.plan.options),
            "crees": {cle: list(valeur) for cle, valeur in self.crees.items()},
            "comptes": self.compter(),
            "ignores": list(self.ignores) + list(self.plan.ignores),
            "erreurs": list(self.erreurs),
            "notes": list(self.notes) + list(self.plan.avertissements),
            "correspondances": {
                cle: {source: cible for source, cible in valeur.items()
                      if not str(cible).startswith(("role:", "categorie:"))}
                for cle, valeur in self.correspondances.items()
            },
            "limitations": [
                "Les membres, messages et webhooks ne sont pas copies.",
                "Les surcharges de membre sont ignorees.",
                "Les positions exactes ne sont pas forcees : l'ordre relatif est "
                "recree par l'ordre de creation, sous la hierarchie du bot.",
            ],
        }


def _resoudre_destination(valeur, correspondances):
    valeur = str(valeur or "")
    if valeur.startswith("role:"):
        cible = correspondances["roles"].get(valeur.split(":", 1)[1])
        return None if not cible or cible.startswith("role:") else cible
    if valeur.startswith("categorie:"):
        cible = correspondances["categories"].get(valeur.split(":", 1)[1])
        return None if not cible or cible.startswith("categorie:") else cible
    return valeur or None


def _surcharges_resolues(payload, correspondances):
    surcharges = []
    ignorees = 0
    for surcharge in payload.get("permission_overwrites") or []:
        destination = _resoudre_destination(surcharge.get("id"), correspondances)
        if not destination:
            ignorees += 1
            continue
        surcharge = dict(surcharge)
        surcharge["id"] = destination
        surcharges.append(surcharge)
    payload = dict(payload)
    if surcharges:
        payload["permission_overwrites"] = surcharges
    else:
        payload.pop("permission_overwrites", None)
    return payload, ignorees


def _creer_action(api, plan, action, resultat):
    """Construit une etape reelle ; les erreurs remontent au moteur."""

    def operation():
        if action["kind"] == "role":
            cree = api.creer_role(plan.guild_destination["id"], action["payload"],
                                  reason="LeakFr-Tools clone de structure")
            identifiant = str((cree or {}).get("id") or "")
            if not identifiant:
                raise DiscordAPIError("Role cree sans identifiant retourne.")
            resultat.crees["roles"].append(action["name"])
            resultat.correspondances["roles"][action["source_id"]] = identifiant
            return
        if action["kind"] == "categorie":
            payload, ignorees = _surcharges_resolues(action["payload"],
                                                     resultat.correspondances)
            if ignorees:
                resultat.notes.append(
                    f"Categorie {action['name']} : {ignorees} surcharge(s) ignoree(s) "
                    "faute de cible mappee.")
            cree = api.creer_salon(plan.guild_destination["id"], payload,
                                   reason="LeakFr-Tools clone de structure")
            identifiant = str((cree or {}).get("id") or "")
            if not identifiant:
                raise DiscordAPIError("Categorie creee sans identifiant retourne.")
            resultat.crees["categories"].append(action["name"])
            resultat.correspondances["categories"][action["source_id"]] = identifiant
            return
        if action["kind"] == "salon":
            payload, ignorees = _surcharges_resolues(action["payload"],
                                                     resultat.correspondances)
            parent_source = action.get("parent_source_id")
            if parent_source:
                parent = resultat.correspondances["categories"].get(parent_source)
                if parent:
                    payload["parent_id"] = parent
                else:
                    payload.pop("parent_id", None)
                    resultat.notes.append(
                        f"Salon {action['name']} cree sans categorie : la categorie "
                        "source n'a pas ete creee.")
            if ignorees:
                resultat.notes.append(
                    f"Salon {action['name']} : {ignorees} surcharge(s) ignoree(s) "
                    "faute de cible mappee.")
            cree = api.creer_salon(plan.guild_destination["id"], payload,
                                   reason="LeakFr-Tools clone de structure")
            identifiant = str((cree or {}).get("id") or "")
            if not identifiant:
                raise DiscordAPIError("Salon cree sans identifiant retourne.")
            resultat.crees["salons"].append(action["name"])
            resultat.correspondances["salons"][action["source_id"]] = identifiant
            return
        raise ValueError(f"Action inconnue : {action['kind']}")

    def executer():
        try:
            operation()
        except DiscordRateLimitError:
            resultat.notes.append(
                "Arret propre : limite de debit Discord atteinte. Relancez plus "
                "tard ; les elements deja crees sont conserves.")
            raise

    return executer


def executer_plan(api, plan, progression=None, annulation=None,
                  max_erreurs_consecutives=3, journal=None):
    """Execute les creations du plan via le moteur de taches commun."""
    resultat = ResultatClonage(plan=plan)
    resultat.correspondances["roles"].update(plan.correspondances.get("roles") or {})
    resultat.correspondances["categories"].update(plan.correspondances.get("categories") or {})
    actions = plan.creations()
    if not actions:
        return resultat.terminer()

    def suivre(niveau, message):
        if niveau == "erreur":
            resultat.erreurs.append(message)
        if journal:
            journal(niveau, message)

    moteur = MoteurTaches(
        max_erreurs_consecutives=max_erreurs_consecutives,
        exceptions_arret=(DiscordRateLimitError,),
        annulation_externe=annulation,
    )
    etapes = [
        Etape(f"{action['kind']} {action['name']}",
              _creer_action(api, plan, action, resultat))
        for action in actions
    ]
    identifiant = (f"{plan.manifeste.get('source_guild', {}).get('id')}->"
                   f"{plan.guild_destination.get('id')}")
    moteur.ajouter(Tache(identifiant=identifiant, type="clone_structure",
                          description="Clonage de structure Discord",
                          etapes=etapes, destructive=True,
                          metadonnees={"actions": len(actions)}))
    resultat_tache = moteur.executer_suivante(progression=progression, journal=suivre)
    resultat.erreurs = list(resultat_tache.erreurs)
    resultat.statut = {
        "reussi": "reussi", "partiel": "partiel", "echec": "echec",
        "annule": "annule",
    }.get(resultat_tache.statut, "echec")
    resultat.fin = _maintenant()
    if resultat.statut == "annule":
        resultat.notes.append(
            f"Annulation demandee : {len(resultat_tache.etapes_ignorees)} creation(s) "
            "non executee(s).")
    resultat.ignores.extend(plan.ignores)
    return resultat
