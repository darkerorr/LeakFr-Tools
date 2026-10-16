from urllib.parse import quote
import webbrowser
from rich.table import Table
from rich.markup import escape
from core.common import console, demander, choisir_option, titre, BX, C_OSINT, C_GOLD

def generateur_dorks():
    titre("GÉNÉRATEUR DE GOOGLE DORKS", C_OSINT)
    cible = demander("Cible (domaine, pseudo, email...)")
    if not cible:
        return
    dorks = [
        ("site", f'site:{cible}'),
        ("Fichiers PDF", f'site:{cible} filetype:pdf'),
        ("Fichiers Excel", f'site:{cible} (filetype:xls OR filetype:xlsx)'),
        ("Login / admin", f'site:{cible} (inurl:login OR inurl:admin OR intitle:login)'),
        ("Index ouvert", f'site:{cible} intitle:"index of"'),
        ("Config exposée", f'site:{cible} (ext:env OR ext:ini OR ext:cfg OR ext:log)'),
        ("Mentions hors site", f'"{cible}" -site:{cible}' if "." in cible else f'"{cible}"'),
        ("LinkedIn", f'site:linkedin.com/in "{cible}"'),
        ("GitHub", f'site:github.com "{cible}"'),
        ("Paste / leaks", f'site:pastebin.com OR site:ghostbin.com "{cible}"'),
        ("Docs publics", f'site:{cible} (filetype:doc OR filetype:docx OR filetype:txt)'),
        ("Caméras / IoT", f'site:{cible} (inurl:view/index.shtml OR intitle:"webcam")'),
    ]
    t = Table(box=BX, border_style=C_OSINT, header_style=f"bold {C_OSINT}")
    t.add_column("Usage")
    t.add_column("Dork")
    for usage, dork in dorks:
        t.add_row(usage, escape(dork))
    console.print(t)
    console.print("[dim]Utilise ces requêtes sur Google / DuckDuckGo / Bing.[/]")
    choix = choisir_option("OUVRIR UNE REQUETE", [usage for usage, _ in dorks] + ["Terminer"])
    if choix not in (None, "Terminer"):
        requete = next(dork for usage, dork in dorks if usage == choix)
        webbrowser.open(f"https://www.google.com/search?q={quote(requete)}")
