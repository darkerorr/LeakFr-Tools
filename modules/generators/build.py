"""Compilation PyInstaller controlee : arguments, execution, verification."""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

NOM_INTERDITS = set('<>:"/\\|?*')


def executable_pyinstaller():
    """Retourne le chemin de PyInstaller, ou None s'il est absent."""
    return shutil.which("pyinstaller") or shutil.which("pyinstaller.exe")


def valider_nom_executable(nom):
    """Refuse les noms vides, les separateurs et les caracteres reserves."""
    nom = (nom or "").strip()
    if not nom:
        raise ValueError("nom d'executable vide")
    if any(caractere in NOM_INTERDITS for caractere in nom):
        raise ValueError("caractere interdit dans le nom (<>:\"/\\|?*)")
    if nom in {".", ".."} or nom.endswith((" ", ".")):
        raise ValueError("nom d'executable invalide")
    return nom


def construire_arguments(script, nom, dossier=None, onefile=True):
    """Construit la liste d'arguments PyInstaller sans concaténation de chemins."""
    script = Path(script).expanduser().resolve()
    executable = executable_pyinstaller() or "pyinstaller"
    arguments = [executable]
    if onefile:
        arguments.append("--onefile")
    arguments.extend(["--name", valider_nom_executable(nom)])
    arguments.extend(["--distpath", str(Path(dossier).expanduser().resolve()) if dossier
                      else str(script.parent / "dist")])
    arguments.append(str(script))
    return arguments


def compiler(script, nom=None, dossier=None, timeout=900, runner=subprocess.run):
    """Lance PyInstaller et ne declare un succes que si l'artefact existe."""
    source = Path(script).expanduser()
    if not source.is_file():
        return {"ok": False, "code": None, "chemin": None, "sortie": "",
                "erreur": f"script introuvable : {source}"}
    nom = valider_nom_executable(nom or source.stem)
    if not executable_pyinstaller():
        return {"ok": False, "code": None, "chemin": None, "sortie": "",
                "erreur": "PyInstaller introuvable : installez-le avec 'pip install pyinstaller'"}

    dist = Path(dossier).expanduser().resolve() if dossier else source.parent.resolve() / "dist"
    with tempfile.TemporaryDirectory(prefix="leakfr-build-") as travail:
        arguments = construire_arguments(source, nom, dist, onefile=True)
        arguments[1:1] = ["--workpath", travail, "--specpath", travail]
        try:
            resultat = runner(arguments, capture_output=True, text=True,
                              timeout=timeout, check=False)
        except subprocess.TimeoutExpired:
            return {"ok": False, "code": None, "chemin": None, "sortie": "",
                    "erreur": f"delai de compilation depasse ({timeout} s)"}
        except OSError as exc:
            return {"ok": False, "code": None, "chemin": None, "sortie": "",
                    "erreur": f"{type(exc).__name__}: {exc}"}

    sortie = ((resultat.stdout or "") + (resultat.stderr or ""))[-4000:]
    candidats = [dist / f"{nom}.exe", dist / nom]
    artefact = next((candidat for candidat in candidats if candidat.is_file()), None)
    if resultat.returncode != 0:
        return {"ok": False, "code": resultat.returncode, "chemin": None, "sortie": sortie,
                "erreur": f"PyInstaller a echoue (code {resultat.returncode})"}
    if artefact is None:
        return {"ok": False, "code": 0, "chemin": None, "sortie": sortie,
                "erreur": "PyInstaller a termine sans produire l'executable attendu"}
    return {"ok": True, "code": 0, "chemin": str(artefact.resolve()), "sortie": sortie,
            "erreur": None}


def commande_installation():
    return f"{sys.executable} -m pip install pyinstaller"
