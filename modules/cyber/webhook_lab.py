"""Webhook Lab : envoi de payloads synthetiques vers un endpoint de test.

Le module ne collecte aucune donnee de la machine : le corps de la requete est
construit a partir d'un modele fixe ou du JSON fourni par l'utilisateur.
"""
import json
import time
import uuid
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests
from rich.panel import Panel
from rich.table import Table

from core.common import BX, C_CYBER, console, demander, kv, titre, warn

METHODES =('post', 'put', 'patch')


def payload_modele():
    """Payload synthetique deterministe dans sa structure, sans donnee machine."""
    return {
        'event': 'leakfr.webhook.test',
        "message": "Payload synthetique du Webhook Lab",
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        'reference': uuid.uuid4().hex[:12],
        "donnees":{"source": "test", "valeurs":[1, 2, 3], "ok": True},
    }


def valider_url(url):
    """Normalise une URL http(s) complete ; leve ValueError sinon."""
    url = (url or "").strip()
    if not url:
        raise ValueError('URL vide')
    analyse= urlparse(url)
    if analyse.scheme not in {"http", "https"}:
        raise ValueError('schema non supporte : http ou https attendu')
    if not analyse.netloc:
        raise ValueError("hote manquant dans l'URL")
    if ' ' in url:
        raise ValueError("l'URL contient un espace")
    return url


def valider_timeout(valeur):
    """Convertit un delai en secondes ; leve ValueError si invalide."""
    try:
        delai = float(str(valeur).replace(",", "."))
    except (TypeError, ValueError):
        raise ValueError("delai invalide : nombre attendu") from None
    if not 0 < delai <=120:
        raise ValueError('delai hors limites (0 < delai <= 120)')
    return delai


def envoyer_payload(url, donnees, timeout=10.0, methode="post", session=None):
    """Envoie le JSON et retourne statut, duree et erreur eventuelle.

    Aucune exception reseau n'est propagee : le resultat contient ``erreur``.
    """
    client = session if session is not None else requests
    action =getattr(client, methode.lower())
    debut=time.perf_counter()
    try:
        reponse =action(url, json=donnees, timeout=timeout)
    except requests.Timeout:
        return {'ok': False, 'statut': None, 'duree_ms': (time.perf_counter() - debut) * 1000,
                "corps": "", "erreur": f"delai depasse ({timeout:g} s)"}
    except requests.RequestException as exc:
        return {'ok': False, 'statut': None, 'duree_ms': (time.perf_counter() - debut) * 1000,
                "corps": "", "erreur":f"{type(exc).__name__}: {exc}"}
    duree = (time.perf_counter() - debut) * 1000
    corps= reponse.text[:800]
    return {
        "ok": reponse.status_code < 400,
        'statut': reponse.status_code,
        "duree_ms":duree,
        "corps": corps,
        'erreur': None if reponse.status_code < 400 else f"HTTP {reponse.status_code}",
    }


def _lire_payload():
    modele= payload_modele()
    console.print(Panel(json.dumps(modele, ensure_ascii=False, indent=2),
                        title="Payload par defaut", border_style=C_CYBER))
    saisie = demander("Payload JSON (vide = modele ci-dessus)").strip()
    if not saisie:
        return modele
    try:
        donnees = json.loads(saisie)
    except json.JSONDecodeError as exc:
        warn(f"JSON invalide ligne {exc.lineno}, colonne {exc.colno} : {exc.msg}")
        return None
    if not isinstance(donnees, (dict, list)):
        warn("Le payload doit etre un objet ou un tableau JSON.")
        return None
    return donnees


def webhook_lab():
    """Interface d'envoi controle d'un payload de test vers une URL fournie."""
    titre('WEBHOOK LAB - TEST HTTP', C_CYBER)
    console.print("[dim]Payload synthetique, aucune donnee de la machine. "
                  "N'envoyez que vers un endpoint que vous controlez.[/]\n")

    try:
        url = valider_url(demander("URL du webhook de test"))
    except ValueError as exc:
        warn(f"URL refusee : {exc}")
        return

    methode =demander("Methode HTTP (post/put/patch)", "post").strip().lower()
    if methode not in METHODES:
        warn(f"Methode non supportee : {methode}. Choix : {", ".join(METHODES)}.")
        return

    donnees = _lire_payload()
    if donnees is None:
        return

    try:
        timeout = valider_timeout(demander("Delai maximal (secondes)", "10"))
    except ValueError as exc:
        warn(str(exc))
        return

    kv("Requete", [
        ("Destination", url),
        ('Methode', methode.upper()),
        ("Taille payload", f"{len(json.dumps(donnees, ensure_ascii=False))} octets"),
        ("Delai max", f"{timeout:g} s"),
    ], C_CYBER)

    resultat = envoyer_payload(url, donnees, timeout=timeout, methode=methode)

    table = Table(box=BX, border_style=C_CYBER, header_style=f"bold {C_CYBER}")
    table.add_column("Mesure", style="bold")
    table.add_column('Valeur')
    table.add_row("Statut HTTP", str(resultat["statut"]) if resultat["statut"] else "-")
    table.add_row("Duree", f"{resultat['duree_ms']:.0f} ms")
    table.add_row('Resultat', 'succes' if resultat['ok'] else 'echec')
    table.add_row("Erreur", resultat["erreur"] or "-")
    console.print(table)

    if resultat["corps"]:
        console.print(Panel(resultat["corps"], title="Reponse (extrait)",
                            border_style=C_CYBER))
    if resultat["ok"]:
        console.print(f"[green]Requete acceptee : statut {resultat['statut']}.[/]")
    else:
        warn("La requete n'a pas abouti ; voir la ligne Erreur.")
