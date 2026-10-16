import base64
from datetime import datetime, timezone
import requests
from core.common import DISCORD_EPOCH, demander, titre, ok, bad, warn, kv, attente, C_DISCORD

def user_token_info():
    titre("DISCORD USER TOKEN CHECKER & OSINT", C_DISCORD)
    warn("Utilise uniquement tes propres tokens de test dans un cadre autorisé.")
    token = demander("Token Utilisateur (User Token)")
    if not token or "." not in token:
        bad("Format de token invalide.")
        return

    # Extraction ID depuis la 1ère partie en Base64
    part1 = token.split(".")[0]
    try:
        pad = "=" * (-len(part1) % 4)
        uid_decoded = base64.b64decode(part1 + pad).decode(errors="ignore")
    except Exception:
        uid_decoded = "Inconnu"

    headers = {
        "Authorization": token.strip(),
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    try:
        with attente("Interrogation de Discord @me"):
            r = requests.get("https://discord.com/api/v10/users/@me", headers=headers, timeout=8)
    except Exception as e:
        bad(f"Erreur de contact : {e}")
        return

    if r.status_code == 401:
        bad("Token Utilisateur Invalide ou expiré (401 Unauthorized).")
        return
    elif r.status_code != 200:
        bad(f"Réponse HTTP {r.status_code} ({r.text})")
        return

    data = r.json()
    user_id = data.get("id", uid_decoded)
    date_crea = "?"
    if user_id.isdigit():
        ts_ms = (int(user_id) >> 22) + DISCORD_EPOCH
        dt = datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc)
        date_crea = dt.strftime("%d/%m/%Y %H:%M:%S UTC")

    nitro_types = {0: "Aucun", 1: "Nitro Classic", 2: "Nitro Boost", 3: "Nitro Basic"}
    nitro = nitro_types.get(data.get("premium_type", 0), "Inconnu")

    lignes = [
        ("Tag / Pseudo", f"{data.get('username', '?')} ({data.get('global_name', '-')})"),
        ("ID Utilisateur", user_id),
        ("Date de création", date_crea),
        ("Email associé", data.get("email", "Non communiqué / masqué")),
        ("Téléphone vérifié", data.get("phone") or "Aucun"),
        ("2FA / A2F", "Oui" if data.get("mfa_enabled") else "Non"),
        ("Abonnement Nitro", nitro),
        ("Langue (Locale)", data.get("locale", "?")),
        ("Contenu NSFW autorisé", "Oui" if data.get("nsfw_allowed") else "Non"),
    ]

    # Amis / Relations
    try:
        rel = requests.get("https://discord.com/api/v10/users/@me/relationships", headers=headers, timeout=5)
        if rel.status_code == 200:
            amis = [a for a in rel.json() if a.get("type") == 1]
            bloques = [a for a in rel.json() if a.get("type") == 2]
            lignes.append(("Nombre d'amis", str(len(amis))))
            lignes.append(("Utilisateurs bloqués", str(len(bloques))))
    except Exception:
        pass

    # Facturation / Cartes bancaires liées
    try:
        bill = requests.get("https://discord.com/api/v10/users/@me/billing/payment-sources", headers=headers, timeout=5)
        if bill.status_code == 200:
            methods = bill.json()
            lignes.append(("Méthodes de paiement liées", str(len(methods))))
    except Exception:
        pass

    kv("Données du Compte Discord", lignes, C_DISCORD)
    ok("Token Utilisateur valide et actif !")
