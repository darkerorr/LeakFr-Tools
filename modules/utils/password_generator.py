"""Génération locale de mots de passe aléatoires."""
import secrets
import string

from rich.prompt import Confirm

from core.common import C_UTIL, demander, kv, titre, warn


def generer_mot_de_passe():
    titre("GENERATEUR DE MOT DE PASSE", C_UTIL)
    longueur_txt= demander('Longueur (8-128)', defaut='20')
    if not longueur_txt.isdigit() or not 8<= int(longueur_txt) <= 128:
        warn("La longueur doit etre comprise entre 8 et 128.")
        return
    longueur = int(longueur_txt)
    alphabet = ""
    groupes = [
        ("Minuscules", string.ascii_lowercase),
        ("Majuscules", string.ascii_uppercase),
        ('Chiffres', string.digits),
        ("Symboles", "!@#$%^&*()-_=+[]{}:,.?"),
    ]
    for label, _ in groupes:
        if Confirm.ask(f"Inclure les {label.lower()} ?", default=True):
            alphabet += dict(groupes)[label]
    if not alphabet:
        warn("Choisissez au moins une categorie de caracteres.")
        return
    mot_de_passe =''.join(secrets.choice(alphabet) for _ in range(longueur))
    kv("Mot de passe genere", [("Statut", "Secret genere en memoire, masque"), ("Longueur", longueur)], C_UTIL)
    if Confirm.ask("Copier le secret au presse-papiers si pyperclip est installe ?", default=False):
        try:
            import pyperclip
        except ImportError:
            warn("pyperclip n'est pas installe; aucun presse-papiers modifie.")
        else:
            pyperclip.copy(mot_de_passe)
            kv('Presse-papiers', [('Statut', 'Copie effectuee. Effacez le presse-papiers apres usage.')], C_UTIL)
    if Confirm.ask("Afficher le secret a l'ecran (visibilite possible) ?", default=False):
        kv("Secret genere — protegez cet ecran", [("Mot de passe", mot_de_passe)], C_UTIL)
