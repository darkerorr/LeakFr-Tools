# Matrice de compatibilité multiplateforme

Cette matrice décrit ce qui a réellement été vérifié. Elle distingue :

- **Testé** : exécuté sur cette machine ou couvert par un test automatisé reproductible ;
- **Vérifié à l’exécution** : le module contrôle la présence du binaire avant de lancer la commande ; le résultat dépend de l’installation locale ;
- **Non exécuté** : aucun test réel n’a été mené sur cette plateforme dans ce dépôt. Ce n’est pas une promesse de fonctionnement.

La sélection Windows/Linux/Android/macOS dans l’interface n’active jamais un outil :
elle ne change que l’affichage et les valeurs par défaut. Les binaires sont vérifiés sur
le système réellement détecté.

## Vue d’ensemble

| Fonction | Windows | Linux | Termux (Android) | macOS |
|---|---|---|---|---|
| Outils Python purs (OSINT, recon, cyber, utilitaires, astro, dossiers) | Non exécuté | **Testé sur l’hôte Linux** | Non exécuté sur téléphone | Non exécuté |
| Navigation numérique, `0`/`00`, pagination | Non exécuté | **Testé** | Rendu `--phone` testé (largeur de terminal forcée) | Non exécuté |
| Menus et tableaux en 40–44 colonnes | Non exécuté | **Testé** (`test_platform_compat.py`) | Largeur 40–44 colonnes forcée | Non exécuté |
| Appels réseau TCP/UDP (recon, cyber, pentest) | Non exécuté | **Testé** : serveurs locaux + appels réels (DNS, HTTP, WHOIS) vers des domaines publics | Non exécuté | Non exécuté |
| Sockets TLS / certificats | Non exécuté | **Testé sur certificats réels** (github.com, TLSv1.3) et sur sockets locales | Non exécuté | Non exécuté |
| Binaires externes (voir ci-dessous) | Vérifié à l’exécution | Vérifié à l’exécution ; détection testée | Vérifié à l’exécution | Vérifié à l’exécution |
| Privilèges élevés | Aucun requis | Aucun requis pour les outils fournis | Aucun root requis par l’application | Aucun requis |
| Photographie/GIF (Pillow) | Message explicite si absent | Message explicite si absent | Installation à valider | Message explicite si absent |
| Gateway Discord (`discord.py`) | Message explicite si absent | Message explicite si absent | Optionnel, message explicite | Message explicite si absent |
| Mode `--bot` (session en ligne) | Non exécuté (couvert par la CI) | **Testé avec un faux client `discord.py`** (aucun token réel) | Non exécuté sur téléphone | Non exécuté (couvert par la CI) |
| Introduction et bannière de démarrage | Non exécuté (couvert par la CI) | **Testé** (phases adossées aux mesures réelles : système, Python, terminal, catalogue et contrôles ; modes texte/téléphone/interactif) | Rendu `--phone` et compact (largeur forcée) | Non exécuté (couvert par la CI) |
| En-tête LEAKFR dans les menus | Non exécuté (couvert par la CI) | **Testé** (logo complet, bandeau compact ≤ 44 colonnes) | Bandeau compact ≤ 44 colonnes (largeur forcée) | Non exécuté (couvert par la CI) |

## Binaires externes et correction

| Outil | Windows | Linux | Termux | macOS |
|---|---|---|---|---|
| Scan WiFi | `netsh wlan show networks` | `nmcli` ou `iwlist` | **Indisponible sans root** : Android restreint l’énumération ; l’outil le dit | outil `airport` de macOS |
| Interfaces & routage | `ipconfig /all`, `route print` | `ip addr`, `ip route` (repli `ifconfig`, `netstat`) | `ip` si présent ; interfaces partielles sans root | `ifconfig`, `netstat -rn` |
| Table ARP | `arp -a` | `arp -n` ou `ip neigh` | `ip neigh` / `arp` si présents ; table possiblement partielle | `arp -n` |
| Traceroute | `tracert` | `traceroute` | `pkg install traceroute` ; certains sauts peuvent être bloqués | `traceroute` |
| Audit de la machine | API Windows (`ctypes`, `winreg`) | `/proc`, `/sys`, `machine-id` | Inventaire volontairement partiel sans root | `ioreg` pour l’UUID |

Au démarrage, la présence de ces binaires est vérifiée avec `shutil.which`, puis une
commande de version explicite (`--version`, `-V`) est lancée avec `shell=False`, une
sortie capturée et un délai maximal de 1,2 s (2,5 s pour l'ensemble). Une version
illisible reste `VERSION UNKNOWN` ; un binaire absent est listé comme absent. Aucun
scan réseau, aucune connexion distante et aucune force brute ne sont déclenchés par
l'introduction.

Corrections usuelles :

```bash
# Debian/Ubuntu
sudo apt install iproute2 net-tools traceroute network-manager

# Fedora
sudo dnf install iproute net-tools traceroute NetworkManager

# macOS (Homebrew)
brew install traceroute

# Termux
pkg install iproute2 traceroute
```

## Comportement des outils indisponibles

- `core/compat.py` vérifie `shutil.which` et les chemins système avant l’appel.
- Un outil indisponible affiche le nom de la commande manquante, une cause et, si connue,
  la commande d’installation probable.
- **Aucune action n’est simulée** : le message « Aucune action n’a été simulée » est
  explicite et le journal local n’enregistre pas de faux succès.
- Le diagnostic est accessible dans **Paramètres → Compatibilité des outils**.

## Intégration continue

Le workflow `.github/workflows/ci.yml` est suivi par Git (`.gitignore` ne l’exclut plus). Il cible
`ubuntu-latest`, `windows-latest` et `macos-latest` avec Python 3.9 et 3.12, puis compile, vérifie
les imports/le catalogue/la compatibilité, l’interface CLI (`--version`, `--help`) et exécute pytest.

- La partie Linux de la matrice a été rejouée localement dans les conteneurs officiels
  `python:3.9-slim` et `python:3.12-slim` : compilation et suite de tests vertes sur les deux
  versions. Aucun run GitHub Actions n’a pu être consulté depuis cet environnement, et
  Windows/macOS ne sont pas exécutés localement.
- **Termux/Android n’est pas exécuté depuis Linux dans la CI** : la détection Termux est testée en
  forçant les variables `PREFIX`, `TERMUX_VERSION` et `ANDROID_ROOT` ; un contrôle sur un appareil
  Android réel reste nécessaire pour valider Termux de bout en bout.

## Ce qui n’a pas été validé

- Aucune exécution réelle sur un téléphone Android/Termux : la détection Termux est testée en
  forçant les variables `PREFIX`, `TERMUX_VERSION` et `ANDROID_ROOT`, pas sur appareil.
- Aucune connexion Discord réelle : le mode `--bot` est validé avec un faux client `discord.py`
  (cache des serveurs après `READY`, reconnexion, timeout, présence). L’établissement d’une vraie
  session Gateway avec un token valide n’a donc pas été prouvé.
- Aucune exécution sur Windows ni macOS dans ce dépôt ; les branches de commandes sont
  choisies automatiquement mais n’ont pas été lancées.
- Les tests automatisés n’appellent aucun service externe : ils utilisent des serveurs locaux
  éphémères, des sockets locales et des doubles de test. Les appels réels ont été passés à la main
  (voir « Vérifications réelles exécutées » ci-dessous) ; ils ne sont pas rejoués dans la CI pour
  éviter des échecs liés à la disponibilité des services tiers.
- Le scan WiFi Android, les interfaces masquées et certaines tables de voisins nécessitent
  des permissions système absentes de Termux sans root : la fonction est refusée, pas contournée.

## Vérifications réelles exécutées

Ces exécutions ont été lancées hors tests, sur le réseau réel, et leurs sorties brutes ont été
constatées (aucun résultat fabriqué) :

| Outil | Cible réelle | Résultat observé |
|---|---|---|
| Enregistrements DNS | `example.com` | 2 A, 2 AAAA, MX, 2 NS (`elliott.ns.cloudflare.com`, `hera.ns.cloudflare.com`), 2 TXT |
| Sonde HTTP | `example.com` | HTTP 200 en 56 ms, 577 octets, serveur `cloudflare`, titre « Example Domain » |
| Certificat SSL/TLS | `github.com` | Sectigo DV E36, valide jusqu’au 29/11/2026, TLSv1.3, `TLS_AES_128_GCM_SHA256` |
| Image du jour NASA (APOD) | `api.nasa.gov` | Requête réelle, titre et explication renvoyés |
| Astéroïdes NASA (NeoWs) | `api.nasa.gov` | Passages du jour listés avec diamètre, vitesse et distance réels |
| Recherche de pseudo | 91 plateformes publiques | 48 profils trouvés en 12,2 s (pseudo de test) |
| Découverte d’hôtes locaux | réseau local de la machine | IP locale mesurée (192.168.0.160), ping ICMP système réel, hostnames réels |
