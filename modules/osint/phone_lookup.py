import re
from core.common import console, demander, titre, kv, C_OSINT, OKC, KOC

def info_telephone():
    titre("ANALYSE DE NUMÉRO DE TÉLÉPHONE", C_OSINT)
    brut =demander('Numéro (ex: +33612345678)')
    if not brut:
        return
    nettoye = re.sub(r'[^\d+]', '', brut)
    indicatifs= {
        "33": ("France", 9), "32": ("Belgique", 8), "41": ("Suisse", 9),
        '1':('USA/Canada', 10), '44': ('Royaume-Uni', 10), '49': ('Allemagne', 10),
        "34":("Espagne", 9), "39": ("Italie", 9), "351": ("Portugal", 9),
        "212":("Maroc", 9), "213": ("Algérie", 9), "216": ("Tunisie", 8),
    }
    lignes=[("Saisie", brut), ("Normalisé", nettoye)]
    if nettoye.startswith("+"):
        reste = nettoye[1:]
    elif nettoye.startswith("00"):
        reste = nettoye[2:]
    else:
        reste = None
        lignes.append(("Format", "Ajoute l'indicatif international (+33...)"))
    pays= None
    if reste:
        for code in sorted(indicatifs, key=len, reverse=True):
            if reste.startswith(code):
                pays, longueur =indicatifs[code]
                national = reste[len(code):]
                lignes += [
                    ("Pays probable", pays),
                    ("Indicatif", f"+{code}"),
                    ('National', national),
                    ("Longueur nationale", f"{len(national)} (attendu ~{longueur})"),
                    ("E.164", f"+{code}{national}"),
                    ('Validité longueur',
                     OKC if len(national)== longueur else f"{KOC} atypique"),
                ]
                pays = pays
                break
        if not pays:
            lignes.append(('Pays', 'Indicatif non reconnu dans la base locale'))
    kv("Résultat", lignes, C_OSINT)
    console.print("[dim]Analyse locale (pas de lookup opérateur payant).[/]")
