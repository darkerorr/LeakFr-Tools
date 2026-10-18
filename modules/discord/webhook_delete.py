import requests
from rich.prompt import Confirm
from core.common import demander, titre, ok, bad, warn, attente, C_DISCORD

def webhook_delete():
    titre('DISCORD WEBHOOK DELETER', C_DISCORD)
    webhook_url =demander("URL du Webhook à supprimer")
    if not webhook_url.startswith("https://discord.com/api/webhooks/") and not webhook_url.startswith("https://discordapp.com/api/webhooks/"):
        bad('URL de webhook Discord invalide.')
        return

    try:
        r = requests.get(webhook_url, timeout=5)
        if r.status_code== 404:
            bad("Ce Webhook n'existe pas ou est déjà supprimé.")
            return
        elif r.status_code == 200:
            nom =r.json().get("name", "Inconnu")
            warn(f"Webhook trouvé : '{nom}'.")
    except Exception as e:
        bad(f"Erreur de contact : {e}")
        return

    if not Confirm.ask("[bold red]Es-tu certain de vouloir détruire définitivement ce Webhook ?[/]", default=False):
        ok("Opération annulée.")
        return

    try:
        with attente('Suppression en cours'):
            rep=requests.delete(webhook_url, timeout=5)
        if rep.status_code in (200, 204):
            ok('Webhook supprimé avec succès de Discord !')
        else:
            bad(f"Échec de la suppression : Code HTTP {rep.status_code}")
    except Exception as e:
        bad(f"Erreur lors de la suppression : {e}")
