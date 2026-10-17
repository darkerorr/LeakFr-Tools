"""Moteur d'execution commun aux operations longues.

Le moteur ne connait ni Discord ni l'interface : il execute une suite
d'etapes, expose une progression reelle, permet l'annulation entre deux
etapes et conserve un journal JSONL sans secret. Les taches sont mises en
file et une signature identique ne peut pas etre empilee deux fois.
"""
import json
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

STATUT_EN_ATTENTE = "en_attente"
STATUT_EN_COURS = "en_cours"
STATUT_REUSSI = "reussi"
STATUT_PARTIEL = "partiel"
STATUT_ANNULE = "annule"
STATUT_ECHEC = "echec"


def _maintenant():
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Etape:
    """Une unite de travail verifiable.

    ``obligatoire`` interrompt la tache si l'etape echoue. Une etape non
    obligatoire peut echouer sans empecher la suite : le resultat devient
    alors ``partiel``.
    """

    libelle: str
    action: object
    obligatoire: bool = False

    def __post_init__(self):
        if not callable(self.action):
            raise TypeError("L'action d'une etape doit etre appelable.")
        if not str(self.libelle or "").strip():
            raise ValueError("Une etape doit avoir un libelle.")


@dataclass
class Tache:
    """Description d'une operation executable par le moteur."""

    identifiant: str
    type: str
    description: str
    etapes: list
    signature: str = ""
    destructive: bool = False
    metadonnees: dict = field(default_factory=dict)

    def __post_init__(self):
        if not str(self.identifiant or "").strip():
            raise ValueError("Identifiant de tache obligatoire.")
        self.etapes = list(self.etapes or [])
        if not self.etapes:
            raise ValueError("Une tache doit contenir au moins une etape.")
        if not all(isinstance(etape, Etape) for etape in self.etapes):
            raise TypeError("Les etapes doivent etre des instances de Etape.")
        if not self.signature:
            self.signature = f"{self.type}:{self.identifiant}"


@dataclass
class ResultatTache:
    tache: Tache
    statut: str = STATUT_EN_ATTENTE
    etapes_reussies: list = field(default_factory=list)
    erreurs: list = field(default_factory=list)
    etapes_ignorees: list = field(default_factory=list)
    debut: str = ""
    fin: str = ""
    annulee: bool = False

    def duree_secondes(self):
        if not self.debut or not self.fin:
            return 0.0
        try:
            debut = datetime.fromisoformat(self.debut)
            fin = datetime.fromisoformat(self.fin)
        except ValueError:
            return 0.0
        return max(0.0, (fin - debut).total_seconds())

    def to_dict(self):
        return {
            "identifiant": self.tache.identifiant,
            "type": self.tache.type,
            "description": self.tache.description,
            "signature": self.tache.signature,
            "destructive": self.tache.destructive,
            "statut": self.statut,
            "debut": self.debut,
            "fin": self.fin,
            "duree_secondes": round(self.duree_secondes(), 3),
            "etapes_reussies": list(self.etapes_reussies),
            "etapes_ignorees": list(self.etapes_ignorees),
            "erreurs": list(self.erreurs),
            "annulee": self.annulee,
            "metadonnees": dict(self.tache.metadonnees),
        }

    def resume(self):
        total = len(self.tache.etapes)
        return (f"{self.statut} : {len(self.etapes_reussies)}/{total} etape(s) reussie(s), "
                f"{len(self.erreurs)} erreur(s), {len(self.etapes_ignorees)} ignoree(s)")


class MoteurTaches:
    """File FIFO synchrone, testable sans thread ni interface.

    Les callbacks ``progression`` et ``journal`` sont appeles pendant
    l'execution. ``journal`` recoit ``(niveau, message)`` ; les secrets
    doivent avoir ete retires par l'appelant avant de construire les
    messages.
    """

    def __init__(self, journal_path=None, max_erreurs_consecutives=3,
                 redact=None, horloge=_maintenant, sleep=time.sleep,
                 exceptions_arret=(), annulation_externe=None):
        self._file = deque()
        self._signatures = set()
        self._en_cours = None
        self._annulation = threading.Event()
        self.exceptions_arret = tuple(exceptions_arret or ())
        self._annulation_externe = annulation_externe
        self.journal_path = Path(journal_path) if journal_path else None
        self.max_erreurs_consecutives = max(1, int(max_erreurs_consecutives))
        self._redact = redact or (lambda texte: str(texte))
        self._horloge = horloge
        self._sleep = sleep
        self.resultats = []

    # ------------------------------------------------------------------
    # File et annulation
    # ------------------------------------------------------------------
    @property
    def taille_file(self):
        return len(self._file)

    @property
    def en_cours(self):
        return self._en_cours

    def ajouter(self, tache):
        """Ajoute une tache ; refuse un doublon deja en file ou en cours."""
        if not isinstance(tache, Tache):
            raise TypeError("Une tache doit etre une instance de Tache.")
        if tache.signature in self._signatures:
            return False
        self._signatures.add(tache.signature)
        self._file.append(tache)
        return True

    def annuler(self):
        """Demande l'arret de la tache courante entre deux etapes."""
        self._annulation.set()

    def executer_suivante(self, progression=None, journal=None):
        """Execute la prochaine tache et retourne son resultat, ou None."""
        if self._en_cours is not None:
            raise RuntimeError("Une tache est deja en cours d'execution.")
        if not self._file:
            return None
        tache = self._file.popleft()
        self._en_cours = tache
        self._annulation.clear()
        resultat = self._executer(tache, progression, journal)
        self._signatures.discard(tache.signature)
        self._en_cours = None
        self.resultats.append(resultat)
        self._journaliser_resultat(resultat)
        return resultat

    def executer_file(self, progression=None, journal=None):
        """Execute toute la file dans l'ordre et retourne les resultats."""
        resultats = []
        while self._file:
            resultat = self.executer_suivante(progression, journal)
            if resultat is not None:
                resultats.append(resultat)
            if self._annulation.is_set():
                break
        return resultats

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------
    def _executer(self, tache, progression, journal):
        resultat = ResultatTache(tache=tache, statut=STATUT_EN_COURS,
                                 debut=self._horloge())
        total = len(tache.etapes)
        echecs_consecutifs = 0
        arret_force = False

        for index, etape in enumerate(tache.etapes, start=1):
            externe = (self._annulation_externe is not None
                       and self._annulation_externe())
            if self._annulation.is_set() or externe:
                resultat.annulee = True
                resultat.etapes_ignorees.extend(
                    fin.libelle for fin in tache.etapes[index - 1:])
                break
            if progression:
                progression(index, total, etape.libelle)
            if journal:
                journal("info", f"Etape {index}/{total} : {etape.libelle}")
            try:
                etape.action()
            except Exception as exc:  # noqa: BLE001 - le moteur doit tout rapporter
                message = self._redact(f"{etape.libelle} : {type(exc).__name__} - {exc}")
                resultat.erreurs.append(message)
                echecs_consecutifs += 1
                if journal:
                    journal("erreur", message)
                if self.exceptions_arret and isinstance(exc, self.exceptions_arret):
                    arret_force = True
                    resultat.etapes_ignorees.extend(
                        fin.libelle for fin in tache.etapes[index:])
                    break
                if etape.obligatoire:
                    resultat.statut = STATUT_ECHEC
                    resultat.etapes_ignorees.extend(
                        fin.libelle for fin in tache.etapes[index:])
                    break
                if echecs_consecutifs >= self.max_erreurs_consecutives:
                    resultat.statut = STATUT_ECHEC
                    resultat.erreurs.append(
                        f"Arret apres {echecs_consecutifs} erreurs consecutives.")
                    resultat.etapes_ignorees.extend(
                        fin.libelle for fin in tache.etapes[index:])
                    if journal:
                        journal("erreur", "Arret de securite apres erreurs repetees.")
                    break
            else:
                echecs_consecutifs = 0
                resultat.etapes_reussies.append(etape.libelle)
                if journal:
                    journal("ok", f"Termine : {etape.libelle}")

        resultat.fin = self._horloge()
        if resultat.annulee:
            resultat.statut = STATUT_ANNULE
        elif resultat.statut == STATUT_ECHEC:
            if arret_force and resultat.etapes_reussies:
                resultat.statut = STATUT_PARTIEL
        else:
            resultat.statut = STATUT_PARTIEL if resultat.erreurs else STATUT_REUSSI
        return resultat

    # ------------------------------------------------------------------
    # Journal
    # ------------------------------------------------------------------
    def _journaliser_resultat(self, resultat):
        if not self.journal_path:
            return
        try:
            self.journal_path.parent.mkdir(parents=True, exist_ok=True)
            ligne = json.dumps(resultat.to_dict(), ensure_ascii=False)
            with self.journal_path.open("a", encoding="utf-8") as fichier:
                fichier.write(ligne + "\n")
        except OSError:
            pass

    def lire_journal(self, limite=50):
        """Relit les derniers resultats enregistres (liste vide si absent)."""
        if not self.journal_path or not self.journal_path.is_file():
            return []
        entrees = []
        try:
            for ligne in self.journal_path.read_text(encoding="utf-8").splitlines():
                try:
                    entrees.append(json.loads(ligne))
                except ValueError:
                    continue
        except OSError:
            return []
        return entrees[-max(1, int(limite)):]
