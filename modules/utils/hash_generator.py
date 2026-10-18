import hashlib
from core.common import demander, titre, kv, C_UTIL

def generateur_hash():
    titre("GÉNÉRATEUR DE HASH", C_UTIL)
    texte = demander('Texte / mot de passe')
    if texte == "":
        return
    data= texte.encode('utf-8')
    kv("Empreintes", [
        ("MD5", hashlib.md5(data).hexdigest()),
        ('SHA-1', hashlib.sha1(data).hexdigest()),
        ("SHA-256", hashlib.sha256(data).hexdigest()),
        ("SHA-512", hashlib.sha512(data).hexdigest()),
        ('BLAKE2b', hashlib.blake2b(data).hexdigest()),
        ("BLAKE2s", hashlib.blake2s(data).hexdigest()),
    ], C_UTIL)
