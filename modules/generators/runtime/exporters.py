"""Exporteurs autonomes (stdlib) : un rapport structure, trois formats.

Les trois formats derivent du meme dictionnaire pour rester coherents.
Aucun script distant n'est inclus dans le HTML.
"""
import json
import unicodedata
from html import escape as _echapper

LIBELLES_STATUT = {
    "ok": "reussie",
    "partiel": "partielle",
    "indisponible": "indisponible",
    "erreur": "en erreur",
}


def _ancre(texte):
    texte = unicodedata.normalize("NFKD", str(texte)).encode("ascii", "ignore").decode()
    return "".join(car if car.isalnum() else "-" for car in texte.lower()).strip("-")


def _valeur_lisible(valeur):
    if valeur is None:
        return "inconnu"
    if isinstance(valeur, bool):
        return "oui" if valeur else "non"
    if isinstance(valeur, (int, float)):
        return str(valeur)
    return str(valeur)


def _table_lignes(donnees, prefixe=""):
    """Aplatit un dictionnaire imbrique en lignes (cle, valeur)."""
    lignes = []
    for cle, valeur in donnees.items():
        libelle = f"{prefixe}{cle}"
        if isinstance(valeur, dict) and valeur:
            lignes.extend(_table_lignes(valeur, f"{libelle} · "))
        elif isinstance(valeur, list) and valeur and all(isinstance(e, dict) for e in valeur):
            lignes.append((libelle, f"{len(valeur)} entree(s)"))
        elif isinstance(valeur, list):
            lignes.append((libelle, ", ".join(_valeur_lisible(v) for v in valeur) or "vide"))
        else:
            lignes.append((libelle, _valeur_lisible(valeur)))
    return lignes


def vers_json(rapport):
    return json.dumps(rapport, ensure_ascii=False, indent=2) + "\n"


def vers_markdown(rapport):
    synthese = rapport.get("synthese", {})
    lignes = [f"# {rapport.get('nom', 'Rapport systeme')}", ""]
    lignes.append(f"- **Identifiant** : `{rapport.get('id')}`")
    lignes.append(f"- **Genere le** : {rapport.get('genere_le')}")
    lignes.append(f"- **Profil** : {rapport.get('profil')}")
    lignes.append(f"- **Plateforme** : {rapport.get('plateforme')}")
    lignes.append(f"- **Statut global** : {LIBELLES_STATUT.get(synthese.get('statut'), synthese.get('statut'))}")
    lignes.append("")

    lignes.append("## Sommaire")
    for numero, (cle, section) in enumerate(rapport.get("sections", {}).items(), 1):
        lignes.append(f"{numero}. [{section['titre']}](#{_ancre(section['titre'])})")
    lignes.append(f"{len(rapport.get('sections', {})) + 1}. [Erreurs et limites](#erreurs-et-limites)")
    lignes.append("")

    lignes.append("## Synthese")
    lignes.append("")
    lignes.append("| Mesure | Valeur |")
    lignes.append("|---|---|")
    for cle in ("sections_total", "ok", "partiel", "indisponible", "erreur", "duree_ms"):
        if cle in synthese:
            lignes.append(f"| {cle} | {_valeur_lisible(synthese[cle])} |")
    lignes.append("")

    for cle, section in rapport.get("sections", {}).items():
        lignes.append(f"## {section['titre']}")
        lignes.append("")
        lignes.append(f"*Statut : {LIBELLES_STATUT.get(section['statut'], section['statut'])}*")
        lignes.append("")
        lignes.extend(_markdown_donnees(section.get("donnees")))
        lignes.append("")

    lignes.append("## Erreurs et limites")
    lignes.append("")
    erreurs = [(cle, section) for cle, section in rapport.get("sections", {}).items()
               if section.get("erreurs")]
    if not erreurs:
        lignes.append("Aucune erreur enregistree.")
    for cle, section in erreurs:
        for erreur in section["erreurs"]:
            solution = f" — {erreur['solution']}" if erreur.get("solution") else ""
            lignes.append(f"- **{section['titre']}** : {erreur.get('type')} — "
                          f"{erreur.get('message')}{solution}")
    lignes.append("")
    return "\n".join(lignes)


def _markdown_donnees(donnees):
    if donnees is None:
        return ["*Aucune donnee.*"]
    if isinstance(donnees, dict):
        lignes = ["| Champ | Valeur |", "|---|---|"]
        for cle, valeur in _table_lignes(donnees):
            lignes.append(f"| {cle} | {_valeur_lisible(valeur)} |")
        return lignes
    if isinstance(donnees, list):
        return [f"- {_valeur_lisible(element)}" for element in donnees] or ["*Aucune donnee.*"]
    return [str(donnees)]


def vers_html(rapport):
    synthese = rapport.get("synthese", {})
    parties = [
        "<!DOCTYPE html>",
        '<html lang="fr"><head><meta charset="utf-8">',
        f"<title>{_echapper(str(rapport.get('nom', 'Rapport systeme')))}</title>",
        "<style>",
        "body{font-family:system-ui,sans-serif;margin:2rem auto;max-width:60rem;padding:0 1rem;color:#1d2433}",
        "h1{border-bottom:2px solid #2f6feb;padding-bottom:.4rem}",
        "h2{margin-top:2rem;border-bottom:1px solid #d7dce5;padding-bottom:.2rem}",
        "table{border-collapse:collapse;width:100%;margin:.8rem 0}",
        "th,td{border:1px solid #d7dce5;padding:.35rem .6rem;text-align:left;vertical-align:top}",
        "th{background:#eef2f9}",
        ".ok{color:#1a7f37}.partiel{color:#9a6700}.indisponible{color:#57606a}.erreur{color:#cf222e}",
        ".meta{color:#57606a;font-size:.9rem}",
        "</style></head><body>",
        f"<h1>{_echapper(str(rapport.get('nom', 'Rapport systeme')))}</h1>",
        f'<p class="meta">Identifiant {_echapper(str(rapport.get("id")))} — '
        f'genere le {_echapper(str(rapport.get("genere_le")))} — '
        f'profil {_echapper(str(rapport.get("profil")))}</p>',
    ]
    parties.append("<h2>Synthese</h2><table><tr><th>Mesure</th><th>Valeur</th></tr>")
    for cle in ("sections_total", "ok", "partiel", "indisponible", "erreur", "duree_ms"):
        if cle in synthese:
            parties.append(f"<tr><td>{_echapper(cle)}</td>"
                           f"<td>{_echapper(_valeur_lisible(synthese[cle]))}</td></tr>")
    parties.append("</table>")

    for cle, section in rapport.get("sections", {}).items():
        partie = section["statut"]
        parties.append(f'<h2 id="{_ancre(section["titre"])}">{_echapper(section["titre"])}</h2>')
        parties.append(f'<p class="{_echapper(partie)}">Statut : '
                       f'{_echapper(LIBELLES_STATUT.get(partie, partie))}</p>')
        parties.extend(_html_donnees(section.get("donnees")))
        for erreur in section.get("erreurs", []):
            solution = f" — {erreur['solution']}" if erreur.get("solution") else ""
            parties.append(f'<p class="erreur">{_echapper(erreur.get("type", "erreur"))} : '
                           f'{_echapper(erreur.get("message", ""))}{_echapper(solution)}</p>')

    parties.append("</body></html>")
    return "\n".join(parties) + "\n"


def _html_donnees(donnees):
    if donnees is None:
        return ["<p><em>Aucune donnee.</em></p>"]
    if isinstance(donnees, dict):
        lignes = ["<table><tr><th>Champ</th><th>Valeur</th></tr>"]
        for cle, valeur in _table_lignes(donnees):
            lignes.append(f"<tr><td>{_echapper(str(cle))}</td>"
                          f"<td>{_echapper(_valeur_lisible(valeur))}</td></tr>")
        lignes.append("</table>")
        return lignes
    if isinstance(donnees, list):
        return ["<ul>" + "".join(f"<li>{_echapper(_valeur_lisible(e))}</li>" for e in donnees)
                + "</ul>"] if donnees else ["<p><em>Aucune donnee.</em></p>"]
    return [f"<p>{_echapper(str(donnees))}</p>"]


EXPORTEURS = {
    "json": ("json", vers_json),
    "markdown": ("md", vers_markdown),
    "html": ("html", vers_html),
}

EXPORTERS = EXPORTEURS
