"""Controles reels executes avant l'ouverture du menu LEAKFR.

Chaque controle retourne un :class:`Verification` portant son statut et un
detail mesure. Aucune valeur n'est inventee : un outil absent est signale
absent, une version illisible est dite inconnue, et un echec critique n'est
jamais presente comme un succes.

Les sondes externes se limitent a des commandes de version documentees,
lancees avec ``shell=False``, une sortie capturee et un delai maximal. Aucun
scan reseau, aucune connexion distante et aucune ecriture hors du repertoire
de donnees du projet ne sont effectues.
"""
import importlib.util
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from concurrent.futures import TimeoutError as FuturesTimeout
from dataclasses import dataclass, replace
from pathlib import Path

from core.compat import OUTILS_EXTERNES, systeme_reel
from core.config import DATA_DIR
from core.environment import detecter_environnement, est_termux, libelle_environnement

STATUTS_REUSSITE= frozenset({"OK", "OPTIONAL", "UNKNOWN"})
STATUTS_AVERTISSEMENT =frozenset({'WARN', 'MISSING'})

LIBELLES_STATUT ={
    'PENDING': 'EN ATTENTE',
    "RUNNING": "EN COURS",
    "OK": "OK",
    'WARN': 'ATTENTION',
    "ERROR": "ERREUR",
    "OPTIONAL": "OPTIONNEL",
    'UNKNOWN': 'INCONNU',
    "MISSING": "ABSENT",
    "SKIPPED":"INTERROMPU",
}

ARGUMENTS_VERSION = {
    'ip': ['-V'],
    "nmcli":["--version"],
    "iwlist":["--version"],
    'traceroute': ['--version'],
    "arp":["--version"],
    "ifconfig": ["--version"],
    'netstat': ['--version'],
    "tracert": None,
    "netsh": None,
    'ipconfig':None,
    "route": None,
}

DEPENDANCES_OBLIGATOIRES = ("rich", "requests")
DEPENDANCES_FACULTATIVES= {
    'pygments': 'Pygments / coloration syntaxique',
    "PIL": "Pillow / GIF Studio",
    "discord": "discord.py / gateway",
}
NOMS_DEPENDANCES ={"pygments": "Pygments", "PIL":"Pillow", "discord": "discord.py"}


@dataclass
class Verification:
    """Resultat d'un controle de demarrage."""

    nom: str
    categorie: str
    statut: str ="PENDING"
    detail: str = ""
    critique: bool = False

    @property
    def ok(self):
        return self.statut in STATUTS_REUSSITE

    @property
    def terminee(self):
        return self.statut not in {"PENDING", "RUNNING"}

    @property
    def libelle(self):
        return LIBELLES_STATUT.get(self.statut, self.statut)


@dataclass(frozen=True)
class Controle:
    """Un controle : nom affiche, categorie et fonction sans argument."""

    nom: str
    categorie: str
    fonction: object
    critique:bool = False



def verifier_python():
    version =platform.python_version()
    ok=sys.version_info >=(3, 9)
    return Verification(
        'Python', 'Environnement', 'OK' if ok else 'ERROR',
        version if ok else f"{version} · 3.9+ requis", critique=not ok)


def verifier_environnement():
    try:
        detection = detecter_environnement()
        label =libelle_environnement(detection.get("cle"))
        statut = "OK"
        detail = label
    except Exception:
        statut, detail = "WARN", "détection indisponible"
    return Verification('Environnement', 'Environnement', statut, detail)


def verifier_systeme():
    try:
        systeme=platform.system() or "inconnu"
        version = platform.release() or '?'
        detail = f"{systeme} {version}"
        if est_termux():
            detail += ' · Termux'
        return Verification("Système", "Environnement", "OK", detail[:48])
    except Exception:
        return Verification('Système', 'Environnement', 'UNKNOWN',
                            "plateforme illisible")


def verifier_terminal():
    try:
        from core.common import MODE_TEXTE, UNICODE, console
        encodage = (console.encoding or "ascii").upper()
        couleurs =getattr(console, "color_system", None)
        if MODE_TEXTE:
            return Verification("Terminal", "Environnement", "OPTIONAL",
                                f"{encodage} · mode texte")
        if not UNICODE:
            return Verification("Terminal", "Environnement", "OPTIONAL",
                                f"{encodage} · rendu ASCII")
        detail = f"{encodage} · {couleurs or "sans couleur"}"
        return Verification("Terminal", "Environnement", "OK", detail)
    except Exception:
        return Verification('Terminal', 'Environnement', 'UNKNOWN',
                            "capacités non vérifiables")


def _module_disponible(nom):
    try:
        return importlib.util.find_spec(nom) is not None
    except (ImportError, ValueError, AttributeError, ModuleNotFoundError):
        return False


def verifier_dependances():
    manquants = [nom for nom in DEPENDANCES_OBLIGATOIRES
                 if not _module_disponible(nom)]
    optionnels= [nom for nom in DEPENDANCES_FACULTATIVES
                  if _module_disponible(nom)]
    total = len(DEPENDANCES_OBLIGATOIRES) + len(DEPENDANCES_FACULTATIVES)
    presents= (len(DEPENDANCES_OBLIGATOIRES) - len(manquants)) + len(optionnels)
    detail = f"{presents}/{total} modules Python"
    if manquants:
        return Verification("Dépendances", "Framework", "ERROR",
                            'manque : ' + ', '.join(manquants), critique=True)
    absents = [NOMS_DEPENDANCES.get(nom, nom) for nom in DEPENDANCES_FACULTATIVES
               if nom not in optionnels]
    if absents:
        detail += " · optionnels absents : " + ", ".join(absents)
    return Verification("Dépendances", "Framework", "OK", detail)


def verifier_catalogue(outils=None, noms=None, catalogue=None, routes=None):
    """Integrite du catalogue : outils appelables, noms uniques et routes."""
    if outils is None or noms is None or catalogue is None or routes is None:
        from core.catalogue import CATALOGUE, FLAT, _ROUTE_PAR_NOM
        if outils is None:
            outils = [entree["fn"] for entree in FLAT if entree["fn"]]
        if noms is None:
            noms= [nom for _cat, _couleur, groupes in CATALOGUE
                    for nom, _desc, _fn in groupes]
        catalogue = CATALOGUE if catalogue is None else catalogue
        routes= _ROUTE_PAR_NOM if routes is None else routes
    integre = (bool(outils) and all(callable(fn) for fn in outils)
               and len(set(noms)) == len(noms)
               and all(nom in routes for nom in noms))
    detail = (f"{len(outils)} outils / {len(catalogue)} categories"
              if integre else "catalogue incomplet")
    return Verification('Catalogue', 'Framework', 'OK' if integre else 'ERROR',
                        detail, critique=True)


def _module_reel(fonction):
    """Module d'origine, en traversant l'enveloppe de protection."""
    cible = getattr(fonction, '__wrapped__', fonction)
    return getattr(cible, "__module__", "") or getattr(fonction, "__module__", "")


def verifier_modules(outils=None):
    if outils is None:
        from core.catalogue import FLAT
        outils = [entree["fn"] for entree in FLAT if entree["fn"]]
    modules =sorted({_module_reel(fn) for fn in outils} - {""})
    indisponibles = []
    for nom_module in modules:
        try:
            disponible = importlib.util.find_spec(nom_module) is not None
        except (ImportError, ValueError, AttributeError, ModuleNotFoundError):
            disponible = False
        if not disponible:
            indisponibles.append(nom_module)
    if not modules:
        return Verification('Modules', 'Framework', 'ERROR',
                            "aucun module detecte", critique=True)
    if indisponibles:
        return Verification(
            "Modules", "Framework", "ERROR",
            f"{len(indisponibles)} module(s) indisponible(s)", critique=True)
    return Verification('Modules', 'Framework', 'OK',
                        f"{len(modules)} modules importables")


def verifier_theme(config=None):
    try:
        from core.theme import SLOTS, nommer_theme, palette_active
        config = config or {}
        palette =palette_active(config)
        invalides = [slot for slot in SLOTS
                     if not str(palette.get(slot) or "").startswith("#")]
        if invalides:
            return Verification('Thème', 'Framework', 'WARN',
                                f"{len(invalides)} couleur(s) invalide(s)")
        cle = (config.get("apparence") or {}).get("theme_actif", "original")
        return Verification('Thème', 'Framework', 'OK', nommer_theme(cle))
    except Exception:
        return Verification("Thème", "Framework", "WARN", "thème illisible")


def verifier_donnees(dossier=None):
    """Teste l'ecriture reelle dans data/ puis supprime le fichier cree."""
    dossier = Path(dossier or DATA_DIR)
    chemin = None
    try:
        dossier.mkdir(parents=True, exist_ok=True)
        descripteur, nom = tempfile.mkstemp(
            prefix='.leakfr_demarrage_', suffix='.tmp', dir=str(dossier))
        chemin = Path(nom)
        with os.fdopen(descripteur, "w", encoding="utf-8") as flux:
            flux.write('leakfr')
        contenu = chemin.read_text(encoding="utf-8")
        if contenu !="leakfr":
            return Verification('Données', 'Stockage', 'WARN',
                                "écriture incomplète")
        return Verification("Données", "Stockage", "OK",
                            f"écriture OK ({dossier.name}/)")
    except OSError as exc:
        return Verification("Données", "Stockage", "WARN",
                            f"écriture impossible ({type(exc).__name__})")
    finally:
        if chemin is not None:
            try:
                chemin.unlink()
            except OSError:
                pass


def binaires_attendus(systeme=None):
    """Binaires documentes pour le systeme reel (aucune invention)."""
    systeme = systeme or systeme_reel()
    binaires =set()
    for regle in OUTILS_EXTERNES.values():
        specifique=regle.get(systeme) or regle.get("linux") or {}
        if specifique.get('disponible') is False:
            continue
        binaires.update(specifique.get("binaires") or [])
        for chemin in specifique.get('chemins') or []:
            binaires.add(Path(chemin).name)
    return sorted(nom for nom in binaires if nom)


def _version_courte(sortie):
    """Extrait un numero de version lisible, sans inventer de valeur."""
    correspondance = re.search(r"\d+(?:\.\d+)+(?:[-\w.+]*)", sortie or "")
    return correspondance.group(0)[:24] if correspondance else None


def sonder_binaire(nom, arguments=None, timeout=1.2):
    """Detecte un binaire et, si possible, sa version reelle.

    Retourne ``{"present", "chemin", "version", "detail", "statut"}``. La
    commande est toujours une liste, sans shell, avec sortie capturee et
    delai maximal. Une version illisible n'est jamais inventee.
    """
    chemin= shutil.which(nom)
    if not chemin:
        return {"present": False, "chemin":None, "version": None,
                'statut': 'MISSING', 'detail': 'introuvable'}
    if arguments is None:
        return {"present":True, "chemin": chemin, "version":None,
                'statut': 'UNKNOWN', 'detail': 'FOUND — VERSION UNKNOWN'}
    try:
        resultat =subprocess.run(
            [chemin, *arguments], capture_output=True, text=True, timeout=timeout,
            shell=False, stdin=subprocess.DEVNULL, encoding="utf-8",
            errors="replace", check=False)
    except subprocess.TimeoutExpired:
        return {"present": True, "chemin": chemin, "version": None,
                "statut":"UNKNOWN", "detail": "délai de version dépassé"}
    except (OSError, ValueError):
        return {"present": True, "chemin":chemin, "version": None,
                "statut": "UNKNOWN", "detail": "FOUND — VERSION UNKNOWN"}
    sortie =((resultat.stdout or '') + '\n' + (resultat.stderr or '')).strip()
    version = _version_courte(sortie) if resultat.returncode ==0 else None
    if not version:
        return {'present': True, 'chemin':chemin, 'version': None,
                "statut": "UNKNOWN", "detail": "FOUND — VERSION UNKNOWN"}
    return {"present": True, "chemin": chemin, "version": version,
            'statut': 'OK', 'detail': version}


def collecter_outils_externes(timeout_sonde=1.2, timeout_global=2.5, systeme=None):
    """Sonde les binaires documentes, sans jamais bloquer le demarrage."""
    attendus = binaires_attendus(systeme)
    if not attendus:
        return Verification("Outils externes", "Compatibilité", "OPTIONAL",
                            "aucun binaire requis ici")
    trouves =[nom for nom in attendus if shutil.which(nom)]
    manquants = [nom for nom in attendus if nom not in trouves]
    sondes= {}
    if trouves:
        with ThreadPoolExecutor(max_workers=min(4, len(trouves))) as pool:
            futurs={
                pool.submit(sonder_binaire, nom,
                            ARGUMENTS_VERSION.get(nom), timeout_sonde):nom
                for nom in trouves
            }
            try:
                for futur in as_completed(futurs, timeout=timeout_global):
                    try:
                        sondes[futurs[futur]] = futur.result()
                    except Exception:
                        sondes[futurs[futur]] = {
                            "present": True, "version":None,
                            "statut": "UNKNOWN", "detail": "FOUND — VERSION UNKNOWN"}
            except FuturesTimeout:
                pass
    detail_presents =[]
    connues = []
    for nom in trouves:
        version = sondes.get(nom, {}).get("version")
        if version:
            connues.append(f"{nom} {version}")
            detail_presents.append(f"{nom} {version}")
        else:
            detail_presents.append(f"{nom} (v. inconnue)")
    if not trouves:
        return Verification('Outils externes', 'Compatibilité', 'WARN',
                            f"0/{len(attendus)} présents · absents : "
                            + ", ".join(manquants))
    resume =f"{len(trouves)}/{len(attendus)} · " + ', '.join(detail_presents)
    if manquants:
        resume += " · absents : " + ", ".join(manquants)
    if not connues:
        return Verification("Outils externes", "Compatibilité", "UNKNOWN",
                            resume + " · versions inconnues")
    return Verification('Outils externes', 'Compatibilité', 'OK', resume)


def controles_par_defaut(config=None):
    """Liste ordonnee des controles reellement executes au demarrage."""
    config = config or {}
    return [
        Controle("Python", "Environnement", verifier_python, True),
        Controle("Système", "Environnement", verifier_systeme),
        Controle('Terminal', 'Environnement', verifier_terminal),
        Controle("Dépendances", "Framework", verifier_dependances, True),
        Controle("Catalogue", "Framework", verifier_catalogue, True),
        Controle('Modules', 'Framework', verifier_modules, True),
        Controle("Thème", "Framework", lambda:verifier_theme(config)),
        Controle("Données", "Stockage", verifier_donnees),
        Controle('Outils externes', 'Compatibilité', collecter_outils_externes),
    ]



class Orchestrateur:
    """Execute les controles en arriere-plan et expose leur etat reel.

    La progression exposee est le rapport ``controles termines / total`` :
    elle n'avance qu'apres le resultat effectif d'un controle. Le rendu peut
    tourner a 20 images/s sans jamais mentir sur l'avancement technique.
    """

    def __init__(self, controles, delai_max=None):
        self.controles = list(controles)
        self.delai_max = delai_max
        self._etats = [
            Verification(controle.nom, controle.categorie, "PENDING",
                         'en attente', controle.critique)
            for controle in self.controles
        ]
        self._verrou = threading.Lock()
        self._fin= threading.Event()
        self._annulation = threading.Event()
        self._debut= time.monotonic()
        self._fil =None

    def _ecrire(self, index, resultat):
        with self._verrou:
            if self._annulation.is_set() and resultat.statut in STATUTS_REUSSITE:
                return
            self._etats[index] = resultat

    def etats(self):
        with self._verrou:
            return list(self._etats)

    @property
    def total(self):
        return len(self.controles)

    @property
    def termines(self):
        return sum(1 for etat in self.etats()
                   if etat.terminee and etat.statut!="SKIPPED")

    @property
    def progression(self):
        return self.termines / self.total if self.total else 1.0

    @property
    def ecoule(self):
        return max(0.0, time.monotonic() - self._debut)

    @property
    def termine(self):
        return self._fin.is_set()

    @property
    def en_cours(self):
        return next((etat.nom for etat in self.etats()
                     if etat.statut == 'RUNNING'), '')

    def executer(self):
        """Execute les controles dans le thread courant (tests inclus)."""
        try:
            for index, controle in enumerate(self.controles):
                if self._annulation.is_set():
                    self._ecrire(index, Verification(
                        controle.nom, controle.categorie, "SKIPPED",
                        'délai dépassé', controle.critique))
                    continue
                self._ecrire(index, Verification(
                    controle.nom, controle.categorie, 'RUNNING',
                    "vérification…", controle.critique))
                try:
                    resultat=controle.fonction()
                except Exception as exc:
                    resultat = Verification(
                        controle.nom, controle.categorie, 'ERROR',
                        f"échec interne ({type(exc).__name__})", controle.critique)
                if not isinstance(resultat, Verification):
                    resultat = Verification(
                        controle.nom, controle.categorie, "UNKNOWN",
                        "résultat non exploitable", controle.critique)
                if not resultat.detail:
                    resultat= replace(resultat, detail=resultat.libelle)
                if self._annulation.is_set():
                    continue
                self._ecrire(index, replace(resultat, nom=controle.nom,
                                            categorie=controle.categorie,
                                            critique=controle.critique))
        finally:
            self._fin.set()
        return self.etats()

    def lancer(self):
        if self._fil is None and not self._fin.is_set():
            self._fil = threading.Thread(target=self.executer,
                                         name="leakfr-startup", daemon=True)
            self._fil.start()
        return self

    def attendre(self, timeout=None):
        return self._fin.wait(timeout)

    def interrompre(self, detail='délai de vérification dépassé'):
        """Marque les controles restants comme non executes (honnete)."""
        self._annulation.set()
        with self._verrou:
            for index, etat in enumerate(self._etats):
                if etat.statut in {"PENDING", "RUNNING"}:
                    self._etats[index] = replace(
                        etat, statut="SKIPPED", detail=detail)
        self._fin.set()


def resume_verifications(resultats):
    """Bilan global fonde sur les statuts reels, jamais sur une animation."""
    resultats =list(resultats or [])
    erreurs = [r for r in resultats if r.statut=="ERROR"]
    critiques= [r for r in erreurs if r.critique]
    avertissements =[r for r in resultats if r.statut in STATUTS_AVERTISSEMENT]
    interrompus= [r for r in resultats if r.statut == "SKIPPED"]
    if critiques:
        niveau, label = "CRITIQUE", "ERREUR CRITIQUE"
    elif erreurs or avertissements or interrompus:
        niveau, label ='PARTIEL', 'PARTIELLEMENT PRÊT'
    else:
        niveau, label= "PRET", "PRÊT"
    return {
        "niveau": niveau,
        "label": label,
        'total':len(resultats),
        "ok": sum(1 for r in resultats if r.statut == "OK"),
        "optionnels": sum(1 for r in resultats if r.statut == "OPTIONAL"),
        'erreurs': len(erreurs),
        "avertissements":len(avertissements),
        "inconnus": sum(1 for r in resultats if r.statut == "UNKNOWN"),
        'interrompus':sum(1 for r in resultats if r.statut == 'SKIPPED'),
    }
