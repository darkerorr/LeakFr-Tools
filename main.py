#!/usr/bin/env python3
"""OSINT & PENTEST TOOLBOX
Suite complete d'investigation, reconnaissance, cybersecurite, pentest et utilitaires.
Architecture modulaire : modules/<categorie>/<outil>.py
"""
import argparse
import os
import sys
import time
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
    console, arc, texte_arc, bad, warn, ok, BX, UNICODE, INTERACTIF,
    CONN_T, CONN_L, PIPE, ARROW,
    BANNER, C_OSINT, C_RECON, C_CYBER, C_PENTEST, C_UTIL, C_ASTRO, C_GOLD, C_DISCORD,
    initialiser_theme, obtenir_theme, obtenir_config_ui
)
from core.config import charger, sauvegarder, restaurer_defauts, DEFAUTS
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
    convertir_base, calculer_dates,
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


def _ecran_parametres():
    """Menu de parametres persistant."""
    global _CONFIG
    from core.theme import THEMES, liste_themes, nommer_theme

    while True:
        console.clear()
        titre("PARAMETRES", C_GOLD)

        t = Table(box=BX, border_style=C_GOLD, header_style=f"bold {C_GOLD}")
        t.add_column("N.", style="bold", width=3)
        t.add_column("Option", width=30)
        t.add_column("Valeur actuelle")

        app = _CONFIG.get("apparence", {})
        reseau = _CONFIG.get("reseau", {})

        styles = {"dashboard": "Dashboard split", "classique": "Classique", "compact": "Compact"}
        largeurs = {"auto": "Automatique", "large": "Large", "etroit": "Etroit"}
        t.add_row("1", "Palette de couleurs", nommer_theme(app.get("theme_actif", "original")))
        t.add_row("2", "Style d'interface", styles.get(app.get("style_interface"), "Dashboard split"))
        t.add_row("3", "Couleur d'accent", app.get("couleur_accent") or "Auto (palette)")
        t.add_row("4", "Couleur du texte shell", app.get("couleur_shell_texte", "#ffffff"))
        t.add_row("5", "Fond shell (sorties Rich)", app.get("couleur_shell_fond", "#10131c"))
        t.add_row("6", "Largeur du menu", largeurs.get(app.get("largeur_menu"), "Automatique"))
        t.add_row("7", "Panneau lateral", str(app.get("afficher_panneau_lateral", True)))
        t.add_row("8", "Badges de categories", str(app.get("afficher_badges_categories", True)))
        t.add_row("9", "Banniere de demarrage", str(app.get("banniere_demarrage", True)))
        t.add_row("10", "Animations", str(app.get("animations", True)))
        t.add_row("11", "Timeout reseau (s)", str(reseau.get("timeout", 8)))
        t.add_row("12", "Restaurer parametres par defaut", "")
        t.add_row("13", "Personnaliser les couleurs du theme", "")
        t.add_row("0", "Retour au menu principal", "")

        console.print(t)
        c = Prompt.ask(f"[bold {C_GOLD}]Parametres {ARROW}[/]", default="0").strip()

        if c == "0":
            break
        elif c == "1":
            _menu_themes()
            sauvegarder(_CONFIG)
            _appliquer_configuration_visuelle()
        elif c == "13":
            _menu_palette_personnalisee()
            pause()
            continue
        elif c == "2":
            console.print("[1] Dashboard split  [2] Classique  [3] Compact")
            choix = Prompt.ask("Style", choices=["1", "2", "3"], default="1")
            _CONFIG["apparence"]["style_interface"] = {"1": "dashboard", "2": "classique", "3": "compact"}[choix]
        elif c == "3":
            _configurer_couleur("couleur_accent", "Accent (hex #RRGGBB ou vide pour Auto)", optionnelle=True)
            pause()
            continue
        elif c == "4":
            _configurer_couleur("couleur_shell_texte", "Couleur du texte shell")
            pause()
            continue
        elif c == "5":
            _configurer_couleur("couleur_shell_fond", "Couleur de fond shell")
            pause()
            continue
        elif c == "6":
            console.print("[1] Automatique  [2] Large  [3] Etroit")
            choix = Prompt.ask("Largeur", choices=["1", "2", "3"], default="1")
            _CONFIG["apparence"]["largeur_menu"] = {"1": "auto", "2": "large", "3": "etroit"}[choix]
        elif c == "7":
            app["afficher_panneau_lateral"] = not app.get("afficher_panneau_lateral", True)
        elif c == "8":
            app["afficher_badges_categories"] = not app.get("afficher_badges_categories", True)
        elif c == "9":
            app["banniere_demarrage"] = not app.get("banniere_demarrage", True)
        elif c == "10":
            app["animations"] = not app.get("animations", True)
        elif c == "11":
            v = Prompt.ask("Timeout reseau (secondes)", default=str(reseau.get("timeout", 8)))
            if v.isdigit() and 1 <= int(v) <= 120:
                reseau["timeout"] = int(v)
                sauvegarder(_CONFIG)
                ok("Timeout mis a jour.")
            else:
                bad("Valeur invalide (1-120).")
        elif c == "12":
            if Confirm.ask("Restaurer tous les parametres par defaut ?"):
                _CONFIG = restaurer_defauts()
                _appliquer_configuration_visuelle()
                ok("Parametres reinitialises.")
        if c in {"2", "6", "7", "8", "9", "10"}:
            sauvegarder(_CONFIG)
            _appliquer_configuration_visuelle()
            ok("Reglage d'interface sauvegarde et applique.")
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
        table.add_column("N.", width=4)
        table.add_column("Role")
        table.add_column("Couleur")
        for index, slot in enumerate(SLOTS, 1):
            table.add_row(str(index), labels[slot], palette.get(slot, "#ffffff"))
        table.add_row("0", "Terminer", "")
        console.print(table)
        choix = Prompt.ask("Role a modifier", default="0").strip()
        if choix == "0":
            break
        if not choix.isdigit() or not 1 <= int(choix) <= len(SLOTS):
            bad("Choix de role invalide.")
            continue
        slot = SLOTS[int(choix) - 1]
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
        t.add_column("N.", style="bold", width=3)
        t.add_column("Theme", width=25)
        t.add_column("Statut")

        for i, cle in enumerate(liste_themes(), 1):
            actif = " [ACTIF]" if cle == theme_actif else ""
            t.add_row(str(i), nommer_theme(cle), f"[bold green]{actif}[/]" if actif else "")

        t.add_row("0", "Retour", "")

        console.print(t)
        c = Prompt.ask(f"[bold {C_GOLD}]Themes {ARROW}[/]", default="0").strip()

        if c == "0":
            break

        themes_liste = liste_themes()
        if c.isdigit() and 1 <= int(c) <= len(themes_liste):
            cle = themes_liste[int(c) - 1]
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

def construire_menu(sel, buf, t, msg="", tout=False):
    parts = []
    ui_cfg = obtenir_config_ui()
    palette = obtenir_theme()
    haut = console.height or 30

    if UNICODE and haut >= 36:
        for y, ligne in enumerate(BANNER):
            parts.append(Align.center(texte_arc(ligne, t, y * 5)))
    else:
        parts.append(Align.center(texte_arc(">  O S I N T  &  P E N T E S T   T O O L B O X  <", t, 0)))

    # Badges de categories au centre
    badges = Text(justify="center")
    badges_liste = [
        ("OSINT", C_OSINT),
        ("RECON", C_RECON),
        ("CYBER", C_CYBER),
        ("PENTEST", C_PENTEST),
        ("DISCORD", C_DISCORD),
        ("UTILS", C_UTIL),
        ("ASTRO", C_ASTRO),
    ]
    if ui_cfg.get("afficher_badges_categories", True):
        for idx, (b_nom, b_col) in enumerate(badges_liste):
            badges.append(f" {b_nom} ", style=f"bold black on {b_col}")
            if idx < len(badges_liste) - 1:
                badges.append("  ")
        parts.append(Align.center(badges))
        parts.append(Text(""))

    cat_sel = FLAT[sel]["cat"] if 0 <= sel < len(FLAT) else None
    item_sel = FLAT[sel] if 0 <= sel < len(FLAT) else None

    # Construction de l'arbre (colonne de gauche)
    arbre = [texte_arc(("* " if UNICODE else "* ") + "SUITE DE SECURITE & RECON", t, 0)]
    ln = 0
    categories_dynamiques = [
        palette.get("principale", C_OSINT), palette.get("secondaire", C_RECON),
        palette.get("erreurs", C_CYBER), palette.get("avertissements", C_PENTEST),
        palette.get("secondaire", C_DISCORD), palette.get("succes", C_UTIL),
        palette.get("principale", C_ASTRO),
    ]
    style_ui = ui_cfg.get("style_interface", "dashboard")
    for ci, (cat, couleur_defaut, opts) in enumerate(CATALOGUE):
        couleur = categories_dynamiques[ci] if ci < len(categories_dynamiques) else couleur_defaut
        ln += 1
        ouvert = tout or ci == cat_sel
        l = texte_arc(CONN_T, t, ln * 4)
        l.append(("v " if UNICODE else "v ") if ouvert else ("> " if UNICODE else "> "),
                 style=f"bold {couleur}")
        l.append(f"{cat:<16}", style=f"bold {couleur}")
        l.append(f" [{len(opts)} modules]", style="grey50")
        arbre.append(l)
        if not ouvert:
            continue
        items = [f for f in FLAT if f["cat"] == ci]
        for oi, f in enumerate(items):
            ln += 1
            dernier = oi == len(items) - 1
            l = texte_arc(PIPE, t, ln * 4)
            l.append_text(texte_arc(CONN_L if dernier else CONN_T, t, ln * 4 + 4))
            est_actif = (FLAT.index(f) == sel)
            if est_actif:
                l.append(f" {f['num']:>2} ", style="bold black on white")
                l.append(f" {f['nom']} ", style=f"bold black on {arc(ln * 4, t, 0.35)}")
                l.append(f"  {f['desc']}", style="white")
            else:
                l.append(f"{f['num']:>2} ", style=f"bold {couleur}")
                l.append(f"{f['nom']}", style="white")
                l.append(f"  {f['desc']}", style="grey50")
            arbre.append(l)

    ln += 1
    l = texte_arc(CONN_L, t, ln * 4)
    quit_idx = NUM_IDX["0"]
    if sel == quit_idx:
        l.append("  0  Quitter la suite ", style=f"bold black on {arc(ln * 4, t, 0.35)}")
    else:
        l.append(" 0 ", style="bold red")
        l.append("Quitter", style="red")
    arbre.append(l)

    boite_ui = box.SQUARE if style_ui == "classique" else (box.MINIMAL if style_ui == "compact" else BX)
    couleur_bordure = palette.get("bordures", arc(0, t, 0.3))
    panneau_arbre = Panel(
        Group(*arbre),
        box=boite_ui,
        border_style=couleur_bordure if style_ui != "dashboard" else arc(0, t, 0.3),
        padding=(0, 2),
        title=texte_arc(" [ CATALOGUE D'OUTILS ] ", t, 0),
        title_align="left"
    )

    # Volet lateral / Encart d'information (Dashboard sur le cote)
    total_outils = sum(len(opts) for _, _, opts in CATALOGUE)
    nom_cat = CATALOGUE[cat_sel][0] if cat_sel is not None and cat_sel < len(CATALOGUE) else "General"
    col_cat = CATALOGUE[cat_sel][1] if cat_sel is not None and cat_sel < len(CATALOGUE) else C_GOLD

    side_elements = []
    side_elements.append(Text.from_markup(f"[bold {palette.get('secondaire', 'cyan')}]> ETAT SYSTEME[/]"))

    side_elements.append(Text.from_markup(f". Modules dispos : [bold green]{total_outils}[/]"))
    side_elements.append(Text.from_markup(f". Categories     : [bold yellow]{len(CATALOGUE)}[/]"))
    side_elements.append(Text.from_markup(f". OS             : [bold white]{platform.system()} {platform.release()}[/]"))
    side_elements.append(Text(""))

    side_elements.append(Text.from_markup(f"[bold {col_cat}]> INSPECTEUR[/]"))
    if item_sel and item_sel["num"] != "0":
        side_elements.append(Text.from_markup(f". N  Module  : [bold gold1]#{item_sel['num']}[/]"))
        side_elements.append(Text.from_markup(f". Nom        : [bold white]{escape(item_sel['nom'])}[/]"))
        side_elements.append(Text.from_markup(f". Domaine    : [bold {col_cat}]{nom_cat}[/]"))
        side_elements.append(Text.from_markup(f". Role       : [dim italic]{escape(item_sel['desc'])}[/]"))
    elif item_sel and item_sel["num"] == "0":
        side_elements.append(Text.from_markup(f"[bold red]Quitter le programme[/]"))
        side_elements.append(Text.from_markup(f"[dim]Ferme la console et libere les sockets.[/]"))
    else:
        side_elements.append(Text.from_markup(f"[dim]Survole un outil pour inspecter[/]"))

    side_elements.append(Text(""))
    side_elements.append(Text.from_markup(f"[bold magenta]>  RACCOURCIS[/]"))
    side_elements.append(Text.from_markup(f"[bold white]^ / v[/]   : Naviguer"))
    side_elements.append(Text.from_markup(f"[bold white]Entree[/]  : Executer"))
    side_elements.append(Text.from_markup(f"[bold white]0..9[/]    : Acces direct"))
    side_elements.append(Text.from_markup(f"[bold white]s[/]       : Parametres"))
    side_elements.append(Text.from_markup(f"[bold white]q[/]       : Quitter"))

    panneau_side = Panel(
        Group(*side_elements),
        box=boite_ui,
        border_style=col_cat,
        padding=(0 if style_ui == "compact" else 1, 1 if style_ui == "compact" else 2),
        title=f"[bold {col_cat}] INFO & CONTROLE [/]",
        title_align="center"
    )

    w_console = console.width or 100
    afficher_side = (style_ui == "dashboard" and ui_cfg.get("afficher_panneau_lateral", True))
    largeur_mode = ui_cfg.get("largeur_menu", "auto")
    if largeur_mode == "large":
        w_console = max(w_console, 115)
    elif largeur_mode == "etroit":
        w_console = min(w_console, 78)
    if w_console >= 82 and not tout and afficher_side:
        layout_table = Table.grid(padding=(0, 1))
        largeur_totale = min(w_console, 115)
        w_main = int(largeur_totale * 0.64)
        w_side = int(largeur_totale * 0.36)
        panneau_arbre.width = w_main
        panneau_side.width = w_side
        layout_table.add_column()
        layout_table.add_column()
        layout_table.add_row(panneau_arbre, panneau_side)
        parts.append(Align.center(layout_table))
    else:
        panneau_arbre.width = min(w_console, 88)
        parts.append(Align.center(panneau_arbre))

    if not tout and ui_cfg.get("afficher_aide_menu", True):
        parts.append(Text(""))
        saisie = Text(justify="center")
        saisie.append("COMMANDE : ", style="bold grey70")
        saisie.append(buf + ("|" if UNICODE else "_"), style=f"bold {arc(0, t, 0.6)}")
        if msg:
            saisie.append(f"   ! {msg}", style="bold red")
        parts.append(Align.center(Panel(saisie, box=BX, border_style="grey42", width=min(w_console, 70))))

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

def menu_interactif():
    global SEL
    buf = ""
    msg = ""
    t0 = time.time()
    n = len(FLAT)
    with Touches() as T, Live(console=console, screen=True, auto_refresh=False) as live:
        while True:
            live.update(construire_menu(SEL, buf, time.time() - t0, msg), refresh=True)
            k = T.lire(0.04)
            if not k:
                continue
            msg = ""
            if k == "UP":
                SEL = (SEL - 1) % n
                buf = ""
            elif k == "DOWN":
                SEL = (SEL + 1) % n
                buf = ""
            elif k == "ENTER":
                if buf:
                    if buf in NUM_IDX:
                        SEL = NUM_IDX[buf]
                        return buf
                    msg = "choix invalide"
                    buf = ""
                else:
                    return FLAT[SEL]["num"]
            elif k == "BACK":
                buf = buf[:-1]
            elif k == "ESC":
                buf = ""
            elif k in ("s", "S"):
                _ecran_parametres()
                buf = ""
                console.clear()
            elif k in ("q", "Q", "QUIT"):
                return "0"
            elif len(k) == 1 and k.isdigit() and len(buf) < 2:
                buf += k
                if buf in NUM_IDX:
                    SEL = NUM_IDX[buf]

def menu_simple():
    console.clear()
    console.print(construire_menu(-1, "", 0.0, tout=True))
    while True:
        c = Prompt.ask(f"\n[bold {C_GOLD}]osint {ARROW}[/]").strip().lower()
        if c in ("q", "quit", "exit"):
            return "0"
        if c in NUM_IDX:
            return c
        bad("Choix invalide.")

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