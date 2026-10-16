from urllib.parse import quote
import webbrowser
from rich.table import Table
from rich.markup import escape
from core.common import console, demander, choisir_option, titre, BX, C_OSINT, C_GOLD

def recherche_username_urls():
    titre("LIENS OSINT RAPIDES", C_OSINT)
    q = demander("Pseudo / nom / email / domaine")
    if not q:
        return
    liens = [
        ("Google", f"https://www.google.com/search?q={quote(q)}"),
        ("DuckDuckGo", f"https://duckduckgo.com/?q={quote(q)}"),
        ("Bing", f"https://www.bing.com/search?q={quote(q)}"),
        ("GitHub users", f"https://github.com/search?q={quote(q)}&type=users"),
        ("GitHub code", f"https://github.com/search?q={quote(q)}&type=code"),
        ("Twitter/X", f"https://x.com/search?q={quote(q)}"),
        ("Reddit", f"https://www.reddit.com/search/?q={quote(q)}"),
        ("LinkedIn", f"https://www.linkedin.com/search/results/all/?keywords={quote(q)}"),
        ("Wayback", f"https://web.archive.org/web/*/{quote(q)}"),
        ("crt.sh", f"https://crt.sh/?q={quote(q)}"),
        ("VirusTotal", f"https://www.virustotal.com/gui/search/{quote(q)}"),
        ("Shodan", f"https://www.shodan.io/search?query={quote(q)}"),
        ("Intelligence X", f"https://intelx.io/?s={quote(q)}"),
        ("WhatsMyName", "https://whatsmyname.app/"),
        ("Namechk", f"https://namechk.com/"),
    ]
    t = Table(box=BX, border_style=C_OSINT, header_style=f"bold {C_OSINT}")
    t.add_column("Service")
    t.add_column("URL")
    for nom, url in liens:
        t.add_row(nom, escape(url))
    console.print(t)
    choix = choisir_option("OUVRIR UN LIEN", [nom for nom, _ in liens] + ["Terminer"])
    if choix not in (None, "Terminer"):
        url = next(url for nom, url in liens if nom == choix)
        webbrowser.open(url)
