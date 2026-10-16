import re
from urllib.parse import urlparse
import requests
from rich.panel import Panel
from rich.text import Text
from core.common import console, demander, titre, ok, bad, kv, attente, nettoyer_cible, BX, C_OSINT, HEADERS, TIMEOUT

def robots_sitemap():
    cible = nettoyer_cible(demander("URL ou domaine"))
    if not cible:
        return
    base = cible if cible.startswith("http") else "https://" + cible
    parsed = urlparse(base)
    racine = f"{parsed.scheme}://{parsed.netloc}"
    titre(f"ROBOTS.TXT & SITEMAP : {parsed.netloc}", C_OSINT)
    for chemin, label in (("/robots.txt", "robots.txt"),
                          ("/sitemap.xml", "sitemap.xml"),
                          ("/sitemap_index.xml", "sitemap_index.xml")):
        url = racine + chemin
        try:
            with attente(f"Récupération {label}"):
                r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            if r.status_code == 200 and r.text.strip():
                ok(f"{label} trouvé ({len(r.text)} octets)")
                console.print(Panel(Text(r.text[:2500]), box=BX, border_style=C_OSINT,
                                    title=f"[bold {C_OSINT}]{label}[/]"))
                if label == "robots.txt":
                    smaps = re.findall(r"(?i)^sitemap:\s*(\S+)", r.text, re.M)
                    if smaps:
                        kv("Sitemaps déclarés", [(f"#{i}", u) for i, u in enumerate(smaps, 1)],
                           C_OSINT)
            else:
                bad(f"{label} : HTTP {r.status_code}")
        except Exception as e:
            bad(f"{label} : {e}")
