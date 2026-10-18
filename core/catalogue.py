"""Catalogue unique des outils, métadonnées de navigation et moteur de recherche.

Ce module est la seule source de vérité pour la liste des outils : le menu,
la recherche globale, les captures d'écran et les tests le lisent tous ici.
Les actions transverses qui dépendent de l'interface (dossiers, historique)
sont fournies à `rechercher_outils` via le paramètre `extras`.
"""
import unicodedata

from core.common import (
    C_OSINT, C_RECON, C_CYBER, C_PENTEST, C_UTIL, C_ASTRO, C_GOLD, C_DISCORD,
)
from core.compat import proteger_outil

from modules.osint import (
    PLATEFORMES, recherche_pseudo, analyse_email, wayback, robots_sitemap,
    analyse_url, generateur_dorks, info_telephone, recherche_username_urls,
    archive_change_watcher,
)
from modules.recon import (
    dns_lookup, reverse_dns, geoloc_ip, asn_info, whois,
    sous_domaines, spf_dmarc, detect_techno, http_probe, lookup_mac,
)
from modules.cyber import (
    audit_headers, scan_ports, certificat_ssl, chaine_redirect,
    cookie_audit, dnsbl_check, jwt_inspect, recherche_cve, latence_tcp, cors_check,
    webhook_lab, api_contract_lab, tls_policy_diff,
)
from modules.pentest import (
    scan_ports_avance, banner_grabbing, scan_reseau_local, scan_wifi,
    info_interfaces, table_arp, dns_bruteforce, dir_bruteforce,
    sqli_detect, xss_detect, lfi_detect, waf_detect, http_bruteforce,
    wordlist_gen, traceroute, snmp_probe, http_header_fuzz,
    open_redirect_test, check_dangerous_ports,
)
from modules.discord import (
    discord_id_lookup, webhook_info, webhook_spammer, webhook_delete,
    bot_token_info, invite_lookup, guild_widget_lookup,
    snowflake_parser, bot_invite_generator, bot_panel, personal_panel,
    server_cloner, emoji_cloner,
)
from modules.media import gif_studio
from modules.profile_studio import profile_studio

from modules.utils import (
    identifier_hash, generateur_hash, encode_decode, force_mdp,
    calc_reseau, hash_fichier, luhn_check, user_agent_parse, timestamp_outil,
    generer_mot_de_passe, formater_json, analyser_texte, generer_uuid,
    convertir_base, calculer_dates, generer_corpus_http, audit_systeme,
)
from modules.astro import (
    iss, apod, asteroides, planetes, lancements,
    recherche_astre, lune_soleil, convertisseur, poids_planetes,
)


CATALOGUE =[
    ("OSINT", C_OSINT, [
        ("Recherche de pseudo", f"{len(PLATEFORMES)} plateformes en parallele",
         recherche_pseudo),
        ("Analyse d'email", "Format, MX, Gravatar", analyse_email),
        ("Wayback Machine", "Archives paginees + export", wayback),
        ('Robots.txt & sitemap', "Fichiers d'exploration du site", robots_sitemap),
        ("Analyse d'URL", "Parse + redirections + titre", analyse_url),
        ("Archive Change Watcher", "Comparer deux captures Internet Archive", archive_change_watcher),
        ('Google Dorks', "Requetes OSINT pretes a l'emploi", generateur_dorks),
        ("Analyse telephone", "Indicatif, pays, format E.164", info_telephone),
        ("Liens OSINT rapides", "Google, GitHub, VT, Shodan...", recherche_username_urls),
    ]),
    ("RECONNAISSANCE", C_RECON, [
        ("Enregistrements DNS", "A, AAAA, MX, NS, TXT", dns_lookup),
        ('Reverse DNS (PTR)', "IP -> nom d'hote", reverse_dns),
        ("Geolocalisation IP", "Pays, ville, fournisseur", geoloc_ip),
        ("Info ASN / reseau", "AS, hosting, proxy, PTR", asn_info),
        ('WHOIS', "Infos d'un domaine", whois),
        ("Sous-domaines", "Via les certificats crt.sh", sous_domaines),
        ("SPF / DMARC / DKIM", "Securite email du domaine", spf_dmarc),
        ('Detection techno', 'CMS, frameworks, serveur', detect_techno),
        ("Sonde HTTP", "Statut, temps, titre, taille", http_probe),
        ("Lookup MAC", "Fabricant via OUI", lookup_mac),
    ]),
    ("CYBER", C_CYBER, [
        ("Audit des headers", "Securite HTTP", audit_headers),
        ('Scan de ports', '19 ports courants', scan_ports),
        ("Certificat SSL/TLS", "Validite, SAN, cipher", certificat_ssl),
        ("Chaine de redirections", "Suivi hop par hop", chaine_redirect),
        ('Audit des cookies', 'Secure, HttpOnly, SameSite', cookie_audit),
        ("DNSBL / reputation IP", "Spamhaus, SpamCop...", dnsbl_check),
        ("Decodeur JWT", "Header + payload (sans verif)", jwt_inspect),
        ('Recherche CVE', 'CIRCL / NVD', recherche_cve),
        ("Latence TCP", "RTT + banner leger", latence_tcp),
        ("Test CORS", "Allow-Origin / credentials", cors_check),
        ('Webhook Lab', 'Envoi de payload JSON synthetique, statut et duree', webhook_lab),
        ("API Contract Lab", "Analyse OpenAPI hors ligne et fixtures", api_contract_lab),
        ("TLS Policy Diff", "Comparer des instantanes TLS et suivre les changements", tls_policy_diff),
    ]),
    ("PENTEST & RESEAU", C_PENTEST, [
        ("Scan de ports avance", "Range custom + banner grabbing", scan_ports_avance),
        ('Banner grabbing', 'Service fingerprinting multi-ports', banner_grabbing),
        ("Scan reseau local", "Decouverte d'hopes LAN", scan_reseau_local),
        ("Scan WiFi", "Reseaux WiFi visibles + securite", scan_wifi),
        ('Interfaces & routage', 'IP, MAC, table de routage', info_interfaces),
        ("Table ARP", "IP <-> MAC du reseau local", table_arp),
        ("DNS Brute-force", "Decouverte de sous-domaines", dns_bruteforce),
        ('Directory Bruteforce', 'Chemins caches sur serveur web', dir_bruteforce),
        ("Detection SQLi", "Parametres decouverts automatiquement", sqli_detect),
        ("Detection XSS", "XSS reflechi, cible et params auto", xss_detect),
        ('Detection LFI', 'Local File Inclusion, params auto', lfi_detect),
        ("Detection WAF", "Fingerprint firewall applicatif", waf_detect),
        ("Brute-force HTTP", "Formulaire de login detecte automatiquement", http_bruteforce),
        ('Generateur wordlist', 'Mutations, combos, patterns', wordlist_gen),
        ("Traceroute", "Chemin reseau hop-by-hop", traceroute),
        ("Sondage SNMP", "Community strings SNMP v1/v2", snmp_probe),
        ('Fuzzing headers HTTP', 'Injection de headers speciaux', http_header_fuzz),
        ("Open Redirect", "Redirections ouvertes, params auto", open_redirect_test),
        ("Ports dangereux", "Audit des ports a risque", check_dangerous_ports),
    ]),
    ("DISCORD OSINT", C_DISCORD, [
        ("Panel Bot Discord", "Dashboard Gateway, serveurs, permissions, actions confirmees", bot_panel),
        ('Server Cloner', 'Copier structure, roles, salons et permissions (apercu puis ecriture reelle)', server_cloner),
        ("Emoji Cloner", "Exporter et importer des emojis accessibles avec manifeste", emoji_cloner),
        ("GIF Studio", "Bibliotheque locale de GIF, conversion et publication Discord", gif_studio),
        ('Profile Studio', 'Preparer avatar, banniere, bio et variantes localement', profile_studio),
        ("Discord Personal Panel", "OAuth2 officiel, profil, serveurs et outils locaux", personal_panel),
        ("Lookup ID Discord", "Infos compte + date creation snowflake", discord_id_lookup),
        ('Info Webhook', 'Auteur, serveur, channel, avatar', webhook_info),
        ("Envoi / Test Webhook", "Test d'envoi & message personnalise", webhook_spammer),
        ("Supprimer Webhook", "Destruction d'un webhook distant", webhook_delete),
        ('Info Bot Token', 'Permissions, statut, serveurs rejoints', bot_token_info),
        ("Resolveur Invitation", "Membres, stats, serveur, createur", invite_lookup),
        ("Widget Serveur", "Membres en ligne, salons, statut", guild_widget_lookup),
        ('Decodeur Snowflake', 'Timestamp, worker, process, binaire', snowflake_parser),
        ("Generateur OAuth Bot", "Liens d'invitation avec permissions", bot_invite_generator),
    ]),
    ('UTILITAIRES', C_UTIL, [
        ("Identifier un hash", "MD5, SHA, bcrypt...", identifier_hash),
        ("Generateur de hash", "MD5 -> BLAKE2", generateur_hash),
        ('Encode / Decode', 'Base64, URL, Hex', encode_decode),
        ("Force mot de passe", "Score + entropie locale", force_mdp),
        ("Calculateur CIDR", "Sous-reseau IPv4/IPv6", calc_reseau),
        ('Hash de fichier', 'MD5 / SHA-1 / SHA-256', hash_fichier),
        ("Validateur Luhn", "Cartes, IMEI...", luhn_check),
        ("Parseur User-Agent", "Navigateur / OS / bot", user_agent_parse),
        ('Timestamp', 'Epoch <-> date UTC', timestamp_outil),
        ("Generateur de mot de passe", "Secrets aleatoires configurables", generer_mot_de_passe),
        ("Formateur JSON", "Valider, embellir ou compacter du JSON", formater_json),
        ('Analyseur de texte', 'Compteurs, mots, lignes et frequences', analyser_texte),
        ("Generateur UUID", "UUID v4 aleatoires en lot", generer_uuid),
        ("Convertisseur de bases", "Binaire, octal, decimal, hexadecimal", convertir_base),
        ('Calculateur de dates', 'Duree entre deux dates', calculer_dates),
        ("Corpus cas limites HTTP", "Fixtures locales de fuzzing de parseurs HTTP", generer_corpus_http),
        ("Audit de la machine", "HWID et inventaire local, sans reseau", audit_systeme),
    ]),
    ("ASTRONOMIE", C_ASTRO, [
        ("ISS en direct", "Position + equipage", iss),
        ('Image du jour NASA', "APOD, n'importe quelle date", apod),
        ("Asteroides du jour", "Passages pres de la Terre", asteroides),
        ("Planetes", "Fiches du systeme solaire", planetes),
        ('Lancements de fusees', 'Calendrier a venir', lancements),
        ("Recherche d'un astre", "Etoiles, galaxies (SIMBAD)", recherche_astre),
        ("Lune & Soleil", "Phase, lever, coucher", lune_soleil),
        ('Convertisseur spatial', 'UA, annees-lumiere, parsec', convertisseur),
        ("Poids sur les astres", "Gravite de chaque astre", poids_planetes),
    ]),
]

NAV_GROUPS = [
    ("OSINT", C_OSINT, "Recherches publiques et sources ouvertes", [
        ('Identités & profils', 'Pseudos, numéros et pistes de recherche', [
            "Recherche de pseudo", "Analyse telephone", "Liens OSINT rapides" ]),
        ("E-mail", "Validation et signaux publics d'une adresse", ["Analyse d'email"]),
        ('Domaines & archives', 'Contenus indexés, historiques et fichiers publics', [
            "Wayback Machine", "Robots.txt & sitemap", "Analyse d'URL", "Google Dorks",
            "Archive Change Watcher"]),
    ]),
    ("RECONNAISSANCE", C_RECON, "Cartographie DNS, domaines, IP et services", [
        ("Domaines & DNS", "Enregistrements et informations d'enregistrement", [
            'Enregistrements DNS', 'WHOIS', 'Sous-domaines', 'SPF / DMARC / DKIM']),
        ("Adresses & réseau", "Résolution inverse, ASN, géolocalisation et OUI", [
            "Reverse DNS (PTR)", "Geolocalisation IP", "Info ASN / reseau", "Lookup MAC"]),
        ('Services Web', 'Technologies détectées et sonde HTTP', [
            "Detection techno", "Sonde HTTP"]),
    ]),
    ('SECURITE WEB', C_CYBER, 'Contrôles HTTP, TLS et données applicatives', [
        ("HTTP & navigateur", "En-têtes, cookies, CORS et redirections", [
            "Audit des headers", "Chaine de redirections", "Audit des cookies", "Test CORS",
            'Webhook Lab', 'API Contract Lab']),
        ("TLS & identité", "Certificats, politique TLS et inspection locale de JWT", [
            "Certificat SSL/TLS", "TLS Policy Diff", "Decodeur JWT"]),
        ('Réputation & vulnérabilités', 'Sources de réputation et références CVE', [
            "DNSBL / reputation IP", "Recherche CVE"]),
    ]),
    ('RESEAU & LABORATOIRE', C_PENTEST, 'Diagnostics et tests contrôlés sur systèmes autorisés', [
        ("Connectivité & LAN", "Hôtes locaux, interfaces, routes et latence", [
            "Scan de ports", "Latence TCP", "Scan reseau local", "Scan WiFi",
            'Interfaces & routage', 'Table ARP', 'Traceroute']),
        ("Services & protocoles", "Ports, bannières et sondes SNMP", [
            "Scan de ports avance", "Banner grabbing", "Ports dangereux", "Sondage SNMP"]),
        ('Tests applicatifs autorisés', 'Fuzzing et détection en laboratoire uniquement', [
            "DNS Brute-force", "Directory Bruteforce", "Detection SQLi", "Detection XSS",
            "Detection LFI", "Detection WAF", "Brute-force HTTP", "Fuzzing headers HTTP",
            'Open Redirect']),
        ("Artefacts de test", "Génération locale de jeux de mots", ["Generateur wordlist"]),
    ]),
    ('DISCORD', C_DISCORD, 'Outils de plateforme et audit de bot autorisé', [
        ("Identifiants & serveurs", "Snowflakes, invitations et widgets publics", [
            "Lookup ID Discord", "Decodeur Snowflake", "Resolveur Invitation", "Widget Serveur"]),
        ('Bots & intégration', 'Configuration et audit avec un bot autorisé', [
            "Panel Bot Discord", "Server Cloner", "Emoji Cloner", "Discord Personal Panel",
            "Info Bot Token", "Generateur OAuth Bot"]),
        ('Médias & profil', 'Bibliothèque locale et préparation de compte', [
            "GIF Studio", "Profile Studio"]),
        ("Webhooks", "Inspection, test et suppression avec confirmation", [
            'Info Webhook', 'Envoi / Test Webhook', 'Supprimer Webhook']),
    ]),
    ("ANALYSE & UTILITAIRES", C_UTIL, "Transformations locales et génération de données", [
        ('Hashes & mots de passe', 'Empreintes et estimation/génération locale', [
            "Identifier un hash", "Generateur de hash", "Hash de fichier",
            "Force mot de passe", "Generateur de mot de passe"]),
        ('Encodage & données', 'Formats structurés, texte et identifiants', [
            "Encode / Decode", "Formateur JSON", "Analyseur de texte", "Generateur UUID"]),
        ("Réseau & conversions", "CIDR, bases numériques, dates et timestamps", [
            'Calculateur CIDR', 'Validateur Luhn', 'Parseur User-Agent', 'Timestamp',
            "Convertisseur de bases", "Calculateur de dates"]),
        ("Machine & artefacts", "Inventaire local et fixtures de laboratoire", [
            'Audit de la machine', 'Corpus cas limites HTTP']),
    ]),
    ("DOSSIERS & RAPPORTS", C_GOLD, "Conserver notes, sources et exports localement", [
        ('Investigations', "Dossiers SQLite, journal d'activité et export JSON", []),
    ]),
    ("ASTRONOMIE", C_ASTRO, "Observation, éphémérides et conversions spatiales", [
        ('Observation & événements', 'ISS, astéroïdes et lancements', [
            "ISS en direct", "Asteroides du jour", "Lancements de fusees"]),
        ("Références & conversions", "Corps célestes, Soleil/Lune et unités", [
            'Image du jour NASA', 'Planetes', "Recherche d'un astre", 'Lune & Soleil',
            "Convertisseur spatial", "Poids sur les astres"]),
    ]),
]

FLAT =[]
for _ci, (_cat, _couleur, _opts) in enumerate(CATALOGUE):
    for _nom, _desc, _fn in _opts:
        FLAT.append(dict(num=str(len(FLAT) + 1), nom=_nom, desc=_desc,
                         fn=proteger_outil(_nom, _fn), cat=_ci, couleur=_couleur))
FLAT.append(dict(num="0", nom="Quitter", desc="", fn=None, cat=None, couleur="red"))
ACTIONS= {f["num"]: f["fn"] for f in FLAT if f["fn"]}
NUM_IDX = {f['num']: i for i, f in enumerate(FLAT)}
SEL = NUM_IDX["1"]

_OUTILS_PAR_NOM = {outil['nom']:outil for outil in FLAT if outil['fn']}

_CHEMIN_PAR_NOM = {}
for _groupe, _couleur_groupe, _description_groupe, _sections in NAV_GROUPS:
    for _section, _description_section, _noms in _sections:
        for _nom_section in _noms:
            _CHEMIN_PAR_NOM.setdefault(_nom_section, f"{_groupe} > {_section}")

_ROUTE_PAR_NOM={}
for _categorie, _couleur, _outils in CATALOGUE:
    for _nom, _description, _fonction in _outils:
        _outil = _OUTILS_PAR_NOM[_nom]
        _outil['categorie_navigation']=_categorie
        _outil["section_navigation"] = _categorie
        _outil["chemin_navigation"]= _CHEMIN_PAR_NOM.get(_nom, _categorie)
        _ROUTE_PAR_NOM[_nom] = _categorie

MOTS_CLES_RECHERCHE = {
    'Recherche de pseudo': 'username handle compte profil social media',
    "Analyse d'email": "courriel mailbox mx adresse électronique",
    "Enregistrements DNS": "dns record zone aaaa mx ns txt",
    'Reverse DNS (PTR)': 'ptr reverse résolution inverse hostname',
    "Info ASN / reseau":"asn bgp fournisseur opérateur réseau",
    "Sous-domaines":"crt certificats domains enumeration",
    'Audit des headers': 'headers entêtes csp hsts x-frame-options',
    "Certificat SSL/TLS": "https certificat x509 tls expiration",
    "Test CORS": "cross origin navigateur cors",
    'Webhook Lab': 'webhook endpoint http post payload json test integration',
    "Archive Change Watcher": "archive wayback diff historique comparaison capture",
    "API Contract Lab": "openapi swagger schema contrat api fixtures validation",
    'TLS Policy Diff':'tls certificat fingerprint expiration renouvellement politique',
    "Discord Personal Panel": "discord oauth2 oauth personnel profil compte serveurs scopes pkce",
    "Panel Bot Discord":"discord bot gateway permissions moderation salons roles webhooks",
    'Server Cloner':'cloner clone copier structure serveur categories salons roles permissions manifeste',
    "Emoji Cloner": "emoji emoticone cloner importer exporter anime statique manifeste",
    "GIF Studio":"gif media anime bibliotheque convertir webp png importer url publier",
    'Profile Studio': 'profil avatar banniere bio biographie statut variante recadrage',
    "Decodeur JWT":"token bearer json web token",
    "Fuzzing headers HTTP": "fuzz edge cases malformed request",
    'Generateur wordlist':'dictionnaire mutations jeu de données',
    "Calculateur CIDR": "subnet masque réseau ip",
    "Corpus cas limites HTTP": "http protocol parser fuzzing edge cases corpus fixtures",
    'Audit de la machine': 'hwid machine identifiant systeme inventaire hostname',
    "Dossiers & rapports": "case investigation notes sources dossier",
    "Evidence Chain Ledger": "preuve evidence ledger integrite chaine empreinte sha256 fichier registre",
    'Finding Correlator': 'correlation correler entites domaines url ip email pseudo rapprochement relations',
    "Gestion des dossiers": "case investigation notes sources dossier registre",
    "Historique local": "journal activite historique operations",
}


def _normaliser_recherche(texte):
    texte = unicodedata.normalize("NFKD", str(texte).casefold())
    return "".join(car for car in texte if not unicodedata.combining(car))


def rechercher_outils(terme, limite=20, extras=()):
    """Recherche déterministe dans nom, usage, catégorie et alias.

    `extras` permet à l'interface d'ajouter ses actions transverses sans
    dupliquer le catalogue.
    """
    termes = _normaliser_recherche(terme).split()
    if not termes:
        return []
    resultats =[]
    for outil in [*FLAT, *extras]:
        if not outil["fn"]:
            continue
        texte =' '.join((outil['nom'], outil['desc'], outil.get('chemin_navigation', ''),
                          MOTS_CLES_RECHERCHE.get(outil["nom"], "")))
        normalise= _normaliser_recherche(texte)
        if all(mot in normalise for mot in termes):
            nom = _normaliser_recherche(outil["nom"])
            score = (0 if nom.startswith(" ".join(termes)) else 1,
                     0 if all(mot in nom for mot in termes) else 1,
                     outil["nom"].casefold())
            resultats.append((score, outil))
    resultats.sort(key=lambda item:item[0])
    return [outil for _, outil in resultats[:limite]]
