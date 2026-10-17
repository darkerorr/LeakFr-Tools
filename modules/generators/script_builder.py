"""Generation de scripts Python autonomes a partir d'une liste fermee de sections.

Les scripts produits utilisent uniquement la bibliotheque standard, n'ouvrent
aucune connexion et n'ecrivent que les fichiers explicitement demandes.
"""
import shutil
from pathlib import Path

from rich.prompt import Confirm
from rich.table import Table

from core.common import BX, C_GOLD, console, demander, kv, ok, titre, warn

SECTIONS = {
    "1": ("systeme", "Rapport systeme + HWID"),
    "2": ("hashes", "Inventaire d'un dossier (SHA-256)"),
    "3": ("fichier", "Metadonnees d'un fichier"),
    "4": ("json", "Export JSON local du rapport"),
}

_IMPORTS = r'''import hashlib
import json
import mimetypes
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


'''

_SYSTEME = r'''
def _lire(chemin, defaut=""):
    try:
        return Path(chemin).read_text(encoding="utf-8", errors="replace").strip() or defaut
    except OSError:
        return defaut


def _taille(octets):
    unites = ("o", "Ko", "Mo", "Go", "To")
    valeur = float(octets or 0)
    for unite in unites:
        if valeur < 1024 or unite == unites[-1]:
            return f"{valeur:.1f} {unite}"
        valeur /= 1024
    return f"{octets} o"


def _cpu():
    if sys.platform.startswith("linux"):
        for ligne in _lire("/proc/cpuinfo").splitlines():
            if ligne.lower().startswith("model name"):
                return ligne.split(":", 1)[1].strip()
    return platform.processor() or platform.machine()


def _composants():
    composants = {}
    if sys.platform.startswith("linux"):
        composants["machine-id"] = _lire("/etc/machine-id") or _lire("/var/lib/dbus/machine-id")
        composants["carte-mere"] = _lire("/sys/class/dmi/id/product_uuid")
        composants["modele"] = "/".join(
            valeur for valeur in (_lire("/sys/class/dmi/id/sys_vendor"),
                                  _lire("/sys/class/dmi/id/product_name")) if valeur)
    elif os.name == "nt":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, "SOFTWARE\\Microsoft\\Cryptography") as cle:
                composants["machine-guid"] = str(winreg.QueryValueEx(cle, "MachineGuid")[0])
        except (ImportError, OSError):
            pass
    elif sys.platform == "darwin":
        try:
            sortie = subprocess.run(
                ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
                capture_output=True, text=True, timeout=3, check=False,
            ).stdout
        except (OSError, subprocess.SubprocessError):
            sortie = ""
        for ligne in sortie.splitlines():
            if "IOPlatformUUID" in ligne:
                composants["platform-uuid"] = ligne.split("=")[-1].strip().strip('"')
                break
    composants["cpu"] = _cpu()
    composants["coeurs"] = str(os.cpu_count() or 0)
    composants["arch"] = platform.machine()
    return {cle: valeur for cle, valeur in composants.items() if valeur}


def rapport_systeme():
    composants = _composants()
    graine = "\n".join(f"{cle}={composants[cle]}" for cle in sorted(composants))
    digest = hashlib.sha256(graine.encode("utf-8")).hexdigest().upper()
    disque = shutil.disk_usage(Path.home())
    return {
        "hote": platform.node() or "?",
        "os": f"{platform.system()} {platform.release()} ({platform.machine()})",
        "utilisateur": os.environ.get("USER") or os.environ.get("USERNAME") or "?",
        "cpu": composants.get("cpu", "?"),
        "coeurs": os.cpu_count() or 0,
        "disque_libre": _taille(disque.free),
        "disque_total": _taille(disque.total),
        "composants": composants,
        "hwid": "-".join(digest[index:index + 8] for index in range(0, 32, 8)),
    }


def afficher_rapport(rapport):
    entrees = (
        ("Hote", rapport["hote"]),
        ("Systeme", rapport["os"]),
        ("Utilisateur", rapport["utilisateur"]),
        ("Processeur", rapport["cpu"]),
        ("Coeurs", rapport["coeurs"]),
        ("Stockage", f"{rapport['disque_libre']} libres sur {rapport['disque_total']}"),
        ("HWID", rapport["hwid"]),
    )
    largeur = max(len(cle) for cle, _ in entrees)
    for cle, valeur in entrees:
        print(f"{cle:<{largeur}} : {valeur}")
    print()
    print("Identifiants lus :")
    for cle, valeur in sorted(rapport["composants"].items()):
        print(f"  {cle:<{largeur}} : {valeur}")


def exporter_json(donnees, prefixe="rapport"):
    horodatage = datetime.now().strftime("%Y%m%d-%H%M%S")
    cible = Path.cwd() / f"{prefixe}-{horodatage}.json"
    cible.write_text(json.dumps(donnees, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return cible


'''

_HASHES = r'''
def inventaire_dossier(racine="."):
    base = Path(racine).expanduser()
    if not base.is_dir():
        return []
    entrees = []
    for chemin in sorted(base.rglob("*")):
        if not chemin.is_file():
            continue
        digest = hashlib.sha256()
        try:
            with chemin.open("rb") as flux:
                for bloc in iter(lambda: flux.read(1 << 20), b""):
                    digest.update(bloc)
        except OSError as exc:
            entrees.append({"chemin": str(chemin), "erreur": str(exc)})
            continue
        entrees.append({
            "chemin": str(chemin),
            "taille": chemin.stat().st_size,
            "sha256": digest.hexdigest(),
        })
    return entrees


def afficher_inventaire(entrees):
    for entree in entrees:
        if "erreur" in entree:
            print(f"{entree['chemin']} : erreur ({entree['erreur']})")
        else:
            print(f"{entree['sha256']}  {entree['taille']:>10}  {entree['chemin']}")
    print(f"{len(entrees)} fichier(s).")


'''

_FICHIER = r'''
def metadonnees_fichier(chemin):
    cible = Path(chemin).expanduser()
    if not cible.is_file():
        return {"chemin": str(cible), "erreur": "fichier introuvable"}
    digest = hashlib.sha256()
    with cible.open("rb") as flux:
        for bloc in iter(lambda: flux.read(1 << 20), b""):
            digest.update(bloc)
    stat = cible.stat()
    return {
        "chemin": str(cible.resolve()),
        "taille": stat.st_size,
        "sha256": digest.hexdigest(),
        "mime": mimetypes.guess_type(cible.name)[0] or "inconnu",
        "modifie": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
    }


def afficher_metadonnees(donnees):
    if "erreur" in donnees:
        print(f"{donnees['chemin']} : {donnees['erreur']}")
        return
    largeur = max(len(cle) for cle in donnees if cle != "chemin")
    for cle in ("chemin", "taille", "mime", "modifie", "sha256"):
        if cle in donnees:
            print(f"{cle:<{largeur}} : {donnees[cle]}")

'''


def _corps_principal(sections):
    """Assemble main() selon les sections choisies."""
    defaut = []
    if "systeme" in sections:
        defaut.append("    rapport = rapport_systeme()")
        defaut.append("    afficher_rapport(rapport)")
        if "json" in sections:
            defaut.append("    print()")
            defaut.append("    print('JSON ecrit :', exporter_json(rapport))")
    defaut.append("    return 0")

    dispatch = []
    if "hashes" in sections:
        dispatch.extend([
            '        if commande == "hash":',
            "            cible = args[1] if len(args) > 1 else '.'",
            "            afficher_inventaire(inventaire_dossier(cible))",
            "            return 0",
        ])
    if "fichier" in sections:
        dispatch.extend([
            '        if commande == "fichier" and len(args) > 1:',
            "            afficher_metadonnees(metadonnees_fichier(args[1]))",
            "            return 0",
        ])

    usage = ["        print('Usage : python <script> [commande]')"]
    if "hashes" in sections:
        usage.append("        print('  hash [dossier]        inventaire SHA-256')")
    if "fichier" in sections:
        usage.append("        print('  fichier <chemin>      metadonnees et SHA-256')")
    if "systeme" in sections:
        usage.append("        print('  (sans argument)       rapport systeme et HWID')")

    morceaux = ["\n\ndef main():", "    args = sys.argv[1:]", "    if args:", "        commande = args[0].lower()"]
    morceaux.extend(dispatch or ["        pass"])
    morceaux.extend(usage)
    morceaux.append("        return 1")
    morceaux.extend(defaut)
    morceaux.append("")
    morceaux.append("")
    morceaux.append('if __name__ == "__main__":')
    morceaux.append("    raise SystemExit(main())")
    return "\n".join(morceaux) + "\n"


def construire_script(sections, description="Rapport local genere par LeakFr-Tools"):
    """Retourne le source complet d'un script autonome pour ces sections."""
    sections = set(sections)
    if not sections:
        sections = {"systeme"}
    blocs = [_IMPORTS]
    if "systeme" in sections:
        blocs.append(_SYSTEME)
    if "hashes" in sections:
        blocs.append(_HASHES)
    if "fichier" in sections:
        blocs.append(_FICHIER)
    entete = (
        "#!/usr/bin/env python3\n"
        f'"""{description}.\n\n'
        f"Sections : {', '.join(sorted(sections))}.\n"
        "Autonome, bibliotheque standard uniquement : aucune connexion reseau,\n"
        "aucune donnee transmise. Les seuls fichiers ecrits sont les exports JSON\n"
        'demandes explicitement (option 4).\n"""\n'
    )
    return entete + "\n".join(blocs) + _corps_principal(sections)


def _choisir_sections():
    table = Table(box=BX, border_style=C_GOLD, header_style=f"bold {C_GOLD}")
    table.add_column("#", justify="right")
    table.add_column("Section")
    table.add_column("Contenu")
    for numero, (_cle, libelle) in SECTIONS.items():
        table.add_row(numero, libelle, "Incluse dans le script genere")
    console.print(table)
    reponse = demander("Sections a inclure (ex: 1 2, vide = tout)").strip()
    if not reponse:
        return [cle for cle, _ in SECTIONS.values()]
    choix = [partie for partie in reponse.replace(",", " ").split() if partie]
    inconnues = [partie for partie in choix if partie not in SECTIONS]
    if inconnues:
        warn(f"Numero(s) inconnu(s) : {', '.join(inconnues)}. Aucun fichier écrit.")
        return None
    return [SECTIONS[partie][0] for partie in choix]


def generer_script():
    """Ecrit un script autonome, sans emission reseau, et propose la compilation."""
    titre("GENERATEUR DE SCRIPTS LOCAUX", C_GOLD)
    console.print("[dim]Scripts autonomes (stdlib), sans webhook ni envoi reseau. "
                  "Les sections sont limitées à une liste fermée.[/]\n")

    sections = _choisir_sections()
    if not sections:
        return

    nom = demander("Nom du fichier de sortie", "rapport-machine.py").strip()
    if not nom:
        warn("Nom vide : aucun fichier créé.")
        return
    chemin = Path(nom).expanduser()
    if chemin.suffix.lower() not in {".py", ".pyw"}:
        chemin = chemin.with_suffix(".py")

    if chemin.exists() and not Confirm.ask(f"{chemin} existe déjà. Écraser ?", default=False):
        warn("Generation annulee.")
        return

    source = construire_script(sections)
    try:
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_text(source, encoding="utf-8")
        if hasattr(chemin, "chmod"):
            chemin.chmod(chemin.stat().st_mode | 0o111)
    except OSError as exc:
        warn(f"Impossible d'écrire le script : {exc}")
        return

    kv("Script genere", [
        ("Fichier", str(chemin.resolve())),
        ("Lignes", len(source.splitlines())),
        ("Sections", ", ".join(sections)),
        ("Reseau", "Aucun (aucun import ni appel réseau)"),
    ], C_GOLD)

    commande = f'pyinstaller --onefile --name "{chemin.stem}" "{chemin}"'
    console.print("\n[bold]Compilation en executable :[/]")
    console.print(f"  {commande}", markup=False, style="shell.text")
    if not shutil.which("pyinstaller"):
        warn("PyInstaller n'est pas installé : lance `pip install pyinstaller` puis la commande ci-dessus.")
    elif Confirm.ask("Lancer la compilation maintenant ?", default=False):
        import subprocess
        resultat = subprocess.run(
            [shutil.which("pyinstaller"), "--onefile", "--name", chemin.stem, str(chemin)],
            capture_output=False, check=False,
        )
        if resultat.returncode == 0:
            ok(f"Executable produit dans dist/{chemin.stem}")
        else:
            warn(f"PyInstaller a echoue (code {resultat.returncode}).")

    ok("Script ecrit. Il affiche son rapport dans le terminal, sans rien envoyer.")
