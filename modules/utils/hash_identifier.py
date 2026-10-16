import re
from core.common import demander, titre, bad, kv, C_UTIL

def identifier_hash():
    h = demander("Hash")
    titre("IDENTIFICATION DU HASH", C_UTIL)
    types = {32: "MD5 / NTLM", 40: "SHA-1", 56: "SHA-224", 64: "SHA-256",
             96: "SHA-384", 128: "SHA-512"}
    if not re.match(r"^[a-fA-F0-9]+$", h):
        if h.startswith(("$2a$", "$2b$", "$2y$")):
            kv("Résultat", [("Type", "bcrypt")], C_UTIL)
        elif h.startswith("$6$"):
            kv("Résultat", [("Type", "SHA-512 crypt (Linux)")], C_UTIL)
        else:
            bad("Format inconnu.")
        return
    kv("Résultat", [("Longueur", len(h)),
                    ("Type probable", types.get(len(h), "inconnu"))], C_UTIL)
