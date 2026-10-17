#!/usr/bin/env python3
"""OSINT & PENTEST TOOLBOX
Suite complete d'investigation, reconnaissance, cybersecurite, pentest et utilitaires.
Architecture modulaire : modules/<categorie>/<outil>.py
"""
import argparse
import json
import os
import sys
import time
import unicodedata
import platform

if os.name == "nt":
    os.system("chcp 65001 >nul")
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from rich import box
from rich.align import Align
from rich.console import Console, Group
from rich.live import Live
from rich.markup import escape
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich.text import Text

# Core & Helpers
from core.common import (
    console, arc, texte_arc, bad, warn, ok, choisir_option, BX, UNICODE, INTERACTIF,
    CONN_T, CONN_L, PIPE, ARROW,
    BANNER, C_OSINT, C_RECON, C_CYBER, C_PENTEST, C_UTIL, C_ASTRO, C_GOLD, C_DISCORD,
    initialiser_theme, obtenir_theme, obtenir_config_ui, titre, pause
)
from core.config import charger, sauvegarder, restaurer_defauts, DEFAUTS, EXPORTS_DIR
from core.cases import (
    lister_cases, creer_case, obtenir_case, renommer_case, supprimer_case,
    ajouter_note, modifier_note, supprimer_note,
    ajouter_source, charger_historique, effacer_historique,
    exporter_case_json
)

# Modules individuels par categorie
from modules.osint import (
    recherche_pseudo, analyse_email, wayback, robots_sitemap,
    analyse_url, generateur_dorks, info_telephone, recherche_username_urls
)
from modules.recon import (
    dns_lookup, reverse_dns, geoloc_ip, asn_info, whois,
    sous_domaines, spf_dmarc, detect_techno, http_probe, lookup_mac
)
from modules.cyber import (
    audit_headers, scan_ports, certificat_ssl, chaine_redirect,
    cookie_audit, dnsbl_check, jwt_inspect, recherche_cve, latence_tcp, cors_check
)
from modules.pentest import (
    scan_ports_avance, banner_grabbing, scan_reseau_local, scan_wifi,
    info_interfaces, table_arp, dns_bruteforce, dir_bruteforce,
    sqli_detect, xss_detect, lfi_detect, waf_detect, http_bruteforce,
    wordlist_gen, traceroute, snmp_probe, http_header_fuzz,
    open_redirect_test, check_dangerous_ports
)
from modules.discord import (
    discord_id_lookup, webhook_info, webhook_spammer, webhook_delete,
    bot_token_info, invite_lookup, guild_widget_lookup,
    snowflake_parser, bot_invite_generator, bot_panel
)
from modules.utils import (
    identifier_hash, generateur_hash, encode_decode, force_mdp,
    calc_reseau, hash_fichier, luhn_check, user_agent_parse, timestamp_outil,
    generer_mot_de_passe, formater_json, analyser_texte, generer_uuid,
    convertir_base, calculer_dates, generer_corpus_http,
)
from modules.astro import (
    iss, apod, asteroides, planetes, lancements,
    recherche_astre, lune_soleil, convertisseur, poids_planetes
)

# --- Configuration globale ---
_CONFIG = charger()


def _synchroniser_couleurs_locales():
    """Actualise les constantes importees apres un changement de palette."""
    global C_OSINT, C_RECON, C_CYBER, C_PENTEST, C_UTIL, C_ASTRO, C_GOLD, C_DISCORD
    import core.common as common_ui
    for nom in ("C_OSINT", "C_RECON", "C_CYBER", "C_PENTEST", "C_UTIL", "C_ASTRO", "C_GOLD", "C_DISCORD"):
        globals()[nom] = getattr(common_ui, nom)


def _appliquer_configuration_visuelle():
    initialiser_theme(_CONFIG)
    _synchroniser_couleurs_locales()


_appliquer_configuration_visuelle()


def selectionner_option(titre_menu, options, selection_initiale=0):
    """Sélection unifiée pour les menus et leurs sous-menus."""
    return choisir_option(titre_menu, options, selection_initiale)


def _ecran_parametres():
    """Menu de parametres persistant."""
    global _CONFIG
    from core.theme import THEMES, liste_themes, nommer_theme

    while True:
        console.clear()
        titre("PARAMETRES", C_GOLD)

        t = Table(box=BX, border_style=C_GOLD, header_style=f"bold {C_GOLD}")
        t.add_column("Reglage", width=40)
        t.add_column("Valeur actuelle")

        app = _CONFIG.get("apparence", {})
        reseau = _CONFIG.get("reseau", {})

        styles = {"dashboard": "Dashboard split", "classique": "Classique", "compact": "Compact"}
        largeurs = {"auto": "Automatique", "large": "Large", "etroit": "Etroit"}
        reglages = [
            "Palette de couleurs", "Style d'interface", "Couleur d'accent",
            "Couleur du texte shell", "Fond shell", "Largeur du menu",
            "Panneau lateral", "Badges de categories", "Banniere de demarrage",
            "Animations", "Timeout reseau", "Restaurer les parametres par defaut",
            "Personnaliser les couleurs du theme", "Retour au menu principal",
        ]
        t.add_row("Palette de couleurs", nommer_theme(app.get("theme_actif", "original")))
        t.add_row("Style d'interface", styles.get(app.get("style_interface"), "Dashboard split"))
        t.add_row("Couleur d'accent", app.get("couleur_accent") or "Auto (palette)")
        t.add_row("Couleur du texte shell", app.get("couleur_shell_texte", "#ffffff"))
        t.add_row("Fond shell (sorties Rich)", app.get("couleur_shell_fond", "#10131c"))
        t.add_row("Largeur du menu", largeurs.get(app.get("largeur_menu"), "Automatique"))
        t.add_row("Panneau lateral", str(app.get("afficher_panneau_lateral", True)))
        t.add_row("Badges de categories", str(app.get("afficher_badges_categories", True)))
        t.add_row("Banniere de demarrage", str(app.get("banniere_demarrage", True)))
        t.add_row("Animations", str(app.get("animations", True)))
        t.add_row("Timeout reseau (s)", str(reseau.get("timeout", 8)))
        t.add_row("Restaurer les parametres par defaut", "")
        t.add_row("Personnaliser les couleurs du theme", "")
        t.add_row("Retour au menu principal", "")

        console.print(t)
        c = selectionner_option("PARAMETRES", reglages)
        if c is None or c == "Retour au menu principal":
            break
        elif c == "Palette de couleurs":
            _menu_themes()
            sauvegarder(_CONFIG)
            _appliquer_configuration_visuelle()
        elif c == "Personnaliser les couleurs du theme":
            _menu_palette_personnalisee()
            pause()
            continue
        elif c == "Style d'interface":
            choix = selectionner_option("STYLE D'INTERFACE", ["Dashboard split", "Classique", "Compact"])
            if choix is None:
                continue
            _CONFIG["apparence"]["style_interface"] = {
                "Dashboard split": "dashboard", "Classique": "classique", "Compact": "compact"
            }[choix]
        elif c == "Couleur d'accent":
            _configurer_couleur("couleur_accent", "Accent (hex #RRGGBB ou vide pour Auto)", optionnelle=True)
            pause()
            continue
        elif c == "Couleur du texte shell":
            _configurer_couleur("couleur_shell_texte", "Couleur du texte shell")
            pause()
            continue
        elif c == "Fond shell":
            _configurer_couleur("couleur_shell_fond", "Couleur de fond shell")
            pause()
            continue
        elif c == "Largeur du menu":
            choix = selectionner_option("LARGEUR DU MENU", ["Automatique", "Large", "Etroit"])
            if choix is None:
                continue
            _CONFIG["apparence"]["largeur_menu"] = {
                "Automatique": "auto", "Large": "large", "Etroit": "etroit"
            }[choix]
        elif c == "Panneau lateral":
            app["afficher_panneau_lateral"] = not app.get("afficher_panneau_lateral", True)
        elif c == "Badges de categories":
            app["afficher_badges_categories"] = not app.get("afficher_badges_categories", True)
        elif c == "Banniere de demarrage":
            app["banniere_demarrage"] = not app.get("banniere_demarrage", True)
        elif c == "Animations":
            app["animations"] = not app.get("animations", True)
        elif c == "Timeout reseau":
            v = Prompt.ask("Timeout reseau (secondes)", default=str(reseau.get("timeout", 8)))
            if v.isdigit() and 1 <= int(v) <= 120:
                reseau["timeout"] = int(v)
                sauvegarder(_CONFIG)
                ok("Timeout mis a jour.")
            else:
                bad("Valeur invalide (1-120).")
        elif c == "Restaurer les parametres par defaut":
            if Confirm.ask("Restaurer tous les parametres par defaut ?"):
                _CONFIG = restaurer_defauts()
                _appliquer_configuration_visuelle()
                ok("Parametres reinitialises.")
        if c in {"Style d'interface", "Largeur du menu", "Panneau lateral",
                 "Badges de categories", "Banniere de demarrage", "Animations"}:
            sauvegarder(_CONFIG)
            _appliquer_configuration_visuelle()
            ok("Reglage d'interface sauvegarde et applique.")
        if c not in {"Couleur d'accent", "Couleur du texte shell", "Fond shell",
                     "Personnaliser les couleurs du theme"}:
            pause()


def _menu_palette_personnalisee():
    """Editeur de couleurs par role, sauvegarde dans la configuration locale."""
    global _CONFIG
    from core.theme import SLOTS, couleur_valide, appliquer_theme
    palette = _CONFIG.setdefault("theme_personnalise", {}).copy()
    theme_config = dict(_CONFIG)
    theme_config.setdefault("apparence", {})["couleur_accent"] = ""
    palette.update(appliquer_theme(theme_config))
    _CONFIG["theme_personnalise"] = palette
    labels = {
        "principale": "Couleur principale", "secondaire": "Couleur secondaire",
        "titres": "Titres", "texte_principal": "Texte principal",
        "texte_secondaire": "Texte secondaire", "selection": "Selection",
        "bordures": "Bordures", "accents": "Accents", "succes": "Succes",
        "avertissements": "Avertissements", "erreurs": "Erreurs", "panneaux": "Panneaux",
    }
    while True:
        console.clear()
        titre("PALETTE PERSONNALISEE", C_GOLD)
        table = Table(box=BX, border_style=C_GOLD, header_style=f"bold {C_GOLD}")
        table.add_column("Role")
        table.add_column("Couleur")
        roles = [labels[slot] for slot in SLOTS]
        for slot in SLOTS:
            table.add_row(labels[slot], palette.get(slot, "#ffffff"))
        table.add_row("Terminer", "")
        console.print(table)
        choix = selectionner_option("PALETTE PERSONNALISEE", roles + ["Terminer"])
        if choix in (None, "Terminer"):
            break
        slot = SLOTS[roles.index(choix)]
        valeur = Prompt.ask(f"Nouvelle couleur pour {labels[slot]}", default=palette.get(slot, "#ffffff")).strip()
        if not couleur_valide(valeur):
            bad("Couleur invalide : saisissez #RRGGBB ou un nom Rich reconnu.")
            continue
        palette[slot] = valeur.lower()
        _CONFIG["theme_personnalise"] = palette
        _CONFIG["apparence"]["theme_actif"] = "personnalise"
        _appliquer_configuration_visuelle()
        sauvegarder(_CONFIG)
        ok(f"{labels[slot]} appliquee.")


def _configurer_couleur(cle, invite, optionnelle=False):
    from core.theme import couleur_valide
    valeur = Prompt.ask(invite, default="" if optionnelle else _CONFIG["apparence"].get(cle, "#ffffff"),
                        show_default=not optionnelle).strip()
    if optionnelle and not valeur:
        _CONFIG["apparence"][cle] = ""
    elif couleur_valide(valeur):
        _CONFIG["apparence"][cle] = valeur.lower()
    else:
        bad("Couleur invalide : utilisez #RRGGBB ou un nom Rich reconnu.")
        return
    sauvegarder(_CONFIG)
    _appliquer_configuration_visuelle()
    ok("Couleur appliquee et sauvegardee.")


def _menu_themes():
    """Sous-menu de personnalisation des themes/couleurs."""
    global _CONFIG
    from core.theme import THEMES, liste_themes, nommer_theme

    while True:
        console.clear()
        titre("PERSONNALISATION DES COULEURS", C_GOLD)

        app = _CONFIG.get("apparence", {})
        theme_actif = app.get("theme_actif", "original")

        t = Table(box=BX, border_style=C_GOLD, header_style=f"bold {C_GOLD}")
        t.add_column("Theme", width=25)
        t.add_column("Statut")

        themes_liste = liste_themes()
        options = []
        for cle in themes_liste:
            label = nommer_theme(cle)
            options.append(label)
            actif = " [ACTIF]" if cle == theme_actif else ""
            t.add_row(label, f"[bold green]{actif}[/]" if actif else "")

        t.add_row("Retour", "")

        console.print(t)
        choix = selectionner_option("THEMES", options + ["Retour"])
        if choix in (None, "Retour"):
            break

        cle = themes_liste[options.index(choix)]
        _CONFIG["apparence"]["theme_actif"] = cle
        initialiser_theme(_CONFIG)
        sauvegarder(_CONFIG)
        ok(f"Theme '{nommer_theme(cle)}' applique.")
        pause()


def _intro_ascii(config):
    """Affiche l'introduction ASCII au demarrage."""
    app = config.get("apparence", {})
    if not app.get("banniere_demarrage", True):
        return

    anim = app.get("animations", True)
    palette = obtenir_theme()

    logo = [
        " █████╗  ██████╗██╗███████╗██╗███╗   ██╗████████╗",
        "██╔══██╗██╔════╝██║██╔════╝██║████╗  ██║╚══██╔══╝",
        "███████║██║     ██║█████╗  ██║██╔██╗ ██║   ██║   ",
        "██╔══██║██║     ██║██╔══╝  ██║██║╚██╗██║   ██║   ",
        "██║  ██║╚██████╗██║██║     ██║██║ ╚████║   ██║   ",
        "╚═╝  ╚═╝ ╚═════╝╚═╝╚═╝     ╚═╝╚═╝  ╚═══╝   ╚═╝   ",
    ]

    # Petite animation de fondu
    if anim and UNICODE:
        for etape in range(1, 4):
            console.clear()
            if etape == 1:
                console.print(Align.center(Text("Initialisation...", style=f"bold {palette.get('principale', '#ff5fd2')}")))
            elif etape == 2:
                console.print(Align.center(Text("Chargement de LeakFr-Tools...", style=f"bold {palette.get('secondaire', '#36d1ff')}")))
            else:
                for ligne in logo:
                    console.print(Align.center(Text(ligne, style=f"bold {palette.get('principale', '#ff5fd2')}")))
                console.print()
                console.print(Align.center(Text("v2.0  |  OSINT & SECURITY TOOLBOX", style=f"bold {palette.get('titres', '#ffd166')}")))
                console.print(Align.center(Text("Investigations  |  Reconnaissance  |  Cyber  |  Reseau", style=f"dim {palette.get('texte_secondaire', '#888888')}")))
            time.sleep(0.15)
    else:
        console.clear()
        for ligne in logo:
            console.print(Align.center(Text(ligne, style=f"bold {palette.get('principale', '#ff5fd2')}")))
        console.print()
        console.print(Align.center(Text("v2.0  |  OSINT & SECURITY TOOLBOX", style=f"bold {palette.get('titres', '#ffd166')}")))
        console.print(Align.center(Text("Investigations  |  Reconnaissance  |  Cyber  |  Reseau", style=f"dim {palette.get('texte_secondaire', '#888888')}")))
        time.sleep(0.3)


CATALOGUE = [
    ("OSINT", C_OSINT, [
        ("Recherche de pseudo", "20 plateformes en parallele", recherche_pseudo),
        ("Analyse d'email", "Format, MX, Gravatar", analyse_email),
        ("Wayback Machine", "Archives paginees + export", wayback),
        ("Robots.txt & sitemap", "Fichiers d'exploration du site", robots_sitemap),
        ("Analyse d'URL", "Parse + redirections + titre", analyse_url),
        ("Google Dorks", "Requetes OSINT pretes a l'emploi", generateur_dorks),
        ("Analyse telephone", "Indicatif, pays, format E.164", info_telephone),
        ("Liens OSINT rapides", "Google, GitHub, VT, Shodan...", recherche_username_urls),
    ]),
    ("RECONNAISSANCE", C_RECON, [
        ("Enregistrements DNS", "A, AAAA, MX, NS, TXT", dns_lookup),
        ("Reverse DNS (PTR)", "IP -> nom d'hote", reverse_dns),
        ("Geolocalisation IP", "Pays, ville, fournisseur", geoloc_ip),
        ("Info ASN / reseau", "AS, hosting, proxy, PTR", asn_info),
        ("WHOIS", "Infos d'un domaine", whois),
        ("Sous-domaines", "Via les certificats crt.sh", sous_domaines),
        ("SPF / DMARC / DKIM", "Securite email du domaine", spf_dmarc),
        ("Detection techno", "CMS, frameworks, serveur", detect_techno),
        ("Sonde HTTP", "Statut, temps, titre, taille", http_probe),
        ("Lookup MAC", "Fabricant via OUI", lookup_mac),
    ]),
    ("CYBER", C_CYBER, [
        ("Audit des headers", "Securite HTTP", audit_headers),
        ("Scan de ports", "19 ports courants", scan_ports),
        ("Certificat SSL/TLS", "Validite, SAN, cipher", certificat_ssl),
        ("Chaine de redirections", "Suivi hop par hop", chaine_redirect),
        ("Audit des cookies", "Secure, HttpOnly, SameSite", cookie_audit),
        ("DNSBL / reputation IP", "Spamhaus, SpamCop...", dnsbl_check),
        ("Decodeur JWT", "Header + payload (sans verif)", jwt_inspect),
        ("Recherche CVE", "CIRCL / NVD", recherche_cve),
        ("Latence TCP", "RTT + banner leger", latence_tcp),
        ("Test CORS", "Allow-Origin / credentials", cors_check),
    ]),
    ("PENTEST & RESEAU", C_PENTEST, [
        ("Scan de ports avance", "Range custom + banner grabbing", scan_ports_avance),
        ("Banner grabbing", "Service fingerprinting multi-ports", banner_grabbing),
        ("Scan reseau local", "Decouverte d'hopes LAN", scan_reseau_local),
        ("Scan WiFi", "Reseaux WiFi visibles + securite", scan_wifi),
        ("Interfaces & routage", "IP, MAC, table de routage", info_interfaces),
        ("Table ARP", "IP <-> MAC du reseau local", table_arp),
        ("DNS Brute-force", "Decouverte de sous-domaines", dns_bruteforce),
        ("Directory Bruteforce", "Chemins caches sur serveur web", dir_bruteforce),
        ("Detection SQLi", "Injection SQL (passif/actif)", sqli_detect),
        ("Detection XSS", "Cross-Site Scripting reflechi", xss_detect),
        ("Detection LFI", "Local File Inclusion", lfi_detect),
        ("Detection WAF", "Fingerprint firewall applicatif", waf_detect),
        ("Brute-force HTTP", "Login form bruteforce", http_bruteforce),
        ("Generateur wordlist", "Mutations, combos, patterns", wordlist_gen),
        ("Traceroute", "Chemin reseau hop-by-hop", traceroute),
        ("Sondage SNMP", "Community strings SNMP v1/v2", snmp_probe),
        ("Fuzzing headers HTTP", "Injection de headers speciaux", http_header_fuzz),
        ("Open Redirect", "Test de redirections ouvertes", open_redirect_test),
        ("Ports dangereux", "Audit des ports a risque", check_dangerous_ports),
    ]),
    ("DISCORD OSINT", C_DISCORD, [
        ("Panel Bot Discord", "Dashboard split-view, presence & audit", bot_panel),
        ("Lookup ID Discord", "Infos compte + date creation snowflake", discord_id_lookup),
        ("Info Webhook", "Auteur, serveur, channel, avatar", webhook_info),
        ("Envoi / Test Webhook", "Test d'envoi & message personnalise", webhook_spammer),
        ("Supprimer Webhook", "Destruction d'un webhook distant", webhook_delete),
        ("Info Bot Token", "Permissions, statut, serveurs rejoints", bot_token_info),
        ("Resolveur Invitation", "Membres, stats, serveur, createur", invite_lookup),
        ("Widget Serveur", "Membres en ligne, salons, statut", guild_widget_lookup),
        ("Decodeur Snowflake", "Timestamp, worker, process, binaire", snowflake_parser),
        ("Generateur OAuth Bot", "Liens d'invitation avec permissions", bot_invite_generator),
    ]),
    ("UTILITAIRES", C_UTIL, [
        ("Identifier un hash", "MD5, SHA, bcrypt...", identifier_hash),
        ("Generateur de hash", "MD5 -> BLAKE2", generateur_hash),
        ("Encode / Decode", "Base64, URL, Hex", encode_decode),
        ("Force mot de passe", "Score + entropie locale", force_mdp),
        ("Calculateur CIDR", "Sous-reseau IPv4/IPv6", calc_reseau),
        ("Hash de fichier", "MD5 / SHA-1 / SHA-256", hash_fichier),
        ("Validateur Luhn", "Cartes, IMEI...", luhn_check),
        ("Parseur User-Agent", "Navigateur / OS / bot", user_agent_parse),
        ("Timestamp", "Epoch <-> date UTC", timestamp_outil),
        ("Generateur de mot de passe", "Secrets aleatoires configurables", generer_mot_de_passe),
        ("Formateur JSON", "Valider, embellir ou compacter du JSON", formater_json),
        ("Analyseur de texte", "Compteurs, mots, lignes et frequences", analyser_texte),
        ("Generateur UUID", "UUID v4 aleatoires en lot", generer_uuid),
        ("Convertisseur de bases", "Binaire, octal, decimal, hexadecimal", convertir_base),
        ("Calculateur de dates", "Duree entre deux dates", calculer_dates),
        ("Corpus cas limites HTTP", "Fixtures locales de fuzzing de parseurs HTTP", generer_corpus_http),
    ]),
    ("ASTRONOMIE", C_ASTRO, [
        ("ISS en direct", "Position + equipage", iss),
        ("Image du jour NASA", "APOD, n'importe quelle date", apod),
        ("Asteroides du jour", "Passages pres de la Terre", asteroides),
        ("Planetes", "Fiches du systeme solaire", planetes),
        ("Lancements de fusees", "Calendrier a venir", lancements),
        ("Recherche d'un astre", "Etoiles, galaxies (SIMBAD)", recherche_astre),
        ("Lune & Soleil", "Phase, lever, coucher", lune_soleil),
        ("Convertisseur spatial", "UA, annees-lumiere, parsec", convertisseur),
        ("Poids sur les astres", "Gravite de chaque astre", poids_planetes),
    ]),
]

FLAT = []
for _ci, (_cat, _couleur, _opts) in enumerate(CATALOGUE):
    for _nom, _desc, _fn in _opts:
        FLAT.append(dict(num=str(len(FLAT) + 1), nom=_nom, desc=_desc, fn=_fn,
                         cat=_ci, couleur=_couleur))
FLAT.append(dict(num="0", nom="Quitter", desc="", fn=None, cat=None, couleur="red"))
ACTIONS = {f["num"]: f["fn"] for f in FLAT if f["fn"]}
NUM_IDX = {f["num"]: i for i, f in enumerate(FLAT)}
SEL = NUM_IDX["1"]

# La navigation est un arbre de tâches ; les fonctions restent définies une seule
# fois dans CATALOGUE, puis sont référencées ici par leur nom stable.
NAV_GROUPS = [
    ("OSINT", C_OSINT, "Recherches publiques et sources ouvertes", [
        ("Identités & profils", "Pseudos, numéros et pistes de recherche", [
            "Recherche de pseudo", "Analyse telephone", "Liens OSINT rapides" ]),
        ("E-mail", "Validation et signaux publics d'une adresse", ["Analyse d'email"]),
        ("Domaines & archives", "Contenus indexés, historiques et fichiers publics", [
            "Wayback Machine", "Robots.txt & sitemap", "Analyse d'URL", "Google Dorks"]),
    ]),
    ("RECONNAISSANCE", C_RECON, "Cartographie DNS, domaines, IP et services", [
        ("Domaines & DNS", "Enregistrements et informations d'enregistrement", [
            "Enregistrements DNS", "WHOIS", "Sous-domaines", "SPF / DMARC / DKIM"]),
        ("Adresses & réseau", "Résolution inverse, ASN, géolocalisation et OUI", [
            "Reverse DNS (PTR)", "Geolocalisation IP", "Info ASN / reseau", "Lookup MAC"]),
        ("Services Web", "Technologies détectées et sonde HTTP", [
            "Detection techno", "Sonde HTTP"]),
    ]),
    ("SECURITE WEB", C_CYBER, "Contrôles HTTP, TLS et données applicatives", [
        ("HTTP & navigateur", "En-têtes, cookies, CORS et redirections", [
            "Audit des headers", "Chaine de redirections", "Audit des cookies", "Test CORS"]),
        ("TLS & identité", "Certificats et inspection locale de JWT", [
            "Certificat SSL/TLS", "Decodeur JWT"]),
        ("Réputation & vulnérabilités", "Sources de réputation et références CVE", [
            "DNSBL / reputation IP", "Recherche CVE"]),
    ]),
    ("RESEAU & LABORATOIRE", C_PENTEST, "Diagnostics et tests contrôlés sur systèmes autorisés", [
        ("Connectivité & LAN", "Hôtes locaux, interfaces, routes et latence", [
            "Scan de ports", "Latence TCP", "Scan reseau local", "Scan WiFi",
            "Interfaces & routage", "Table ARP", "Traceroute"]),
        ("Services & protocoles", "Ports, bannières et sondes SNMP", [
            "Scan de ports avance", "Banner grabbing", "Ports dangereux", "Sondage SNMP"]),
        ("Tests applicatifs autorisés", "Fuzzing et détection en laboratoire uniquement", [
            "DNS Brute-force", "Directory Bruteforce", "Detection SQLi", "Detection XSS",
            "Detection LFI", "Detection WAF", "Brute-force HTTP", "Fuzzing headers HTTP",
            "Open Redirect"]),
        ("Artefacts de test", "Génération locale de jeux de mots", ["Generateur wordlist"]),
    ]),
    ("DISCORD", C_DISCORD, "Outils de plateforme et audit de bot autorisé", [
        ("Identifiants & serveurs", "Snowflakes, invitations et widgets publics", [
            "Lookup ID Discord", "Decodeur Snowflake", "Resolveur Invitation", "Widget Serveur"]),
        ("Bots & intégration", "Configuration et audit avec un bot autorisé", [
            "Panel Bot Discord", "Info Bot Token", "Generateur OAuth Bot"]),
        ("Webhooks", "Inspection, test et suppression avec confirmation", [
            "Info Webhook", "Envoi / Test Webhook", "Supprimer Webhook"]),
    ]),
    ("ANALYSE & UTILITAIRES", C_UTIL, "Transformations locales et génération de données", [
        ("Hashes & mots de passe", "Empreintes et estimation/génération locale", [
            "Identifier un hash", "Generateur de hash", "Hash de fichier",
            "Force mot de passe", "Generateur de mot de passe"]),
        ("Encodage & données", "Formats structurés, texte et identifiants", [
            "Encode / Decode", "Formateur JSON", "Analyseur de texte", "Generateur UUID"]),
        ("Réseau & conversions", "CIDR, bases numériques, dates et timestamps", [
            "Calculateur CIDR", "Validateur Luhn", "Parseur User-Agent", "Timestamp",
            "Convertisseur de bases", "Calculateur de dates", "Corpus cas limites HTTP"]),
    ]),
    ("DOSSIERS & RAPPORTS", C_GOLD, "Conserver notes, sources et exports localement", [
        ("Investigations", "Dossiers SQLite, journal d'activité et export JSON", []),
    ]),
    ("ASTRONOMIE", C_ASTRO, "Observation, éphémérides et conversions spatiales", [
        ("Observation & événements", "ISS, astéroïdes et lancements", [
            "ISS en direct", "Asteroides du jour", "Lancements de fusees"]),
        ("Références & conversions", "Corps célestes, Soleil/Lune et unités", [
            "Image du jour NASA", "Planetes", "Recherche d'un astre", "Lune & Soleil",
            "Convertisseur spatial", "Poids sur les astres"]),
    ]),
]

_OUTILS_PAR_NOM = {outil["nom"]: outil for outil in FLAT if outil["fn"]}
_ROUTE_PAR_NOM = {}
NAVIGATION = []
for _categorie, _couleur, _description, _sections in NAV_GROUPS:
    _cat_node = {"label": _categorie, "description": _description, "color": _couleur, "children": []}
    for _section, _section_desc, _noms in _sections:
        _section_node = {"label": _section, "description": _section_desc, "children": []}
        for _nom in _noms:
            _outil = _OUTILS_PAR_NOM[_nom]
            _outil["categorie_navigation"] = _categorie
            _outil["section_navigation"] = _section
            _outil["chemin_navigation"] = f"{_categorie} > {_section}"
            _section_node["children"].append({
                "label": _outil["nom"], "description": _outil["desc"],
                "action": _outil["num"], "tool": _outil,
            })
            _ROUTE_PAR_NOM[_nom] = _outil["chemin_navigation"]
        if _section_node["children"]:
            _cat_node["children"].append(_section_node)
    if _categorie == "DOSSIERS & RAPPORTS":
        _section_node["children"].extend([
            {"label": "Gestion des dossiers", "description": "Créer, annoter, sourcer et exporter une investigation", "action": "cases"},
            {"label": "Historique local", "description": "Consulter les dernières opérations enregistrées", "action": "history"},
        ])
        _cat_node["children"].append(_section_node)
    NAVIGATION.append(_cat_node)

NAVIGATION.extend([
    {"label": "Recherche globale", "description": "Retrouver un outil par nom, catégorie ou fonction", "action": "search"},
    {"label": "Configuration", "description": "Thèmes, interface et préférences", "action": "settings"},
    {"label": "Quitter", "description": "Fermer LeakFr-Tools", "action": "quit"},
])
def _selectionner_dossier(titre_menu):
    dossiers = lister_cases()
    if not dossiers:
        warn("Aucun dossier d'investigation. Créez-en un depuis le menu Dossiers.")
        return None
    choix = selectionner_option(titre_menu, [f"#{case['id']} · {case['title']}" for case in dossiers] + ["Retour"])
    if not choix or choix == "Retour":
        return None
    return next(case for case in dossiers if choix.startswith(f"#{case['id']} · "))


def _gestion_dossiers():
    """Interface locale de gestion des dossiers, notes, sources et exports."""
    while True:
        console.clear()
        titre("DOSSIERS & RAPPORTS", C_GOLD)
        choix = selectionner_option("DOSSIERS & RAPPORTS", [
            "Lister les dossiers", "Créer un dossier", "Ajouter une note",
            "Ajouter une source", "Exporter un dossier JSON", "Retour au menu principal",
        ])
        if choix is None or choix == "Retour au menu principal":
            return
        if choix == "Créer un dossier":
            nom = Prompt.ask("Nom du dossier").strip()
            if not nom:
                warn("Le nom du dossier ne peut pas être vide.")
                continue
            description = Prompt.ask("Description (facultative)", default="").strip()
            case_id = creer_case(nom, description)
            ok(f"Dossier #{case_id} créé localement.")
            pause()
        elif choix == "Lister les dossiers":
            dossiers = lister_cases()
            if dossiers:
                tableau = Table(box=BX, border_style=C_GOLD, header_style=f"bold {C_GOLD}")
                tableau.add_column("ID")
                tableau.add_column("Dossier")
                tableau.add_column("Mis à jour")
                for case in dossiers:
                    tableau.add_row(str(case["id"]), case["title"], case["updated_at"])
                console.print(tableau)
            else:
                warn("Aucun dossier enregistré.")
            pause()
        elif choix in {"Ajouter une note", "Ajouter une source", "Exporter un dossier JSON"}:
            case = _selectionner_dossier(choix.upper())
            if case is None:
                continue
            if choix == "Ajouter une note":
                kind = selectionner_option("TYPE DE NOTE", ["observation", "hypothese", "conclusion", "note_libre"])
                if not kind:
                    continue
                contenu = Prompt.ask("Contenu de la note").strip()
                if contenu:
                    ajouter_note(case["id"], kind, contenu)
                    ok("Note ajoutée au dossier.")
                else:
                    warn("Note vide : aucune modification effectuée.")
                pause()
            elif choix == "Ajouter une source":
                valeur = Prompt.ask("Valeur / URL de la source").strip()
                if valeur:
                    type_source = Prompt.ask("Type de donnée", default="observation").strip()
                    outil = Prompt.ask("Outil d'origine (facultatif)", default="").strip()
                    ajouter_source(case["id"], data_type=type_source, value=valeur, tool_name=outil)
                    ok("Source ajoutée au dossier.")
                else:
                    warn("Source vide : aucune modification effectuée.")
                pause()
            else:
                donnee = exporter_case_json(case["id"])
                os.makedirs(EXPORTS_DIR, exist_ok=True)
                chemin = os.path.join(EXPORTS_DIR, f"dossier-{case['id']}.json")
                with open(chemin, "w", encoding="utf-8") as fichier:
                    json.dump(donnee, fichier, ensure_ascii=False, indent=2)
                ok(f"Export JSON créé : {chemin}")
                pause()


def _afficher_historique():
    historique = charger_historique(50)
    titre("HISTORIQUE LOCAL", C_GOLD)
    if not historique:
        warn("Aucune activité enregistrée.")
    else:
        tableau = Table(box=BX, border_style=C_GOLD, header_style=f"bold {C_GOLD}")
        tableau.add_column("Date (UTC)")
        tableau.add_column("Action")
        tableau.add_column("Détails")
        for entree in reversed(historique):
            details = json.dumps(entree.get("details", {}), ensure_ascii=False)
            tableau.add_row(entree.get("timestamp", ""), entree.get("action", ""), details)
        console.print(tableau)
    pause()


_SEARCH_ACTIONS = [
    {"num": "cases", "nom": "Gestion des dossiers", "desc": "Créer des dossiers, ajouter des notes/sources et exporter en JSON",
     "fn": _gestion_dossiers, "chemin_navigation": "DOSSIERS & RAPPORTS > Investigations"},
    {"num": "history", "nom": "Historique local", "desc": "Consulter les dernières opérations enregistrées localement",
     "fn": _afficher_historique, "chemin_navigation": "DOSSIERS & RAPPORTS > Investigations"},
]
ACTIONS.update({outil["num"]: outil["fn"] for outil in _SEARCH_ACTIONS})

# Mots-clés métier complémentaires aux noms/descriptions (recherche sans accents).
MOTS_CLES_RECHERCHE = {
    "Recherche de pseudo": "username handle compte profil social media",
    "Analyse d'email": "courriel mailbox mx adresse électronique",
    "Enregistrements DNS": "dns record zone aaaa mx ns txt",
    "Reverse DNS (PTR)": "ptr reverse résolution inverse hostname",
    "Info ASN / reseau": "asn bgp fournisseur opérateur réseau",
    "Sous-domaines": "crt certificats domains enumeration",
    "Audit des headers": "headers entêtes csp hsts x-frame-options",
    "Certificat SSL/TLS": "https certificat x509 tls expiration",
    "Test CORS": "cross origin navigateur cors",
    "Decodeur JWT": "token bearer json web token",
    "Fuzzing headers HTTP": "fuzz edge cases malformed request",
    "Generateur wordlist": "dictionnaire mutations jeu de données",
    "Calculateur CIDR": "subnet masque réseau ip",
    "Corpus cas limites HTTP": "http protocol parser fuzzing edge cases corpus fixtures",
    "Dossiers & rapports": "case investigation notes sources dossier",
}


def _normaliser_recherche(texte):
    texte = unicodedata.normalize("NFKD", str(texte).casefold())
    return "".join(car for car in texte if not unicodedata.combining(car))


def rechercher_outils(terme, limite=20):
    """Recherche déterministe dans nom, usage, catégorie et alias fonctionnels."""
    termes = _normaliser_recherche(terme).split()
    if not termes:
        return []
    resultats = []
    for outil in [*FLAT, *_SEARCH_ACTIONS]:
        if not outil["fn"]:
            continue
        texte = " ".join((outil["nom"], outil["desc"], outil.get("chemin_navigation", ""),
                          MOTS_CLES_RECHERCHE.get(outil["nom"], "")))
        normalise = _normaliser_recherche(texte)
        if all(mot in normalise for mot in termes):
            nom = _normaliser_recherche(outil["nom"])
            score = (0 if nom.startswith(" ".join(termes)) else 1,
                     0 if all(mot in nom for mot in termes) else 1,
                     outil["nom"].casefold())
            resultats.append((score, outil))
    resultats.sort(key=lambda item: item[0])
    return [outil for _, outil in resultats[:limite]]


def _libelle_resultat(outil):
    return f"{outil['nom']} · {outil.get('chemin_navigation', 'Outil')} — {outil['desc']}"


def recherche_globale():
    """Recherche interactive puis retourne directement l'action sélectionnée."""
    try:
        requete = Prompt.ask("Recherche outil (Entrée pour annuler)").strip()
    except (KeyboardInterrupt, EOFError):
        return None
    if not requete:
        return None
    resultats = rechercher_outils(requete)
    if not resultats:
        warn(f"Aucun outil trouvé pour « {requete} ». Essayez un terme plus court.")
        return None
    table = Table(box=BX, border_style=C_GOLD, header_style=f"bold {C_GOLD}")
    table.add_column("Outil")
    table.add_column("Catégorie")
    table.add_column("Description")
    for outil in resultats:
        table.add_row(outil["nom"], outil.get("chemin_navigation", ""), outil["desc"])
    console.print(table)
    libelles = {_libelle_resultat(outil): outil for outil in resultats}
    selection = selectionner_option("RESULTATS DE RECHERCHE", list(libelles))
    return libelles[selection]["num"] if selection else None


def construire_menu(sel, buf, t, msg="", tout=False):
    """Rendu compact du menu principal, partagé par les captures et le terminal."""
    ui_cfg = obtenir_config_ui()
    palette = obtenir_theme()
    parts = []
    parts.append(Align.center(Text("LEAKFR-TOOLS · CYBERSECURITY WORKBENCH", style=f"bold {palette.get('principale', C_OSINT)}")))
    parts.append(Align.center(Text("Menu principal  >  choisissez un domaine ou recherchez un outil", style="dim")))
    parts.append(Text(""))

    tableau = Table(box=BX, border_style=palette.get("bordures", C_GOLD),
                    header_style=f"bold {C_GOLD}", title="DOMAINES")
    tableau.add_column("Catégorie", style="bold")
    tableau.add_column("Sous-catégories", justify="right")
    tableau.add_column("Outils")
    for node in NAVIGATION:
        if node.get("children"):
            count = sum(len(section.get("children", [])) for section in node["children"])
            tableau.add_row(node["label"], str(len(node["children"])), node["description"])
        else:
            tableau.add_row(node["label"], "—", node["description"])
    parts.append(Align.center(tableau))
    parts.append(Text(""))
    side = Text("Flèches haut/bas · Entrée ouvrir · Échap retour · Ctrl-C annuler/quitter", justify="center")
    if msg:
        side.append(f"  ·  {msg}", style="bold yellow")
    parts.append(Align.center(Panel(side, border_style="grey42", box=BX)))
    return Group(*parts)

class Touches:
    """Lecture clavier sans Entree (Windows et Linux/Mac)."""

    def __enter__(self):
        if os.name == "nt":
            import msvcrt
            while msvcrt.kbhit():
                msvcrt.getwch()
        else:
            import termios
            import tty
            self.fd = sys.stdin.fileno()
            self.old = termios.tcgetattr(self.fd)
            tty.setcbreak(self.fd)
        return self

    def __exit__(self, *a):
        if os.name != "nt":
            import termios
            termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old)

    @staticmethod
    def _norm(c):
        if c in ("\r", "\n"):
            return "ENTER"
        if c == "\x1b":
            return "ESC"
        if c in ("\x08", "\x7f"):
            return "BACK"
        if c == "\x03":
            return "QUIT"
        return c

    def lire(self, timeout=0.04):
        if os.name == "nt":
            import msvcrt
            fin = time.time() + timeout
            while time.time() < fin:
                if msvcrt.kbhit():
                    c = msvcrt.getwch()
                    if c in ("\x00", "\xe0"):
                        c2 = msvcrt.getwch()
                        return {"H": "UP", "P": "DOWN", "K": "LEFT", "M": "RIGHT"}.get(c2, "")
                    return self._norm(c)
                time.sleep(0.01)
            return None
        import select
        r, _, _ = select.select([self.fd], [], [], timeout)
        if not r:
            return None
        c = os.read(self.fd, 1).decode(errors="ignore")
        if c == "\x1b":
            r2, _, _ = select.select([self.fd], [], [], 0.02)
            if r2:
                seq = os.read(self.fd, 2).decode(errors="ignore")
                return {"[A": "UP", "[B": "DOWN", "[C": "RIGHT", "[D": "LEFT",
                        "OA": "UP", "OB": "DOWN"}.get(seq, "")
            return "ESC"
        return self._norm(c)

def _naviguer_menu():
    """Parcours hiérarchique partagé par l'interface terminal et le mode simple."""
    etiquettes = {node["label"]: node for node in NAVIGATION}
    while True:
        console.clear()
        titre("MENU PRINCIPAL", C_GOLD)
        table = Table(box=BX, border_style=C_GOLD, header_style=f"bold {C_GOLD}")
        table.add_column("Section")
        table.add_column("Contenu")
        for node in NAVIGATION:
            table.add_row(node["label"], node["description"])
        console.print(table)
        choix = selectionner_option("MENU PRINCIPAL", list(etiquettes))
        if choix is None:
            return "0"
        if choix == "Quitter":
            return "0"
        node = etiquettes[choix]
        action = node.get("action")
        if action == "quit":
            return "0"
        if action == "settings":
            _ecran_parametres()
            continue
        if action == "search":
            result = recherche_globale()
            if result:
                return result
            pause()
            continue

        categorie = node
        while True:
            console.clear()
            chemin = f"Menu principal > {categorie['label']}"
            titre(chemin.upper(), C_GOLD)
            options = categorie["children"]
            descriptions = Table(box=BX, border_style=C_GOLD, header_style=f"bold {C_GOLD}")
            descriptions.add_column("Sous-catégorie")
            descriptions.add_column("Usage")
            for section in options:
                descriptions.add_row(section["label"], section["description"])
            console.print(descriptions)
            labels = [section["label"] for section in options]
            labels.extend(["Recherche globale", "Menu principal"])
            selection = selectionner_option(chemin, labels)
            if selection is None or selection == "Menu principal":
                break
            if selection == "Recherche globale":
                result = recherche_globale()
                if result:
                    return result
                continue
            section = next(item for item in options if item["label"] == selection)
            if section.get("action") == "cases":
                _gestion_dossiers()
                continue
            if section.get("action") == "history":
                _afficher_historique()
                continue
            while True:
                chemin_section = f"{chemin} > {section['label']}"
                console.clear()
                titre(chemin_section.upper(), categorie.get("color", C_GOLD))
                outils = section["children"]
                tableau = Table(box=BX, border_style=C_GOLD, header_style=f"bold {C_GOLD}")
                tableau.add_column("Outil")
                tableau.add_column("Fonction")
                for outil_node in outils:
                    tableau.add_row(outil_node["label"], outil_node["description"])
                console.print(tableau)
                libelles = [(_libelle_resultat(outil_node["tool"]) if "tool" in outil_node
                             else f"{outil_node['label']} — {outil_node['description']}")
                            for outil_node in outils]
                libelles.extend([f"Retour à {categorie['label']}", "Menu principal"])
                choix_outil = selectionner_option(chemin_section, libelles)
                if choix_outil is None:
                    return_to_main = False
                    break
                if choix_outil == "Menu principal":
                    return_to_main = True
                    break
                if choix_outil == f"Retour à {categorie['label']}":
                    return_to_main = False
                    break
                selected_node = next((outil_node for outil_node, label in zip(outils, libelles)
                                      if label == choix_outil), None)
                if selected_node and "tool" in selected_node:
                    return selected_node["tool"]["num"]
                if selected_node and selected_node.get("action"):
                    return selected_node["action"]
            if selection == "Menu principal" or return_to_main:
                break
    return "0"


def menu_interactif():
    """Navigation fléchée, hiérarchique ; Ctrl-C remonte au gestionnaire principal."""
    return _naviguer_menu()


def menu_simple():
    """Fallback console utilisant la même arborescence, sans sélection numérique."""
    return _naviguer_menu()

def main():
    global _CONFIG
    parser = argparse.ArgumentParser(
        description="LeakFr-Tools : boîte à outils OSINT, réseau et cybersécurité.",
        epilog="Utilise les tests actifs uniquement sur des systèmes autorisés.",
    )
    parser.add_argument("--simple", action="store_true", help="désactive le menu clavier interactif")
    parser.add_argument("--ascii", action="store_true", help="privilégie un affichage compatible ASCII")
    parser.add_argument("--version", action="version", version="LeakFr-Tools 2.0")
    args = parser.parse_args()
    global INTERACTIF, UNICODE, BX, CONN_T, CONN_L, PIPE
    if args.simple:
        INTERACTIF = False
    if args.ascii:
        UNICODE = False
        BX = box.ASCII
        CONN_T, CONN_L, PIPE = ("|-- ", "`-- ", "|   ")
    _intro_ascii(_CONFIG)
    while True:
        try:
            choix = menu_interactif() if INTERACTIF else menu_simple()
        except KeyboardInterrupt:
            break
        if choix == "0":
            break
        console.clear()
        try:
            ACTIONS[choix]()
        except KeyboardInterrupt:
            warn("Interrompu.")
        except Exception as e:
            bad(f"Erreur inattendue : {e}")
        try:
            from core.common import pause
            pause()
        except (KeyboardInterrupt, EOFError):
            pass
    console.clear()
    console.print(texte_arc("A bientot !", time.time(), 0), justify="center")

if __name__ == "__main__":
    main()