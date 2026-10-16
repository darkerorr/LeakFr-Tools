import re
import hashlib
import requests
from core.common import demander, titre, bad, kv, doh, C_OSINT, OKC, KOC, TIMEOUT

def analyse_email():
    mail = demander("Adresse email").lower()
    titre(f"ANALYSE EMAIL : {mail}", C_OSINT)
    if not re.match(r"^[\w.+-]+@[\w-]+\.[\w.-]+$", mail):
        bad("Format invalide.")
        return
    domaine = mail.split("@")[1]
    lignes = [("Adresse", mail), ("Format", f"{OKC} valide"), ("Domaine", domaine)]
    mx = doh(domaine, "MX")
    lignes.append(("Serveurs mail (MX)",
                   "\n".join(mx) if mx else f"{KOC} aucun (ne reçoit probablement pas de mails)"))
    h = hashlib.md5(mail.encode()).hexdigest()
    try:
        r = requests.get(f"https://www.gravatar.com/avatar/{h}?d=404", timeout=TIMEOUT)
        if r.status_code == 200:
            lignes.append(("Gravatar", f"{OKC} https://www.gravatar.com/{h}"))
        else:
            lignes.append(("Gravatar", f"{KOC} aucun profil"))
    except Exception:
        lignes.append(("Gravatar", "? injoignable"))
    kv("Résultat", lignes, C_OSINT)
