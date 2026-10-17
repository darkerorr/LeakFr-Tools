"""Transmission manuelle d'un rapport JSON deja genere.

Le script genere par le builder n'effectue aucun envoi : l'utilisateur choisit
explicitement un fichier local, le previsualise, peut retirer les sections
sensibles, puis confirme l'envoi vers l'URL qu'il fournit.
"""
import copy
import importlib
import json
from pathlib import Path
from urllib.parse import urlparse

from rich.panel import Panel
from rich.table import Table

from core.common import BX, C_GOLD, console, demander, kv, ok, titre, warn

# La categorie CYBER expose une fonction du meme nom : on charge le module.
webhook_lab = importlib.import_module("modules.cyber.webhook_lab")

SCHEMA = "leakfr.system-report.v1"

SECTIONS_SENSIBLES = {
    "empreinte": "Empreinte machine (HWID)",
    "session": "Session et compte",
    "reseau": "Reseau",
    "fichiers": "Fichiers selectionnes",
}

LIBELLES_STATUT = {"ok": "reussie", "partiel": "partielle",
                   "indisponible": "indisponible", "erreur": "en erreur"}


def lister_rapports(dossier):
    """Retourne les rapports JSON valides du dossier, du plus recent au plus ancien."""
    base = Path(dossier).expanduser()
    if not base.is_dir():
        return []
    rapports = []
    for chemin in base.glob("*.json"):
        try:
            donnees = json.loads(chemin.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(donnees, dict) and donnees.get("schema") == SCHEMA:
            rapports.append(chemin)
    return sorted(rapports, key=lambda chemin: chemin.stat().st_mtime, reverse=True)


def charger_rapport(chemin):
    """Charge un rapport et verifie son schema minimal."""
    try:
        donnees = json.loads(Path(chemin).read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON invalide : {exc.msg}") from None
    if not isinstance(donnees, dict) or not isinstance(donnees.get("sections"), dict):
        raise ValueError("ce fichier n'est pas un rapport LeakFr")
    return donnees


def sections_presentes(rapport):
    return list(rapport.get("sections", {}))


def sections_sensibles_presentes(rapport):
    return [cle for cle in rapport.get("sections", {}) if cle in SECTIONS_SENSIBLES]


def retirer_sections(rapport, sections):
    """Retourne une copie sans les sections demandees, synthese recalculee."""
    copie = copy.deepcopy(rapport)
    for cle in sections:
        copie.get("sections", {}).pop(cle, None)
    statuts = [section.get("statut", "erreur") for section in copie["sections"].values()]
    synthese = dict(copie.get("synthese", {}))
    synthese.update({
        "sections_total": len(statuts),
        "ok": statuts.count("ok"),
        "partiel": statuts.count("partiel"),
        "indisponible": statuts.count("indisponible"),
        "erreur": statuts.count("erreur"),
        "statut": ("erreur" if statuts and statuts.count("erreur") == len(statuts)
                   else "partiel" if any(statut != "ok" for statut in statuts) else "ok"),
        "sections_exclues": sorted(set(copie.get("synthese", {}).get("sections_exclues", []))
                                   | set(sections)),
    })
    copie["synthese"] = synthese
    return copie


def _taille(octets):
    kilo = octets / 1024
    return f"{kilo:.1f} Ko" if kilo >= 1 else f"{octets} o"


def _choisir_rapport(dossier):
    rapports = lister_rapports(dossier)
    if not rapports:
        warn(f"Aucun rapport JSON trouve dans {Path(dossier).expanduser()}.")
        return None
    table = Table(box=BX, border_style=C_GOLD, header_style=f"bold {C_GOLD}")
    table.add_column("#", justify="right", width=3)
    table.add_column("Fichier")
    table.add_column("Taille", justify="right")
    for index, chemin in enumerate(rapports, 1):
        table.add_row(str(index), chemin.name, _taille(chemin.stat().st_size))
    console.print(table)
    while True:
        saisie = demander("Numero du rapport a transmettre", "1").strip()
        if not saisie:
            return None
        if not saisie.isdigit() or not 1 <= int(saisie) <= len(rapports):
            warn(f"Choix attendu entre 1 et {len(rapports)}.")
            continue
        return rapports[int(saisie) - 1]


def _apercu(rapport, sections):
    lignes = [
        f"Identifiant : {rapport.get('id', '?')}",
        f"Genere le   : {rapport.get('genere_le', '?')}",
        f"Sections    : {len(rapport.get('sections', {}))} ({', '.join(sections) or 'aucune'})",
        f"Statut      : {LIBELLES_STATUT.get(rapport.get('synthese', {}).get('statut'), '?')}",
        f"Taille      : {_taille(len(json.dumps(rapport, ensure_ascii=False)))}",
    ]
    console.print(Panel("\n".join(lignes), title="Rapport a transmettre", border_style=C_GOLD))


def _confirmer(destination):
    while True:
        reponse = demander(f"Confirmer l'envoi vers {destination} ? (oui/non)", "non").strip().lower()
        if reponse in {"oui", "o", "y"}:
            return True
        if reponse in {"non", "n", "no"}:
            return False
        warn("Reponse attendue : oui ou non.")


def _demander_url():
    while True:
        try:
            return webhook_lab.valider_url(demander("URL de destination"))
        except ValueError as exc:
            warn(f"URL refusee : {exc}")


def _demander_exclusions(rapport):
    sensibles = sections_sensibles_presentes(rapport)
    if not sensibles:
        return []
    detail = ", ".join(SECTIONS_SENSIBLES[cle] for cle in sensibles)
    console.print(f"[bold]Sections sensibles detectees :[/] {detail}")
    while True:
        reponse = demander("Exclure ces sections avant l'envoi (oui/non/tout)", "oui").strip().lower()
        if reponse in {"oui", "o", "y"}:
            return list(sensibles)
        if reponse in {"non", "n", "no"}:
            return []
        if reponse == "tout":
            return list(rapport.get("sections", {}))
        warn("Reponse attendue : oui, non ou tout.")


def transmettre_rapport(dossier):
    """Parcours manuel : choix du fichier, apercu, expurgation, confirmation, envoi."""
    titre("TRANSMISSION MANUELLE D'UN RAPPORT", C_GOLD)
    console.print("[dim]Aucun envoi automatique : le fichier local reste inchange.[/]\n")

    chemin = _choisir_rapport(dossier)
    if chemin is None:
        return None
    try:
        rapport = charger_rapport(chemin)
    except ValueError as exc:
        warn(str(exc))
        return None

    exclusions = _demander_exclusions(rapport)
    donnees = retirer_sections(rapport, exclusions) if exclusions else rapport
    _apercu(donnees, sections_presentes(donnees))
    if exclusions:
        console.print(f"[yellow]Retire : {', '.join(exclusions)}[/]")

    url = _demander_url()
    saisie = demander("Delai maximal (secondes)", "10").strip() or "10"
    try:
        timeout = webhook_lab.valider_timeout(saisie)
    except ValueError as exc:
        warn(str(exc))
        return None

    destination = urlparse(url).hostname or url
    if not _confirmer(destination):
        warn("Transmission annulee ; le rapport local est conserve.")
        return None

    resultat = webhook_lab.envoyer_payload(url, donnees, timeout=timeout)
    kv("Resultat", [
        ("Statut HTTP", str(resultat["statut"]) if resultat["statut"] else "-"),
        ("Duree", f"{resultat['duree_ms']:.0f} ms"),
        ("Resultat", "succes" if resultat["ok"] else "echec"),
        ("Erreur", resultat["erreur"] or "-"),
    ], C_GOLD)
    if resultat["ok"]:
        ok(f"Rapport transmis (statut {resultat['statut']}).")
    else:
        warn("Envoi echoue ; le rapport local est conserve intact.")
    return resultat
