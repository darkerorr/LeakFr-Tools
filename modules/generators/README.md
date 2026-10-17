# Générateurs — scripts autonomes locaux

La catégorie contient **1 outil** : un assembleur de scripts Python autonomes. Les scripts produits n'utilisent que la bibliothèque standard, n'ouvrent aucune connexion et n'écrivent que les exports JSON explicitement demandés.

![Aperçu de la catégorie Générateurs](../../docs/screenshots/categories/generateurs.svg)

| Outil | Fonction | Aperçu |
|---|---|---|
| Générateur de scripts | Assemble un script Python à partir d'une liste fermée de sections, avec nom de fichier au choix et commande PyInstaller. | ![Générateur de scripts](../../docs/screenshots/modules/generateurs/generateur-de-scripts.svg) |

## Sections disponibles

1. **Rapport système + HWID** — OS, hôte, utilisateur, CPU, cœurs, stockage, identifiants locaux et hash SHA-256 présenté en blocs.
2. **Inventaire d'un dossier** — parcours récursif, taille et SHA-256 de chaque fichier (`script hash <dossier>`).
3. **Métadonnées d'un fichier** — chemin, taille, type MIME, date de modification et SHA-256 (`script fichier <chemin>`).
4. **Export JSON local** — écrit le rapport à côté du script, dans le dossier courant.

Aucune section ne collecte de cookies, de mots de passe, de jetons ou de contenu de navigateur, et aucune ne transmet quoi que ce soit.

## Utilisation

Lancez `python3 main.py`, ouvrez **GENERATEURS** puis **Generateur de scripts**. Choisissez les numéros de sections, le nom du fichier, puis exécutez-le :

```bash
python3 rapport-machine.py
python3 rapport-machine.py hash ./mon-dossier
python3 rapport-machine.py fichier ./mon-fichier.bin
```

Pour un exécutable, l'outil affiche la commande :

```bash
pyinstaller --onefile --name rapport-machine rapport-machine.py
```

PyInstaller reste une dépendance externe optionnelle : le dépôt ne l'installe pas et le script généré fonctionne sans lui.

## Périmètre

Le générateur écrit un script que vous lancez vous-même sur votre machine. Il ne produit ni persistance, ni exfiltration, ni contournement de contrôle d'accès. Les scripts générés affichent leurs résultats dans le terminal ; le seul fichier écrit est l'export JSON local de la section 4.
