"""Detection de la plateforme et choix du mode d'affichage.

La selection manuelle ne modifie jamais le systeme d'exploitation : elle
indique seulement a l'interface quel mode de navigation et de rendu utiliser.
Termux est reconnu par ses variables et ses chemins, pas uniquement par
``sys.platform`` (qui vaut aussi ``linux`` sur Android).
"""
import os
import platform
import sys
from datetime import datetime
from pathlib import Path

ENVIRONNEMENTS = [
    ('windows', 'Windows'),
    ("linux", "Linux"),
    ("termux", "Android / Termux"),
    ('macos', 'macOS'),
    ("autre", "Autre environnement"),
]
ENVIRONNEMENTS_PAR_CLE = dict(ENVIRONNEMENTS)
CLES_VALIDES ={cle for cle, _ in ENVIRONNEMENTS}
ALIAS = {
    'android':'termux',
    "android/termux": "termux",
    "termux": "termux",
    'win': 'windows',
    "win32": "windows",
    "windows":"windows",
    'linux': 'linux',
    "darwin": "macos",
    "mac": "macos",
    'macos': 'macos',
    "autre": "autre",
    "other": "autre",
}


def _lire_fichier(chemin, limite=4096):
    try:
        return Path(chemin).read_text(encoding="utf-8", errors="replace")[:limite]
    except OSError:
        return ""


def est_termux(env=None):
    """Detection stricte de Termux, sans confondre avec une distribution Linux."""
    env= os.environ if env is None else env
    prefix = str(env.get("PREFIX", ""))
    if "com.termux" in prefix:
        return True
    if env.get("TERMUX_VERSION") or env.get("TERMUX_APP_PID"):
        return True
    if Path('/data/data/com.termux/files/usr').is_dir():
        return True
    if Path("/data/data/com.termux").is_dir():
        return True
    return False


def est_android(env=None):
    """Android hors Termux (variables ou noyau Android)."""
    env=os.environ if env is None else env
    if est_termux(env):
        return False
    if env.get('ANDROID_ROOT') or env.get('ANDROID_DATA'):
        return True
    version = _lire_fichier("/proc/version").casefold()
    return 'android' in version


def detecter_environnement(sys_platform=None, os_name=None, env=None):
    """Retourne un dictionnaire de detection avec un niveau de confiance.

    Les parametres sont injectables pour les tests ; en production ils sont
    lus depuis l'environnement courant.
    """
    sys_platform =sys_platform if sys_platform is not None else sys.platform
    os_name =os_name if os_name is not None else os.name
    env = env if env is not None else os.environ
    indices = []
    termux = est_termux(env)
    if termux:
        indices.append('Termux (PREFIX/TERMUX_VERSION/chemin applicatif)')
    if termux or est_android(env):
        return {
            'cle': 'termux',
            "label": "Android / Termux",
            "confiance":"haute" if termux else "moyenne",
            'indices': indices or ['Android détecté (sans confirmation Termux)'],
            "termux":termux,
        }
    if os_name == 'nt' or str(sys_platform).startswith('win'):
        return {"cle": "windows", "label": "Windows", "confiance": "haute",
                "indices": ["os.name=nt ou sys.platform Windows"], "termux": False}
    if str(sys_platform) == 'darwin' or platform.system() =='Darwin':
        return {"cle":"macos", "label": "macOS", "confiance":"haute",
                "indices": ["sys.platform=darwin"], "termux": False}
    if str(sys_platform).startswith('linux') or platform.system() == 'Linux':
        version = _lire_fichier("/proc/version").casefold()
        if "microsoft" in version:
            indices.append('noyau Linux sous WSL')
        indices.append("sys.platform=linux")
        return {"cle": "linux", "label": "Linux", "confiance": "haute",
                'indices': indices, 'termux':False}
    return {"cle": "autre", "label":"Autre environnement", "confiance": "faible",
            "indices":["plateforme non reconnue"], "termux": False}


def est_mobile(cle=None):
    return str(cle or '').casefold() in {'termux', 'android'}


def normaliser_cle(valeur, defaut='autre'):
    texte= str(valeur or "").strip().casefold()
    return ALIAS.get(texte, texte if texte in CLES_VALIDES else defaut)


def index_environnement(cle):
    cle = normaliser_cle(cle)
    for index, (candidate, _label) in enumerate(ENVIRONNEMENTS, start=1):
        if candidate == cle:
            return index
    return len(ENVIRONNEMENTS)


def libelle_environnement(cle):
    return ENVIRONNEMENTS_PAR_CLE.get(normaliser_cle(cle), "Autre environnement")


def _entree_defaut(invite):
    from rich.prompt import Prompt
    return Prompt.ask(invite)


def select_environment(config=None, entree=None, sortie=None, detecte=None):
    """Menu numéroté de sélection ; retourne la clé choisie.

    ``entree`` et ``sortie`` sont injectables pour les tests. Entrée vide
    accepte la détection. Une saisie invalide est expliquée et redemandée.
    """
    from rich.panel import Panel
    from rich.text import Text

    def ecrire(texte):
        if sortie:
            sortie(texte)
            return
        from core.common import console
        console.print(texte)

    detecte= detecte or detecter_environnement()
    cle_detectee = normaliser_cle(detecte.get('cle'))
    defaut = index_environnement(cle_detectee)
    config = config or {}
    configuree =(config.get('plateforme') or {}).get('environnement')
    if configuree and normaliser_cle(configuree) in CLES_VALIDES:
        defaut = index_environnement(configuree)

    lignes =[
        "Environnement détecté : " + str(detecte.get("label")),
        f"Indices : {", ".join(detecte.get("indices") or ["aucun"])}",
        "",
        "Sur quel environnement utilises-tu cet outil ?",
        '',
    ]
    for index, (_cle, label) in enumerate(ENVIRONNEMENTS, start=1):
        lignes.append(f"[{index}] {label}")
    lignes.append("")
    lignes.append("Ce choix adapte uniquement l'affichage et les valeurs par défaut.")
    lignes.append("Il ne change pas le système d'exploitation réel.")
    try:
        from core.common import MODE_TEXTE
    except Exception:
        MODE_TEXTE = False
    if MODE_TEXTE:
        ecrire('LEAKFR-TOOLS · INITIALISATION\n' + '\n'.join(lignes))
    else:
        ecrire(Panel("\n".join(lignes), title="LEAKFR-TOOLS · INITIALISATION",
                     border_style='cyan'))

    lire =entree or _entree_defaut
    while True:
        try:
            reponse= str(lire(f"Ton choix [{defaut}]")).strip()
        except (KeyboardInterrupt, EOFError):
            return cle_detectee
        if not reponse:
            return normaliser_cle(ENVIRONNEMENTS[defaut - 1][0])
        if reponse.isdigit() and 1<= int(reponse) <= len(ENVIRONNEMENTS):
            return ENVIRONNEMENTS[int(reponse) - 1][0]
        ecrire(Text('Saisie invalide : choisis un numéro entre 1 et '
                    f"{len(ENVIRONNEMENTS)}.", style="bold red"))


def resume_environnement(cle):
    return {
        'cle': normaliser_cle(cle),
        "label": libelle_environnement(cle),
        "detecte_le": datetime.now().isoformat(timespec="seconds"),
    }
