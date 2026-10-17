"""TLS Policy Diff : instantanes structures et comparaison de configurations.

Reutilise ``recuperer_certificat`` du module de certificat existant : la
connexion TLS est verifiee normalement, avec un delai d'expiration explicite.
"""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from rich.table import Table

from core.common import BX, C_CYBER, console, demander, kv, ok, titre, warn
from core.config import DATA_DIR
from modules.cyber.ssl_cert import recuperer_certificat

HISTORY_FILE = Path(DATA_DIR) / "tls_history.json"
CHAMPS = ("fingerprint_sha256", "serial", "issuer", "subject", "sans",
          "not_before", "not_after", "tls_version", "cipher")


def _nom_rdn(rdns):
    morceaux = []
    for rdn in rdns or ():
        for attribut, valeur in rdn:
            morceaux.append(f"{attribut}={valeur}")
    return ", ".join(morceaux)


def _date_iso(brut):
    try:
        return datetime.strptime(brut, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def instantane(hote, port=443, timeout=10, recuperer=recuperer_certificat):
    """Capture un instantane structure d'une configuration TLS observable."""
    donnees = recuperer(hote, port, timeout)
    cert = donnees["cert"] or {}
    empreinte = hashlib.sha256(donnees["der"] or b"").hexdigest()
    sans = [valeur for type_nom, valeur in cert.get("subjectAltName", ()) if type_nom == "DNS"]
    cipher = donnees.get("cipher") or (None, None, None)
    return {
        "hote": hote,
        "port": port,
        "captured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "fingerprint_sha256": empreinte,
        "serial": cert.get("serialNumber"),
        "issuer": _nom_rdn(cert.get("issuer")),
        "subject": _nom_rdn(cert.get("subject")),
        "sans": sans,
        "not_before": cert.get("notBefore"),
        "not_after": cert.get("notAfter"),
        "tls_version": donnees.get("version"),
        "cipher": f"{cipher[0]} ({cipher[1]} bits)" if cipher and cipher[0] else None,
    }


def comparer(avant, apres, maintenant=None):
    """Compare deux instantanes et qualifie les changements observes."""
    maintenant = maintenant or datetime.now(timezone.utc)
    changements = []
    for champ in CHAMPS:
        if avant.get(champ) != apres.get(champ):
            changements.append({"champ": champ, "avant": avant.get(champ),
                                "apres": apres.get(champ)})
    expiration = _date_iso(apres.get("not_after"))
    jours = (expiration - maintenant).days if expiration else None
    renouvellement = bool(avant.get("serial") and apres.get("serial")
                          and avant["serial"] != apres["serial"])
    return {
        "hote": apres.get("hote"),
        "changements": changements,
        "modifie": bool(changements),
        "renouvellement": renouvellement,
        "jours_restants": jours,
        "expire_bientot": jours is not None and jours < 30,
        "risques": _risques(changements),
    }


def _risques(changements):
    champs = {change["champ"] for change in changements}
    risques = []
    if "fingerprint_sha256" in champs and "serial" not in champs:
        risques.append("empreinte differente sans changement de numero de serie")
    if "issuer" in champs:
        risques.append("changement d'autorite emettrice")
    if "tls_version" in champs:
        risques.append("version TLS modifiee : verifier la politique du service")
    if "cipher" in champs:
        risques.append("suite de chiffrement modifiee")
    return risques


def charger_historique():
    if not HISTORY_FILE.is_file():
        return []
    try:
        donnees = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return donnees if isinstance(donnees, list) else []


def enregistrer(instantane_donnees, limite=200):
    historique = charger_historique()
    historique.append(instantane_donnees)
    historique = historique[-limite:]
    try:
        HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        HISTORY_FILE.write_text(json.dumps(historique, ensure_ascii=False, indent=2) + "\n",
                                encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"historique non ecrit : {exc}") from None
    return len(historique)


def exporter_json(comparaison):
    return json.dumps(comparaison, ensure_ascii=False, indent=2) + "\n"


def exporter_markdown(comparaison):
    lignes = [f"# Comparaison TLS — {comparaison.get('hote')}", ""]
    changement = "des changements" if comparaison["modifie"] else "aucun changement"
    lignes.append(f"- Resultat : {changement}")
    lignes.append(f"- Renouvellement : {'oui' if comparaison['renouvellement'] else 'non'}")
    jours = comparaison.get("jours_restants")
    lignes.append(f"- Expiration : {jours} jour(s)" if jours is not None else "- Expiration : inconnue")
    lignes.extend(["", "## Changements observes", ""])
    if not comparaison["changements"]:
        lignes.append("Aucun champ different entre les deux instantanes.")
    else:
        lignes.append("| Champ | Avant | Apres |")
        lignes.append("|---|---|---|")
        for change in comparaison["changements"]:
            lignes.append(f"| {change['champ']} | {change['avant']} | {change['apres']} |")
    lignes.extend(["", "## Risques potentiels", ""])
    lignes.extend([f"- {risque}" for risque in comparaison["risques"]] or
                  ["Aucun signal supplementaire ; une observation n'est pas une preuve d'incident."])
    return "\n".join(lignes) + "\n"


def _afficher(instantane_donnees):
    kv("Instantane TLS", [
        ("Hote", f"{instantane_donnees['hote']}:{instantane_donnees['port']}"),
        ("Capture", instantane_donnees["captured_at"]),
        ("Fingerprint", instantane_donnees["fingerprint_sha256"][:32] + "..."),
        ("Serie", instantane_donnees["serial"]),
        ("Emetteur", instantane_donnees["issuer"]),
        ("Valide jusqu'au", instantane_donnees["not_after"]),
        ("TLS", instantane_donnees["tls_version"]),
        ("Cipher", instantane_donnees["cipher"]),
    ], C_CYBER)


def tls_policy_diff():
    """Capture, compare et exporte des instantanes TLS."""
    titre("TLS POLICY DIFF", C_CYBER)
    while True:
        choix = demander("Action (capturer/comparer/historique/retour)", "capturer").lower()
        if choix in {"retour", "r", "quitter", "q"}:
            return
        if choix == "capturer":
            hote = demander("Hote (ex: example.com)").strip()
            if not hote:
                warn("Hote vide.")
                continue
            try:
                donnees = instantane(hote)
            except (OSError, ValueError) as exc:
                warn(f"Capture impossible : {type(exc).__name__}: {exc}")
                continue
            try:
                enregistrer(donnees)
            except ValueError as exc:
                warn(str(exc))
            _afficher(donnees)
            ok("Instantane enregistre dans l'historique local.")
        elif choix == "comparer":
            historique = charger_historique()
            if len(historique) < 2:
                warn("Deux instantanes sont necessaires.")
                continue
            avant, apres = historique[-2], historique[-1]
            resultat = comparer(avant, apres)
            table = Table(box=BX, border_style=C_CYBER, header_style=f"bold {C_CYBER}")
            table.add_column("Champ")
            table.add_column("Avant")
            table.add_column("Apres")
            for change in resultat["changements"]:
                table.add_row(change["champ"], str(change["avant"]), str(change["apres"]))
            if resultat["changements"]:
                console.print(table)
            else:
                ok("Aucun changement entre les deux derniers instantanes.")
            if resultat["expire_bientot"]:
                warn(f"Expiration dans {resultat['jours_restants']} jour(s).")
            for risque in resultat["risques"]:
                warn(risque)
            exporter = demander("Exporter (json/markdown/rien)", "rien").lower()
            if exporter in {"json", "markdown"}:
                contenu = exporter_json(resultat) if exporter == "json" else exporter_markdown(resultat)
                destination = Path(demander("Fichier de sortie", f"tls-diff.{ 'json' if exporter == 'json' else 'md'}")).expanduser()
                try:
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_text(contenu, encoding="utf-8")
                except OSError as exc:
                    warn(f"Ecriture impossible : {exc}")
                else:
                    ok(f"Export ecrit : {destination.resolve()}")
        elif choix == "historique":
            historique = charger_historique()
            if not historique:
                warn("Historique vide.")
                continue
            table = Table(box=BX, border_style=C_CYBER, header_style=f"bold {C_CYBER}")
            table.add_column("#", justify="right")
            table.add_column("Hote")
            table.add_column("Capture")
            table.add_column("Fingerprint")
            for index, entree in enumerate(historique[-20:], 1):
                table.add_row(str(index), entree.get("hote", "?"), entree.get("captured_at", "?"),
                              (entree.get("fingerprint_sha256") or "")[:16])
            console.print(table)
        else:
            warn("Action inconnue : capturer, comparer, historique ou retour.")
