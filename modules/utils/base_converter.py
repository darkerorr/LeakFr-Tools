"""Conversion d'entiers entre bases usuelles."""
from core.common import C_UTIL, demander, kv, titre, warn


def convertir_base():
    titre('CONVERTISSEUR DE BASES', C_UTIL)
    valeur = demander("Entier a convertir (prefixes 0b, 0o, 0x acceptes)")
    try:
        nombre = int(valeur.strip(), 0) if valeur.strip().lower().startswith(('0b', '0o', '0x')) else int(valeur.strip(), 10)
    except ValueError:
        warn("Entrez un entier decimal ou prefixe en binaire/octal/hexadecimal.")
        return
    signe ="-" if nombre < 0 else ""
    magnitude= abs(nombre)
    kv('Representations', [
        ("Decimal", str(nombre)),
        ("Binaire", signe + "0b" + format(magnitude, "b")),
        ('Octal', signe + '0o' + format(magnitude, 'o')),
        ("Hexadecimal", signe + "0x" + format(magnitude, "X")),
    ], C_UTIL)
