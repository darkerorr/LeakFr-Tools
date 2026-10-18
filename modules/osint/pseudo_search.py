import concurrent.futures
import requests
from rich.table import Table
from rich.markup import escape
from core.common import console, demander, titre, barre, BX, C_OSINT, OKC, KOC, HEADERS, TIMEOUT

# Une entrée = une plateforme et le modèle d'URL du profil public.
# `{}` est remplacé par le pseudo saisi. La liste reste volontairement
# statique : aucun service tiers n'est interrogé pour la construire.
PLATEFORMES = {
    # Développement et code
    "GitHub": "https://github.com/{}",
    "GitLab": "https://gitlab.com/{}",
    "Codeberg": "https://codeberg.org/{}",
    "Bitbucket": "https://bitbucket.org/{}",
    "SourceForge": "https://sourceforge.net/u/{}/profile",
    "Replit": "https://replit.com/@{}",
    "CodePen": "https://codepen.io/{}",
    "Dev.to": "https://dev.to/{}",
    "Hacker News": "https://news.ycombinator.com/user?id={}",
    "Kaggle": "https://www.kaggle.com/{}",
    "Hugging Face": "https://huggingface.co/{}",
    "npm": "https://www.npmjs.com/~{}",
    "PyPI": "https://pypi.org/user/{}",
    "Docker Hub": "https://hub.docker.com/u/{}",
    "LeetCode": "https://leetcode.com/u/{}",
    "Codeforces": "https://codeforces.com/profile/{}",
    "HackerRank": "https://www.hackerrank.com/profile/{}",
    "Exercism": "https://exercism.org/profiles/{}",
    "TryHackMe": "https://tryhackme.com/p/{}",
    # Réseaux sociaux et messageries
    "Reddit": "https://www.reddit.com/user/{}",
    "X (Twitter)": "https://x.com/{}",
    "Mastodon": "https://mastodon.social/@{}",
    "Bluesky": "https://bsky.app/profile/{}.bsky.social",
    "Threads": "https://www.threads.net/@{}",
    "Instagram": "https://www.instagram.com/{}/",
    "Facebook": "https://www.facebook.com/{}",
    "TikTok": "https://www.tiktok.com/@{}",
    "Snapchat": "https://www.snapchat.com/add/{}",
    "Telegram": "https://t.me/{}",
    "VK": "https://vk.com/{}",
    "Pinterest": "https://www.pinterest.com/{}/",
    # Blogs et publications
    "Tumblr": "https://{}.tumblr.com",
    "WordPress.com": "https://{}.wordpress.com",
    "Blogger": "https://{}.blogspot.com",
    "Substack": "https://{}.substack.com",
    "Medium": "https://medium.com/@{}",
    "Wattpad": "https://www.wattpad.com/user/{}",
    "Scribd": "https://www.scribd.com/{}",
    "SlideShare": "https://www.slideshare.net/{}",
    "Notion": "https://{}.notion.site",
    "Disqus": "https://disqus.com/by/{}",
    # Vidéo, musique et streaming
    "Twitch": "https://www.twitch.tv/{}",
    "Kick": "https://kick.com/{}",
    "YouTube": "https://www.youtube.com/@{}",
    "Dailymotion": "https://www.dailymotion.com/{}",
    "Rumble": "https://rumble.com/user/{}",
    "Vimeo": "https://vimeo.com/{}",
    "SoundCloud": "https://soundcloud.com/{}",
    "Spotify": "https://open.spotify.com/user/{}",
    "Last.fm": "https://www.last.fm/user/{}",
    "Bandcamp": "https://bandcamp.com/{}",
    "Mixcloud": "https://www.mixcloud.com/{}",
    "Genius": "https://genius.com/artists/{}",
    # Jeux et communautés
    "Steam": "https://steamcommunity.com/id/{}",
    "Roblox": "https://www.roblox.com/user.aspx?username={}",
    "Planet Minecraft": "https://www.planetminecraft.com/member/{}",
    "NameMC": "https://namemc.com/profile/{}",
    "Chess.com": "https://www.chess.com/member/{}",
    "Lichess": "https://lichess.org/@/{}",
    "Duolingo": "https://www.duolingo.com/profile/{}",
    "MyAnimeList": "https://myanimelist.net/profile/{}",
    "AniList": "https://anilist.co/user/{}",
    "Trakt": "https://trakt.tv/users/{}",
    "Speedrun.com": "https://www.speedrun.com/user/{}",
    "itch.io": "https://{}.itch.io",
    "Newgrounds": "https://{}.newgrounds.com",
    # Culture, photos et portfolios
    "Letterboxd": "https://letterboxd.com/{}",
    "Goodreads": "https://www.goodreads.com/{}",
    "Flickr": "https://www.flickr.com/people/{}",
    "Behance": "https://www.behance.net/{}",
    "Dribbble": "https://dribbble.com/{}",
    "ArtStation": "https://www.artstation.com/{}",
    "DeviantArt": "https://www.deviantart.com/{}",
    "About.me": "https://about.me/{}",
    "Keybase": "https://keybase.io/{}",
    "Gravatar": "https://gravatar.com/{}",
    # Liens, financement et boutiques
    "Linktree": "https://linktr.ee/{}",
    "Beacons": "https://beacons.ai/{}",
    "Carrd": "https://{}.carrd.co",
    "Bio.link": "https://bio.link/{}",
    "AllMyLinks": "https://allmylinks.com/{}",
    "Product Hunt": "https://www.producthunt.com/@{}",
    "Patreon": "https://www.patreon.com/{}",
    "Ko-fi": "https://ko-fi.com/{}",
    "Buy Me a Coffee": "https://www.buymeacoffee.com/{}",
    "Etsy": "https://www.etsy.com/shop/{}",
    "eBay": "https://www.ebay.com/usr/{}",
    "Depop": "https://www.depop.com/{}",
    "Fiverr": "https://www.fiverr.com/{}",
    "PayPal": "https://www.paypal.com/paypalme/{}",
    "Venmo": "https://account.venmo.com/u/{}",
}


def recherche_pseudo():
    pseudo = demander("Pseudo à chercher")
    if not pseudo:
        return
    sites = PLATEFORMES
    titre(f"RECHERCHE DE PSEUDO : {pseudo}", C_OSINT)

    def check(item):
        nom, url = item
        url = url.format(pseudo)
        try:
            r = requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
            if r.status_code in (404, 410):
                return nom, url, False
            if r.status_code == 200:
                return nom, url, True
            return nom, url, None
        except Exception:
            return nom, url, None

    resultats = []
    with barre() as p:
        tache = p.add_task(f"Analyse de {len(sites)} plateformes", total=len(sites))
        with concurrent.futures.ThreadPoolExecutor(max_workers=12) as ex:
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
    console.print("[dim]Résultats indicatifs : certains sites bloquent les bots "
                  "ou renvoient une page de connexion.[/]")
