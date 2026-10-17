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

from rich.prompt import Confirm
from rich.table import Table

from core.common import BX, C_GOLD, console, demander, kv, ok, titre, warn
from modules.generators import build
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
        "sensible": True,
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

FORMATS = {"json": "json", "markdown": "md", "html": "html"}

NOM_INTERDITS = set('<>:"/\\|?*')


def config_par_defaut():
    return {
        "nom_script": "rapport-machine.py",
        "nom_rapport": "Rapport machine",
        "dossier_sortie": str(Path.cwd() / "rapports"),
        "profil": "standard",
        "sections": list(PROFILS["standard"]),
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


def _table_sections(sections):
    table = Table(box=BX, border_style=C_GOLD, header_style=f"bold {C_GOLD}")
    table.add_column("#", justify="right")
    table.add_column("Section")
    table.add_column("Description")
    table.add_column("Sensible", justify="center")
    for numero, cle in NUMEROS.items():
        definition = SECTIONS[cle]
        table.add_row(numero, definition["titre"], definition["description"],
                      "oui" if definition["sensible"] else "non")
    console.print(table)


def _etape_a(config):
    config["nom_script"] = valider_nom_script(
        demander("Nom du script Python", config["nom_script"]))
    config["nom_rapport"] = demander("Nom du rapport", config["nom_rapport"]).strip() \
        or config["nom_rapport"]
    formats = demander("Formats (json markdown html)", " ".join(config["formats"]))
    selection = [partie.lower() for partie in formats.replace(",", " ").split()]
    inconnus = [partie for partie in selection if partie not in FORMATS]
    if inconnus:
        raise ValueError(f"format(s) inconnu(s) : {', '.join(inconnus)}")
    if not selection:
        raise ValueError("aucun format selectionne")
    config["formats"] = selection
    config["dossier_sortie"] = str(valider_dossier(
        demander("Repertoire de sortie", config["dossier_sortie"])))
    profil = demander("Profil (minimal/standard/detaille)", config["profil"]).lower()
    if profil not in PROFILS:
        raise ValueError("profil inconnu : choisissez minimal, standard ou detaille")
    config["profil"] = profil
    config["sections"] = list(PROFILS[profil])
    return config


def _etape_b(config):
    while True:
        _table_sections(config["sections"])
        actuelles = " ".join(numero for numero, cle in NUMEROS.items()
                             if cle in config["sections"])
        saisie = demander("Sections a inclure (numeros, 'tout', vide = conserve)",
                          actuelles).strip().lower()
        if saisie == "tout":
            config["sections"] = list(ORDRE)
        elif saisie:
            demandes = [partie for partie in saisie.replace(",", " ").split() if partie]
            inconnus = [partie for partie in demandes if partie not in NUMEROS]
            if inconnus:
                warn(f"Numero(s) inconnu(s) : {', '.join(inconnus)}")
                continue
            config["sections"] = [NUMEROS[partie] for partie in demandes]
        if not config["sections"]:
            warn("Selectionnez au moins une section.")
            continue
        console.print("[bold]Selection :[/] " + ", ".join(
            SECTIONS[cle]["titre"] for cle in config["sections"]))
        if Confirm.ask("Valider cette selection ?", default=True):
            return config


def _etape_c(config):
    if "fichiers" in config["sections"]:
        chemins = demander("Fichiers/dossiers a inventorier (separes par ';', vide = aucun)",
                           ";".join(config["fichiers"]))
        config["fichiers"] = [partie.strip() for partie in chemins.split(";") if partie.strip()]
        extensions = demander("Extensions autorisees (ex: .py .txt, vide = toutes)",
                              " ".join(config["extensions"]))
        config["extensions"] = [partie if partie.startswith(".")
                                else f".{partie}" for partie in extensions.split()]
        config["limite_fichiers"] = _entier("Limite de fichiers analyses",
                                            config["limite_fichiers"], 1, 5000)
        exclusions = demander("Dossiers exclus (separes par ';', vide = aucun)",
                              ";".join(config["dossiers_exclus"]))
        config["dossiers_exclus"] = [partie.strip() for partie in exclusions.split(";")
                                     if partie.strip()]
    if "logiciels" in config["sections"]:
        config["limite_logiciels"] = _entier("Limite de logiciels listes",
                                             config["limite_logiciels"], 1, 2000)
    if "session" in config["sections"]:
        config["session_compte"] = Confirm.ask(
            "Inclure le nom de compte et le domaine ?", default=config["session_compte"])
        config["session_home"] = Confirm.ask(
            "Inclure le dossier personnel ?", default=config["session_home"])
    if "empreinte" in config["sections"]:
        config["empreinte"] = Confirm.ask(
            "Calculer l'empreinte machine (HWID) ?", default=config["empreinte"])
    config["details_erreurs"] = demander("Detail des erreurs (complet/resume)",
                                         config["details_erreurs"]).lower()
    if config["details_erreurs"] not in {"complet", "resume"}:
        raise ValueError("detail des erreurs : complet ou resume")
    mode = demander("Mode de sortie (terminal/fichier/les_deux)",
                    config["mode_sortie"]).lower()
    if mode not in {"terminal", "fichier", "les_deux"}:
        raise ValueError("mode de sortie : terminal, fichier ou les_deux")
    config["mode_sortie"] = mode
    return config


def _entier(libelle, defaut, minimum, maximum):
    brut = demander(libelle, str(defaut))
    try:
        valeur = int(brut)
    except ValueError:
        raise ValueError(f"{libelle} : nombre entier attendu") from None
    if not minimum <= valeur <= maximum:
        raise ValueError(f"{libelle} : entre {minimum} et {maximum}")
    return valeur


def _recapitulatif(config):
    kv("Recapitulatif", [
        ("Script", config["nom_script"]),
        ("Rapport", config["nom_rapport"]),
        ("Profil", config["profil"]),
        ("Sections", ", ".join(SECTIONS[cle]["titre"] for cle in config["sections"])),
        ("Champs sensibles", ", ".join(SECTIONS[cle]["titre"] for cle in config["sections"]
                                        if SECTIONS[cle]["sensible"]) or "aucun"),
        ("Formats", ", ".join(config["formats"])),
        ("Sortie", config["mode_sortie"]),
        ("Dossier", config["dossier_sortie"]),
        ("Transmission", "locale uniquement (aucun envoi genere)"),
    ], C_GOLD)


def _choisir_compilation(config):
    kv("Compilation", [
        ("1", "Generer le fichier Python uniquement"),
        ("2", "Generer puis executer le script"),
        ("3", "Generer puis compiler en executable"),
        ("4", "Generer, tester localement, puis proposer la compilation"),
    ], C_GOLD)
    choix = demander("Choix", "1").strip()
    modes = {"1": "aucune", "2": "executer", "3": "compiler", "4": "tester"}
    if choix not in modes:
        raise ValueError("choix de compilation invalide (1 a 4)")
    config["compilation"] = modes[choix]
    return config


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
        if not Confirm.ask("Installer PyInstaller maintenant (via pip) ?", default=False):
            return None
        installation = subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"],
                                      check=False)
        if installation.returncode != 0:
            warn("Installation impossible : compilation abandonnee.")
            return None
    nom = demander("Nom de l'executable", Path(chemin).stem)
    dossier = demander("Dossier de destination", str(Path(chemin).parent / "dist"))
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


def _finaliser(config):
    try:
        source = construire_script(config)
    except ValueError as exc:
        warn(str(exc))
        return
    chemin = Path(config["nom_script"]).expanduser()
    if chemin.exists() and not Confirm.ask(f"{chemin} existe deja. Ecraser ?", default=False):
        warn("Generation annulee.")
        return
    try:
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_text(source, encoding="utf-8")
    except OSError as exc:
        warn(f"Impossible d'ecrire le script : {exc}")
        return
    kv("Script genere", [
        ("Fichier", str(chemin.resolve())),
        ("Lignes", len(source.splitlines())),
        ("Sections", len(config["sections"])),
        ("Formats", ", ".join(config["formats"])),
        ("Reseau", "aucun envoi genere"),
    ], C_GOLD)

    mode = config.get("compilation", "aucune")
    if mode in {"executer", "tester"}:
        _executer_script(chemin.resolve())
    if mode == "compiler":
        _compiler_script(chemin.resolve())
    elif mode == "tester" and Confirm.ask("Compiler maintenant en executable ?", default=False):
        _compiler_script(chemin.resolve())
    ok("Termine.")


def generer_script():
    """Parcours complet : configuration, selection, apercu, generation."""
    titre("GENERATEUR DE RAPPORTS SYSTEME", C_GOLD)
    console.print("[dim]Scripts autonomes, format JSON/Markdown/HTML. "
                  "Aucune transmission reseau n'est generee.[/]\n")
    config = config_par_defaut()
    etapes = {
        "a": ("Informations generales", _etape_a),
        "b": ("Sections de donnees", _etape_b),
        "c": ("Options du rapport", _etape_c),
    }
    ordre = ["a", "b", "c"]
    index = 0
    while index < len(ordre):
        cle = ordre[index]
        libelle, fonction = etapes[cle]
        console.rule(f"[bold]{libelle}[/]")
        try:
            fonction(config)
        except ValueError as exc:
            warn(str(exc))
            continue
        index += 1

    while True:
        console.rule("[bold]Apercu[/]")
        _recapitulatif(config)
        try:
            _choisir_compilation(config)
        except ValueError as exc:
            warn(str(exc))
            continue
        choix = demander("Generer maintenant (oui / sections / options / annuler)",
                         "oui").strip().lower()
        if choix in {"oui", "o", "y", ""}:
            _finaliser(config)
            return
        if choix in {"sections", "s"}:
            index = 1
            while index < len(ordre):
                cle = ordre[index]
                console.rule(f"[bold]{etapes[cle][0]}[/]")
                try:
                    etapes[cle][1](config)
                except ValueError as exc:
                    warn(str(exc))
                    continue
                index += 1
            continue
        if choix in {"options", "c"}:
            try:
                _etape_c(config)
            except ValueError as exc:
                warn(str(exc))
            continue
        warn("Generation annulee.")
        return
