# Utilitaires — transformations locales

La suite contient maintenant **15 outils**. Tous les nouveaux calculateurs fonctionnent localement et n’ajoutent aucune dépendance.

Outils essentiellement locaux pour les formats, checksums, valeurs numériques et informations de texte. Les mots de passe saisis ne doivent pas être réutilisés ; le score de robustesse est une estimation.

![Aperçu de la catégorie Utilitaires](../../docs/screenshots/categories/utilitaires.svg)

| Outil | Fonction | Aperçu |
|---|---|---|
| Identifier un hash | Estime les formats de hash compatibles à partir de leur apparence. | ![Identifier](../../docs/screenshots/modules/utils/identifier-un-hash.svg) |
| Générateur de hash | Calcule plusieurs digests d’une chaîne fournie. | ![Générateur](../../docs/screenshots/modules/utils/generateur-de-hash.svg) |
| Encode / Decode | Encode ou décode Base64, URL et hex. | ![Encode](../../docs/screenshots/modules/utils/encode-decode.svg) |
| Force mot de passe | Estime la diversité et l’entropie d’un secret localement. | ![Mot de passe](../../docs/screenshots/modules/utils/force-mot-de-passe.svg) |
| Calculateur CIDR | Calcule réseau, plage et hôtes IPv4/IPv6. | ![CIDR](../../docs/screenshots/modules/utils/calculateur-cidr.svg) |
| Hash de fichier | Calcule des checksums de fichier sans modifier la source. | ![Fichier](../../docs/screenshots/modules/utils/hash-de-fichier.svg) |
| Validateur Luhn | Vérifie le checksum Luhn d’une valeur numérique. | ![Luhn](../../docs/screenshots/modules/utils/validateur-luhn.svg) |
| Parseur User-Agent | Identifie des indices de navigateur, OS ou robot dans un UA. | ![UA](../../docs/screenshots/modules/utils/parseur-user-agent.svg) |
| Timestamp | Convertit des timestamps et dates UTC. | ![Timestamp](../../docs/screenshots/modules/utils/timestamp.svg) |
| Générateur de mot de passe | Génère localement un secret aléatoire configurable, masqué par défaut. | ![Mot de passe aléatoire](../../docs/screenshots/modules/utils/generateur-de-mot-de-passe.svg) |
| Formateur JSON | Valide puis formate ou compacte un texte JSON. | ![JSON](../../docs/screenshots/modules/utils/formateur-json.svg) |
| Analyseur de texte | Calcule localement des compteurs et termes fréquents. | ![Analyse texte](../../docs/screenshots/modules/utils/analyseur-de-texte.svg) |
| Générateur UUID | Génère des UUID v4 locaux en lot. | ![UUID](../../docs/screenshots/modules/utils/generateur-uuid.svg) |
| Convertisseur de bases | Convertit des entiers entre binaire, octal, décimal et hexadécimal. | ![Bases](../../docs/screenshots/modules/utils/convertisseur-de-bases.svg) |
| Calculateur de dates | Calcule une différence ou un décalage entre dates. | ![Dates](../../docs/screenshots/modules/utils/calculateur-de-dates.svg) |

## Utilisation

Lancez `python3 main.py` et choisissez **UTILITAIRES**. N’entrez pas de secrets de production : même sans sauvegarde, un terminal ou une capture peut conserver les entrées.

Les illustrations sont des aperçus statiques du menu, sans données réelles.
