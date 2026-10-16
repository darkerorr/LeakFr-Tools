import requests
from rich.markup import escape
from core.common import demander, titre, bad, attente, nettoyer_cible, afficher_pagine, C_RECON, HEADERS

def sous_domaines():
    domaine = nettoyer_cible(demander("Domaine"))
    titre(f"SOUS-DOMAINES (crt.sh) : {domaine}", C_RECON)
    try:
        with attente("Interrogation de crt.sh (peut être lent)"):
            r = requests.get("https://crt.sh/",
                             params={"q": f"%.{domaine}", "output": "json"},
                             headers=HEADERS, timeout=40)
            subs = set()
            for entree in r.json():
                for n in entree["name_value"].split("\n"):
                    subs.add(n.strip().lstrip("*."))
    except Exception as e:
        bad(f"Erreur (crt.sh est parfois lent/indisponible) : {e}")
        return
    if not subs:
        bad("Aucun sous-domaine trouvé.")
        return
    rows = [(s,) for s in sorted(subs)]
    afficher_pagine(f"SOUS-DOMAINES DE {domaine}", ["Sous-domaine"], rows,
                    lambda r: [f"[green]{escape(r[0])}[/]"],
                    lien=lambda r: "https://" + r[0], par_page=20,
                    fichier=f"sousdomaines_{domaine}.csv", couleur=C_RECON)
