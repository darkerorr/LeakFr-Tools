import re
from urllib.parse import quote
import requests
from rich.markup import escape
from core.common import demander, titre, bad, attente, afficher_pagine, C_CYBER, HEADERS

def recherche_cve():
    titre("RECHERCHE CVE", C_CYBER)
    q = demander("Produit / CVE-ID (ex: apache 2.4 ou CVE-2021-44228)")
    if not q:
        return
    try:
        with attente("Interrogation CIRCL / cve.circl.lu"):
            if re.match(r"(?i)^CVE-\d{4}-\d+", q.strip()):
                r = requests.get(f"https://cve.circl.lu/api/cve/{q.strip().upper()}",
                                 headers=HEADERS, timeout=20)
                data = r.json() if r.status_code == 200 else None
                items = [data] if data and data.get("id") else []
            else:
                r = requests.get(f"https://cve.circl.lu/api/search/{quote(q)}",
                                 headers=HEADERS, timeout=25)
                data = r.json() if r.status_code == 200 else {}
                items = (data.get("results") or data.get("data") or [])[:40]
                if isinstance(data, list):
                    items = data[:40]
    except Exception as e:
        bad(f"Erreur : {e}")
        return
    if not items:
        bad("Aucun résultat (API parfois limitée).")
        return
    rows = []
    for it in items:
        if not isinstance(it, dict):
            continue
        cve_id = it.get("id") or it.get("cve") or "?"
        summary = (it.get("summary") or it.get("description") or "")[:80]
        cvss = it.get("cvss") or it.get("cvss3") or it.get("cvssV3") or "-"
        rows.append((cve_id, str(cvss), summary))

    def rendu(row):
        return [f"[bold]{escape(row[0])}[/]", escape(row[1]), escape(row[2])]

    afficher_pagine(f"CVE : {q}", ["CVE", "CVSS", "Résumé"], rows, rendu,
                    lien=lambda r: f"https://nvd.nist.gov/vuln/detail/{r[0]}",
                    par_page=12, fichier="cve_results.csv", couleur=C_CYBER,
                    caption="Source : cve.circl.lu — o N pour ouvrir sur le NVD")
