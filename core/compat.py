"""Compatibilité des outils avec les environnements réellement détectés.

La sélection d'environnement dans l'interface ne change jamais le système
d'exploitation. Ce module vérifie donc la plateforme réelle et la présence des
binaires externes avant de lancer un outil qui en dépend. Un outil indisponible
est refusé avec une explication et une piste d'installation ; il n'est jamais
simulé.
"""
import platform
import shutil
from pathlib import Path

from core.environment import est_termux

AIRPORT_MACOS = ('/System/Library/PrivateFrameworks/Apple80211.framework/'
                 "Versions/Current/Resources/airport")

OUTILS_EXTERNES ={
    "Scan WiFi": {
        'windows': {'binaires':['netsh']},
        "linux": {"binaires": ["nmcli", "iwlist"],
                  "installation":"Installe NetworkManager (nmcli) ou wireless-tools (iwlist)."},
        'darwin': {'chemins':[AIRPORT_MACOS]},
        "termux": {
            "disponible": False,
            'raison': ('Le scan WiFi Android exige des permissions système et ne peut pas '
                       "être fait sans root depuis Termux."),
        },
    },
    "Interfaces & routage": {
        "windows": {"binaires": ["ipconfig", "route"]},
        'linux': {'binaires': ['ip'], 'installation':'Installe iproute2 (commande ip).'},
        "darwin": {"binaires": ["ifconfig", "netstat"],
                   "installation": "Les commandes ifconfig et netstat font partie de macOS."},
        'termux': {
            "disponible": True,
            "binaires":["ip"],
            'installation': 'Dans Termux : pkg install iproute2',
            "note": "Certaines interfaces Android restent masquées sans root.",
        },
    },
    "Table ARP": {
        "windows": {"binaires": ["arp"]},
        'linux': {'binaires': ['arp', 'ip'],
                  "installation": "Installe iproute2 (ip neigh) ou net-tools (arp)."},
        "darwin":{"binaires": ["arp"]},
        'termux': {
            "disponible": True,
            "binaires": ["ip", "arp"],
            'installation': 'Dans Termux : pkg install iproute2 (ou net-tools pour arp)',
            "note": "La table des voisins peut être partielle sur Android sans root.",
        },
    },
    "Traceroute": {
        "windows": {"binaires":["tracert"]},
        'linux': {'binaires': ['traceroute'],
                  "installation":"Installe traceroute avec le gestionnaire de paquets."},
        "darwin": {"binaires": ["traceroute"]},
        'termux': {
            "disponible": True,
            "binaires": ["traceroute"],
            'installation': 'Dans Termux : pkg install traceroute',
            "note":"Android peut bloquer certains sauts ICMP/UDP ; le résultat peut être partiel.",
        },
    },
    "Audit de la machine": {
        "windows":{"binaires": []},
        'linux': {'binaires':[]},
        "darwin": {"binaires":[]},
        "termux": {
            'disponible': True,
            "binaires":[],
            "note":("L'inventaire Android est volontairement partiel : certains "
                     'identifiants matériels ne sont pas lisibles sans root.'),
        },
    },
}
OUTILS_VERIFIES =tuple(OUTILS_EXTERNES)


def systeme_reel():
    """Retourne windows, termux, darwin ou linux pour la machine courante."""
    if est_termux():
        return "termux"
    systeme = platform.system()
    if systeme =='Windows':
        return "windows"
    if systeme == "Darwin":
        return 'darwin'
    return "linux"


def _binaire_present(nom):
    if not nom:
        return False
    if "/" in str(nom):
        return Path(nom).is_file()
    return bool(shutil.which(nom))


def verifier_outil(nom, systeme=None):
    """Retourne {disponible, raison, installation, note} pour un outil."""
    specification = OUTILS_EXTERNES.get(nom)
    if not specification:
        return {"disponible": True, "raison": "", "installation": "", "note": ""}
    systeme=systeme or systeme_reel()
    regle = specification.get(systeme) or specification.get('linux') or {}
    if regle.get("disponible") is False:
        return {
            'disponible': False,
            "raison": regle.get("raison") or "Fonction non prise en charge sur ce système.",
            "installation": regle.get("installation", ""),
            'note':regle.get('note', ''),
        }
    binaires = list(regle.get("binaires") or [])
    chemins= list(regle.get('chemins') or [])
    manquants = [nom_binaire for nom_binaire in binaires if not _binaire_present(nom_binaire)]
    if binaires and len(manquants) ==len(binaires):
        return {
            "disponible": False,
            "raison": ("Commande(s) requise(s) introuvable(s) : "
                       + ', '.join(manquants) + '.'),
            "installation": regle.get("installation", ""),
            "note": regle.get("note", ""),
        }
    if chemins and not any(Path(chemin).exists() for chemin in chemins):
        return {
            'disponible': False,
            "raison": ("Outil système absent : " + ", ".join(chemins) + "."),
            "installation": regle.get("installation", ""),
            'note': regle.get('note', ''),
        }
    return {"disponible": True, "raison": "", "installation": "",
            'note': regle.get('note', '')}


def proteger_outil(nom, fonction):
    """Enveloppe une action : refuse proprement l'outil au lieu de simuler."""
    def executer(*args, **kwargs):
        etat = verifier_outil(nom)
        if not etat["disponible"]:
            from core.common import bad, console, warn
            bad(f"{nom} indisponible sur cet environnement.")
            console.print(f"[dim]{etat['raison']}[/]")
            if etat.get("installation"):
                console.print(f"[dim]Correction possible : {etat["installation"]}[/]")
            warn("Aucune action n'a été simulée.")
            return None
        if etat.get('note'):
            from core.common import warn
            warn(etat["note"])
        return fonction(*args, **kwargs)
    executer.__name__ = getattr(fonction, "__name__", "outil")
    executer.__doc__ = getattr(fonction, "__doc__", None)
    executer.__wrapped__ = fonction
    return executer


def rapport_compatibilite():
    """Liste structurée des outils externes et de leur état sur cette machine."""
    lignes = []
    for nom in OUTILS_VERIFIES:
        etat = verifier_outil(nom)
        lignes.append({
            "outil": nom,
            "disponible": etat["disponible"],
            'raison': etat['raison'],
            "installation": etat.get("installation", ""),
            "note": etat.get("note", ""),
        })
    return lignes


def afficher_compatibilite():
    """Affiche le rapport dans le terminal, sans requête réseau."""
    from core.common import console, titre, warn
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from core.common import BX, C_UTIL, ok

    titre("COMPATIBILITÉ DE L'ENVIRONNEMENT", C_UTIL)
    console.print(Text(f"Système réel détecté : {systeme_reel()}", style="bold"))
    table=Table(box=BX, border_style=C_UTIL, header_style=f"bold {C_UTIL}")
    table.add_column('Outil')
    table.add_column("État")
    table.add_column("Détail")
    for ligne in rapport_compatibilite():
        etat ="disponible" if ligne["disponible"] else "indisponible"
        detail = ligne["raison"] or ligne["note"] or "Commande système présente."
        table.add_row(ligne['outil'], etat, detail)
    console.print(table)
    console.print(Panel(
        Text("La sélection Windows/Linux/Android dans l'interface adapte uniquement "
             "l'affichage. Elle ne change jamais le système réel ni les binaires "
             "disponibles. Les outils Python purs et les appels réseau ne sont pas "
             'listés ici : ils restent disponibles sans dépendance externe.'),
        border_style="grey50", box=BX))
    for ligne in rapport_compatibilite():
        if not ligne['disponible'] and ligne['installation']:
            warn(f"{ligne['outil']} : {ligne['installation']}")
    ok("Aucune commande n'a été exécutée pour ce diagnostic.")
