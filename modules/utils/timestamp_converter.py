import re
from datetime import datetime, timezone
from core.common import demander, titre, bad, kv, C_UTIL

def timestamp_outil():
    titre("CONVERTISSEUR TIMESTAMP", C_UTIL)
    saisie = demander("Epoch (s/ms) ou date AAAA-MM-JJ HH:MM:SS (Entrée = maintenant)",
                      defaut="")
    now = datetime.now(timezone.utc)
    if not saisie:
        dt = now
    elif re.match(r"^\d+$", saisie):
        val = int(saisie)
        if val > 10_000_000_000:
            val /= 1000
        dt = datetime.fromtimestamp(val, tz=timezone.utc)
    else:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y"):
            try:
                dt = datetime.strptime(saisie, fmt).replace(tzinfo=timezone.utc)
                break
            except ValueError:
                continue
        else:
            bad("Format non reconnu.")
            return
    kv("Résultat", [
        ("UTC", dt.strftime("%d/%m/%Y %H:%M:%S")),
        ("ISO 8601", dt.isoformat()),
        ("Epoch (s)", int(dt.timestamp())),
        ("Epoch (ms)", int(dt.timestamp() * 1000)),
        ("Jour", dt.strftime("%A")),
    ], C_UTIL)
