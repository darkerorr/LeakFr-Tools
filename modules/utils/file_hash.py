import os
import hashlib
from core.common import demander, titre, bad, kv, attente, C_UTIL

def hash_fichier():
    titre("HASH D'UN FICHIER", C_UTIL)
    chemin = demander("Chemin du fichier")
    if not chemin or not os.path.isfile(chemin):
        bad("Fichier introuvable.")
        return
    md5 = hashlib.md5()
    sha1 = hashlib.sha1()
    sha256 = hashlib.sha256()
    taille = 0
    with attente("Calcul des empreintes"):
        with open(chemin, "rb") as f:
            while True:
                chunk = f.read(1024 * 1024)
                if not chunk:
                    break
                taille += len(chunk)
                md5.update(chunk)
                sha1.update(chunk)
                sha256.update(chunk)
    kv(os.path.basename(chemin), [
        ("Taille", f"{taille:,} octets".replace(",", " ")),
        ("MD5", md5.hexdigest()),
        ("SHA-1", sha1.hexdigest()),
        ("SHA-256", sha256.hexdigest()),
    ], C_UTIL)
