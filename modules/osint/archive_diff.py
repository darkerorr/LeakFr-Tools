"""Archive Change Watcher : comparaison de deux captures Internet Archive.

Les differences observees sont des observations historiques, pas une preuve de
modification malveillante. Toutes les requetes utilisent un delai d'expiration
et une limite de taille.
"""
import difflib
import json
from html.parser import HTMLParser
from pathlib import Path

import requests

from core.common import (C_OSINT, HEADERS, attente, console, demander, kv, ok,
                         titre, warn)
from rich.panel import Panel

CDX_URL = "https://web.archive.org/cdx/search/cdx"
BASE_ARCHIVE = "https://web.archive.org/web"
BALISES_IGNOREES = {"script", "style", "noscript", "svg", "template"}


class _ExtracteurTexte(HTMLParser):
    """Extrait le texte visible en ignorant les blocs decoratifs ou scriptes."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._ignorer = 0
        self.morceaux = []

    def handle_starttag(self, tag, attrs):
        if tag in BALISES_IGNOREES:
            self._ignorer += 1

    def handle_endtag(self, tag):
        if tag in BALISES_IGNOREES and self._ignorer:
            self._ignorer -= 1

    def handle_data(self, data):
        if self._ignorer:
            return
        texte = " ".join(data.split())
        if texte:
            self.morceaux.append(texte)


def extraire_texte(html, limite=200_000):
    """Retourne le texte utile d'une page, sans balises ni scripts."""
    parseur = _ExtracteurTexte()
    try:
        parseur.feed(html or "")
    except Exception:  # noqa: BLE001 - un HTML casse ne doit pas bloquer
        pass
    return "\n".join(parseur.morceaux)[:limite]


def lister_captures(url, session=None, limite=40, timeout=20):
    """Interroge l'index CDX et retourne les captures succes 200."""
    client = session or requests
    parametres = {
        "url": url, "output": "json", "fl": "timestamp,original,statuscode,mimetype",
        "filter": "statuscode:200", "collapse": "digest", "limit": limite,
    }
    try:
        reponse = client.get(CDX_URL, params=parametres, headers=HEADERS, timeout=timeout)
        reponse.raise_for_status()
        donnees = reponse.json()
    except (requests.RequestException, ValueError) as exc:
        raise ValueError(f"Internet Archive indisponible : {exc}") from None
    lignes = donnees[1:] if isinstance(donnees, list) and len(donnees) > 1 else []
    captures = []
    for ligne in lignes:
        if len(ligne) < 3:
            continue
        captures.append({"timestamp": ligne[0], "url": ligne[1],
                         "statut": ligne[2], "type": ligne[3] if len(ligne) > 3 else ""})
    return captures


def recuperer_texte(capture, session=None, timeout=30, taille_max=2_000_000):
    """Telecharge une capture et retourne son texte utile tronque.

    La lecture est bornee a ``taille_max`` octets : le corps complet n'est pas
    conserve en memoire pour une page volumineuse.
    """
    client = session or requests
    cible = f"{BASE_ARCHIVE}/{capture['timestamp']}id_/{capture['url']}"
    try:
        reponse = client.get(cible, headers=HEADERS, timeout=timeout, stream=True)
        reponse.raise_for_status()
    except requests.RequestException as exc:
        raise ValueError(f"capture {capture['timestamp']} indisponible : {exc}") from None
    lecteur = getattr(reponse, "iter_content", None)
    if lecteur is None:
        return extraire_texte(reponse.text[:taille_max])
    morceaux = []
    lus = 0
    try:
        for morceau in lecteur(chunk_size=65_536):
            morceaux.append(morceau)
            lus += len(morceau)
            if lus >= taille_max:
                break
    except requests.RequestException as exc:
        raise ValueError(f"capture {capture['timestamp']} interrompue : {exc}") from None
    brut = b"".join(morceaux)[:taille_max]
    return extraire_texte(brut.decode(getattr(reponse, "encoding", None) or "utf-8", errors="replace"))


def comparer_textes(avant, apres, contexte=2, lignes_max=400):
    """Diff lisible : ajouts, suppressions et lignes inchangees de contexte."""
    diff = list(difflib.unified_diff((avant or "").splitlines(),
                                     (apres or "").splitlines(),
                                     fromfile="avant", tofile="apres",
                                     lineterm="", n=contexte))
    ajouts = sum(1 for ligne in diff if ligne.startswith("+") and not ligne.startswith("+++"))
    suppressions = sum(1 for ligne in diff if ligne.startswith("-") and not ligne.startswith("---"))
    return {
        "identique": (avant or "") == (apres or ""),
        "ajouts": ajouts,
        "suppressions": suppressions,
        "diff": diff[:lignes_max],
        "tronque": len(diff) > lignes_max,
    }


def chronologie(captures):
    """Ordonne les captures disponibles avec leur URL d'archive verifiable."""
    entrees = []
    for capture in sorted(captures, key=lambda item: item.get("timestamp", "")):
        entrees.append({
            "timestamp": capture.get("timestamp"),
            "url": capture.get("url"),
            "archive_url": f"{BASE_ARCHIVE}/{capture.get('timestamp')}/{capture.get('url')}",
            "statut": capture.get("statut"),
        })
    return entrees


def analyser(url, capture_a, capture_b, session=None, timeout=30):
    """Compare deux captures et conserve leurs URL et horodatages."""
    texte_a = recuperer_texte(capture_a, session=session, timeout=timeout)
    texte_b = recuperer_texte(capture_b, session=session, timeout=timeout)
    comparaison = comparer_textes(texte_a, texte_b)
    return {
        "url": url,
        "captures": [capture_a, capture_b],
        "chronologie": chronologie([capture_a, capture_b]),
        "comparaison": comparaison,
        "avertissement": "Une difference d'archive est une observation historique, "
                         "pas une preuve de modification malveillante.",
    }


def exporter_json(resultat):
    return json.dumps(resultat, ensure_ascii=False, indent=2) + "\n"


def exporter_markdown(resultat):
    captures = resultat["captures"]
    comparaison = resultat["comparaison"]
    lignes = [f"# Archive Change Watcher — {resultat['url']}", ""]
    lignes.append(f"> {resultat['avertissement']}")
    lignes.append("")
    lignes.append("## Captures comparees")
    lignes.append("")
    lignes.append("| Horodatage | URL d'origine | URL archive |")
    lignes.append("|---|---|---|")
    for entree in resultat.get("chronologie") or chronologie(captures):
        lignes.append(f"| {entree['timestamp']} | {entree['url']} | {entree['archive_url']} |")
    lignes.extend(["", "## Differences", ""])
    lignes.append(f"- Ajouts : {comparaison['ajouts']}")
    lignes.append(f"- Suppressions : {comparaison['suppressions']}")
    lignes.append(f"- Contenus identiques : {'oui' if comparaison['identique'] else 'non'}")
    lignes.extend(["", "```diff"])
    lignes.extend(comparaison["diff"][:200])
    lignes.append("```")
    return "\n".join(lignes) + "\n"


def archive_change_watcher():
    """Selection de deux captures, comparaison et export."""
    titre("ARCHIVE CHANGE WATCHER", C_OSINT)
    cible = demander("URL ou domaine (ex: example.com)").strip()
    if not cible:
        warn("Cible vide.")
        return
    try:
        with attente("Consultation de l'index Internet Archive"):
            captures = lister_captures(cible)
    except ValueError as exc:
        warn(str(exc))
        return
    if len(captures) < 2:
        warn("Moins de deux captures disponibles : comparaison impossible.")
        return

    kv("Captures", [("Disponibles", len(captures)),
                    ("Plus recente", captures[-1]["timestamp"]),
                    ("Plus ancienne", captures[0]["timestamp"])], C_OSINT)
    for index, capture in enumerate(captures, 1):
        console.print(f"  {index:>2}. {capture['timestamp']}  {capture['url']}")

    premiers = demander("Premiere capture (numero)", "1").strip()
    second = demander("Seconde capture (numero)", str(len(captures))).strip()
    if not (premiers.isdigit() and second.isdigit()):
        warn("Numeros attendus.")
        return
    index_a, index_b = int(premiers), int(second)
    if not (1 <= index_a <= len(captures) and 1 <= index_b <= len(captures)) or index_a == index_b:
        warn("Indices invalides ou identiques.")
        return

    try:
        with attente("Telechargement des captures"):
            resultat = analyser(cible, captures[index_a - 1], captures[index_b - 1])
    except ValueError as exc:
        warn(str(exc))
        return

    comparaison = resultat["comparaison"]
    kv("Comparaison", [
        ("Ajouts", comparaison["ajouts"]),
        ("Suppressions", comparaison["suppressions"]),
        ("Identique", "oui" if comparaison["identique"] else "non"),
    ], C_OSINT)
    if comparaison["diff"]:
        console.print(Panel("\n".join(comparaison["diff"][:30]), title="Diff (extrait)",
                            border_style=C_OSINT))

    format_export = demander("Exporter (json/markdown/rien)", "rien").lower()
    if format_export in {"json", "markdown"}:
        contenu = exporter_json(resultat) if format_export == "json" else exporter_markdown(resultat)
        extension = "json" if format_export == "json" else "md"
        destination = Path(demander("Fichier de sortie", f"archive-diff.{extension}")).expanduser()
        if destination.exists():
            warn("Le fichier existe deja : choisissez un autre nom.")
            return
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(contenu, encoding="utf-8")
        except OSError as exc:
            warn(f"Ecriture impossible : {exc}")
            return
        ok(f"Export ecrit : {destination.resolve()}")
