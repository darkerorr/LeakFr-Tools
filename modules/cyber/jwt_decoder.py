import json
import base64
from datetime import datetime, timezone
from rich.panel import Panel
from rich.text import Text
from core.common import console, demander, titre, ok, bad, warn, BX, C_CYBER

def jwt_inspect():
    titre('DÉCODEUR JWT', C_CYBER)
    token= demander("JWT (header.payload.signature)")
    if not token or token.count(".") < 2:
        bad('Format JWT invalide.')
        return
    parts = token.strip().split(".")
    labels = ('Header', 'Payload', 'Signature')

    def b64url(data):
        pad = '=' * (-len(data) % 4)
        return base64.urlsafe_b64decode(data + pad)

    for i, (label, part) in enumerate(zip(labels, parts[:3])):
        if i < 2:
            try:
                raw = b64url(part)
                obj= json.loads(raw)
                console.print(Panel(Text(json.dumps(obj, indent=2, ensure_ascii=False)),
                                    box=BX, border_style=C_CYBER,
                                    title=f"[bold {C_CYBER}]{label}[/]"))
                if label =="Payload":
                    for claim in ('exp', 'iat', 'nbf'):
                        if claim in obj and isinstance(obj[claim], (int, float)):
                            dt =datetime.fromtimestamp(obj[claim], tz=timezone.utc)
                            ok(f"{claim} → {dt.strftime("%d/%m/%Y %H:%M:%S UTC")}")
            except Exception as e:
                bad(f"{label} illisible : {e}")
        else:
            ok(f"Signature (base64url) : {part[:40]}{'...' if len(part) > 40 else ''}")
    warn("Décodage uniquement — la signature n'est pas vérifiée.")
