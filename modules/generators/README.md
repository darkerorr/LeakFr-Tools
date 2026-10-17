# Générateurs — rapports système autonomes

La catégorie contient **1 outil** : un assembleur de rapports système. Le script produit n'utilise que la bibliothèque standard, ne dépend d'aucun module du projet et n'effectue aucune transmission réseau.

![Aperçu de la catégorie Générateurs](../../docs/screenshots/categories/generateurs.svg)

| Outil | Fonction | Aperçu |
|---|---|---|
| Générateur de scripts | Configure et assemble un rapport système multi-sections, l'exporte en JSON, Markdown et HTML, puis propose de l'exécuter ou de le compiler. | ![Générateur de scripts](../../docs/screenshots/modules/generateurs/generateur-de-scripts.svg) |

## Parcours de génération

1. **Informations générales** — nom du script (validé, `.py` forcé), nom du rapport, formats, répertoire de sortie, profil (`minimal`, `standard`, `détaillé`).
2. **Sections** — sélection numérotée, description et caractère sensible affichés, confirmation avant de continuer, correction possible.
3. **Options** — fichiers/dossiers à inventorier, extensions autorisées, limite de fichiers, exclusions, limite de logiciels, activation explicite du compte, du dossier personnel et du HWID, détail des erreurs (`complet`/`résumé`), mode de sortie (`terminal`, `fichier`, `les_deux`).
4. **Aperçu** — récapitulatif complet (sections, champs sensibles, formats, dossier, transmission) avec retour possible vers les sections ou les options.
5. **Compilation** — fichier seul, exécution immédiate, compilation PyInstaller, ou test local suivi d'une proposition de compilation.

## Sections disponibles

| Clé | Contenu | Sensible |
|---|---|---|
| `systeme` | OS, version, build, architecture, hôte, démarrage, langue, fuseau. | non |
| `materiel` | Processeur, cœurs, mémoire, fabricant/modèle, GPU détectés. | non |
| `disques` | Points de montage, capacité, espace libre, taux d'utilisation. | non |
| `reseau` | Interfaces, état, adresses privées, passerelle, DNS. | oui |
| `logiciels` | Registre Windows ou `dpkg`, avec limite. | non |
| `dev` | Versions de Python, Git, pip, Node, GCC, .NET, PowerShell. | non |
| `peripheriques` | Compteurs de classes et composants détectés. | non |
| `fichiers` | Inventaire limité avec taille, extension, date, SHA-256. | oui |
| `session` | Utilisateur, domaine, shell, dossier personnel (explicite). | oui |
| `empreinte` | HWID SHA-256, désactivé par défaut. | oui |
| `historique` | Résumé des exports JSON précédents. | non |

Chaque collecteur gère l'absence de données, les permissions refusées et les différences Windows/Linux : il retourne un statut `ok`, `partiel`, `indisponible` ou `erreur`, et une erreur n'interrompt jamais le rapport.

## Formats

- **JSON** — schéma stable `leakfr.system-report.v1`.
- **Markdown** — sommaire, synthèse, tableaux par section, section « Erreurs et limites ».
- **HTML** — autonome, CSS en ligne, aucun script distant.

Les trois formats sont produits à partir du même rapport structuré. Les noms incluent un horodatage et un suffixe numérique en cas de collision : aucun fichier existant n'est écrasé.

## Compilation

Le module `build.py` vérifie le script, l'installation de PyInstaller, construit les arguments sans concaténation de chemins, lance le processus avec un délai maximal, contrôle le code de sortie **et** la présence réelle de l'exécutable. Le succès n'est annoncé que si l'artefact existe. Si PyInstaller est absent, la commande `pip install pyinstaller` est proposée sans installation silencieuse. L'exécutable produit n'est jamais lancé automatiquement.

## Limites

- L'inventaire logiciel dépend du registre Windows ou de `dpkg` ; les autres systèmes renvoient `indisponible`.
- Les GPU et périphériques sont détectés via `lspci`, `wmic` ou `/sys` lorsqu'ils sont présents.
- La transmission vers un webhook n'est pas générée : les scripts écrivent leurs rapports localement.
