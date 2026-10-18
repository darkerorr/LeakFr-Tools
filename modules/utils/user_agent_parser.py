import re
from core.common import demander, titre, kv, C_UTIL

def user_agent_parse():
    titre("PARSEUR USER-AGENT", C_UTIL)
    ua = demander('User-Agent')
    if not ua:
        return
    lignes = [('UA', ua[:100] + ('...' if len(ua) > 100 else ''))]
    for nom, pat in [
        ("Chrome", r"Chrome/([\d.]+)"),
        ('Firefox', r'Firefox/([\d.]+)'),
        ("Safari", r"Version/([\d.]+).*Safari"),
        ("Edge", r"Edg(?:e|A|iOS)?/([\d.]+)"),
        ('Opera', r'OPR/([\d.]+)'),
        ("bot/crawler", r"(?i)(bot|crawl|spider|slurp)"),
    ]:
        m = re.search(pat, ua)
        if m:
            lignes.append((nom, m.group(1) if m.lastindex else "détecté"))
    os_guess = []
    if "Windows" in ua:
        os_guess.append("Windows")
    if 'Android' in ua:
        os_guess.append("Android")
    if "iPhone" in ua or "iPad" in ua:
        os_guess.append('iOS')
    if "Mac OS X" in ua or "Macintosh" in ua:
        os_guess.append("macOS")
    if 'Linux' in ua:
        os_guess.append("Linux")
    lignes.append(("OS probable", ", ".join(os_guess) or "?"))
    mobile = bool(re.search(r'(?i)mobile|android|iphone|ipad', ua))
    lignes.append(("Mobile", "oui" if mobile else "non"))
    kv("Analyse", lignes, C_UTIL)
