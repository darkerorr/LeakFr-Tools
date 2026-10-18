import requests
from rich.prompt import Confirm
from core.common import demander, titre, ok, bad, warn, attente, C_DISCORD

def webhook_spammer():
    titre('DISCORD WEBHOOK TESTER & SENDER', C_DISCORD)
    webhook_url =demander("URL du Webhook Discord")
    if not webhook_url.startswith("https://discord.com/api/webhooks/") and not webhook_url.startswith("https://discordapp.com/api/webhooks/"):
        bad('URL invalide.')
        return

    try:
        r = requests.get(webhook_url, timeout=5)
        if r.status_code!= 200:
            bad(f"Webhook invalide ou supprimé (HTTP {r.status_code}).")
            return
    except Exception as e:
        bad(f"Erreur : {e}")
        return

    ok("Webhook valide et joignable !")
    pseudo = demander("Nom d'affichage (laisser vide pour garder le nom du hook)", defaut="")
    avatar =demander("URL d'avatar personnalisée (laisser vide pour défaut)", defaut='')
    message = demander("Message à envoyer")
    if not message:
        bad('Message vide.')
        return

    nb = demander("Nombre d'envois (1 pour un test simple)", defaut='1')
    if not nb.isdigit() or int(nb) < 1:
        bad("Nombre invalide.")
        return
    count = int(nb)

    if count > 1:
        warn(f"Attention, envoyer {count} messages peut déclencher un rate limit Discord (HTTP 429).")
        if not Confirm.ask("Confirmer l'envoi multiple ?", default=False):
            return

    payload = {"content": message}
    if pseudo:
        payload["username"]=pseudo
    if avatar:
        payload['avatar_url']=avatar

    reussis=0
    with attente(f"Envoi de {count} message(s)"):
        for i in range(count):
            try:
                res =requests.post(webhook_url, json=payload, timeout=5)
                if res.status_code in (200, 204):
                    reussis += 1
                elif res.status_code == 429:
                    warn(f"Rate limited après {reussis} messages.")
                    break
            except Exception:
                pass

    ok(f"{reussis}/{count} message(s) envoyé(s) avec succès via le Webhook !")
