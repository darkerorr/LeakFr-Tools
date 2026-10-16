import requests
from rich.table import Table
from rich.markup import escape
from core.common import console, demander, titre, barre, BX, C_OSINT, OKC, KOC, HEADERS, TIMEOUT

def recherche_pseudo():
    pseudo = demander("Pseudo à chercher")
    if not pseudo:
        return
    sites = {
        "GitHub": "https://github.com/{}",
        "Reddit": "https://www.reddit.com/user/{}",
        "Twitter/X": "https://x.com/{}",
        "Instagram": "https://www.instagram.com/{}/",
        "TikTok": "https://www.tiktok.com/@{}",
        "Twitch": "https://www.twitch.tv/{}",
        "YouTube": "https://www.youtube.com/@{}",
        "Pinterest": "https://www.pinterest.com/{}/",
        "Steam": "https://steamcommunity.com/id/{}",
        "GitLab": "https://gitlab.com/{}",
        "Medium": "https://medium.com/@{}",
        "SoundCloud": "https://soundcloud.com/{}",
        "Dev.to": "https://dev.to/{}",
        "HackerNews": "https://news.ycombinator.com/user?id={}",
        "Keybase": "https://keybase.io/{}",
        "About.me": "https://about.me/{}",
        "Flickr": "https://www.flickr.com/people/{}",
        "Vimeo": "https://vimeo.com/{}",
        "Roblox": "https://www.roblox.com/user.aspx?username={}",
        "Linktree": "https://linktr.ee/{}",
    }
    titre(f"RECHERCHE DE PSEUDO : {pseudo}", C_OSINT)

    def check(item):
        nom, url = item
        url = url.format(pseudo)
        try:
            r = requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
            return nom, url, r.status_code == 200
        except Exception:
            return nom, url, None

    resultats = []
    with barre() as p:
        tache = p.add_task("Analyse des plateformes", total=len(sites))
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
            futs = [ex.submit(check, it) for it in sites.items()]
            for f in concurrent.futures.as_completed(futs):
                resultats.append(f.result())
                p.advance(tache)

    resultats.sort(key=lambda x: (x[2] is not True, x[0]))
    t = Table(box=BX, border_style=C_OSINT, header_style=f"bold {C_OSINT}")
    t.add_column("Plateforme", style="bold")
    t.add_column("Statut")
    t.add_column("Lien")
    for nom, url, etat in resultats:
        if etat:
            t.add_row(nom, f"[bold green]{OKC} trouvé[/]", escape(url))
        elif etat is None:
            t.add_row(nom, "[yellow]? erreur[/]", "")
        else:
            t.add_row(nom, f"[red]{KOC} absent[/]", "[dim]-[/]")
    console.print(t)
    trouves = sum(1 for r in resultats if r[2])
    console.print(f"\n[bold green]{trouves}[/] profil(s) trouvé(s) sur {len(sites)}.")
    console.print("[dim]Résultats indicatifs : certains sites bloquent les bots.[/]")
