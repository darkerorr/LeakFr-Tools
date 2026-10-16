# Reconnaissance — DNS, IP et services

Vérifications techniques et données de sources publiques. Une adresse IP ou un domaine doit être celui d’un actif que vous êtes autorisé à examiner.

![Aperçu de la catégorie Reconnaissance](../../docs/screenshots/categories/reconnaissance.svg)

| Outil | Fonction | Aperçu |
|---|---|---|
| Enregistrements DNS | Interroge les enregistrements A, AAAA, MX, NS et TXT. | ![DNS](../../docs/screenshots/modules/recon/enregistrements-dns.svg) |
| Reverse DNS (PTR) | Cherche le nom associé à une adresse IP. | ![Reverse DNS](../../docs/screenshots/modules/recon/reverse-dns-ptr.svg) |
| Géolocalisation IP | Estime le pays/la région via un service tiers. | ![Géolocalisation](../../docs/screenshots/modules/recon/geolocalisation-ip.svg) |
| Info ASN / réseau | Recherche l’ASN et des informations publiques réseau. | ![ASN](../../docs/screenshots/modules/recon/info-asn-reseau.svg) |
| WHOIS | Consulte les informations d’enregistrement disponibles. | ![WHOIS](../../docs/screenshots/modules/recon/whois.svg) |
| Sous-domaines | Recherche des noms publiés dans les certificats publics. | ![Sous-domaines](../../docs/screenshots/modules/recon/sous-domaines.svg) |
| SPF / DMARC / DKIM | Examine les mécanismes de sécurité mail publiés en DNS. | ![Mail](../../docs/screenshots/modules/recon/spf-dmarc-dkim.svg) |
| Détection techno | Signale des technologies web détectables publiquement. | ![Technos](../../docs/screenshots/modules/recon/detection-techno.svg) |
| Sonde HTTP | Vérifie statut, latence et métadonnées HTTP simples. | ![HTTP](../../docs/screenshots/modules/recon/sonde-http.svg) |
| Lookup MAC | Cherche le fabricant correspondant à un préfixe OUI. | ![MAC](../../docs/screenshots/modules/recon/lookup-mac.svg) |

## Utilisation

Démarrez `python3 main.py`, ouvrez **RECONNAISSANCE** et sélectionnez l’outil. Les données de géolocalisation et WHOIS sont indicatives et peuvent être incomplètes ou anciennes.

Les visuels sont des aperçus statiques du menu, sans requête réseau exécutée.
