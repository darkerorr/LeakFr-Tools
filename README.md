 <div align="center">

# LeakFr-Tools

### OSINT · Reconnaissance · Réseau · Cybersécurité

*Plusieurs outils, un seul terminal.*

[![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![Interface](https://img.shields.io/badge/Interface-Rich-222222?style=flat-square)](https://github.com/Textualize/rich)
[![Langue](https://img.shields.io/badge/Langue-Fran%C3%A7ais-0055A4?style=flat-square)](#)
[![Projet](https://img.shields.io/badge/Projet-en%20%C3%A9volution-orange?style=flat-square)](#)

[**Voir le dépôt GitHub**](https://github.com/darkerorr/LeakFr-Tools)

</div>

---

## Présentation

**LeakFr-Tools** rassemble des outils d'OSINT, de reconnaissance technique, d'analyse réseau, de cybersécurité et différents utilitaires dans une seule interface terminal.

Le projet est développé en Python et s'appuie sur **Rich** pour afficher ses menus, tableaux et panneaux. Chaque catégorie possède ses propres modules, ce qui permet de retrouver rapidement les outils selon le type de recherche à effectuer.

Le projet comprend également un système de thèmes personnalisables, des paramètres persistants et une gestion locale de dossiers d'investigation avec SQLite.

> Le projet évolue encore. La présence d'un outil dans le menu ne garantit pas qu'il fonctionnera dans toutes les situations. Les résultats dépendent notamment du module utilisé, de la connexion et des services interrogés.

## Sommaire

- [Fonctionnalités](#fonctionnalités)
- [Installation](#installation)
- [Démarrage](#démarrage)
- [Paramètres et thèmes](#paramètres-et-thèmes)
- [Dossiers d'investigation](#dossiers-dinvestigation)
- [Organisation du projet](#organisation-du-projet)
- [Dépendances](#dépendances)
- [Utilisation responsable](#utilisation-responsable)
- [Contribuer](#contribuer)
- [Licence](#licence)

---

## Fonctionnalités

<table>
<tr>
<td width="50%" valign="top">

### 🔎 OSINT

- Recherche de pseudonymes sur différentes plateformes
- Analyse d'adresses e-mail
- Consultation des archives Wayback Machine
- Lecture de `robots.txt` et des sitemaps
- Analyse d'URL
- Génération de Google Dorks
- Informations liées aux numéros de téléphone
- Génération de liens de recherche

</td>
<td width="50%" valign="top">

### 🌐 RECON

- Requêtes DNS et résolution inverse
- Informations ASN et WHOIS
- Géolocalisation approximative d'adresses IP
- Recherche de sous-domaines via des sources publiques
- Vérifications SPF et DMARC
- Détection indicative de technologies web
- Vérification HTTP
- Recherche liée aux adresses MAC

</td>
</tr>
<tr>
<td width="50%" valign="top">

### 🛡️ CYBER

- Audit d'en-têtes HTTP
- Inspection de certificats SSL/TLS
- Analyse de redirections et de cookies
- Vérifications DNSBL
- Inspection de jetons JWT
- Recherche de vulnérabilités CVE
- Contrôle CORS
- Mesure de latence TCP

</td>
<td width="50%" valign="top">

### 🧭 PENTEST & RÉSEAU

- Scan de ports et récupération de bannières
- Informations sur les interfaces et routes réseau
- Consultation de la table ARP
- Diagnostic réseau local et Wi-Fi
- Outils de vérification DNS et HTTP
- Génération de wordlists
- Tests techniques sur des environnements autorisés

</td>
</tr>
<tr>
<td width="50%" valign="top">

### 💬 DISCORD

- Recherche d'informations accessibles via des identifiants
- Consultation de données publiques liées aux invitations et widgets
- Analyse de Snowflakes
- Génération de liens d'invitation de bots
- Outils d'administration liés aux bots et aux webhooks

</td>
<td width="50%" valign="top">

### 🧰 UTILITAIRES & ASTRONOMIE

- Identification et génération de hachages
- Encodage et décodage
- Évaluation de la robustesse d'un mot de passe
- Calcul CIDR
- Hachage de fichiers
- Validation Luhn
- Analyse de User-Agent et conversion de timestamps
- Informations astronomiques, ISS, planètes et astéroïdes

</td>
</tr>
</table>

### Vue d'ensemble

| Catégorie | Contenu |
|---|---|
| **OSINT** | Pseudonymes, e-mails, archives web et recherches |
| **RECON** | DNS, IP, ASN, WHOIS et sous-domaines |
| **CYBER** | En-têtes, TLS, cookies, JWT et CVE |
| **PENTEST** | Tests techniques et diagnostics réseau |
| **DISCORD** | Identifiants, invitations, widgets et bots |
| **UTILS** | Hachages, encodage, CIDR et conversions |
| **ASTRO** | ISS, planètes et informations célestes |

*Les fonctionnalités disponibles et leurs résultats dépendent de l'implémentation de chaque module et de son environnement.*

---

## Installation

### Prérequis

- Python **3.9 ou supérieur**
- `pip`
- Un terminal compatible
- Une connexion Internet pour les outils qui interrogent des services externes

Certaines fonctions peuvent dépendre du système d'exploitation, des permissions ou de services tiers.

### 1. Récupérer le projet

```bash
git clone https://github.com/darkerorr/LeakFr-Tools.git
cd LeakFr-Tools
```

Si tu possèdes déjà le projet, ouvre simplement un terminal dans son dossier.

### 2. Créer un environnement virtuel

**Windows — PowerShell**

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**Windows — CMD**

```bat
py -m venv .venv
.venv\Scripts\activate.bat
```

**Linux**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

L'environnement virtuel permet d'isoler les dépendances du projet du reste de ton installation Python.

### 3. Installer les dépendances

Depuis la racine du dépôt :

```bash
python -m pip install -r requirements.txt
```

Si la commande `python` ne fonctionne pas sous Windows, essaie :

```powershell
py -m pip install -r requirements.txt
```

---

## Démarrage

Une fois les dépendances installées, lance l'application :

```bash
python main.py
```

Sous Windows, cette commande fonctionne également dans de nombreuses installations :

```powershell
py main.py
```

L'interface terminal s'ouvre et permet de naviguer entre les catégories et les outils.

**Conseil :** lance le programme depuis la racine du dépôt afin d'éviter les problèmes de chemins relatifs et d'importation des modules.

---

## Paramètres et thèmes

LeakFr-Tools dispose d'un système de configuration local et d'un gestionnaire de thèmes.

Les paramètres comprennent notamment :

- La sélection d'un thème prédéfini
- L'activation ou la désactivation de la bannière de démarrage
- Le contrôle des animations
- Le réglage du délai d'attente réseau
- La restauration des paramètres par défaut

Les palettes permettent de modifier les couleurs de l'interface. Les préférences sont conservées localement pour être réutilisées lors des prochains lancements.

Les options peuvent évoluer au fil du développement : le menu de l'application reste la référence pour connaître celles qui sont disponibles dans la version installée.

## Dossiers d'investigation

Le projet comprend un système de gestion de dossiers reposant sur SQLite. Il permet notamment de conserver :

- Des dossiers avec un titre et une description
- Des notes et observations
- Des sources accompagnées de métadonnées
- Un historique local
- Des exports de dossiers au format JSON

### Stockage local

Les chemins configurés par défaut se trouvent dans le dossier `data/`.

| Chemin | Utilisation |
|---|---|
| `data/settings.json` | Préférences et configuration |
| `data/cases.db` | Base de données SQLite des dossiers |
| `data/history.json` | Historique |
| `data/exports/` | Dossier destiné aux exports |
| `data/logs/` | Dossier destiné aux journaux |

Certains fichiers et dossiers sont créés lors de l'exécution et peuvent ne pas exister avant le premier lancement.

Les données enregistrées peuvent contenir des informations sensibles. Vérifie leur contenu avant de les partager ou de les ajouter au dépôt.

---

## Organisation du projet

Le code est organisé autour d'un point d'entrée et de modules regroupés par domaine.

```text
LeakFr-Tools/
├── main.py
├── requirements.txt
├── core/
│   ├── common.py
│   ├── config.py
│   ├── theme.py
│   └── cases.py
├── modules/
│   ├── osint/
│   ├── recon/
│   ├── cyber/
│   ├── pentest/
│   ├── discord/
│   ├── utils/
│   └── astro/
└── data/
    ├── settings.json
    ├── cases.db
    ├── history.json
    ├── exports/
    └── logs/
```

| Fichier ou dossier | Rôle |
|---|---|
| `main.py` | Point d'entrée, menus et navigation |
| `core/common.py` | Fonctions communes et interface terminal |
| `core/config.py` | Configuration et chemins locaux |
| `core/theme.py` | Palettes et gestion des couleurs |
| `core/cases.py` | Dossiers, notes, sources et historique |
| `modules/` | Outils classés par catégorie |
| `data/` | Données locales générées pendant l'utilisation |

---

## Dépendances

Les principales bibliothèques déclarées dans `requirements.txt` sont :

| Bibliothèque | Utilisation |
|---|---|
| [Requests](https://requests.readthedocs.io/) | Requêtes HTTP |
| [Rich](https://github.com/Textualize/rich) | Interface terminal |
| [Pygments](https://pygments.org/) | Coloration et traitement de texte |

Le projet utilise également des modules de la bibliothèque standard de Python, notamment SQLite pour le stockage local.

Les outils qui interrogent des services externes peuvent être affectés par les délais d'attente, les limites de requêtes, les changements d'API ou les restrictions de ces services.

## Utilisation responsable

Les résultats techniques doivent être interprétés avec prudence et recoupés lorsque c'est nécessaire.

- Utilise les tests actifs uniquement sur des systèmes que tu possèdes ou pour lesquels tu disposes d'une autorisation explicite.
- Respecte les lois applicables et les conditions d'utilisation des services consultés.
- Ne cherche pas à accéder à des comptes, des données ou des systèmes sans autorisation.
- Ne partage pas de mots de passe, de jetons de session ou de clés API.
- Vérifie les sources avant d'intégrer une information à un rapport.
- Garde à l'esprit qu'une donnée publique peut être incomplète, ancienne ou erronée.

Une recherche sans résultat ne prouve pas qu'un compte ou un actif n'existe pas. De même, un résultat positif peut correspondre à une homonymie ou à une association incorrecte.

**L'utilisateur est responsable de l'utilisation qu'il fait de l'outil.** La présence d'une fonctionnalité dans le projet ne constitue pas une autorisation de l'utiliser sur une cible donnée.

## Contribuer

Les retours, corrections et améliorations peuvent être proposés via le dépôt GitHub.

Pour signaler un problème, indique si possible :

1. Les étapes permettant de le reproduire
2. Le système d'exploitation et la version de Python
3. Le résultat attendu et le résultat obtenu
4. Le message d'erreur pertinent, en masquant les informations sensibles

Avant de proposer une modification, vérifie qu'elle ne casse pas la navigation, les thèmes ou les autres modules.

## Licence

Aucun fichier de licence n'a été confirmé lors de la rédaction de ce README. Tant qu'une licence n'est pas ajoutée au dépôt, ne considère pas le projet comme librement réutilisable ou redistribuable.

---

<div align="center">

**LeakFr-Tools**

*Une boîte à outils en évolution, réunie dans un seul terminal.*

[GitHub · darkerorr/LeakFr-Tools](https://github.com/darkerorr/LeakFr-Tools)

</div>
