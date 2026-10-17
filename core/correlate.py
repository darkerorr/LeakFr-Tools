"""Correlation d'observations a l'interieur d'un dossier d'investigation.

Le module relie des valeurs identiques ou proches entre sources et notes, en
conservant l'origine de chaque occurrence. Une correspondance technique n'est
jamais presentee comme une identification de personne.
"""
import json
import re
from urllib.parse import urlparse

from core.cases import obtenir_case

REGEX_URL = re.compile(r"https?://[^\s<>\"')\]]+", re.IGNORECASE)
REGEX_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
REGEX_IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
REGEX_PSEUDO = re.compile(r"(?<![\w@./])@[A-Za-z0-9_.-]{2,32}")

TYPES = ("url", "domaine", "email", "ip", "pseudo")


def _domaine_normalise(valeur):
    valeur = valeur.strip().strip(".").lower()
    if valeur.startswith("www."):
        valeur = valeur[4:]
    return valeur


def normaliser_entite(type_entite, valeur):
    """Retourne la forme comparable d'une entite."""
    valeur = (valeur or "").strip()
    if type_entite == "url":
        analyse = urlparse(valeur if "://" in valeur else f"http://{valeur}")
        return _domaine_normalise(analyse.netloc) + (analyse.path.rstrip("/") or "/")
    if type_entite == "email":
        return valeur.lower()
    if type_entite == "pseudo":
        return valeur.lstrip("@").lower().replace("-", "").replace("_", "")
    if type_entite == "domaine":
        return _domaine_normalise(valeur)
    return valeur


def extraire_entites(texte):
    """Extrait les entites techniques d'un texte libre.

    Retourne une liste de dictionnaires ``{type, brut, valeur}``.
    """
    texte = texte or ""
    trouvees = []
    vus = set()

    def ajouter(type_entite, brut):
        normalisee = normaliser_entite(type_entite, brut)
        cle = (type_entite, normalisee)
        if not normalisee or cle in vus:
            return
        vus.add(cle)
        trouvees.append({"type": type_entite, "brut": brut, "valeur": normalisee})

    for url in REGEX_URL.findall(texte):
        ajouter("url", url)
        ajouter("domaine", urlparse(url).netloc)
    sans_url = REGEX_URL.sub(" ", texte)
    for email in REGEX_EMAIL.findall(sans_url):
        ajouter("email", email)
        ajouter("domaine", email.split("@", 1)[1])
    for ip in REGEX_IPV4.findall(sans_url):
        octets = ip.split(".")
        if all(0 <= int(octet) <= 255 for octet in octets):
            ajouter("ip", ip)
    for pseudo in REGEX_PSEUDO.findall(sans_url):
        ajouter("pseudo", pseudo)
    return trouvees


def _provenances(case):
    """Itere sur les textes du dossier avec leur origine."""
    for source in case.get("sources", []):
        texte = " ".join(str(source.get(champ) or "") for champ in
                         ("value", "source_url", "user_note"))
        yield {"origine": "source", "id": source["id"], "outil": source.get("tool_name") or "",
               "extrait": texte.strip()[:300]}, texte
    for note in case.get("notes", []):
        yield {"origine": "note", "id": note["id"], "outil": note.get("kind") or "",
               "extrait": note.get("content", "").strip()[:300]}, note.get("content", "")


def correler_case(case_id):
    """Regroupe les entites d'un dossier avec leurs provenances."""
    case = obtenir_case(case_id)
    if not case:
        raise ValueError(f"dossier inconnu : {case_id}")

    groupes = {}
    for provenance, texte in _provenances(case):
        for entite in extraire_entites(texte):
            cle = (entite["type"], entite["valeur"])
            groupe = groupes.setdefault(cle, {
                "type": entite["type"], "valeur": entite["valeur"],
                "occurrences": 0, "provenances": [],
            })
            groupe["occurrences"] += 1
            if provenance not in groupe["provenances"]:
                groupe["provenances"].append(provenance)

    entites = sorted(groupes.values(), key=lambda item: (-item["occurrences"], item["valeur"]))
    exactes = [entite for entite in entites if len(entite["provenances"]) > 1]
    proches = []
    for index, entite in enumerate(entites):
        for autre in entites[index + 1:]:
            if entite["valeur"] == autre["valeur"]:
                continue
            if entite["type"] == "pseudo" and autre["type"] == "pseudo":
                continue
            relation = _relation_proche(entite, autre)
            if relation:
                proches.append({"a": entite["valeur"], "type_a": entite["type"],
                                "b": autre["valeur"], "type_b": autre["type"],
                                "indice": relation})
    return {
        "case_id": case_id,
        "case_title": case.get("title"),
        "entites": entites,
        "correspondances_exactes": exactes,
        "rapprochements": proches,
        "avertissement": "Une correspondance technique n'etablit pas l'identite d'une personne.",
    }


def _relation_proche(a, b):
    if a["type"] == b["type"] == "domaine":
        if a["valeur"].endswith("." + b["valeur"]) or b["valeur"].endswith("." + a["valeur"]):
            return "sous-domaine"
    if {a["type"], b["type"]} == {"email", "pseudo"}:
        pseudo = a["valeur"] if a["type"] == "pseudo" else b["valeur"]
        email = a["valeur"] if a["type"] == "email" else b["valeur"]
        if email.split("@", 1)[0] == pseudo:
            return "pseudo identique a la partie locale"
    return None


def exporter_json(correlation):
    return json.dumps(correlation, ensure_ascii=False, indent=2) + "\n"


def exporter_markdown(correlation):
    lignes = [f"# Correlation — {correlation['case_title']} (#{correlation['case_id']})", ""]
    lignes.append(f"> {correlation['avertissement']}")
    lignes.append("")
    lignes.append("## Correspondances exactes")
    lignes.append("")
    if not correlation["correspondances_exactes"]:
        lignes.append("Aucune valeur partagee entre plusieurs origines.")
    else:
        lignes.append("| Type | Valeur | Origines |")
        lignes.append("|---|---|---|")
        for entite in correlation["correspondances_exactes"]:
            origines = ", ".join(f"{p['origine']} #{p['id']}" for p in entite["provenances"])
            lignes.append(f"| {entite['type']} | {entite['valeur']} | {origines} |")
    lignes.extend(["", "## Rapprochements moins certains", ""])
    if not correlation["rapprochements"]:
        lignes.append("Aucun rapprochement fonde sur un indice technique.")
    for proche in correlation["rapprochements"]:
        lignes.append(f"- {proche['a']} ({proche['type_a']}) ~ {proche['b']} "
                      f"({proche['type_b']}) : {proche['indice']}")
    lignes.extend(["", "## Provenance detaillee", ""])
    for entite in correlation["entites"]:
        lignes.append(f"### {entite['type']} — {entite['valeur']}")
        for provenance in entite["provenances"]:
            lignes.append(f"- {provenance['origine']} #{provenance['id']}"
                          f" ({provenance['outil'] or 'sans outil'}) : "
                          f"{provenance['extrait'][:160]}")
        lignes.append("")
    return "\n".join(lignes) + "\n"
