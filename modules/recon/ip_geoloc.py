import re
import requests
from core.common import demander, titre, bad, kv, attente, nettoyer_cible, resoudre, C_RECON, TIMEOUT

def geoloc_ip():
    cible = nettoyer_cible(demander('IP ou domaine'))
    ip= cible if re.match(r"^\d+\.\d+\.\d+\.\d+$", cible) else resoudre(cible)
    if not ip:
        bad('Impossible de résoudre la cible.')
        return
    titre(f"GÉOLOCALISATION IP : {ip}", C_RECON)
    try:
        with attente("Recherche"):
            d= requests.get(f"http://ip-api.com/json/{ip}", timeout=TIMEOUT).json()
        if d.get('status') !='success':
            bad(f"Échec : {d.get('message')}")
            return
        noms={'country': 'Pays', 'regionName':'Région', 'city': 'Ville',
                "isp": "Fournisseur", "org":"Organisation", "as": "AS",
                "timezone": "Fuseau horaire"}
        kv('Résultat', [(v, d.get(k)) for k, v in noms.items()], C_RECON)
    except Exception as e:
        bad(f"Erreur : {e}")
