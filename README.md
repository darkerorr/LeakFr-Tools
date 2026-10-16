<div align="center">

# LeakFr-Tools

### OSINT · Reconnaissance · Cyber · Réseau · Discord · Astronomie

**81 outils · 7 catégories · une interface terminal personnalisable**

[![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Rich](https://img.shields.io/badge/UI-Rich-222222)](https://github.com/Textualize/rich)
[![Langue](https://img.shields.io/badge/Langue-Français-0055A4)](#)

</div>

---

## Présentation

LeakFr-Tools est une boîte à outils Python en ligne de commande pour les recherches en sources ouvertes, la reconnaissance technique, les contrôles de sécurité, les diagnostics réseau et quelques utilitaires pratiques. L’interface repose sur Rich ; les préférences et dossiers d’investigation sont stockés localement.

> Les résultats dépendent des sources, des permissions et de la disponibilité des services externes. Ce dépôt ne promet pas qu’un outil fonctionne sur toutes les cibles ni qu’un résultat constitue une preuve.

## Captures d’écran

Les images ci-dessous sont des rendus de l’interface terminal fournis avec le dépôt (pas des captures d’un navigateur ou d’une connexion réelle). Elles illustrent le menu et les sept catégories. Chaque guide de catégorie contient un visuel pour chacun de ses modules.

| Menu principal | Vue des catégories |
|---|---|
| ![Menu principal LeakFr-Tools](docs/screenshots/menu-principal.svg) | ![Catégories LeakFr-Tools](docs/screenshots/categories.svg) |

## Catégories & guides

| Catégorie | Outils | Guide |
|---|---:|---|
| OSINT | 8 | [modules/osint/README.md](modules/osint/README.md) |
| Reconnaissance | 10 | [modules/recon/README.md](modules/recon/README.md) |
| Cyber | 10 | [modules/cyber/README.md](modules/cyber/README.md) |
| Pentest & réseau | 19 | [modules/pentest/README.md](modules/pentest/README.md) |
| Discord | 10 | [modules/discord/README.md](modules/discord/README.md) |
| Utilitaires | 15 | [modules/utils/README.md](modules/utils/README.md) |
| Astronomie | 9 | [modules/astro/README.md](modules/astro/README.md) |

### En un coup d’œil

- **OSINT** : pseudonymes, e-mails, archives, URLs, dorks et liens de recherche.
- **Recon** : DNS, reverse DNS, IP, ASN, WHOIS, sous-domaines, mail et HTTP.
- **Cyber** : headers, TLS, cookies, JWT, CVE, CORS et latence.
- **Pentest & réseau** : diagnostics locaux et tests techniques. Les tests actifs exigent une autorisation explicite.
- **Discord** : informations publiques, invitations, Snowflakes, webhooks et panneau de gestion de bot.
- **Utilitaires** : hachage, encodage, génération de mots de passe, formatage JSON, UUID, conversions et calculs de dates.
- **Astronomie** : ISS, APOD, astéroïdes, planètes, lancements et conversions spatiales.

## Installation

### Prérequis

- Python 3.9 ou supérieur (testé ici avec Python 3.14)
- pip
- Un terminal compatible avec Rich
- Internet pour les modules qui interrogent des services externes

```bash
git clone https://github.com/darkerorr/LeakFr-Tools.git
cd LeakFr-Tools
python3 -m venv .venv
source .venv/bin/activate       # Windows PowerShell : .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Démarrage & navigation

```bash
python3 main.py
```

Le menu plein écran accepte les flèches, Entrée, les numéros de module, `s` pour les paramètres et `q` pour quitter. Dans un terminal non interactif, le menu simple s’active automatiquement.

```bash
python3 main.py --help       # aide CLI
python3 main.py --version    # version affichée
python3 main.py --simple     # forcer les menus textuels
python3 main.py --ascii      # affichage compatible ASCII
```

## Configuration et données locales

Le fichier `data/settings.json` est créé au premier démarrage. Le menu **Paramètres** permet de choisir le style (dashboard, classique, compact), une palette, les couleurs d’accent/texte/fond de shell, la largeur, le panneau latéral, les badges, la bannière, les animations et le timeout réseau (1–120 s). Une palette entièrement personnalisable par rôle est disponible et les préférences persistent dans `data/settings.json`. Les dossiers d’investigation utilisent SQLite (`data/cases.db`), avec historique (`data/history.json`) et exports (`data/exports/`). Les données collectées peuvent être sensibles : vérifiez les exports avant partage.

## Tests & vérifications

Depuis la racine du dépôt :

```bash
python3 -m compileall -q .
python3 -m pytest -q
python3 main.py --help
```

Les nouveaux modules utilitaires fonctionnent localement et n’ajoutent aucune dépendance. Le générateur de mots de passe masque le secret par défaut ; l’affichage ou la copie au presse-papiers sont des choix explicites.

Les tests automatisés couvrent les helpers locaux, les réglages visuels et les rendus d’interface ; ils ne font aucun appel réseau réel. Les fonctionnalités en ligne nécessitent des tests d’intégration séparés avec des comptes de test, des clés appartenant à l’utilisateur et des cibles explicitement autorisées.

## Dépendances

| Paquet | Usage |
|---|---|
| [Requests](https://requests.readthedocs.io/) | Requêtes HTTP |
| [Rich](https://github.com/Textualize/rich) | Interface terminal |
| [Pygments](https://pygments.org/) | Dépendance de coloration Rich |

Le reste utilise la bibliothèque standard (SQLite, sockets, TLS, JSON, argparse). Certaines fonctions dépendent d’outils système ou d’APIs tierces.

## Utilisation responsable & sécurité

- N’utilisez les tests actifs que sur vos systèmes ou avec une autorisation explicite.
- Respectez les lois, règles des plateformes et limites de requêtes.
- N’utilisez jamais de token utilisateur Discord. Les tokens de bot sont secrets : ne les collez pas dans une issue, un log ou un commit ; révoquez-les immédiatement s’ils sont exposés.
- Le panneau Discord demande une confirmation avant les actions qui modifient le serveur. N’accordez au bot que les permissions strictement nécessaires.
- Une recherche négative n’est pas une preuve d’absence ; une correspondance peut être erronée ou obsolète.

**L’utilisateur est responsable de ses actions et des cibles interrogées.**

## Contribuer

Pour signaler un bug : joignez les étapes de reproduction, Python/OS, le résultat attendu et l’erreur pertinente après avoir retiré les secrets. Pour toute modification, exécutez les tests et évitez d’ajouter des données de comptes ou d’investigation.

## Licence

Aucun fichier `LICENSE` n’est présent dans le dépôt. Ne présumez pas qu’une licence libre autorise la redistribution ou la réutilisation.
