<div align="center">

# LeakFr-Tools

### OSINT · Reconnaissance · Cyber · Réseau · Discord · Astronomie

**85 outils · 8 catégories · interface terminal personnalisable**

[![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Rich](https://img.shields.io/badge/UI-Rich-222222)](https://github.com/Textualize/rich)
[![Langue](https://img.shields.io/badge/Langue-Français-0055A4)](#)

</div>

---

## Présentation

LeakFr-Tools est une boîte à outils Python en ligne de commande pour les recherches en sources ouvertes, la reconnaissance technique, les contrôles de sécurité, les diagnostics réseau et quelques utilitaires pratiques. L’interface repose sur Rich ; les préférences et dossiers d’investigation sont stockés localement.

> Les résultats dépendent des sources, des permissions et de la disponibilité des services externes. Ce dépôt ne promet pas qu’un outil fonctionne sur toutes les cibles ni qu’un résultat constitue une preuve.

## Captures d’écran

Les images ci-dessous sont des rendus de l’interface terminal fournis avec le dépôt (pas des captures d’un navigateur ou d’une connexion réelle). Elles illustrent le menu en arbre d’origine et les huit catégories. Chaque guide de module contient un visuel statique.

| Menu principal | Vue des catégories |
|---|---|
| ![Menu principal LeakFr-Tools](docs/screenshots/menu-principal.svg) | ![Catégories LeakFr-Tools](docs/screenshots/categories.svg) |

## Catégories & guides

Le menu conserve son catalogue d’origine : huit catégories dépliables et les outils rangés dans chacune. Le thème, les badges et les panneaux restent personnalisables ; la recherche et les dossiers sont des raccourcis ajoutés sans remplacer ce parcours.

| Catégorie | Guides des modules |
|---|---|
| OSINT | [modules/osint/README.md](modules/osint/README.md) |
| Reconnaissance | [modules/recon/README.md](modules/recon/README.md) |
| Cyber | [modules/cyber/README.md](modules/cyber/README.md) |
| Pentest & réseau | [modules/pentest/README.md](modules/pentest/README.md) |
| Discord | [modules/discord/README.md](modules/discord/README.md) |
| Utilitaires | [modules/utils/README.md](modules/utils/README.md) |
| Générateurs | [modules/generators/README.md](modules/generators/README.md) |
| Astronomie | [modules/astro/README.md](modules/astro/README.md) |

La recherche globale indexe le nom, la description, la catégorie et des alias fonctionnels (par exemple `tls`, `courriel`, `fuzzing` ou `subnet`) ; un résultat lance l’outil directement. Elle est accessible depuis le menu interactif avec `/` (ou `r`) et depuis le menu textuel.

### En un coup d’œil

- **OSINT** : profils, e-mails, archives, domaines et recherche publique.
- **Reconnaissance** : DNS, domaines, IP/ASN, WHOIS et services Web.
- **Sécurité Web** : HTTP, TLS, cookies, JWT, CVE, CORS, réputation et test de webhooks.
- **Réseau & laboratoire** : connectivité, protocoles et tests actifs réservés aux cibles autorisées.
- **Discord** : données publiques, bots autorisés et webhooks.
- **Utilitaires** : hashes, encodage, conversions, dates, corpus synthétiques et audit local de la machine.
- **Générateurs** : rapports système configurables, exports JSON/Markdown/HTML, compilation PyInstaller intégrée, sans transmission réseau.
- **Dossiers & rapports** : investigations locales, journal et exports JSON.
- **Astronomie** : ISS, APOD, astéroïdes, planètes et conversions spatiales.

## Pistes de développement spécialisées

Ces pistes évitent de dupliquer les scanners/lookup existants et privilégient les workflows de laboratoire. Le **corpus de cas limites HTTP** est le premier outil de cette série, disponible dans Utilitaires ; il produit des fixtures JSON locales et n’envoie aucun paquet.

1. **Differential HTTP Bench** — comparer plusieurs serveurs/proxy locaux sur les mêmes fixtures ; détecte les divergences de parsing plutôt qu’une vulnérabilité au hasard.
2. **API Contract Mutator** — dériver des cas limites d’un schéma OpenAPI local avec validations reproductibles, au lieu de scanner des endpoints inconnus.
3. **HTTP Edge Corpus** — corpus déterministe de valeurs limites (doublons, CRLF, encodage, framing) pour parseurs/labs ; implémenté, réseau désactivé.
4. **WebSocket Frame Studio** — générer, visualiser et rejouer des trames fragmentées/contrôle contre un endpoint loopback configuré.
5. **Protocol State Simulator** — serveur TCP local pilotable par scénarios pour tester les machines à états des clients.
6. **TLS Policy Diff** — comparer deux snapshots locaux de certificats/ciphers et signaler les changements de configuration.
7. **Cookie Scope Matrix** — simuler Domain/Path/SameSite/Secure avec des profils de navigateur synthétiques.
8. **CORS Regression Matrix** — transformer une politique déclarée en cas de tests et comparer les réponses à un serveur de test possédé.
9. **Loopback SSRF Sink** — récepteur local contrôlé pour observer les callbacks d’un labo, sans infrastructure externe.
10. **JWT Negative-Test Bench** — fabriquer des variantes invalides pour vérifier le rejet côté application ; aucune validation de tokens de tiers.
11. **DNS Wire Parser Corpus** — produire des réponses DNS tronquées, compressées ou malformées pour valider des parseurs locaux.
12. **SMTP STARTTLS Verifier** — tester les transitions TLS et commandes SMTP contre un serveur de laboratoire.
13. **OAuth Redirect Auditor** — valider hors-ligne les URI de retour et scénarios d’état/PKCE depuis une configuration fournie.
14. **CSP Policy Evaluator** — analyser une politique CSP avec résultats structurés et exemples de régression, sans injection distante.
15. **Request Framing Lab** — exécuter des scénarios Content-Length/Transfer-Encoding exclusivement sur un service loopback explicite.
16. **URL Canonicalization Diff** — comparer normalisation Unicode, encodage et chemins entre bibliothèques locales pour repérer les interprétations divergentes.
17. **GraphQL Schema Drift** — comparer des snapshots introspection fournis par l’utilisateur et repérer les changements de contrat.
18. **Evidence Chain Ledger** — lier fichiers, horodatages et SHA-256 pour rendre un dossier d’audit local vérifiable.
19. **Synthetic Identity Pack** — générer des données fictives cohérentes pour tester formulaires, pipelines et détecteurs sans données personnelles.
20. **Stateful Agent Loopback** — émuler beacon/check-in d’agents de test vers un serveur local avec journaux explicites, sans persistance ni commande système.
21. **TCP Replay Fixture** — rejouer des conversations enregistrées vers un socket local pour reproduire des bogues protocolaires.
22. **Regex Backtracking Bench** — mesurer des motifs fournis sur des entrées générées en sandbox avec limites strictes de taille/temps.
23. **Wordlist Mutation Profiles** — créer des profils de transformations déterministes et mesurer couverture/dédoublonnage sur un dataset synthétique.
24. **Archive Change Watcher** — comparer des snapshots Wayback fournis/collectés et produire une chronologie de changements documentée.
25. **Finding Correlator** — relier observations, sources et notes d’un dossier sans transformer automatiquement un indice en vulnérabilité confirmée.

Les nouvelles intégrations devraient conserver un mode hors-ligne et un mode de laboratoire explicite ; aucun test actif ne doit viser une cible sans autorisation.

## Sélection d’un outil

Le menu principal garde la présentation d’origine : un catalogue en arbre, une catégorie ouverte à la fois et ses outils listés dessous, avec panneau d’information. Recherche, dossiers/historique et paramètres restent accessibles en raccourci.

| Touche/action | Effet |
|---|---|
| Flèches haut/bas + Entrée | Parcourir le catalogue et lancer l’outil sélectionné |
| `s` | Ouvrir les paramètres |
| `/` ou `r` | Rechercher un outil par nom, catégorie ou fonction |
| `d` | Ouvrir la gestion des dossiers ; `h` ouvre l’historique |
| `q` / Ctrl-C | Quitter proprement |

`--simple` conserve le parcours catégorie puis outil pour les terminaux non interactifs.

## Démarrage & navigation

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

Le menu retrouve le catalogue en arbre d’origine : flèches haut/bas pour parcourir les outils, Entrée pour lancer, `s` pour les paramètres et `q` pour quitter. La recherche (`/` ou `r`) et les dossiers (`d`) sont accessibles comme raccourcis. Dans un terminal non interactif, le menu textuel demande d’abord la catégorie, puis l’outil.

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

Les utilitaires, dont le corpus de cas limites HTTP, fonctionnent localement sans dépendance supplémentaire. Le corpus produit uniquement des fixtures JSON (aucune requête réseau). Le générateur de mots de passe masque le secret par défaut ; l’affichage ou la copie au presse-papiers sont des choix explicites.

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
