"""Generateur de scripts de rapport systeme autonomes.

Le script produit ne depend d'aucun module du projet : les collecteurs et les
exporteurs testes ici sont recopies a l'identique via ``inspect.getsource``.
Aucune transmission reseau n'est generee.
"""
import inspect
import json
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

from rich.panel import Panel
from rich.table import Table

from core.common import BX, C_GOLD, console, demander, kv, ok, titre, warn
from modules.generators import build, transmission
from modules.generators.runtime import collectors, exporters

SECTIONS = {
    "systeme": {
        "titre": "Systeme d'exploitation",
        "description": "OS, version, build, architecture, hote, demarrage, langue, fuseau.",
        "sensible": False,
    },
    "materiel": {
        "titre": "Materiel",
        "description": "Processeur, coeurs, memoire, fabricant, modele, GPU detectes.",
        "sensible": False,
    },
    "disques": {
        "titre": "Stockage et volumes",
        "description": "Points de montage, capacite, espace libre et taux d'utilisation.",
        "sensible": False,
    },
    "reseau": {
        "titre": "Reseau",
        "description": "Interfaces locales, etat, adresses privees, passerelle et DNS.",
        "sensible": False,
    },
    "logiciels": {
        "titre": "Logiciels installes",
        "description": "Inventaire via le registre Windows ou dpkg, avec limite.",
        "sensible": False,
    },
    "dev": {
        "titre": "Environnement de developpement",
        "description": "Versions de Python, Git, pip, Node, GCC, .NET, PowerShell.",
        "sensible": False,
    },
    "peripheriques": {
        "titre": "Peripheriques",
        "description": "Compteurs de classes et liste des composants detectes.",
        "sensible": False,
    },
    "fichiers": {
        "titre": "Fichiers selectionnes",
        "description": "Inventaire limite avec taille, extension, date et SHA-256.",
        "sensible": True,
    },
    "session": {
        "titre": "Session et compte",
        "description": "Utilisateur, domaine, shell et dossier personnel (option explicite).",
        "sensible": True,
    },
    "empreinte": {
        "titre": "Empreinte machine (HWID)",
        "description": "Hash SHA-256 des identifiants locaux ; desactive par defaut.",
        "sensible": True,
    },
    "historique": {
        "titre": "Rapports precedents",
        "description": "Resume des exports JSON deja presents dans le dossier de sortie.",
        "sensible": False,
    },
}

ORDRE = tuple(SECTIONS)
NUMEROS = {str(index): cle for index, cle in enumerate(ORDRE, 1)}

PROFILS = {
    "minimal": ["systeme", "disques"],
    "standard": ["systeme", "materiel", "disques", "reseau"],
    "detaille": ["systeme", "materiel", "disques", "reseau", "logiciels", "dev",
                 "peripheriques"],
}

# "tout" ne selectionne que ces sections : les options sensibles ou couteuses
# (session, fichiers, empreinte, historique) restent explicites.
STANDARD = ("systeme", "materiel", "disques", "reseau", "logiciels", "dev",
            "peripheriques")
OPTIONNELLES = ("fichiers", "session", "empreinte", "historique")

FORMATS = {"json": "json", "markdown": "md", "html": "html"}

NOM_INTERDITS = set('<>:"/\\|?*')


def config_par_defaut():
    return {
        "nom_script": "rapport-machine.py",
        "nom_rapport": "Rapport machine",
        "dossier_sortie": "rapports",
        "profil": "standard",
        "sections": list(STANDARD),
        "formats": ["json", "markdown"],
        "fichiers": [],
        "extensions": [],
        "dossiers_exclus": [],
        "limite_fichiers": 200,
        "limite_logiciels": 100,
        "empreinte": False,
        "session_compte": False,
        "session_home": True,
        "details_erreurs": "complet",
        "mode_sortie": "fichier",
        "compilation": "aucune",
        "transmission": False,
    }


def valider_nom_script(nom):
    """Valide le nom du script et force l'extension .py."""
    nom = (nom or "").strip()
    if not nom:
        raise ValueError("nom de script vide")
    if any(caractere in NOM_INTERDITS for caractere in nom):
        raise ValueError("caractere interdit dans le nom (<>:\"/\\|?*)")
    chemin = Path(nom)
    if chemin.name in {"", ".", ".."} or nom.endswith((" ", ".")):
        raise ValueError("nom de script invalide")
    if chemin.suffix.lower() not in {".py", ".pyw"}:
        chemin = chemin.with_suffix(".py")
    return str(chemin)


def valider_dossier(chemin):
    """Verifie qu'un dossier existe ou peut etre cree et reste accessible."""
    chemin = (chemin or "").strip()
    if not chemin:
        raise ValueError("dossier de sortie vide")
    dossier = Path(chemin).expanduser()
    try:
        dossier.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ValueError(f"dossier inutilisable : {exc}") from None
    if not dossier.is_dir():
        raise ValueError("le chemin n'est pas un dossier")
    return dossier


def _slug(texte):
    texte = unicodedata.normalize("NFKD", str(texte)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", texte.lower()).strip("-") or "rapport"


def _source_fonction(fonction):
    return inspect.getsource(fonction).strip() + "\n"


def _dependances(cle):
    return {
        "materiel": ["_memoire"],
        "reseau": ["_interface_ipv4"],
        "logiciels": ["_valeur"],
    }.get(cle, [])


def _source_collecteurs(sections):
    morceaux = []
    for nom in collectors.HELPERS:
        morceaux.append(_source_fonction(getattr(collectors, nom)))
    for cle in sections:
        if cle not in collectors.COLLECTEURS:
            continue
        for dependance in _dependances(cle):
            morceaux.append(_source_fonction(getattr(collectors, dependance)))
        morceaux.append(_source_fonction(collectors.COLLECTEURS[cle][1]))
    return "\n".join(morceaux)


def _source_exporteurs(formats):
    morceaux = [f"LIBELLES_STATUT = {exporters.LIBELLES_STATUT!r}\n"]
    for nom in ("_ancre", "_valeur_lisible", "_table_lignes"):
        morceaux.append(_source_fonction(getattr(exporters, nom)))
    if "markdown" in formats:
        morceaux.append(_source_fonction(exporters._markdown_donnees))
        morceaux.append(_source_fonction(exporters.vers_markdown))
    if "html" in formats:
        morceaux.append("from html import escape as _echapper\n")
        morceaux.append(_source_fonction(exporters._html_donnees))
        morceaux.append(_source_fonction(exporters.vers_html))
    if "json" in formats:
        morceaux.append(_source_fonction(exporters.vers_json))
    return "\n".join(morceaux)


def _appels_collecteurs(config):
    limite_fichiers = int(config["limite_fichiers"])
    empreinte = bool(config["empreinte"])
    appels = {}
    for cle in config["sections"]:
        if cle not in collectors.COLLECTEURS:
            continue
        if cle == "fichiers":
            appels[cle] = (
                "collecter_fichiers("
                f"{config['fichiers']!r}, {config['extensions']!r}, {limite_fichiers}, "
                f"{empreinte}, {config['dossiers_exclus']!r})"
            )
        elif cle == "logiciels":
            appels[cle] = f"collecter_logiciels({int(config['limite_logiciels'])})"
        elif cle == "session":
            appels[cle] = (
                f"collecter_session({bool(config['session_compte'])}, "
                f"{bool(config['session_home'])})"
            )
        elif cle == "historique":
            appels[cle] = f"collecter_historique({config['dossier_sortie']!r}, 10)"
        elif cle in collectors.COLLECTEURS:
            appels[cle] = f"{collectors.COLLECTEURS[cle][1].__name__}()"
    return appels


def _titre_collecteur(cle):
    return collectors.COLLECTEURS[cle][0]


def construire_script(config):
    """Assemble un script autonome a partir de la configuration validee."""
    formats = [format for format in config["formats"] if format in FORMATS]
    if not formats:
        raise ValueError("aucun format d'export valide")
    sections = [cle for cle in config["sections"] if cle in collectors.COLLECTEURS]
    if not sections:
        raise ValueError("aucune section valide")
    appels = _appels_collecteurs(config)
    titres = {cle: _titre_collecteur(cle) for cle in sections}

    imports = (
        "#!/usr/bin/env python3\n"
        f'"""Rapport systeme autonome : {config["nom_rapport"]}.\n\n'
        "Genere par LeakFr-Tools. Bibliotheque standard uniquement : aucune\n"
        "transmission reseau n'est effectuee par ce script.\n"
        '"""\n'
        "import ctypes\nimport hashlib\nimport json\nimport locale\nimport os\n"
        "import platform\nimport shutil\nimport socket\nimport string\nimport struct\n"
        "import subprocess\nimport sys\nimport time\nimport unicodedata\nimport uuid\n"
        "from datetime import datetime, timezone\nfrom pathlib import Path\n\n\n"
    )

    dispatch = ["def collecter(cle):", "    try:"]
    for index, cle in enumerate(sections):
        mot = "if" if index == 0 else "elif"
        dispatch.append(f"        {mot} cle == {cle!r}:")
        dispatch.append(f"            return {appels[cle]}")
    dispatch.extend([
        "        return {'statut': 'indisponible', 'donnees': None, 'erreurs': []}",
        "    except Exception as exc:  # un collecteur ne casse jamais le rapport",
        "        return {'statut': 'erreur', 'donnees': None, 'erreurs': [{",
        "            'collecteur': cle, 'type': type(exc).__name__,",
        "            'message': str(exc), 'solution': ''}]}",
        "",
        "",
        f"TITRES = {titres!r}",
        "",
        "",
        "def construire_rapport():",
        "    debut = time.perf_counter()",
        "    sections = {}",
        "    for cle, titre in TITRES.items():",
        "        resultat = collecter(cle)",
        "        if not isinstance(resultat, dict) or 'statut' not in resultat:",
        "            resultat = {'statut': 'erreur', 'donnees': None, 'erreurs': []}",
        "        sections[cle] = {'titre': titre, 'statut': resultat['statut'],",
        "                         'donnees': resultat.get('donnees'),",
        "                         'erreurs': resultat.get('erreurs', [])}",
        "    statuts = [section['statut'] for section in sections.values()]",
        "    synthese = {",
        "        'sections_total': len(sections),",
        "        'ok': statuts.count('ok'),",
        "        'partiel': statuts.count('partiel'),",
        "        'indisponible': statuts.count('indisponible'),",
        "        'erreur': statuts.count('erreur'),",
        "        'statut': ('erreur' if statuts and statuts.count('erreur') == len(statuts)",
        "                   else 'partiel' if any(s != 'ok' for s in statuts) else 'ok'),",
        "        'duree_ms': round((time.perf_counter() - debut) * 1000, 1),",
        "    }",
        "    return {",
        "        'schema': 'leakfr.system-report.v1',",
        "        'id': str(uuid.uuid4()),",
        "        'nom': CONFIG['nom_rapport'],",
        "        'genere_le': datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds'),",
        "        'profil': CONFIG['profil'],",
        "        'plateforme': f'{platform.system()} {platform.release()} "
        "({platform.machine()})',",
        "        'synthese': synthese,",
        "        'sections': sections,",
        "    }",
        "",
        "",
        "SERIALISEURS = {",
    ])
    for format in formats:
        dispatch.append(f"    {format!r}: {getattr(exporters, 'vers_' + format).__name__},")
    dispatch.extend([
        "}",
        f"EXTENSIONS = { {format: FORMATS[format] for format in formats}!r}",
        "",
        "",
        "def nom_libre(dossier, base, extension):",
        "    cible = dossier / f'{base}.{extension}'",
        "    compteur = 1",
        "    while cible.exists():",
        "        cible = dossier / f'{base}-{compteur}.{extension}'",
        "        compteur += 1",
        "    return cible",
        "",
        "",
        "def ecrire_rapport(rapport):",
        "    dossier = Path(CONFIG['dossier_sortie']).expanduser()",
        "    dossier.mkdir(parents=True, exist_ok=True)",
        "    base = f\"{CONFIG['nom_fichier']}-{datetime.now().strftime('%Y%m%d-%H%M%S')}\"",
        "    chemins = []",
        "    for format in CONFIG['formats']:",
        "        try:",
        "            contenu = SERIALISEURS[format](rapport)",
        "            cible = nom_libre(dossier, base, EXTENSIONS[format])",
        "            cible.write_text(contenu, encoding='utf-8')",
        "            chemins.append(str(cible))",
        "        except Exception as exc:  # un format en echec ne bloque pas les autres",
        "            print(f'Format {format} impossible : {type(exc).__name__}: {exc}',",
        "                  file=sys.stderr)",
        "    return chemins",
        "",
        "",
        "def main():",
        "    rapport = construire_rapport()",
        "    synthese = rapport['synthese']",
        "    print(f\"{rapport['nom']} - {synthese['statut']} \"",
        "          f\"({synthese['sections_total']} sections, {synthese['duree_ms']} ms)\")",
        "    if CONFIG['mode_sortie'] in {'terminal', 'les_deux'}:",
        "        print()",
        "        if 'markdown' in SERIALISEURS:",
        "            print(SERIALISEURS['markdown'](rapport))",
        "        else:",
        "            print(SERIALISEURS[sorted(SERIALISEURS)[0]](rapport))",
        "    if CONFIG['mode_sortie'] in {'fichier', 'les_deux'}:",
        "        for chemin in ecrire_rapport(rapport):",
        "            print('Rapport ecrit :', chemin)",
        "    return 0",
        "",
        "",
        "if __name__ == '__main__':",
        "    raise SystemExit(main())",
        "",
    ])

    config_script = {
        "nom_rapport": config["nom_rapport"],
        "nom_fichier": _slug(config["nom_rapport"]),
        "profil": config["profil"],
        "formats": formats,
        "mode_sortie": config["mode_sortie"],
        "dossier_sortie": config["dossier_sortie"],
    }
    return (
        imports
        + f"CONFIG = {config_script!r}\n\n\n"
        + _source_collecteurs(sections)
        + "\n"
        + _source_exporteurs(formats)
        + "\n\n"
        + "\n".join(dispatch)
    )


def _libelles(sections):
    return ", ".join(SECTIONS[cle]["titre"] for cle in sections)


def _table_sections(sections):
    table = Table(box=BX, border_style=C_GOLD, header_style=f"bold {C_GOLD}")
    table.add_column("#", justify="right", width=3)
    table.add_column("Section", width=34)
    table.add_column("Sensible", justify="center", width=8)
    for numero, cle in NUMEROS.items():
        definition = SECTIONS[cle]
        marque = "incluse" if cle in sections else "-"
        table.add_row(numero, f"{definition['titre']} [{marque}]",
                      "oui" if definition["sensible"] else "non")
    console.print(table)


# --- Saisies centralisees -------------------------------------------------

def _saisie(label, defaut=""):
    """Affiche le defaut et l'applique si la reponse est vide."""
    if defaut:
        return demander(f"{label} (Entree = {defaut})", defaut)
    return demander(label)


def _oui_non(label, defaut=True):
    """Repete la question tant que la reponse n'est pas oui ou non."""
    defaut_txt = "oui" if defaut else "non"
    while True:
        reponse = _saisie(label, defaut_txt).strip().lower()
        if reponse in {"oui", "o", "y", "yes"}:
            return True
        if reponse in {"non", "n", "no"}:
            return False
        warn(f"Reponse attendue : oui ou non (recu : {reponse!r}).")


def _entier(label, defaut, minimum, maximum):
    """Valide un entier dans un intervalle, avec nouvelle demande sinon."""
    while True:
        brut = _saisie(label, str(defaut)).strip()
        try:
            valeur = int(brut)
        except ValueError:
            warn(f"{label} : nombre entier attendu (recu : {brut!r}).")
            continue
        if not minimum <= valeur <= maximum:
            warn(f"{label} : valeur attendue entre {minimum} et {maximum}.")
            continue
        return valeur


def _liste(label, defaut=""):
    """Liste separee par ';' ; les separateurs seuls valent une liste vide."""
    brut = _saisie(label, defaut)
    return [morceau.strip() for morceau in brut.split(";") if morceau.strip()]


def _choix_parmi(label, defaut, valeurs):
    while True:
        reponse = _saisie(label, defaut).strip().lower()
        if reponse in valeurs:
            return reponse
        warn(f"Choix attendu : {', '.join(valeurs)} (recu : {reponse!r}).")


def _choix_formats(config):
    while True:
        brut = _saisie("Formats (json markdown html)", " ".join(config["formats"]))
        selection = [partie.lower() for partie in brut.replace(",", " ").split() if partie]
        inconnus = [partie for partie in selection if partie not in FORMATS]
        if inconnus:
            warn(f"Format(s) inconnu(s) : {', '.join(inconnus)}")
            continue
        if not selection:
            warn("Selectionnez au moins un format.")
            continue
        config["formats"] = selection
        return config["formats"]


def _nom_libre(dossier, nom):
    """Retourne un chemin disponible en ajoutant un suffixe numerique."""
    base = Path(nom)
    candidat = Path(dossier) / base.name
    compteur = 1
    while candidat.exists():
        candidat = Path(dossier) / f"{base.stem}-{compteur}{base.suffix or '.py'}"
        compteur += 1
    return candidat


def _profil_pour(sections):
    ensemble = set(sections)
    if ensemble <= set(PROFILS["minimal"]):
        return "minimal"
    if ensemble >= set(PROFILS["detaille"]):
        return "detaille"
    return "standard"


def _ordonner(config):
    config["sections"] = [cle for cle in ORDRE if cle in config["sections"]]
    config["profil"] = _profil_pour(config["sections"])
    return config


def _options_sensibles(config):
    actives = []
    for cle in ("fichiers", "session", "empreinte"):
        if cle not in config["sections"]:
            continue
        if cle == "session":
            details = [nom for nom, actif in
                       (("compte", config["session_compte"]),
                        ("dossier personnel", config["session_home"])) if actif]
            actives.append("session" + (f" ({', '.join(details)})" if details else ""))
        elif cle == "empreinte":
            if config["empreinte"]:
                actives.append("HWID")
        else:
            actives.append(SECTIONS[cle]["titre"])
    return ", ".join(actives) or "aucune"


# --- Apercus --------------------------------------------------------------

def _apercu_court(config):
    texte = (
        f"Script    : {config['nom_script']}\n"
        f"Dossier   : {config['dossier_sortie']}\n"
        f"Categories: {_libelles(config['sections'])}\n"
        f"Sensible  : {_options_sensibles(config)}\n"
        f"Formats   : {', '.join(config['formats'])}\n"
        "Resultat  : script autonome + rapports horodates"
    )
    console.print(Panel(texte, title="Apercu", border_style=C_GOLD))


def _apercu_avance(config):
    _apercu_court(config)
    kv("Details", [
        ("Compilation", config.get("compilation", "aucune")),
        ("Sortie", config["mode_sortie"]),
        ("Limite fichiers", config["limite_fichiers"]),
        ("Limite logiciels", config["limite_logiciels"]),
    ], C_GOLD)


# --- Mode rapide ----------------------------------------------------------

def _mode_rapide(config):
    nom = valider_nom_script(_saisie("Nom du script", config["nom_script"]))
    dossier = valider_dossier(_saisie("Dossier de sortie", config["dossier_sortie"]))
    cible = _nom_libre(dossier, nom)
    if cible.name != Path(nom).name:
        console.print(f"[yellow]{Path(nom).name} existe deja : {cible.name} sera utilise.[/]")
    config.update({
        "nom_script": cible.name,
        "nom_rapport": f"Rapport {Path(nom).stem}",
        "dossier_sortie": str(dossier),
        "sections": list(STANDARD),
        "formats": ["json", "markdown"],
        "mode_sortie": "fichier",
    })
    _ordonner(config)
    _apercu_court(config)
    while True:
        reponse = _saisie("Generer (oui / configurer / transmettre / annuler)",
                          "oui").strip().lower()
        if reponse in {"oui", "o", "y"}:
            return _generer(config)
        if reponse in {"transmettre", "t"}:
            return _generer_puis_transmettre(config)
        if reponse in {"configurer", "avance", "c"}:
            return _mode_avance(config)
        if reponse in {"annuler", "a", "non", "n"}:
            warn("Generation annulee.")
            return None
        warn("Reponse attendue : oui, configurer, transmettre ou annuler.")


# --- Mode avance ----------------------------------------------------------

GROUPES = (
    ("sections", "Sections du rapport", "Basculer les sections une par une."),
    ("systeme", "Informations systeme", "OS, version, architecture, hote, demarrage."),
    ("materiel", "Materiel et stockage", "Processeur, memoire, disques, peripheriques."),
    ("logiciels", "Logiciels et developpement", "Inventaire logiciel et versions d'outils."),
    ("reseau", "Reseau", "Interfaces, adresses privees, passerelle, DNS."),
    ("fichiers", "Inventaire de fichiers", "Chemins choisis, extensions, limite, SHA-256."),
    ("session", "Session et identifiants", "Compte, dossier personnel et HWID."),
    ("sortie", "Formats et sortie", "JSON, Markdown, HTML, affichage, dossier."),
    ("compilation", "Compilation", "Generation seule, execution ou executable."),
    ("transmission", "Transmission", "Envoi manuel d'un rapport JSON existant."),
)


def _inclure(config, cle, libelle):
    actif = cle in config["sections"]
    if _oui_non(f"Inclure {libelle} ?", actif):
        if cle not in config["sections"]:
            config["sections"].append(cle)
        return True
    if cle in config["sections"]:
        config["sections"].remove(cle)
    return False


def _editer_sections(config):
    _table_sections(config["sections"])
    saisie = _saisie("Numeros a basculer ('tout' = standards, Entree = conserver)", "")
    if not saisie.strip():
        return
    if saisie.strip().lower() == "tout":
        config["sections"] = list(STANDARD)
        console.print("[dim]Sections standards seules ; options sensibles inchangees.[/]")
        return
    for morceau in saisie.replace(",", " ").split():
        if morceau not in NUMEROS:
            warn(f"Numero inconnu : {morceau}")
            continue
        cle = NUMEROS[morceau]
        if cle in config["sections"]:
            config["sections"].remove(cle)
        else:
            config["sections"].append(cle)


def _editer_systeme(config):
    _inclure(config, "systeme", "le systeme d'exploitation")


def _editer_materiel(config):
    _inclure(config, "materiel", "le materiel")
    _inclure(config, "disques", "le stockage et les volumes")
    _inclure(config, "peripheriques", "les peripheriques")


def _editer_logiciels(config):
    _inclure(config, "logiciels", "l'inventaire des logiciels")
    _inclure(config, "dev", "l'environnement de developpement")
    if "logiciels" in config["sections"]:
        config["limite_logiciels"] = _entier("Limite de logiciels listes",
                                             config["limite_logiciels"], 1, 2000)


def _editer_reseau(config):
    console.print(Panel(
        "Inclus : noms d'interfaces, etat, adresses IPv4 privees, adresse MAC,\n"
        "passerelle et serveurs DNS configures.\n"
        "Aucune adresse publique n'est recherchee et aucune connexion n'est ouverte.",
        title="Reseau - contenu", border_style=C_GOLD))
    _inclure(config, "reseau", "la section reseau")


def _editer_fichiers(config):
    if not _inclure(config, "fichiers", "l'inventaire de fichiers"):
        return
    config["fichiers"] = _liste("Fichiers/dossiers a inventorier (';' separateur)",
                                ";".join(config["fichiers"]))
    brut = _saisie("Extensions autorisees (ex: .py .txt ; vide = toutes)",
                   " ".join(config["extensions"]))
    config["extensions"] = [partie if partie.startswith(".") else f".{partie}"
                            for partie in brut.split() if partie]
    config["limite_fichiers"] = _entier("Limite de fichiers analyses",
                                        config["limite_fichiers"], 1, 5000)
    config["dossiers_exclus"] = _liste("Dossiers exclus (';' separateur)",
                                       ";".join(config["dossiers_exclus"]))


def _editer_session(config):
    if _inclure(config, "session", "les informations de session"):
        config["session_compte"] = _oui_non("Inclure le nom de compte et le domaine ?",
                                            config["session_compte"])
        config["session_home"] = _oui_non("Inclure le dossier personnel ?",
                                          config["session_home"])
    config["empreinte"] = _inclure(config, "empreinte", "l'empreinte machine (HWID)")


def _editer_sortie(config):
    _choix_formats(config)
    config["dossier_sortie"] = str(valider_dossier(
        _saisie("Dossier de sortie", config["dossier_sortie"])))
    config["mode_sortie"] = _choix_parmi("Mode de sortie (terminal/fichier/les_deux)",
                                         config["mode_sortie"],
                                         ("terminal", "fichier", "les_deux"))


def _editer_transmission(config):
    config["transmission"] = _oui_non(
        "Proposer la transmission manuelle apres generation ?",
        config.get("transmission", False))
    if config["transmission"]:
        console.print("[dim]Le rapport reste ecrit localement ; l'envoi se fait apres "
                      "apercu, expurgation et confirmation.[/]")


def _editer_compilation(config):
    kv("Compilation", [
        ("1", "Generer le fichier Python uniquement"),
        ("2", "Generer puis executer le script"),
        ("3", "Generer puis compiler en executable"),
        ("4", "Generer, tester localement, puis proposer la compilation"),
    ], C_GOLD)
    choix = _choix_parmi("Choix", "1", ("1", "2", "3", "4"))
    config["compilation"] = {"1": "aucune", "2": "executer", "3": "compiler",
                            "4": "tester"}[choix]


EDITEURS = {
    "sections": _editer_sections,
    "systeme": _editer_systeme,
    "materiel": _editer_materiel,
    "logiciels": _editer_logiciels,
    "reseau": _editer_reseau,
    "fichiers": _editer_fichiers,
    "session": _editer_session,
    "sortie": _editer_sortie,
    "compilation": _editer_compilation,
    "transmission": _editer_transmission,
}


def _mode_avance(config):
    while True:
        console.print("[bold]Categories a configurer :[/]")
        for numero, (cle, titre, description) in enumerate(GROUPES, 1):
            console.print(f"  [bold]{numero}.[/] {titre} — [dim]{description}[/]")
        saisie = _saisie("Categorie a modifier (Entree = terminer)", "").strip()
        if not saisie:
            break
        if not saisie.isdigit() or not 1 <= int(saisie) <= len(GROUPES):
            warn(f"Choix attendu entre 1 et {len(GROUPES)}.")
            continue
        _ordonner(config)
        EDITEURS[GROUPES[int(saisie) - 1][0]](config)
        _ordonner(config)

    _apercu_avance(config)
    while True:
        reponse = _saisie("Generer (oui / retour / annuler)", "oui").strip().lower()
        if reponse in {"oui", "o", "y"}:
            if config.get("transmission"):
                return _generer_puis_transmettre(config)
            return _generer(config)
        if reponse in {"retour", "r"}:
            return _mode_avance(config)
        if reponse in {"annuler", "a", "non", "n"}:
            warn("Generation annulee.")
            return None
        warn("Reponse attendue : oui, retour ou annuler.")


# --- Generation et verification ------------------------------------------

def verifier_generation(chemin, config):
    """Verifie existence, contenu, syntaxe et coherence des collecteurs."""
    chemin = Path(chemin)
    erreurs = []
    if not chemin.is_file():
        return {"ok": False, "chemin": str(chemin.resolve()), "erreurs": ["fichier absent"]}
    contenu = chemin.read_text(encoding="utf-8")
    if not contenu.strip():
        erreurs.append("fichier vide")
    try:
        compile(contenu, str(chemin), "exec")
    except SyntaxError as exc:
        erreurs.append(f"syntaxe invalide ligne {exc.lineno} : {exc.msg}")
    for cle in config["sections"]:
        nom = collectors.COLLECTEURS[cle][1].__name__
        if f"def {nom}(" not in contenu:
            erreurs.append(f"collecteur manquant : {nom}")
    for cle in OPTIONNELLES:
        if cle in config["sections"]:
            continue
        nom = collectors.COLLECTEURS[cle][1].__name__
        if f"def {nom}(" in contenu:
            erreurs.append(f"collecteur desactive present : {nom}")
    return {"ok": not erreurs, "chemin": str(chemin.resolve()), "erreurs": erreurs}


def _generer(config):
    _ordonner(config)
    try:
        source = construire_script(config)
    except ValueError as exc:
        warn(f"Generation impossible : {exc}")
        return None
    nom = Path(config["nom_script"]).expanduser()
    chemin = nom if nom.parent not in {Path("."), Path("")} else \
        Path(config["dossier_sortie"]).expanduser() / nom.name
    if chemin.exists():
        if not _oui_non(f"{chemin} existe deja. Ecraser ?", False):
            alternatif = _nom_libre(chemin.parent, chemin.name)
            console.print(f"[yellow]Nom alternatif retenu : {alternatif}[/]")
            chemin = alternatif
            config["nom_script"] = str(alternatif)
    try:
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_text(source, encoding="utf-8")
    except OSError as exc:
        warn(f"Ecriture impossible : {exc}")
        return None

    resultat = verifier_generation(chemin, config)
    if not resultat["ok"]:
        for erreur in resultat["erreurs"]:
            warn(erreur)
        warn(f"Script incomplet : {resultat['chemin']}")
        return resultat

    kv("Script genere", [
        ("Chemin", resultat["chemin"]),
        ("Sections", len(config["sections"])),
        ("Formats", ", ".join(config["formats"])),
    ], C_GOLD)

    mode = config.get("compilation", "aucune")
    if mode in {"executer", "tester"}:
        _executer_script(chemin.resolve())
    if mode == "compiler":
        _compiler_script(chemin.resolve())
    elif mode == "tester" and _oui_non("Compiler maintenant en executable ?", False):
        _compiler_script(chemin.resolve())
    return resultat


def _generer_puis_transmettre(config):
    """Genere le script, produit un rapport local si besoin, puis propose l'envoi."""
    if config.get("compilation", "aucune") == "aucune":
        config["compilation"] = "executer"
    resultat = _generer(config)
    if resultat and resultat.get("ok"):
        transmission.transmettre_rapport(config["dossier_sortie"])
    return resultat


def _executer_script(chemin):
    console.print(f"[dim]$ {sys.executable} {chemin}[/]")
    resultat = subprocess.run([sys.executable, str(chemin)], check=False)
    if resultat.returncode == 0:
        ok("Script execute sans erreur.")
    else:
        warn(f"Le script a retourne le code {resultat.returncode}.")
    return resultat.returncode


def _compiler_script(chemin):
    if not build.executable_pyinstaller():
        warn("PyInstaller n'est pas installe.")
        console.print(f"Installation proposee : {build.commande_installation()}",
                      markup=False, style="shell.text")
        if not _oui_non("Installer PyInstaller maintenant (via pip) ?", False):
            return None
        installation = subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"],
                                      check=False)
        if installation.returncode != 0:
            warn("Installation impossible : compilation abandonnee.")
            return None
    nom = _saisie("Nom de l'executable", Path(chemin).stem)
    dossier = _saisie("Dossier de destination", str(Path(chemin).parent / "dist"))
    try:
        resultat = build.compiler(chemin, nom=nom, dossier=dossier)
    except ValueError as exc:
        warn(str(exc))
        return None
    if resultat["ok"]:
        ok(f"Executable produit : {resultat['chemin']}")
    else:
        warn(resultat["erreur"])
        if resultat["sortie"]:
            console.print(resultat["sortie"][-1500:], markup=False, style="dim")
    return resultat


def generer_script():
    """Point d'entree : mode rapide par defaut, mode avance accessible."""
    titre("GENERATEUR DE RAPPORTS SYSTEME", C_GOLD)
    console.print("[dim]Mode rapide : deux questions suffisent. "
                  "Aucune transmission reseau n'est generee.[/]\n")
    return _mode_rapide(config_par_defaut())
