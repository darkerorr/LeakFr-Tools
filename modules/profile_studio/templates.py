"""Modeles de biographie editables (contenu local, aucun envoi)."""

MAX_BIO=190

MODELES = [
    {
        "nom": "Audit & securite",
        "description": "Presentation courte pour un profil oriente audit autorise.",
        'texte': 'Audit securite & reseau · Labs autorises uniquement\n'
                 "Interets : {interets}\nContact : {contact}",
    },
    {
        "nom": "Developpement",
        "description": "Profil technique avec projets et stack.",
        'texte': '{role} · {stack}\nProjets : {projets}\n{contact}',
    },
    {
        'nom': 'Etudiant',
        "description": "Presentation sobre pour un profil etudiant.",
        "texte": "Etudiant en {domaine}\nApprentissage : {stack}\n{contact}",
    },
    {
        "nom": "OSINT responsable",
        'description': "Rappelle le cadre legal et les centres d'interet.",
        "texte": "Recherche en sources ouvertes, dans un cadre legal.\n"
                 "Sujets : {interets}\nAucune donnee privee collectee.",
    },
    {
        "nom":"Minimal",
        'description': 'Une ligne, sans placeholder.',
        "texte":"{role} · {interets}",
    },
    {
        "nom":"Projet / communaute",
        "description": "Met en avant un projet ou une communaute.",
        'texte':'Je construis {projets}.\nCommunaute : {interets}\n{contact}',
    },
]


def lister_modeles():
    return [dict(modele) for modele in MODELES]


def appliquer_modele(modele, valeurs=None):
    """Rend un modele avec les valeurs fournies, sans inventer de donnees."""
    if not isinstance(modele, dict) or "texte" not in modele:
        raise ValueError('Modele de biographie invalide.')
    valeurs = {cle:str(valeur or "").strip()
               for cle, valeur in (valeurs or {}).items()}
    texte = str(modele['texte'])
    for cle, valeur in valeurs.items():
        texte =texte.replace("{" + cle + "}", valeur)
    if len(texte) > MAX_BIO:
        texte = texte[:MAX_BIO].rstrip()
    return texte


def placeholders(modele):
    import re
    return sorted(set(re.findall(r"\{([a-z_]+)\}", str((modele or {}).get("texte", "")))))
