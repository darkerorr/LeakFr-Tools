# Cyber — contrôles de sécurité

Contrôles HTTP/TLS et inspection locale de données fournies par l’utilisateur. Ils donnent des indications et ne remplacent ni un audit professionnel ni une validation manuelle.

![Aperçu de la catégorie Cyber](../../docs/screenshots/categories/cyber.svg)

| Outil | Fonction | Aperçu |
|---|---|---|
| Audit des headers | Vérifie des en-têtes de défense HTTP courants. | ![Headers](../../docs/screenshots/modules/cyber/audit-des-headers.svg) |
| Scan de ports | Contrôle une sélection de ports TCP courants. | ![Ports](../../docs/screenshots/modules/cyber/scan-de-ports.svg) |
| Certificat SSL/TLS | Affiche validité et éléments du certificat présenté. | ![TLS](../../docs/screenshots/modules/cyber/certificat-ssl-tls.svg) |
| Chaîne de redirections | Suit les redirections HTTP rencontrées. | ![Redirections](../../docs/screenshots/modules/cyber/chaine-de-redirections.svg) |
| Audit des cookies | Signale les attributs Secure, HttpOnly et SameSite. | ![Cookies](../../docs/screenshots/modules/cyber/audit-des-cookies.svg) |
| DNSBL / réputation IP | Consulte des listes publiques de réputation. | ![DNSBL](../../docs/screenshots/modules/cyber/dnsbl-reputation-ip.svg) |
| Décodeur JWT | Décode l’en-tête et le payload **sans vérifier la signature**. | ![JWT](../../docs/screenshots/modules/cyber/decodeur-jwt.svg) |
| Recherche CVE | Recherche des entrées CVE via les sources disponibles. | ![CVE](../../docs/screenshots/modules/cyber/recherche-cve.svg) |
| Latence TCP | Mesure une connexion TCP et éventuellement une bannière légère. | ![Latence](../../docs/screenshots/modules/cyber/latence-tcp.svg) |
| Test CORS | Observe les en-têtes CORS renvoyés par une cible. | ![CORS](../../docs/screenshots/modules/cyber/test-cors.svg) |

## Utilisation

Lancez `python3 main.py` puis choisissez **CYBER**. Pour les tests réseau, ne ciblez que vos propres systèmes ou un actif explicitement autorisé. Ne partagez pas les JWT ou données qui y sont encodées.

Les illustrations sont des aperçus statiques du menu, et non des résultats d’audit.
