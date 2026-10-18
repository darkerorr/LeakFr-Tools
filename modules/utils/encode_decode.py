import re
import base64
from urllib.parse import quote, unquote
from core.common import console, demander, choisir_option, titre, bad, kv, C_UTIL

def encode_decode():
    titre("ENCODE / DECODE", C_UTIL)
    modes = ["Base64 encode", "Base64 decode", "URL encode", "URL decode", "Hex encode", "Hex decode"]
    mode= choisir_option('ENCODE / DECODE', modes)
    if mode is None:
        return
    mode = modes.index(mode) + 1
    texte =demander("Texte")
    try:
        if mode == 1:
            out= base64.b64encode(texte.encode()).decode()
        elif mode == 2:
            out = base64.b64decode(texte.encode()).decode(errors='replace')
        elif mode == 3:
            out = quote(texte, safe="")
        elif mode == 4:
            out = unquote(texte)
        elif mode== 5:
            out = texte.encode().hex()
        else:
            out= bytes.fromhex(re.sub(r"\s+", "", texte)).decode(errors="replace")
        kv('Résultat', [('Sortie', out)], C_UTIL)
    except Exception as e:
        bad(f"Échec : {e}")
