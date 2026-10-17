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
| Navigation numérique, `0`/`00`, pagination | Non exécuté | **Testé** | Rendu `--phone` testé (largeur simulée) | Non exécuté |
| Menus et tableaux en 40–44 colonnes | Non exécuté | **Testé** (`test_platform_compat.py`) | Rendu simulé | Non exécuté |
| Appels réseau TCP/UDP (recon, cyber, pentest) | Non exécuté | **Testé hors ligne avec serveurs locaux** | Non exécuté | Non exécuté |
| Sockets TLS / certificats | Non exécuté | **Testé sur services locaux simulés** | Non exécuté | Non exécuté |
| Binaires externes (voir ci-dessous) | Vérifié à l’exécution | Vérifié à l’exécution ; détection testée | Vérifié à l’exécution | Vérifié à l’exécution |
| Privilèges élevés | Aucun requis | Aucun requis pour les outils fournis | Aucun root requis par l’application | Aucun requis |
| Photographie/GIF (Pillow) | Message explicite si absent | Message explicite si absent | Installation à valider | Message explicite si absent |
| Gateway Discord (`discord.py`) | Message explicite si absent | Message explicite si absent | Optionnel, message explicite | Message explicite si absent |
| Mode `--bot` (session en ligne) | Non exécuté (couvert par la CI) | **Testé avec un faux client `discord.py`** (aucun token réel) | Non exécuté sur téléphone | Non exécuté (couvert par la CI) |
| Introduction et bannière de démarrage | Non exécuté (couvert par la CI) | **Testé** (vérifications réelles, durée, modes texte/téléphone/interactif) | Rendu `--phone` simulé | Non exécuté (couvert par la CI) |

## Binaires externes et correction

| Outil | Windows | Linux | Termux | macOS |
|---|---|---|---|---|
| Scan WiFi | `netsh wlan show networks` | `nmcli` ou `iwlist` | **Indisponible sans root** : Android restreint l’énumération ; l’outil le dit | outil `airport` de macOS |
| Interfaces & routage | `ipconfig /all`, `route print` | `ip addr`, `ip route` (repli `ifconfig`, `netstat`) | `ip` si présent ; interfaces partielles sans root | `ifconfig`, `netstat -rn` |
| Table ARP | `arp -a` | `arp -n` ou `ip neigh` | `ip neigh` / `arp` si présents ; table possiblement partielle | `arp -n` |
| Traceroute | `tracert` | `traceroute` | `pkg install traceroute` ; certains sauts peuvent être bloqués | `traceroute` |
| Audit de la machine | API Windows (`ctypes`, `winreg`) | `/proc`, `/sys`, `machine-id` | Inventaire volontairement partiel sans root | `ioreg` pour l’UUID |

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

- Aucun run de CI n’a pu être consulté depuis cet environnement : seule la présence et la portée du
  fichier sont vérifiées localement.
- **Termux/Android n’est pas simulé depuis Linux dans la CI** : un contrôle sur un appareil Android
  réel reste nécessaire pour valider Termux de bout en bout.

## Ce qui n’a pas été validé

- Aucune exécution réelle sur un téléphone Android/Termux : la détection Termux est testée
  par simulation des variables `PREFIX`, `TERMUX_VERSION` et `ANDROID_ROOT`, pas sur appareil.
- Aucune connexion Discord réelle : le mode `--bot` est validé avec un faux client `discord.py`
  (cache des serveurs après `READY`, reconnexion, timeout, présence). L’établissement d’une vraie
  session Gateway avec un token valide n’a donc pas été prouvé.
- Aucune exécution sur Windows ni macOS dans ce dépôt ; les branches de commandes sont
  choisies automatiquement mais n’ont pas été lancées.
- Les tests réseau utilisent des serveurs locaux éphémères ou des sessions simulées ;
  aucune cible externe n’est contactée.
- Le scan WiFi Android, les interfaces masquées et certaines tables de voisins nécessitent
  des permissions système absentes de Termux sans root : la fonction est refusée, pas contournée.
