<div align="center">

# LeakFr-Tools

### OSINT · Reconnaissance · Cyber · Réseau · Discord · Astronomie

**92 outils · 7 catégories · interface terminal personnalisable**

[![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Rich](https://img.shields.io/badge/UI-Rich-222222)](https://github.com/Textualize/rich)
[![Langue](https://img.shields.io/badge/Langue-Français-0055A4)](#)

</div>

---

## Présentation

LeakFr-Tools est une boîte à outils Python en ligne de commande pour les recherches en sources ouvertes, la reconnaissance technique, les contrôles de sécurité, les diagnostics réseau et quelques utilitaires pratiques. L’interface repose sur Rich ; les préférences et dossiers d’investigation sont stockés localement.

> Les résultats dépendent des sources, des permissions et de la disponibilité des services externes. Ce dépôt ne promet pas qu’un outil fonctionne sur toutes les cibles ni qu’un résultat constitue une preuve.

## Captures d’écran

Les images ci-dessous sont des rendus de l’interface terminal fournis avec le dépôt (pas des captures d’un navigateur ou d’une connexion réelle). Elles illustrent le tableau de bord `--dashboard` et les sept catégories. Le parcours par défaut reste le menu numérique. Chaque guide de module contient un visuel statique.

| Menu principal | Vue des catégories |
|---|---|
| ![Menu principal LeakFr-Tools](docs/screenshots/menu-principal.svg) | ![Catégories LeakFr-Tools](docs/screenshots/categories.svg) |

## Catégories & guides

Le menu conserve son catalogue d’origine : sept catégories dépliables et les outils rangés dans chacune. Le thème, les badges et les panneaux restent personnalisables ; la recherche et les dossiers sont des raccourcis ajoutés sans remplacer ce parcours.

| Catégorie | Guides des modules |
|---|---|
| OSINT | [modules/osint/README.md](modules/osint/README.md) |
| Reconnaissance | [modules/recon/README.md](modules/recon/README.md) |
| Cyber | [modules/cyber/README.md](modules/cyber/README.md) |
| Pentest & réseau | [modules/pentest/README.md](modules/pentest/README.md) |
| Discord | [modules/discord/README.md](modules/discord/README.md) |
| Utilitaires | [modules/utils/README.md](modules/utils/README.md) |
| Astronomie | [modules/astro/README.md](modules/astro/README.md) |

La recherche globale indexe le nom, la description, la catégorie et des alias fonctionnels (par exemple `tls`, `courriel`, `fuzzing` ou `subnet`) ; un résultat lance l’outil directement. Elle est accessible depuis le menu principal (« Recherche globale ») et reste disponible dans le tableau de bord `--dashboard` avec `/` ou `r`.

### En un coup d’œil

- **OSINT** : profils, e-mails, archives, domaines, recherche publique et comparaison de captures archivées.
- **Reconnaissance** : DNS, domaines, IP/ASN, WHOIS et services Web.
- **Sécurité Web** : HTTP, TLS, cookies, JWT, CVE, CORS, réputation, test de webhooks, contrats OpenAPI et suivi de politique TLS.
- **Réseau & laboratoire** : connectivité, protocoles et tests actifs réservés aux cibles autorisées.
- **Discord** : panel Bot (`discord.py`, permissions effectives, modération confirmée), Server Cloner avec simulation, Emoji Cloner, GIF Studio local et Profile Studio ; panel personnel OAuth2 (`identify`, `guilds`, outils locaux hors ligne).
- **Utilitaires** : hashes, encodage, conversions, dates, corpus synthétiques et audit local de la machine.
- **Dossiers & rapports** : investigations locales, notes, sources, registre de preuves chaîné, corrélation d'observations, journal et exports JSON/Markdown.
- **Astronomie** : ISS, APOD, astéroïdes, planètes et conversions spatiales.

### Discord — clonage, emojis et médias

Les outils Discord sont accessibles depuis la catégorie **DISCORD OSINT** et, pour le clonage, depuis le panel Bot existant.

- **Server Cloner** : exporte un manifeste JSON réel (rôles, catégories, salons, surcharges), construit un plan, affiche les créations/ignorés/blocages, puis recrée la structure après deux confirmations. Le mode simulation n’écrit rien. Les membres, messages, webhooks et jetons ne sont jamais copiés. Un import partiel n’est jamais présenté comme un clone complet.
- **Emoji Cloner** : télécharge les emojis accessibles depuis le CDN officiel, vérifie signature, taille (256 Kio) et format, gère les noms en conflit et importe via l’endpoint officiel. Les fichiers téléchargés, les imports confirmés et les échecs sont distingués dans un manifeste.
- **GIF Studio** : bibliothèque locale avec empreinte SHA-256, détection de doublons, aperçu terminal, conversion GIF/WebP/APNG via Pillow, copie et publication Discord distincte de l’enregistrement local. Les URL privées ou non http(s) sont refusées.
- **Profile Studio** : prépare avatars, bannières, bios et variantes localement, avec recadrage, comparaison et historique. Aucun faux bouton « Appliquer » : l’API officielle ne permet pas de modifier le profil d’un compte utilisateur, et aucun selfbot n’est utilisé.

Permissions Bot utiles selon l’opération : `Gérer les salons`, `Gérer les rôles`, `Gérer les webhooks`, `Envoyer des messages`, `Joindre des fichiers`, `Créer une invitation`, `Gérer les emojis`. Ces permissions restent vérifiées localement puis par Discord ; la hiérarchie des rôles s’applique.

### Dossiers & rapports

Le menu principal « Dossiers & rapports » ouvre les dossiers d’investigation (SQLite local) ; la touche `d` reste un raccourci du tableau de bord `--dashboard`. Chaque dossier regroupe notes, sources, preuves et exports JSON/Markdown ; la recherche globale retrouve aussi ces fonctions (`preuve`, `corrélation`).

- **Evidence Chain Ledger** : vous choisissez un fichier local ; le registre stocke son SHA-256, sa taille, la source déclarée, une note et la date UTC, chaîne chaque entrée à la précédente et journalise les vérifications. Le fichier n’est jamais modifié. Le registre reste local : il détecte une altération, une insertion ou la suppression d’une entrée intermédiaire, pas une réécriture complète avec recalcul des empreintes ni la suppression de la dernière entrée — conservez la tête de chaîne hors du dépôt pour renforcer la vérification.
- **Finding Correlator** : normalise domaines, URL, adresses IP, e-mails et pseudos, regroupe les valeurs partagées avec leurs sources d’origine et distingue les correspondances exactes des rapprochements moins certains. Une correspondance technique n’établit pas l’identité d’une personne.

## Pistes de développement spécialisées

Cette liste mélange des fonctions **déjà livrées** (signalées comme telles) et des pistes encore ouvertes. Elle évite de dupliquer les scanners/lookup existants et privilégie les workflows de laboratoire.

1. **Differential HTTP Bench** — comparer plusieurs serveurs/proxy locaux sur les mêmes fixtures ; détecte les divergences de parsing plutôt qu’une vulnérabilité au hasard.
2. **API Contract Mutator** — dériver des cas limites d’un schéma OpenAPI local avec validations reproductibles ; **implémenté** sous le nom API Contract Lab (CYBER), hors ligne.
3. **HTTP Edge Corpus** — corpus déterministe de valeurs limites (doublons, CRLF, encodage, framing) pour parseurs/labs ; implémenté, réseau désactivé.
4. **WebSocket Frame Studio** — générer, visualiser et rejouer des trames fragmentées/contrôle contre un endpoint loopback configuré.
5. **Protocol State Simulator** — serveur TCP local pilotable par scénarios pour tester les machines à états des clients.
6. **TLS Policy Diff** — comparer deux snapshots locaux de certificats/ciphers et signaler les changements de configuration ; **implémenté** (CYBER), avec historique local et exports.
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
18. **Evidence Chain Ledger** — lier fichiers, horodatages et SHA-256 pour rendre un dossier d’audit local vérifiable ; **implémenté** dans Dossiers & rapports (registre chaîné, exports JSON/Markdown).
19. **Synthetic Identity Pack** — générer des données fictives cohérentes pour tester formulaires, pipelines et détecteurs sans données personnelles.
20. **Stateful Agent Loopback** — émuler beacon/check-in d’agents de test vers un serveur local avec journaux explicites, sans persistance ni commande système.
21. **TCP Replay Fixture** — rejouer des conversations enregistrées vers un socket local pour reproduire des bogues protocolaires.
22. **Regex Backtracking Bench** — mesurer des motifs fournis sur des entrées générées en sandbox avec limites strictes de taille/temps.
23. **Wordlist Mutation Profiles** — créer des profils de transformations déterministes et mesurer couverture/dédoublonnage sur un dataset synthétique.
24. **Archive Change Watcher** — comparer des snapshots Wayback fournis/collectés et produire une chronologie de changements documentée ; **implémenté** (OSINT), avec diff texte, chronologie et exports JSON/Markdown.
25. **Finding Correlator** — relier observations, sources et notes d’un dossier sans transformer automatiquement un indice en vulnérabilité confirmée ; **implémenté** dans Dossiers & rapports, avec provenance conservée.

Les nouvelles intégrations devraient conserver un mode hors-ligne et un mode de laboratoire explicite ; aucun test actif ne doit viser une cible sans autorisation.

## Compatibilité multiplateforme

Le tableau complet et les commandes de correction sont dans [`docs/COMPATIBILITE.md`](docs/COMPATIBILITE.md). Résumé des vérifications effectuées :

| Fonction | Windows | Linux | Termux | macOS |
|---|---|---|---|---|
| Outils Python purs (OSINT, recon, cyber, utils, astro, dossiers) | Non exécuté | **Testé sur l’hôte Linux** | Non exécuté sur téléphone | Non exécuté |
| Navigation numérique et écran étroit | Non exécuté | **Testé (40–44 colonnes)** | Rendu simulé `--phone` | Non exécuté |
| Binaires externes (WiFi, ARP, traceroute, interfaces) | Vérification à l’exécution | **Détection testée ; binaires selon la distribution** | Détection testée ; WiFi indisponible sans root | Vérification à l’exécution |
| Dépendances optionnelles (Pillow, discord.py) | Message explicite si absentes | Message explicite | Installation à valider | Message explicite |

Un outil dont le binaire manque n’est jamais simulé : il affiche la commande introuvable et la commande d’installation probable. Le choix d’environnement dans l’interface n’active ni ne désactive aucun binaire réel.

## Sélection d’un outil

La navigation est **entièrement numérique** sur tous les environnements : chaque menu affiche `[1] …`, `[2] …` et se pilote au clavier tactile d’Android comme au clavier physique. Aucun menu essentiel ne dépend des flèches directionnelles, de la souris ou d’un raccourci propre à Windows :

| Entrée | Effet |
|---|---|
| `<numéro>` + Entrée | Lancer la catégorie, l’outil ou l’action numérotée |
| `0` | Revenir au menu précédent ou annuler |
| `00` | Quitter l’application depuis n’importe quel menu |
| `98` / `99` | Page suivante / précédente dans les longues listes |
| Entrée vide | Répéter le menu ou accepter la valeur par défaut affichée |

La recherche globale reste accessible depuis le menu principal (« Recherche globale ») : elle indexe le nom, la description, la catégorie et des alias fonctionnels (`tls`, `courriel`, `subnet`…).

`--dashboard` réactive l’ancien tableau de bord à flèches sur un ordinateur de bureau. `--simple` (comportement par défaut) et les terminaux non interactifs utilisent toujours le parcours numérique catégorie puis outil. Options utiles :

```bash
python3 main.py --phone      # rendu mobile et pagination réduite
python3 main.py --text       # mode texte simple, sans couleur ni animation
python3 main.py --env termux # force l'affichage Termux sans changer l'OS réel
```

## Installation

### Prérequis

- Python 3.9 ou supérieur (testé ici avec Python 3.14)
- pip
- Un terminal compatible avec Rich (ou le mode `--text`)
- Internet pour les modules qui interrogent des services externes

### Windows (PowerShell)

```powershell
git clone https://github.com/utilisateur-exemple/LeakFr-Tools.git
cd LeakFr-Tools
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python main.py
```

Si PowerShell bloque l’activation du venv, exécute une fois
`Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` dans la fenêtre courante.

### Linux

```bash
sudo apt install python3 python3-venv python3-pip   # Debian/Ubuntu
sudo dnf install python3 python3-pip                # Fedora
git clone https://github.com/utilisateur-exemple/LeakFr-Tools.git
cd LeakFr-Tools
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python main.py
```

### macOS

```bash
brew install python@3.12
git clone https://github.com/utilisateur-exemple/LeakFr-Tools.git
cd LeakFr-Tools
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python main.py
```

### Android avec Termux (sans root)

Termux fournit Python, pip et les outils réseau de base. Aucun accès au stockage partagé n’est nécessaire tant que `data/` reste dans le dossier du dépôt.

```bash
pkg update && pkg upgrade -y
pkg install -y git python clang libjpeg-turbo libpng freetype
git clone https://github.com/utilisateur-exemple/LeakFr-Tools.git
cd LeakFr-Tools
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python main.py
```

- `clang`, `libjpeg-turbo`, `libpng` et `freetype` sont requis par Pillow (GIF Studio et Profile Studio). Sans elles, `pip install Pillow` échoue ; le message d’erreur est alors affiché par pip au lieu d’être masqué.
- `discord.py` (Gateway du panel Bot) est optionnel : sans réseau ou sans dépendance, le panel l’explique et les actions REST restent disponibles.
- Pour les outils externes, installe uniquement ce dont tu as besoin : `pkg install traceroute` (traceroute), `pkg install iproute2` (commandes `ip`). Le scan WiFi reste indisponible sans root, et l’outil le dit explicitement.
- Si tu préfères stocker les données ailleurs (carte SD, dossier partagé), définis `LEAKFR_DATA_DIR` **avant** le lancement, par exemple
  `LEAKFR_DATA_DIR=~/leakfr-data python main.py`. Le dossier `data/cases.db` existant n’est jamais déplacé automatiquement.

### Vérification des dépendances

Si une dépendance échoue, l’installation s’arrête avec le nom du paquet et la cause renvoyée par pip. Depuis l’application, **Paramètres → Compatibilité des outils** liste les commandes système réellement détectées et la correction possible, sans rien exécuter ni simuler.

## Démarrage & navigation

```bash
python3 main.py
```

Au lancement, l’écran **LEAKFR-TOOLS · INITIALISATION** détecte l’environnement (Termux est reconnu séparément de Linux), affiche les indices utilisés et propose un menu numéroté `[1] Windows` … `[5] Autre environnement`. Appuie sur Entrée pour accepter la détection, ou tapes un numéro pour corriger. Ce choix ne modifie que l’affichage et les valeurs par défaut ; il ne change jamais le système d’exploitation.

```bash
python3 main.py --help          # aide CLI
python3 main.py --version       # version affichée
python3 main.py --text          # mode texte de secours
python3 main.py --phone         # rendu mobile / terminal étroit
python3 main.py --ascii         # polices ASCII uniquement
python3 main.py --dashboard     # ancien tableau de bord à flèches (desktop)
python3 main.py --env macos     # forcer l'environnement d'affichage
```

## Architecture

- `main.py` : navigation numérique, menus Rich et point d’entrée CLI.
- `core/environment.py` : détection Windows/Linux/Termux/macOS et sélection d’affichage.
- `core/compat.py` : vérification des binaires externes et refus explicite des outils indisponibles.
- `core/catalogue.py` : catalogue unique des outils, métadonnées de navigation et moteur de recherche.
- `core/cases.py` : dossiers SQLite, notes, sources, registre de preuves et exports.
- `core/correlate.py` : normalisation et rapprochement des observations d’un dossier.
- `core/common.py`, `core/config.py`, `core/theme.py` : composants d’interface partagés, préférences et palettes.
- `core/tasks.py` : moteur commun (file, progression réelle, annulation, erreurs partielles, journal JSONL, prévention des doublons).
- `modules/<catégorie>/` : un fichier par outil ; les tests suivent le même découpage dans `tests/`.
- `modules/discord/` : client REST partagé (`discord_api.py`), calcul des permissions (`permissions.py`), Gateway `discord.py` (`gateway_bot.py`), journal local, panel Bot et sous-package `personal/` (OAuth2, API, modèles, stockage, outils locaux, rendu). Le sous-package `cloner/` sépare manifeste, planification, exécution et panel.
- `modules/discord/emoji_cloner.py` : téléchargement vérifié, planification et import d’emojis.
- `modules/media/` : bibliothèque GIF, conversion et panel ; `modules/profile_studio/` : images, modèles de bio, variantes et historique local.

## Configuration et données locales

Le fichier `data/settings.json` est créé au premier démarrage. Le menu **Paramètres** permet de choisir :

- l’environnement d’affichage (Windows, Linux, Android/Termux, macOS, autre) **sans modifier l’OS réel** ;
- le style (dashboard, classique, compact), la palette, les couleurs d’accent/texte/fond de shell ;
- la largeur du menu et la largeur de sortie (`auto`, `large`, `étroit`) ;
- le panneau latéral, les badges, la bannière, les animations ;
- le mode texte de secours (sans couleur ni animation) ;
- la pagination (5 à 50 résultats par page) et le timeout réseau (1–120 s) ;
- le diagnostic **Compatibilité des outils**, qui affiche l’état réel des binaires externes.

Toutes les préférences persistent dans `data/settings.json`. Aucun jeton Discord, mot de passe ou secret n’est écrit dans ce fichier : les clés restent dans `api_keys` (vide par défaut) et les identifiants Discord personnels dans leurs propres fichiers locaux ignorés par Git. `LEAKFR_DATA_DIR` permet de déplacer le dossier de données (utile sous Termux) sans perdre `data/cases.db`. Les dossiers d’investigation utilisent SQLite (`data/cases.db`), avec historique (`data/history.json`) et exports (`data/exports/`). GIF Studio stocke ses originaux sous `data/media/`, Profile Studio ses images et variantes sous `data/profile_studio/`, et les manifestes/rapports Discord sous `data/exports/`. Ces fichiers, comme les caches Python et les logs de test, sont ignorés par Git (`.gitignore`) : les données locales ne sont jamais versionnées. Les données collectées peuvent être sensibles : vérifiez les exports avant partage.

## Tests & vérifications

Depuis la racine du dépôt :

```bash
python3 -m compileall -q .
python3 -m pytest -q
python3 main.py --help
```

Les utilitaires, dont le corpus de cas limites HTTP, fonctionnent localement sans dépendance supplémentaire. Le corpus produit uniquement des fixtures JSON (aucune requête réseau). Le générateur de mots de passe masque le secret par défaut ; l’affichage ou la copie au presse-papiers sont des choix explicites.

La suite compte 135 tests répartis par domaine (`test_catalogue_navigation.py`, `test_core_cases.py`, `test_cyber.py`, `test_discord.py`, `test_discord_personal.py`, `test_osint_recon.py`, `test_pentest.py`, `test_utils.py`, `test_server_cloner.py`, `test_emoji_cloner.py`, `test_media.py`, `test_profile_studio.py`, `test_tasks.py`, `test_platform_compat.py`). Les tests multiplateformes vérifient la détection simulée de Termux/Windows/macOS, la navigation numérique, les menus en 40–44 colonnes, le refus explicite d’un outil absent et la conservation de `data/cases.db`. Ils s’exécutent sur l’hôte Linux de développement : **aucun test n’a été exécuté sur un téléphone Android réel dans Termux**, et l’environnement Windows/macOS n’est validé que par simulation des variables et des plateformes, pas par exécution. Aucun test ne contacte de cible réelle ni ne se connecte à la Gateway Discord : les appels HTTP/API sont simulés ou limités à des serveurs locaux éphémères, les téléchargements et imports Discord sont testés avec des sessions/API factices, et la Gateway est testée sur ses chemins d’erreur et d’arrêt propre. Aucune connexion réelle à Discord n’a été effectuée faute de token de test.

Le workflow `.github/workflows/ci.yml` installe les dépendances, compile tous les modules, vérifie les imports, le catalogue et l’absence de références supprimées, puis exécute pytest sur Ubuntu et Windows avec Python 3.9 et 3.12. Les modules en ligne nécessitent des tests d’intégration séparés, avec des comptes de test, des clés appartenant à l’utilisateur et des cibles explicitement autorisées.

## Dépendances

| Paquet | Usage | Termux |
|---|---|---|
| [Requests](https://requests.readthedocs.io/) | Requêtes HTTP | Pure Python, s’installe tel quel |
| [Rich](https://github.com/Textualize/rich) | Interface terminal | Pure Python |
| [Pygments](https://pygments.org/) | Coloration optionnelle de Rich | Pure Python |
| [discord.py](https://discordpy.readthedocs.io/) | Gateway du panel Bot (heartbeats, reconnexion, session unique) | Optionnel ; `aiohttp` peut nécessiter une compilation |
| [Pillow](https://python-pillow.org/) | Analyse, recadrage et conversion GIF/WebP/APNG (GIF Studio, Profile Studio) | Nécessite `pkg install clang libjpeg-turbo libpng freetype` |

Le reste utilise la bibliothèque standard (SQLite, sockets, TLS, JSON, argparse, file d’attente). `discord.py` s’appuie sur `aiohttp` pour la Gateway. Pillow est réellement utilisé par les médias et le Profile Studio ; sans lui, ces fonctions affichent une erreur explicite au lieu de simuler un succès. Certaines fonctions dépendent d’outils système ou d’APIs tierces.

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
