import re
import base64
from urllib.parse import quote, unquote
from rich.prompt import Prompt
from core.common import console, demander, titre, bad, kv, C_UTIL, C_GOLD

def encode_decode():
    titre("ENCODE / DECODE", C_UTIL)
    console.print(f"  [bold {C_GOLD}]1[/] Base64 encode   [bold {C_GOLD}]2[/] Base64 decode")
    console.print(f"  [bold {C_GOLD}]3[/] URL encode      [bold {C_GOLD}]4[/] URL decode")
    console.print(f"  [bold {C_GOLD}]5[/] Hex encode      [bold {C_GOLD}]6[/] Hex decode\n")
    mode = Prompt.ask(f"[bold {C_GOLD}]Mode[/]", choices=list("123456"), default="1")
    texte = demander("Texte")
    try:
        if mode == "1":
            out = base64.b64encode(texte.encode()).decode()
        elif mode == "2":
            out = base64.b64decode(texte.encode()).decode(errors="replace")
        elif mode == "3":
            out = quote(texte, safe="")
        elif mode == "4":
            out = unquote(texte)
        elif mode == "5":
            out = texte.encode().hex()
        else:
            out = bytes.fromhex(re.sub(r"\s+", "", texte)).decode(errors="replace")
        kv("Résultat", [("Sortie", out)], C_UTIL)
    except Exception as e:
        bad(f"Échec : {e}")
