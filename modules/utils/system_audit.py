"""Audit local de la machine : le rapport reste dans le terminal.

Aucune connexion n'est ouverte, aucune donnee n'est ecrite sur disque ni
transmise. Le HWID est un hash calcule a partir d'identifiants deja presents
sur la machine, utile pour distinguer deux postes d'un parc.
"""
import ctypes
import hashlib
import os
import platform
import shutil
import socket
import struct
import subprocess
import sys
from pathlib import Path

from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from core.common import BX, C_UTIL, console, kv, ok, titre

_DMI = Path("/sys/class/dmi/id")


def _lire(chemin, defaut=""):
    try:
        return Path(chemin).read_text(encoding="utf-8", errors="replace").strip() or defaut
    except OSError:
        return defaut


def _guid_windows():
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography") as cle:
            return str(winreg.QueryValueEx(cle, "MachineGuid")[0])
    except (ImportError, OSError):
        return ""


def _serie_volume_windows():
    try:
        numero = ctypes.c_ulong()
        racine = os.environ.get("SystemDrive", "C:") + "\\"
        if ctypes.windll.kernel32.GetVolumeInformationW(
            ctypes.c_wchar_p(racine), None, 0, ctypes.byref(numero), None, None, None, 0
        ):
            return f"{numero.value:08X}"
    except (AttributeError, OSError):
        pass
    return ""


def _uuid_macos():
    try:
        sortie = subprocess.run(
            ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
            capture_output=True, text=True, timeout=3, check=False,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return ""
    for ligne in sortie.splitlines():
        if "IOPlatformUUID" in ligne:
            return ligne.split("=")[-1].strip().strip('"')
    return ""


def _cpu_modele():
    if sys.platform.startswith("linux"):
        for ligne in _lire("/proc/cpuinfo").splitlines():
            if ligne.lower().startswith("model name"):
                return ligne.split(":", 1)[1].strip()
    return platform.processor() or platform.machine()


def _memoire_totale():
    if sys.platform.startswith("linux"):
        for ligne in _lire("/proc/meminfo").splitlines():
            if ligne.startswith("MemTotal:"):
                return int(ligne.split()[1]) * 1024
    if os.name == "nt":
        class _EtatMemoire(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        etat = _EtatMemoire()
        etat.dwLength = ctypes.sizeof(_EtatMemoire)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(etat)):
            return int(etat.ullTotalPhys)
    try:
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    except (AttributeError, ValueError, OSError):
        return 0


def _interfaces_linux():
    try:
        noms = sorted(os.listdir("/sys/class/net"))
    except OSError:
        return []
    resultat = []
    for nom in noms:
        ipv4 = ""
        try:
            import fcntl
            # Socket UDP local : sert uniquement a interroger le noyau, rien n'est envoye.
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sonde:
                requete = struct.pack("256s", nom[:15].encode("utf-8"))
                ipv4 = socket.inet_ntoa(fcntl.ioctl(sonde.fileno(), 0x8915, requete)[20:24])
        except (ImportError, OSError):
            pass
        resultat.append({
            "nom": nom,
            "mac": _lire(f"/sys/class/net/{nom}/address", "-"),
            "ipv4": ipv4 or "-",
        })
    return resultat


def _interfaces():
    try:
        import psutil
    except ImportError:
        return _interfaces_linux() if sys.platform.startswith("linux") else []
    resultat = []
    for nom, adresses in psutil.net_if_addrs().items():
        mac = next((a.address for a in adresses if a.family == psutil.AF_LINK), "-")
        ipv4 = next((a.address for a in adresses if a.family == socket.AF_INET), "-")
        resultat.append({"nom": nom, "mac": mac, "ipv4": ipv4})
    return sorted(resultat, key=lambda entree: entree["nom"])


def _composants_identite():
    """Rassemble les identifiants stables disponibles sur ce systeme."""
    composants = {}
    if sys.platform.startswith("linux"):
        composants["machine-id"] = _lire("/etc/machine-id") or _lire("/var/lib/dbus/machine-id")
        composants["carte-mere"] = _lire(_DMI / "product_uuid") or _lire(_DMI / "board_serial")
        composants["modele"] = "/".join(
            valeur for valeur in (_lire(_DMI / "sys_vendor"), _lire(_DMI / "product_name")) if valeur
        )
        for chemin in sorted(Path("/sys/block").glob("*/device/serial")):
            serie = _lire(chemin)
            if serie:
                composants["disque"] = serie
                break
    elif os.name == "nt":
        composants["machine-guid"] = _guid_windows()
        composants["volume"] = _serie_volume_windows()
    elif sys.platform == "darwin":
        composants["platform-uuid"] = _uuid_macos()

    composants["cpu"] = _cpu_modele()
    composants["coeurs"] = str(os.cpu_count() or 0)
    composants["arch"] = platform.machine()
    return {cle: valeur for cle, valeur in composants.items() if valeur}


def calculer_hwid(composants=None):
    """Hash deterministe des identifiants locaux, presente en blocs de 8."""
    composants = _composants_identite() if composants is None else composants
    graine = "\n".join(
        f"{cle}={composants[cle]}" for cle in sorted(composants) if composants.get(cle)
    )
    digest = hashlib.sha256(graine.encode("utf-8")).hexdigest().upper()
    return "-".join(digest[index:index + 8] for index in range(0, 32, 8))


def _taille(octets):
    if not octets:
        return "?"
    unites = ("o", "Ko", "Mo", "Go", "To")
    valeur = float(octets)
    for unite in unites:
        if valeur < 1024 or unite == unites[-1]:
            return f"{valeur:.1f} {unite}" if unite != "o" else f"{int(valeur)} o"
        valeur /= 1024
    return f"{octets} o"


def collecter_identite():
    """Retourne un rapport structure, sans effet de bord ni acces reseau."""
    stockage = shutil.disk_usage(Path.home())
    return {
        "schema": "leakfr.system-audit.v1",
        "network_requests": False,
        "systeme": {
            "os": platform.system() or "?",
            "version": platform.version() or "?",
            "release": platform.release() or "?",
            "architecture": platform.machine() or "?",
            "hote": socket.gethostname() or "?",
            "utilisateur": os.environ.get("USER") or os.environ.get("USERNAME") or "?",
            "python": platform.python_version(),
        },
        "materiel": {
            "cpu": _cpu_modele() or "?",
            "coeurs": os.cpu_count() or 0,
            "memoire_octets": _memoire_totale(),
            "stockage_total": stockage.total,
            "stockage_libre": stockage.free,
        },
        "interfaces": _interfaces(),
        "composants": _composants_identite(),
        "hwid": calculer_hwid(),
    }


def audit_systeme():
    """Affiche l'audit de la machine courante dans le terminal."""
    titre("AUDIT DE LA MACHINE - LOCAL", C_UTIL)
    infos = collecter_identite()
    systeme = infos["systeme"]
    materiel = infos["materiel"]

    kv("Systeme", [
        ("OS", f"{systeme['os']} {systeme['release']} ({systeme['architecture']})"),
        ("Version", systeme["version"]),
        ("Hote", systeme["hote"]),
        ("Utilisateur", systeme["utilisateur"]),
        ("Python", systeme["python"]),
    ], C_UTIL)

    kv("Materiel", [
        ("Processeur", materiel["cpu"]),
        ("Coeurs", materiel["coeurs"]),
        ("Memoire", _taille(materiel["memoire_octets"])),
        ("Stockage", f"{_taille(materiel['stockage_libre'])} libres sur {_taille(materiel['stockage_total'])}"),
    ], C_UTIL)

    if infos["interfaces"]:
        table = Table(title="Interfaces locales", box=BX, border_style=C_UTIL,
                      header_style=f"bold {C_UTIL}")
        table.add_column("Interface", style="bold")
        table.add_column("Adresse MAC")
        table.add_column("IPv4")
        for entree in infos["interfaces"]:
            table.add_row(entree["nom"], entree["mac"], entree["ipv4"])
        console.print(table)
    else:
        kv("Interfaces locales", [("Etat", "Aucune interface enumeratee sur ce systeme")], C_UTIL)

    composants = infos["composants"]
    kv("Identifiants lus", [(cle, valeur) for cle, valeur in sorted(composants.items())], C_UTIL)

    console.print(Panel(
        Text.from_markup(
            f"[bold]{infos['hwid']}[/]\n\n"
            "[dim]Hash SHA-256 des identifiants ci-dessus, calcule sur cette machine. "
            "Rapport affiche uniquement dans ce terminal : aucune connexion ouverte, "
            "aucune donnee transmise ni ecrite sur disque.[/]"
        ),
        title="HWID local", border_style=C_UTIL,
    ))
    ok("Audit termine. Aucune requete reseau emise.")
