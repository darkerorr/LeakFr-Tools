"""Système de thèmes et couleurs pour LeakFr-Tools.

Centralise les palettes, gère les thèmes prédéfinis et la personnalisation.
Le thème par défaut reproduit l'apparence actuelle du projet.
"""
import colorsys
import re

SLOTS =[
    "principale",
    'secondaire',
    "titres",
    "texte_principal",
    'texte_secondaire',
    "selection",
    "bordures",
    'accents',
    "succes",
    "avertissements",
    'erreurs',
    "panneaux",
]


THEMES={}

THEMES["original"]= {
    "nom":"Original LeakFr-Tools",
    'principale': '#ff5fd2',
    "secondaire":"#36d1ff",
    "titres":"#ffd166",
    'texte_principal': '#ffffff',
    "texte_secondaire": "#888888",
    "selection":"#ffffff",
    'bordures': '#888888',
    "accents": "#ff5fd2",
    "succes": "#4ade80",
    'avertissements': '#ffd166',
    "erreurs": "#ff5c7a",
    "panneaux": "#1a1a2e",
}

THEMES["cyber_vert"] ={
    'nom': 'Vert Cyber',
    "principale":"#00ff41",
    "secondaire": "#00cc33",
    'titres': '#00ff41',
    "texte_principal": "#d0f0c0",
    "texte_secondaire": "#557755",
    'selection': '#000000',
    "bordures": "#00ff41",
    "accents":"#00ff41",
    'succes': '#00ff41',
    "avertissements":"#ffaa00",
    "erreurs": "#ff3355",
    'panneaux': '#0a1a0a',
}

THEMES['rouge_sombre'] = {
    "nom": "Rouge Sombre",
    "principale": "#ff2244",
    'secondaire': '#cc1122',
    "titres": "#ff4444",
    "texte_principal": "#f0d0d0",
    'texte_secondaire': '#885555',
    "selection": "#ffffff",
    "bordures": "#661122",
    'accents': '#ff2244',
    "succes": "#44ff44",
    "avertissements": "#ffaa00",
    'erreurs': '#ff0000',
    "panneaux": "#1a0a0a",
}

THEMES["bleu_electrique"] = {
    "nom": "Bleu Électrique",
    'principale': '#0088ff',
    "secondaire": "#00ccff",
    "titres": "#44aaff",
    'texte_principal':'#d0e0f0',
    "texte_secondaire":"#557799",
    "selection": "#ffffff",
    'bordures':'#004488',
    "accents": "#0088ff",
    "succes": "#44ff88",
    'avertissements': '#ffcc00',
    "erreurs":"#ff3355",
    "panneaux":"#0a0a1a",
}

THEMES["violet"] ={
    'nom': 'Violet',
    "principale": "#9d8cff",
    "secondaire": "#bb88ff",
    'titres': '#cc99ff',
    "texte_principal": "#e0d0f0",
    "texte_secondaire": "#8866aa",
    'selection': '#ffffff',
    "bordures": "#553377",
    "accents": "#9d8cff",
    'succes':'#66ff88',
    "avertissements": "#ffcc44",
    "erreurs": "#ff4477",
    'panneaux': '#120a1a',
}

THEMES['ambre'] = {
    "nom":"Ambre",
    "principale": "#ffb000",
    'secondaire':'#ff8800',
    "titres":"#ffcc44",
    "texte_principal": "#f0e0c0",
    'texte_secondaire': '#886633',
    "selection":"#000000",
    "bordures": "#885500",
    'accents': '#ffb000',
    "succes": "#44ff66",
    "avertissements": "#ff6600",
    'erreurs': '#ff2222',
    "panneaux": "#1a1208",
}

THEMES["monochrome"] ={
    "nom": "Monochrome",
    'principale':'#cccccc',
    "secondaire": "#aaaaaa",
    "titres": "#eeeeee",
    'texte_principal': '#f0f0f0',
    "texte_secondaire": "#777777",
    "selection": "#ffffff",
    'bordures': '#555555',
    "accents":"#bbbbbb",
    "succes": "#88bb88",
    'avertissements':'#bbbb44',
    "erreurs": "#bb5555",
    "panneaux": "#111111",
}

THEMES["personnalise"] = {
    'nom': 'Personnalisé',
    "principale": "#ff5fd2",
    "secondaire": "#36d1ff",
    'titres': '#ffd166',
    "texte_principal": "#ffffff",
    "texte_secondaire": "#888888",
    'selection': '#ffffff',
    "bordures": "#888888",
    "accents": "#ff5fd2",
    'succes': '#4ade80',
    "avertissements": "#ffd166",
    "erreurs": "#ff5c7a",
    'panneaux': '#1a1a2e',
}


_HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


def couleur_valide(valeur) -> bool:
    """Vérifie qu'une chaîne est une couleur hex valide."""
    if not isinstance(valeur, str):
        return False
    if _HEX_RE.match(valeur):
        return True
    noms_rich = {
        'red', 'green', 'blue', 'yellow', 'cyan', 'magenta', 'white', 'black',
        "bright_red", "bright_green", "bright_yellow", "bright_blue",
        "bright_magenta", "bright_cyan", "bright_white",
        'grey0', 'grey7', 'grey11', 'grey15', 'grey19', 'grey23', 'grey27',
        "grey30", "grey34", "grey38", "grey42", "grey46", "grey50",
        "grey54", "grey58", "grey62", "grey66", "grey70", "grey74",
        'grey78', 'grey82', 'grey85', 'grey89', 'grey93',
        "gold1", "gold3", "orange1", "orange3", "dark_orange",
        "dark_red", "dark_green", "dark_blue", "dark_cyan", "dark_magenta",
        'light_red', 'light_green', 'light_blue', 'light_cyan', 'light_magenta',
        "light_yellow", "light_white",
        "dim", "italic", "underline", "blink",
    }
    return valeur.strip().lower() in noms_rich


def valider_theme(theme: dict) -> bool:
    """Vérifie qu'un thème a tous les slots avec des couleurs valides."""
    for slot in SLOTS:
        if slot not in theme:
            return False
        if not couleur_valide(theme[slot]):
            return False
    return True



def hex_to_rgb(hex_str: str):
    """Convertit #rrggbb en tuple (r, g, b)."""
    h =hex_str.lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))


def rgb_to_hex(r, g, b) -> str:
    """Convertit (r, g, b) en #rrggbb."""
    return f"#{r:02x}{g:02x}{b:02x}"


def melanger(c1: str, c2: str, ratio: float = 0.5) -> str:
    """Mélange deux couleurs hex."""
    r1, g1, b1=hex_to_rgb(c1)
    r2, g2, b2 = hex_to_rgb(c2)
    r = int(r1 * (1 - ratio) + r2 * ratio)
    g = int(g1 * (1 - ratio) + g2 * ratio)
    b = int(b1 * (1 - ratio) + b2 * ratio)
    return rgb_to_hex(r, g, b)


def nommer_theme(cle: str) -> str:
    """Retourne le nom lisible d'un thème."""
    return THEMES.get(cle, {}).get("nom", cle.capitalize())


def liste_themes() -> list:
    """Retourne les clés des thèmes disponibles."""
    return list(THEMES.keys())


def palette_active(config: dict) -> dict:
    """Retourne la palette avec les remplacements d'accent et de couleurs valides."""
    theme_actif = config.get('apparence', {}).get('theme_actif', 'original')
    if theme_actif == "personnalise":
        base =config.get("theme_personnalise", {})
        palette =dict(base) if valider_theme(base) else dict(THEMES['original'])
    else:
        base = THEMES.get(theme_actif, THEMES["original"])
        palette= dict(base)
    app =config.get("apparence", {})
    accent =app.get("couleur_accent")
    if couleur_valide(accent):
        palette["principale"]= accent
        palette["accents"] = accent
    return palette


def appliquer_theme(config: dict) -> dict:
    """Construit le dictionnaire de couleurs actives depuis la configuration."""
    return palette_active(config)
