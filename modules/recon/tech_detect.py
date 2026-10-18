import requests
from core.common import demander, titre, bad, warn, kv, attente, C_RECON, HEADERS, TIMEOUT

def detect_techno():
    url = demander("URL (ex: https://example.com)")
    if not url.startswith('http'):
        url="https://" + url
    titre(f"DÉTECTION DE TECHNOLOGIES : {url}", C_RECON)
    try:
        with attente("Analyse HTTP"):
            r = requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
    except Exception as e:
        bad(f"Erreur : {e}")
        return
    html = r.text.lower()
    headers = {k.lower(): v for k, v in r.headers.items()}
    signatures = [
        ('Serveur', headers.get('server')),
        ("X-Powered-By", headers.get("x-powered-by")),
        ("Via", headers.get("via")),
        ('CDN/Cloudflare', 'oui' if 'cf-ray' in headers or 'cloudflare' in headers.get('server', '').lower() else None),
        ("WordPress", "oui" if "wp-content" in html or "wordpress" in html else None),
        ("Drupal", "oui" if "drupal" in html or "/sites/default/" in html else None),
        ('Joomla', 'oui' if 'joomla' in html else None),
        ("React", "oui" if "react" in html or "_next" in html or "data-reactroot" in html else None),
        ("Vue.js", "oui" if "vue" in html or "__vue__" in html else None),
        ('Angular', 'oui' if 'ng-version' in html or 'angular' in html else None),
        ("jQuery", "oui" if "jquery" in html else None),
        ("Bootstrap", "oui" if "bootstrap" in html else None),
        ('Google Analytics', 'oui' if 'google-analytics' in html or 'gtag(' in html else None),
        ("PHP session", "oui" if "phpsessid" in r.headers.get("Set-Cookie", "").lower() else None),
        ("ASP.NET", "oui" if "asp.net" in headers.get("x-powered-by", "").lower()
                     or 'aspxauth' in r.headers.get('Set-Cookie', '').lower() else None),
    ]
    lignes = [(k, v) for k, v in signatures if v]
    lignes.insert(0, ('Code HTTP', r.status_code))
    lignes.insert(1, ("URL finale", r.url))
    if not any(k not in ("Code HTTP", "URL finale") for k, _ in lignes):
        warn("Peu d'indices trouvés (page minimaliste ou obfuscation).")
    kv("Empreinte", lignes, C_RECON)
