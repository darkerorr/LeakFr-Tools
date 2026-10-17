"""Collecteurs systeme autonomes (bibliotheque standard uniquement).

Chaque collecteur retourne un dict ``{"statut", "donnees", "erreurs"}`` ou le
statut vaut ``ok``, ``partiel``, ``indisponible`` ou ``erreur``. Un collecteur
en echec ne leve pas : l'erreur est enregistree et le rapport continue.
"""
import ctypes
import hashlib
import json
import locale
import os
import platform
import shutil
import socket
import string
import struct
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HELPERS = ("_lire", "_taille", "_section", "_erreur", "_commande", "_uptime",
           "_points_de_montage", "_cpu_modele")


def _lire(chemin, defaut=""):
    try:
        return Path(chemin).read_text(encoding="utf-8", errors="replace").strip() or defaut
    except OSError:
        return defaut


def _taille(octets):
    if octets is None:
        return None
    unites = ("o", "Ko", "Mo", "Go", "To", "Po")
    valeur = float(octets)
    for unite in unites:
        if valeur < 1024 or unite == unites[-1]:
            return f"{valeur:.1f} {unite}"
        valeur /= 1024
    return f"{octets} o"


def _section(statut, donnees=None, erreurs=None):
    return {"statut": statut, "donnees": donnees, "erreurs": erreurs or []}


def _erreur(collecteur, exc, solution=""):
    return {
        "collecteur": collecteur,
        "type": type(exc).__name__,
        "message": str(exc),
        "solution": solution,
    }


def _commande(arguments, timeout=5):
    """Execute une commande locale et retourne sa sortie, ou None."""
    try:
        resultat = subprocess.run(arguments, capture_output=True, text=True,
                                  timeout=timeout, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    if resultat.returncode != 0:
        return None
    return (resultat.stdout or "").strip() or None


def _uptime():
    if sys.platform.startswith("linux"):
        brut = _lire("/proc/uptime")
        if brut:
            return float(brut.split()[0])
    if os.name == "nt":
        try:
            return ctypes.windll.kernel32.GetTickCount64() / 1000
        except (AttributeError, OSError):
            return None
    return None


def _points_de_montage():
    if os.name == "nt":
        return [f"{lettre}:\\" for lettre in string.ascii_uppercase
                if Path(f"{lettre}:\\").exists()]
    points = ["/"]
    for ligne in _lire("/proc/mounts").splitlines():
        champs = ligne.split()
        if len(champs) < 3:
            continue
        point, type_fs = champs[1], champs[2]
        if point in points or not point.startswith("/"):
            continue
        if type_fs in {"ext4", "xfs", "btrfs", "vfat", "ntfs", "ntfs3", "zfs", "f2fs"}:
            points.append(point)
    return points[:12]


def _cpu_modele():
    if sys.platform.startswith("linux"):
        for ligne in _lire("/proc/cpuinfo").splitlines():
            if ligne.lower().startswith("model name"):
                return ligne.split(":", 1)[1].strip()
    if sys.platform == "darwin":
        sortie = _commande(["sysctl", "-n", "machdep.cpu.brand_string"])
        if sortie:
            return sortie
    return platform.processor() or None


def _memoire():
    if sys.platform.startswith("linux"):
        total = disponible = None
        for ligne in _lire("/proc/meminfo").splitlines():
            if ligne.startswith("MemTotal:"):
                total = int(ligne.split()[1]) * 1024
            elif ligne.startswith("MemAvailable:"):
                disponible = int(ligne.split()[1]) * 1024
        return total, disponible
    if os.name == "nt":
        class _Etat(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        etat = _Etat()
        etat.dwLength = ctypes.sizeof(_Etat)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(etat)):
            return int(etat.ullTotalPhys), int(etat.ullAvailPhys)
        return None, None
    try:
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES"), None
    except (AttributeError, ValueError, OSError):
        return None, None


def collecter_systeme():
    """OS, version, architecture, hote, demarrage, langue et fuseau."""
    erreurs = []
    donnees = {
        "systeme": platform.system() or None,
        "version": platform.version() or None,
        "release": platform.release() or None,
        "architecture": platform.machine() or None,
        "python": platform.python_version(),
        "hote": platform.node() or None,
        "edition": None,
        "build": None,
    }
    try:
        if sys.platform.startswith("linux"):
            for ligne in _lire("/etc/os-release").splitlines():
                if ligne.startswith("PRETTY_NAME="):
                    donnees["edition"] = ligne.split("=", 1)[1].strip().strip('"')
        elif os.name == "nt":
            release, version, _csd, _ptype = platform.win32_ver()
            donnees["edition"] = release or None
            donnees["build"] = version or None
        elif sys.platform == "darwin":
            donnees["edition"] = _commande(["sw_vers", "-productVersion"])
    except Exception as exc:  # noqa: BLE001 - un collecteur ne doit jamais casser le rapport
        erreurs.append(_erreur("collecter_systeme", exc))

    try:
        secondes = _uptime()
        donnees["demarrage_secondes"] = int(secondes) if secondes is not None else None
    except Exception as exc:  # noqa: BLE001
        erreurs.append(_erreur("uptime", exc))

    try:
        langue, _encodage = locale.getlocale()
        donnees["langue"] = langue or os.environ.get("LANG")
    except Exception:  # noqa: BLE001 - locale peut lever ValueError
        donnees["langue"] = os.environ.get("LANG")

    try:
        donnees["fuseau"] = datetime.now().astimezone().tzname()
    except Exception as exc:  # noqa: BLE001
        erreurs.append(_erreur("fuseau", exc))

    statut = "ok" if not erreurs else "partiel"
    return _section(statut, donnees, erreurs)


def collecter_materiel():
    """Processeur, coeurs, memoire, fabricant/modele et GPU detectables."""
    erreurs = []
    donnees = {"processeur": None, "coeurs_logiques": os.cpu_count() or 0,
               "memoire_totale": None, "memoire_disponible": None,
               "fabricant": None, "modele": None, "gpu": []}
    try:
        donnees["processeur"] = _cpu_modele()
    except Exception as exc:  # noqa: BLE001
        erreurs.append(_erreur("processeur", exc))

    try:
        total, disponible = _memoire()
        donnees["memoire_totale"] = total
        donnees["memoire_disponible"] = disponible
    except Exception as exc:  # noqa: BLE001
        erreurs.append(_erreur("memoire", exc))

    try:
        if sys.platform.startswith("linux"):
            donnees["fabricant"] = _lire("/sys/class/dmi/id/sys_vendor") or None
            donnees["modele"] = _lire("/sys/class/dmi/id/product_name") or None
        elif os.name == "nt":
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                r"HARDWARE\DESCRIPTION\System\BIOS") as cle:
                donnees["fabricant"] = str(winreg.QueryValueEx(cle, "SystemManufacturer")[0])
                donnees["modele"] = str(winreg.QueryValueEx(cle, "SystemProductName")[0])
    except Exception as exc:  # noqa: BLE001 - acces registre/DMI souvent restreint
        erreurs.append(_erreur("fabricant", exc, "droits insuffisants pour interroger le BIOS"))

    try:
        if sys.platform.startswith("linux"):
            sortie = _commande(["lspci"])
            if sortie:
                donnees["gpu"] = [ligne.split(": ", 1)[-1] for ligne in sortie.splitlines()
                                  if "VGA compatible controller" in ligne or "3D controller" in ligne]
        elif os.name == "nt":
            sortie = _commande(["wmic", "path", "win32_VideoController", "get", "name"])
            if sortie:
                donnees["gpu"] = [ligne.strip() for ligne in sortie.splitlines()[1:] if ligne.strip()]
    except Exception as exc:  # noqa: BLE001
        erreurs.append(_erreur("gpu", exc))

    statut = "ok" if not erreurs else "partiel"
    return _section(statut, donnees, erreurs)


def collecter_disques():
    """Volumes accessibles avec capacite, espace libre et taux d'utilisation."""
    erreurs = []
    volumes = []
    try:
        points = _points_de_montage()
    except Exception as exc:  # noqa: BLE001
        return _section("erreur", {"volumes": []}, [_erreur("collecter_disques", exc)])
    for point in points:
        try:
            usage = shutil.disk_usage(point)
        except OSError as exc:
            erreurs.append(_erreur("disque", exc, f"volume inaccessible : {point}"))
            continue
        pourcentage = round(usage.used / usage.total * 100, 1) if usage.total else None
        volumes.append({
            "point": point,
            "total": usage.total,
            "libre": usage.free,
            "utilise": usage.used,
            "utilisation_pct": pourcentage,
        })
    if not volumes:
        return _section("indisponible", {"volumes": []}, erreurs)
    return _section("ok" if not erreurs else "partiel", {"volumes": volumes}, erreurs)


def collecter_fichiers(chemins=None, extensions=None, limite=200, empreinte=True,
                       dossiers_exclus=None):
    """Inventaire limite de fichiers choisis, avec SHA-256 optionnel."""
    exclusions = {str(Path(chemin).expanduser().resolve()) for chemin in (dossiers_exclus or [])}
    extensions = {ext.lower() if ext.startswith(".") else f".{ext.lower()}"
                  for ext in (extensions or [])}
    erreurs = []
    entrees = []

    def ajouter(chemin):
        if len(entrees) >= limite:
            return
        chemin = Path(chemin).expanduser()
        if not chemin.is_file():
            return
        if extensions and chemin.suffix.lower() not in extensions:
            return
        try:
            stat = chemin.stat()
        except OSError as exc:
            erreurs.append(_erreur("fichier", exc, f"inaccessible : {chemin}"))
            return
        entree = {
            "chemin": str(chemin.resolve()),
            "taille": stat.st_size,
            "extension": chemin.suffix.lower() or None,
            "modifie": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
            "sha256": None,
        }
        if empreinte:
            digest = hashlib.sha256()
            try:
                with chemin.open("rb") as flux:
                    for bloc in iter(lambda: flux.read(1 << 20), b""):
                        digest.update(bloc)
                entree["sha256"] = digest.hexdigest()
            except OSError as exc:
                erreurs.append(_erreur("sha256", exc, f"lecture impossible : {chemin}"))
        entrees.append(entree)

    for chemin in chemins or []:
        cible = Path(chemin).expanduser()
        if cible.is_dir():
            for element in sorted(cible.rglob("*")):
                if len(entrees) >= limite:
                    break
                resolve = str(element.resolve())
                if any(resolve.startswith(excl) for excl in exclusions):
                    continue
                ajouter(element)
        else:
            ajouter(cible)

    if not entrees:
        return _section("indisponible", {"fichiers": [], "limite": limite}, erreurs)
    statut = "ok" if not erreurs and len(entrees) < limite else "partiel"
    return _section(statut, {"fichiers": entrees, "limite": limite,
                             "extensions": sorted(extensions)}, erreurs)


def _interface_ipv4(nom):
    try:
        import fcntl
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sonde:
            requete = struct.pack("256s", nom[:15].encode("utf-8"))
            return socket.inet_ntoa(fcntl.ioctl(sonde.fileno(), 0x8915, requete)[20:24])
    except (ImportError, OSError):
        return None


def collecter_reseau():
    """Interfaces locales, adresses privees, passerelle et DNS configures."""
    erreurs = []
    interfaces = []
    try:
        if sys.platform.startswith("linux"):
            for nom in sorted(os.listdir("/sys/class/net")):
                interfaces.append({
                    "nom": nom,
                    "etat": _lire(f"/sys/class/net/{nom}/operstate") or None,
                    "mac": _lire(f"/sys/class/net/{nom}/address") or None,
                    "ipv4": _interface_ipv4(nom),
                })
        elif os.name == "nt":
            for adresse in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
                interfaces.append({"nom": platform.node(), "etat": None, "mac": None,
                                   "ipv4": adresse[4][0]})
    except Exception as exc:  # noqa: BLE001
        erreurs.append(_erreur("interfaces", exc))

    passerelle = dns = None
    try:
        if sys.platform.startswith("linux"):
            for ligne in _lire("/proc/net/route").splitlines()[1:]:
                champs = ligne.split()
                if len(champs) > 2 and champs[1] == "00000000":
                    valeur = int(champs[2], 16)
                    passerelle = socket.inet_ntoa(struct.pack("<L", valeur))
                    break
            serveurs = [ligne.split()[1] for ligne in _lire("/etc/resolv.conf").splitlines()
                        if ligne.startswith("nameserver") and len(ligne.split()) > 1]
            dns = serveurs[:3]
    except Exception as exc:  # noqa: BLE001
        erreurs.append(_erreur("passerelle_dns", exc))

    donnees = {"interfaces": interfaces, "passerelle": passerelle, "dns": dns or []}
    if not interfaces:
        return _section("indisponible", donnees, erreurs)
    return _section("ok" if not erreurs else "partiel", donnees, erreurs)


def collecter_logiciels(limite=100):
    """Logiciels installes lorsque la source systeme est disponible."""
    logiciels = []
    erreurs = []
    try:
        if os.name == "nt":
            import winreg
            cles = (r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
                    r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall")
            for chemin in cles:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, chemin) as base:
                    for index in range(winreg.QueryInfoKey(base)[0]):
                        if len(logiciels) >= limite:
                            break
                        try:
                            with winreg.OpenKey(base, winreg.EnumKey(base, index)) as cle:
                                nom = str(winreg.QueryValueEx(cle, "DisplayName")[0])
                                version = str(winreg.QueryValueEx(cle, "DisplayVersion")[0]) \
                                    if _valeur(cle, "DisplayVersion") else None
                                editeur = str(winreg.QueryValueEx(cle, "Publisher")[0]) \
                                    if _valeur(cle, "Publisher") else None
                                logiciels.append({"nom": nom, "version": version,
                                                  "editeur": editeur})
                        except OSError:
                            continue
        elif shutil.which("dpkg-query"):
            sortie = _commande(["dpkg-query", "-W", "-f=${Package}\\t${Version}\\t${Maintainer}\\n"])
            for ligne in (sortie or "").splitlines()[:limite]:
                morceaux = ligne.split("\t")
                if len(morceaux) >= 2:
                    logiciels.append({"nom": morceaux[0], "version": morceaux[1],
                                      "editeur": morceaux[2] if len(morceaux) > 2 else None})
    except Exception as exc:  # noqa: BLE001
        erreurs.append(_erreur("collecter_logiciels", exc, "droits d'acces au registre ou dpkg"))

    if not logiciels:
        return _section("indisponible", {"logiciels": [], "limite": limite}, erreurs)
    statut = "ok" if not erreurs and len(logiciels) < limite else "partiel"
    return _section(statut, {"logiciels": logiciels, "limite": limite}, erreurs)


def _valeur(cle, nom):
    try:
        import winreg
        winreg.QueryValueEx(cle, nom)
        return True
    except OSError:
        return False


def collecter_dev():
    """Versions des outils de developpement detectables."""
    outils = {
        "python": [sys.executable, "--version"],
        "git": ["git", "--version"],
        "pip": [sys.executable, "-m", "pip", "--version"],
        "node": ["node", "--version"],
        "gcc": ["gcc", "--version"],
        "make": ["make", "--version"],
        "powershell": ["powershell", "-NoProfile", "-Command", "$PSVersionTable.PSVersion.ToString()"],
        "dotnet": ["dotnet", "--version"],
    }
    trouvees = {}
    erreurs = []
    for nom, commande in outils.items():
        if not shutil.which(commande[0]) and commande[0] != sys.executable:
            continue
        try:
            sortie = _commande(commande, timeout=3)
        except Exception as exc:  # noqa: BLE001
            erreurs.append(_erreur(f"dev:{nom}", exc))
            continue
        if sortie:
            trouvees[nom] = sortie.splitlines()[0].strip()
    if not trouvees:
        return _section("indisponible", {"outils": {}}, erreurs)
    return _section("ok" if not erreurs else "partiel", {"outils": trouvees}, erreurs)


def collecter_session(inclure_compte=True, inclure_home=True):
    """Informations de session explicitement demandees."""
    donnees = {"utilisateur": None, "domaine": None, "shell": None, "dossier_personnel": None}
    erreurs = []
    if inclure_compte:
        donnees["utilisateur"] = os.environ.get("USER") or os.environ.get("USERNAME")
        donnees["domaine"] = os.environ.get("USERDOMAIN") or None
    if inclure_home:
        donnees["dossier_personnel"] = str(Path.home())
    donnees["shell"] = os.environ.get("SHELL") or os.environ.get("COMSPEC")
    return _section("ok" if donnees["utilisateur"] or donnees["dossier_personnel"] else "indisponible",
                    donnees, erreurs)


def collecter_peripheriques():
    """Peripheriques detectes via les sources locales disponibles."""
    donnees = {"compteurs": {}, "details": []}
    erreurs = []
    try:
        if sys.platform.startswith("linux"):
            for categorie in ("net", "usb", "block", "drm", "input"):
                base = Path("/sys/class") / categorie
                if base.is_dir():
                    donnees["compteurs"][categorie] = len(list(base.iterdir()))
            sortie = _commande(["lspci"])
            if sortie:
                donnees["details"] = sortie.splitlines()[:20]
        else:
            sortie = _commande(["wmic", "path", "Win32_PnPEntity", "get", "name"])
            if sortie:
                donnees["details"] = [ligne.strip() for ligne in sortie.splitlines()[1:] if ligne.strip()][:20]
    except Exception as exc:  # noqa: BLE001
        erreurs.append(_erreur("collecter_peripheriques", exc))
    if not donnees["compteurs"] and not donnees["details"]:
        return _section("indisponible", donnees, erreurs)
    return _section("ok" if not erreurs else "partiel", donnees, erreurs)


def collecter_empreinte_machine():
    """HWID stable, calcule localement (option sensible, desactivee par defaut)."""
    composants = {}
    erreurs = []
    try:
        if sys.platform.startswith("linux"):
            composants["machine-id"] = _lire("/etc/machine-id") or _lire("/var/lib/dbus/machine-id")
            composants["carte-mere"] = _lire("/sys/class/dmi/id/product_uuid")
        elif os.name == "nt":
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                r"SOFTWARE\Microsoft\Cryptography") as cle:
                composants["machine-guid"] = str(winreg.QueryValueEx(cle, "MachineGuid")[0])
    except Exception as exc:  # noqa: BLE001
        erreurs.append(_erreur("empreinte", exc, "identifiants systeme non lisibles"))

    composants = {cle: valeur for cle, valeur in composants.items() if valeur}
    composants["cpu"] = _cpu_modele() or ""
    composants["arch"] = platform.machine() or ""
    graine = "\n".join(f"{cle}={composants[cle]}" for cle in sorted(composants))
    digest = hashlib.sha256(graine.encode("utf-8")).hexdigest().upper()
    hwid = "-".join(digest[index:index + 8] for index in range(0, 32, 8))
    return _section("ok" if not erreurs else "partiel",
                    {"hwid": hwid, "composants": composants}, erreurs)


def collecter_historique(dossier=".", limite=10):
    """Resume les rapports JSON precedents presents dans un dossier."""
    base = Path(dossier).expanduser()
    rapports = []
    erreurs = []
    if not base.is_dir():
        return _section("indisponible", {"rapports": []},
                        [_erreur("historique", FileNotFoundError(dossier), "dossier absent")])
    for chemin in sorted(base.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        try:
            donnees = json.loads(chemin.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            erreurs.append(_erreur("historique", exc, f"lecture : {chemin.name}"))
            continue
        if not isinstance(donnees, dict) or "synthese" not in donnees:
            continue
        rapports.append({
            "fichier": chemin.name,
            "genere_le": donnees.get("genere_le"),
            "sections": donnees.get("synthese", {}).get("sections_total"),
        })
        if len(rapports) >= limite:
            break
    if not rapports:
        return _section("indisponible", {"rapports": []}, erreurs)
    return _section("ok" if not erreurs else "partiel", {"rapports": rapports}, erreurs)


COLLECTEURS = {
    "systeme": ("Systeme d'exploitation", collecter_systeme),
    "materiel": ("Materiel", collecter_materiel),
    "disques": ("Stockage et volumes", collecter_disques),
    "fichiers": ("Fichiers selectionnes", collecter_fichiers),
    "reseau": ("Reseau", collecter_reseau),
    "logiciels": ("Logiciels installes", collecter_logiciels),
    "dev": ("Environnement de developpement", collecter_dev),
    "session": ("Session et compte", collecter_session),
    "peripheriques": ("Peripheriques", collecter_peripheriques),
    "empreinte": ("Empreinte machine (HWID)", collecter_empreinte_machine),
    "historique": ("Rapports precedents", collecter_historique),
}
