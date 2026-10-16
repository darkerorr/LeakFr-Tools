import re
from core.common import console, demander, titre, bad, kv, C_UTIL, OKC, KOC

def luhn_check():
    titre("VALIDATEUR LUHN (cartes / IMEI...)", C_UTIL)
    console.print("[dim]Vérifie uniquement l'algorithme de Luhn — pas une autorisation bancaire.[/]\n")
    num = re.sub(r"\D", "", demander("Numéro"))
    if len(num) < 2:
        bad("Trop court.")
        return
    digits = [int(c) for c in num]
    checksum = 0
    parity = len(digits) % 2
    for i, d in enumerate(digits):
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        checksum += d
    valid = checksum % 10 == 0
    brands = [
        (r"^4\d{12}(\d{3})?(\d{3})?$", "Visa"),
        (r"^5[1-5]\d{14}$", "Mastercard"),
        (r"^3[47]\d{13}$", "American Express"),
        (r"^6(?:011|5\d{2})\d{12}$", "Discover"),
    ]
    brand = "inconnu / autre"
    for pat, nom in brands:
        if re.match(pat, num):
            brand = nom
            break
    kv("Résultat", [
        ("Numéro (masqué)", num[:4] + "*" * (len(num) - 8) + num[-4:] if len(num) >= 8 else num),
        ("Longueur", len(num)),
        ("Luhn", f"{OKC} valide" if valid else f"{KOC} invalide"),
        ("Marque probable", brand),
    ], C_UTIL)
