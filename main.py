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
import platform
from pathlib import Path

if os.name == "nt":
    try:
        import ctypes
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
    except (AttributeError, OSError):
        pass
    try:
        sys.stdout.reconfigure(encoding='utf-8')
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

from core import ui
from core.branding import en_tete, entete_bandeau, logo_final
from core.vcs import info_commit, ligne_commit
from core.common import (
    console, bad, warn, ok, choisir_option, BX, UNICODE, INTERACTIF,
    CONN_T, CONN_L, PIPE, ARROW, MODE_TEXTE,
    BANNER, BANNER_SOUS_TITRE, BANNER_TAGLINE,
    C_OSINT, C_RECON, C_CYBER, C_PENTEST, C_UTIL, C_ASTRO, C_GOLD, C_DISCORD,
    initialiser_theme, obtenir_theme, obtenir_config_ui, titre, pause,
    clear_screen, configurer_affichage, ask_number, est_ecran_etroit, demander,
    largeur_utile, QuitterApplication,
)
from core.config import charger, sauvegarder, restaurer_defauts, DEFAUTS, EXPORTS_DIR
from core.environment import (
    ENVIRONNEMENTS, detecter_environnement, select_environment,
    resume_environnement, libelle_environnement, normaliser_cle,
)
from core.compat import afficher_compatibilite
from core.cases import (
    lister_cases, creer_case, obtenir_case, renommer_case, supprimer_case,
    ajouter_note, modifier_note, supprimer_note,
    ajouter_source, charger_historique, effacer_historique,
    exporter_case_json, ajouter_preuve, lister_preuves, verifier_preuve,
    verifier_chaine, lister_verifications, exporter_preuves_json, exporter_preuves_markdown
)
from core.correlate import (
    correler_case, exporter_json as exporter_correlation_json,
    exporter_markdown as exporter_correlation_markdown
)

from core.catalogue import (
    CATALOGUE, NAV_GROUPS, FLAT, NUM_IDX, SEL, ACTIONS,
    _OUTILS_PAR_NOM, _ROUTE_PAR_NOM, rechercher_outils as _moteur_recherche,
)

_CONFIG = charger()


def _synchroniser_couleurs_locales():
    """Actualise les constantes importees apres un changement de palette."""
    global C_OSINT, C_RECON, C_CYBER, C_PENTEST, C_UTIL, C_ASTRO, C_GOLD, C_DISCORD
    import core.common as common_ui
    for nom in ("C_OSINT", "C_RECON", "C_CYBER", "C_PENTEST", "C_UTIL", "C_ASTRO", "C_GOLD", "C_DISCORD"):
        globals()[nom]= getattr(common_ui, nom)


def _appliquer_configuration_visuelle():
    initialiser_theme(_CONFIG)
    _synchroniser_couleurs_locales()
    configurer_affichage(_CONFIG)


_appliquer_configuration_visuelle()


def selectionner_option(titre_menu, options, selection_initiale=0):
    """Sélection unifiée pour les menus et leurs sous-menus."""
    return choisir_option(titre_menu, options, selection_initiale)


def _ecran_parametres():
    """Menu de parametres persistant."""
    global _CONFIG
    from core.theme import THEMES, liste_themes, nommer_theme

    while True:
        clear_screen()
        titre('PARAMETRES', C_GOLD)

        t = Table(box=BX, border_style=ui.BORDURE, header_style="bold white")
        t.add_column('Reglage', width=40)
        t.add_column("Valeur actuelle")

        app = _CONFIG.get('apparence', {})
        reseau = _CONFIG.get("reseau", {})

        styles = {'dashboard': 'Dashboard split', 'classique': 'Classique', 'compact':'Compact'}
        largeurs= {"auto":"Automatique", "large": "Large", "etroit": "Etroit"}
        plateforme = _CONFIG.setdefault("plateforme", {})
        reglages =[
            "Palette de couleurs", "Style d'interface", "Couleur d'accent",
            "Couleur du texte shell", "Fond shell", "Largeur du menu",
            'Panneau lateral', 'Badges de categories', 'Banniere de demarrage',
            "Duree de l'introduction", "Animations", "Timeout reseau",
            "Cle API NASA",
            'Environnement (affichage)',
            "Mode texte de secours", "Largeur de sortie", "Pagination",
            "Compatibilite des outils", "Restaurer les parametres par defaut",
            'Personnaliser les couleurs du theme', 'Retour au menu principal',
        ]
        t.add_row("Palette de couleurs", nommer_theme(app.get("theme_actif", "original")))
        t.add_row("Style d'interface", styles.get(app.get('style_interface'), 'Dashboard split'))
        t.add_row("Couleur d'accent", app.get("couleur_accent") or "Auto (palette)")
        t.add_row("Couleur du texte shell", app.get("couleur_shell_texte", "#ffffff"))
        t.add_row('Fond shell (sorties Rich)', app.get('couleur_shell_fond', '#10131c'))
        t.add_row("Largeur du menu", largeurs.get(app.get("largeur_menu"), "Automatique"))
        t.add_row("Panneau lateral", str(app.get("afficher_panneau_lateral", True)))
        t.add_row('Badges de categories', str(app.get('afficher_badges_categories', True)))
        t.add_row("Banniere de demarrage", str(app.get("banniere_demarrage", True)))
        _duree = duree_intro(app)
        t.add_row("Duree de l'introduction",
                  "Instantane (0 s)" if _duree <= 0 else f"{_duree:.1f} s")
        t.add_row("Animations", str(app.get("animations", True)))
        t.add_row('Timeout reseau (s)', str(reseau.get('timeout', 8)))
        cle_nasa = str((_CONFIG.get("api_keys") or {}).get("nasa_api_key") or "")
        t.add_row("Cle API NASA", "definie (masquee)" if cle_nasa else
                  ('NASA_API_KEY (environnement)' if os.environ.get('NASA_API_KEY')
                   else "cle publique DEMO_KEY"))
        env_configure = str(plateforme.get("environnement") or "auto")
        if env_configure == 'auto':
            env_configure =f"Automatique ({libelle_environnement(detecter_environnement()['cle'])})"
        else:
            env_configure = libelle_environnement(env_configure)
        t.add_row("Environnement (affichage)", env_configure)
        t.add_row("Mode texte de secours", str(plateforme.get("mode_texte", False)))
        t.add_row('Largeur de sortie', largeurs.get(plateforme.get('largeur_sortie'), 'Automatique'))
        t.add_row("Pagination", f"{plateforme.get('pagination', 15)} resultats")
        t.add_row("Compatibilite des outils", "Diagnostic local")
        t.add_row('Restaurer les parametres par defaut', '')
        t.add_row("Personnaliser les couleurs du theme", "")
        t.add_row("Retour au menu principal", "")

        console.print(t)
        c = selectionner_option("PARAMETRES", reglages)
        if c is None or c == 'Retour au menu principal':
            break
        elif c == "Palette de couleurs":
            _menu_themes()
            sauvegarder(_CONFIG)
            _appliquer_configuration_visuelle()
        elif c== 'Personnaliser les couleurs du theme':
            _menu_palette_personnalisee()
            pause()
            continue
        elif c == "Style d'interface":
            choix = selectionner_option("STYLE D'INTERFACE", ["Dashboard split", "Classique", "Compact"])
            if choix is None:
                continue
            _CONFIG["apparence"]["style_interface"] = {
                'Dashboard split':'dashboard', 'Classique': 'classique', 'Compact':'compact'
            }[choix]
        elif c == "Couleur d'accent":
            _configurer_couleur('couleur_accent', 'Accent (hex #RRGGBB ou vide pour Auto)', optionnelle=True)
            pause()
            continue
        elif c== 'Couleur du texte shell':
            _configurer_couleur("couleur_shell_texte", "Couleur du texte shell")
            pause()
            continue
        elif c == "Fond shell":
            _configurer_couleur("couleur_shell_fond", "Couleur de fond shell")
            pause()
            continue
        elif c == "Largeur du menu":
            choix =selectionner_option('LARGEUR DU MENU', ['Automatique', 'Large', 'Etroit'])
            if choix is None:
                continue
            _CONFIG['apparence']['largeur_menu'] = {
                "Automatique": "auto", "Large": "large", "Etroit": "etroit"
            }[choix]
        elif c=='Panneau lateral':
            app["afficher_panneau_lateral"] = not app.get("afficher_panneau_lateral", True)
        elif c == "Badges de categories":
            app['afficher_badges_categories'] = not app.get('afficher_badges_categories', True)
        elif c =="Banniere de demarrage":
            app["banniere_demarrage"] = not app.get("banniere_demarrage", True)
        elif c == "Duree de l'introduction":
            brut=demander("Duree de l'introduction (0 a 10 secondes, 0 = instantane)",
                            f"{duree_intro(app):.1f}")
            try:
                valeur = float(str(brut).replace(",", "."))
            except ValueError:
                bad('Valeur invalide (nombres entre 0 et 10).')
                continue
            app["duree_intro"] = max(0.0, min(INTRO_DUREE_MAX, valeur))
            sauvegarder(_CONFIG)
            ok(f"Introduction reglee sur {app['duree_intro']:.1f} s.")
        elif c == "Animations":
            app['animations'] =not app.get('animations', True)
        elif c == "Timeout reseau":
            v = Prompt.ask("Timeout reseau (secondes)", default=str(reseau.get("timeout", 8)))
            if v.isdigit() and 1 <= int(v) <= 120:
                reseau["timeout"] =int(v)
                sauvegarder(_CONFIG)
                ok('Timeout mis a jour.')
            else:
                bad("Valeur invalide (1-120).")
        elif c == 'Cle API NASA':
            actuelle = str((_CONFIG.get("api_keys") or {}).get("nasa_api_key") or "")
            saisie_cle =Prompt.ask(
                'Cle API NASA (vide pour effacer ; NASA_API_KEY reste prioritaire)',
                default=actuelle, show_default=False).strip()
            _CONFIG.setdefault("api_keys", {})["nasa_api_key"] = saisie_cle
            sauvegarder(_CONFIG)
            if saisie_cle:
                ok(f"Cle API NASA enregistree localement ({len(saisie_cle)} caracteres, "
                   'non affichee). Elle sera utilisee au prochain appel NASA.')
            else:
                ok("Cle API NASA effacee : retour a la cle publique DEMO_KEY.")
        elif c == 'Environnement (affichage)':
            cle =select_environment(_CONFIG)
            plateforme["environnement"] = normaliser_cle(cle)
            plateforme['selectionne_le'] = resume_environnement(cle)['detecte_le']
            sauvegarder(_CONFIG)
            _appliquer_configuration_visuelle()
            ok(f"Affichage adapte a {libelle_environnement(cle)} (systeme reel inchange).")
        elif c == "Mode texte de secours":
            plateforme["mode_texte"]=not plateforme.get("mode_texte", False)
            sauvegarder(_CONFIG)
            _appliquer_configuration_visuelle()
            ok("Mode texte active." if plateforme["mode_texte"] else "Mode texte desactive.")
        elif c == 'Largeur de sortie':
            choix = selectionner_option("LARGEUR DE SORTIE",
                                        ["Automatique", "Large", "Etroit"])
            if choix is None:
                continue
            plateforme["largeur_sortie"]= {
                'Automatique': 'auto', 'Large':'large', 'Etroit': 'etroit'
            }[choix]
            sauvegarder(_CONFIG)
            _appliquer_configuration_visuelle()
            ok("Largeur de sortie appliquee.")
        elif c == "Pagination":
            valeur = ask_number('Resultats par page', 5, 50,
                                defaut=plateforme.get("pagination", 15))
            if valeur is not None:
                plateforme['pagination']= valeur
                sauvegarder(_CONFIG)
                _appliquer_configuration_visuelle()
                ok(f"Pagination : {valeur} resultats par page.")
        elif c== "Compatibilite des outils":
            afficher_compatibilite()
            pause()
            continue
        elif c == "Restaurer les parametres par defaut":
            if Confirm.ask('Restaurer tous les parametres par defaut ?'):
                _CONFIG =restaurer_defauts()
                _appliquer_configuration_visuelle()
                ok('Parametres reinitialises.')
        if c in {"Style d'interface", "Largeur du menu", "Panneau lateral",
                 "Badges de categories", "Banniere de demarrage", "Animations"}:
            sauvegarder(_CONFIG)
            _appliquer_configuration_visuelle()
            ok("Reglage d'interface sauvegarde et applique.")
        if c not in {"Couleur d'accent", 'Couleur du texte shell', 'Fond shell',
                     "Personnaliser les couleurs du theme", "Environnement (affichage)",
                     "Mode texte de secours", "Largeur de sortie", "Pagination"}:
            pause()


def _menu_palette_personnalisee():
    """Editeur de couleurs par role, sauvegarde dans la configuration locale."""
    global _CONFIG
    from core.theme import SLOTS, couleur_valide, appliquer_theme
    palette = _CONFIG.setdefault("theme_personnalise", {}).copy()
    theme_config =dict(_CONFIG)
    theme_config.setdefault('apparence', {})['couleur_accent'] = ''
    palette.update(appliquer_theme(theme_config))
    _CONFIG["theme_personnalise"] =palette
    labels = {
        "principale": "Couleur principale", "secondaire": "Couleur secondaire",
        "titres": "Titres", "texte_principal":"Texte principal",
        'texte_secondaire':'Texte secondaire', 'selection': 'Selection',
        "bordures": "Bordures", "accents": "Accents", "succes":"Succes",
        "avertissements": "Avertissements", "erreurs":"Erreurs", "panneaux": "Panneaux",
    }
    while True:
        clear_screen()
        titre('PALETTE PERSONNALISEE', C_GOLD)
        table= Table(box=BX, border_style=ui.BORDURE, header_style="bold white")
        table.add_column("Role")
        table.add_column('Couleur')
        roles = [labels[slot] for slot in SLOTS]
        for slot in SLOTS:
            table.add_row(labels[slot], palette.get(slot, '#ffffff'))
        table.add_row("Terminer", "")
        console.print(table)
        choix = selectionner_option('PALETTE PERSONNALISEE', roles + ['Terminer'])
        if choix in (None, "Terminer"):
            break
        slot = SLOTS[roles.index(choix)]
        valeur =Prompt.ask(f"Nouvelle couleur pour {labels[slot]}", default=palette.get(slot, "#ffffff")).strip()
        if not couleur_valide(valeur):
            bad('Couleur invalide : saisissez #RRGGBB ou un nom Rich reconnu.')
            continue
        palette[slot] = valeur.lower()
        _CONFIG['theme_personnalise'] =palette
        _CONFIG["apparence"]["theme_actif"] = "personnalise"
        _appliquer_configuration_visuelle()
        sauvegarder(_CONFIG)
        ok(f"{labels[slot]} appliquee.")


def _configurer_couleur(cle, invite, optionnelle=False):
    from core.theme import couleur_valide
    valeur = Prompt.ask(invite, default='' if optionnelle else _CONFIG['apparence'].get(cle, '#ffffff'),
                        show_default=not optionnelle).strip()
    if optionnelle and not valeur:
        _CONFIG['apparence'][cle] =''
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
        clear_screen()
        titre('PERSONNALISATION DES COULEURS', C_GOLD)

        app = _CONFIG.get("apparence", {})
        theme_actif = app.get('theme_actif', 'original')

        t = Table(box=BX, border_style=ui.BORDURE, header_style="bold white")
        t.add_column('Theme', width=25)
        t.add_column("Statut")

        themes_liste = liste_themes()
        options= []
        for cle in themes_liste:
            label= nommer_theme(cle)
            options.append(label)
            actif =" [ACTIF]" if cle == theme_actif else ""
            t.add_row(label, f"[bold green]{actif}[/]" if actif else '')

        t.add_row("Retour", "")

        console.print(t)
        choix = selectionner_option("THEMES", options + ["Retour"])
        if choix in (None, 'Retour'):
            break

        cle =themes_liste[options.index(choix)]
        _CONFIG["apparence"]["theme_actif"] = cle
        initialiser_theme(_CONFIG)
        sauvegarder(_CONFIG)
        ok(f"Theme '{nommer_theme(cle)}' applique.")
        pause()


INTRO_DUREE_DEFAUT = 3.2
INTRO_DUREE_COURTE=1.2
INTRO_DUREE_MAX = 10.0


def duree_intro(apparence):
    """Duree de l'introduction en secondes (0 = banniere instantanee).

    La valeur est bornee : une duree negative, enorme ou invalide ne peut pas
    bloquer le demarrage du toolkit.
    """
    apparence= apparence or {}
    brut = apparence.get("duree_intro")
    if brut is None:
        brut = (INTRO_DUREE_DEFAUT if apparence.get("introduction_longue", True)
                else INTRO_DUREE_COURTE)
    try:
        valeur=float(brut)
    except (TypeError, ValueError):
        valeur = INTRO_DUREE_DEFAUT
    if valeur != valeur:
        valeur =INTRO_DUREE_DEFAUT
    return max(0.0, min(INTRO_DUREE_MAX, valeur))


def animations_actives():
    """Etat courant des animations lu dans ``core.common``.

    ``configurer_affichage()`` met a jour la variable du module ``core.common``
    apres le chargement de la configuration : relire cette variable evite de
    garder une copie obsolète faite a l'import de ``main``.
    """
    import core.common as common_ui
    return bool(getattr(common_ui, "ANIMATIONS", False))


def _outils_du_catalogue():
    return [fn for _cat, _couleur, outils in CATALOGUE for _nom, _desc, fn in outils]


def verifications_intro(config):
    """Verifications reellement effectuees avant l'affichage du demarrage.

    Chaque entree porte son resultat : aucun etat positif n'est affiche sans
    controle correspondant, et une valeur indisponible est dite telle.
    """
    from core.startup_checks import verifier_catalogue, verifier_modules
    from core.theme import nommer_theme

    app = (config or {}).get('apparence', {}) or {}
    outils = _outils_du_catalogue()
    noms=[nom for _cat, _couleur, groupes in CATALOGUE for nom, _desc, _fn in groupes]
    catalogue = verifier_catalogue(outils, noms, CATALOGUE, _ROUTE_PAR_NOM)
    resultats = [{"nom": "Catalogue", "ok": catalogue.ok,
                  "detail":catalogue.detail}]

    try:
        environnement = libelle_environnement(detecter_environnement()["cle"])
        env_ok = bool(environnement)
    except Exception:
        environnement, env_ok = "indisponible", False
    resultats.append({'nom': 'Environnement', 'ok': env_ok, 'detail':environnement})

    version = platform.python_version()
    resultats.append({'nom': 'Python', 'ok': sys.version_info>= (3, 9),
                      "detail": version})

    try:
        theme = nommer_theme(app.get("theme_actif", "original"))
        theme_ok= bool(theme)
    except Exception:
        theme, theme_ok= "indisponible", False
    resultats.append({"nom": "Theme", "ok": theme_ok, "detail": theme})

    modules= verifier_modules(outils)
    resultats.append({"nom":"Modules", "ok": modules.ok,
                      'detail': modules.detail})
    return resultats


def etapes_intro(config):
    """Lignes (nom, detail) issues des verifications reelles du demarrage."""
    return [(verification['nom'], verification['detail'])
            for verification in verifications_intro(config)]


def resume_banniere(config):
    """Ligne d'information du pied de banniere, tronquee si l'ecran est etroit."""
    etapes= dict(etapes_intro(config))
    texte = (f"v2.0  |  {etapes['Catalogue']}  |  {etapes['Environnement']}"
             f"  |  theme {etapes['Theme']}")
    limite = max(20, (console.width or 80) - 4)
    return texte if len(texte) <=limite else texte[:limite - 3].rstrip() + "..."


def afficher_banniere(config):
    """Affiche la banniere de secours (logo final + informations reelles)."""
    palette = obtenir_theme()
    console.print(en_tete(
        largeur=largeur_utile(), palette=palette, info=resume_banniere(config),
        compact=est_ecran_etroit() or MODE_TEXTE or not UNICODE,
        unicode=UNICODE, t=time.time()))
    console.print()


def _info_menu():
    """Resume court et bon marche pour l'en-tete des menus."""
    outils = sum(len(outils) for _cat, _couleur, outils in CATALOGUE)
    return (f"v2.0  |  {outils} outils  |  {len(CATALOGUE)} categories"
            f"  |  {platform.system()}")


def _afficher_entete_menu():
    """En-tete LEAKFR commun au menu numerique (meme logo que l'intro).

    Le grand logo est utilise si la place le permet ; sinon un bandeau
    toujours rempli affiche le resume et le commit reel du depot.
    """
    palette = obtenir_theme()
    largeur= min(largeur_utile(), 100)
    hauteur =console.height or 30
    if est_ecran_etroit() or MODE_TEXTE or not UNICODE:
        hauteur = min(hauteur, 24)
    try:
        console.print(_entete_menu(largeur, hauteur, 0.0))
        console.print()
    except Exception:
        console.print(Text('LEAKFR // TOOLS 2.0', style='bold'))


def _animer_intro(config, duree):
    """Sequence animee complete (phases A a D) pilotee par de vrais controles.

    Retourne ``True`` quand l'ecran final a ete affiche ; ``False`` demande a
    l'appelant de retomber sur la banniere statique.
    """
    from core.startup import executer_sequence
    return bool(executer_sequence(config, duree))


def _intro_ascii(config):
    """Affiche l'introduction animee ou une version compacte/statique."""
    app = (config or {}).get('apparence', {}) or {}
    if "--no-intro" in sys.argv or not app.get("banniere_demarrage", True):
        return

    palette = obtenir_theme()
    clear_screen()
    if (est_ecran_etroit() or '--text' in sys.argv
            or "--no-color" in sys.argv):
        console.print(Align.center(Text(
            'LeakFr-Tools 2.0',
            style=f"bold {palette.get('principale', C_OSINT)}")))
        console.print(Align.center(Text(BANNER_TAGLINE, style="dim")))
        console.print(Align.center(Text(
            "LEAKFR // TOOLS 2.0",
            style=f"dim {palette.get('secondaire', C_RECON)}")))
        console.print()
        return

    duree = duree_intro(app)
    interactif =bool(getattr(sys.stdout, "isatty", lambda:False)())
    anime=False
    if animations_actives() and UNICODE and duree > 0 and interactif:
        try:
            anime= _animer_intro(config, duree)
        except KeyboardInterrupt:
            console.print()
            raise QuitterApplication
        except Exception:
            anime=False
    if not anime:
        afficher_banniere(config)




def _selectionner_dossier(titre_menu):
    dossiers = lister_cases()
    if not dossiers:
        warn("Aucun dossier d'investigation. Créez-en un depuis le menu Dossiers.")
        return None
    choix=selectionner_option(titre_menu, [f"#{case['id']} · {case['title']}" for case in dossiers] + ["Retour"])
    if not choix or choix== "Retour":
        return None
    return next(case for case in dossiers if choix.startswith(f"#{case['id']} · "))


def _gestion_dossiers():
    """Interface locale de gestion des dossiers, notes, sources et exports."""
    while True:
        clear_screen()
        titre("DOSSIERS & RAPPORTS", C_GOLD)
        choix = selectionner_option('DOSSIERS & RAPPORTS', [
            "Lister les dossiers", "Créer un dossier", "Ajouter une note",
            "Ajouter une source", "Preuves (chaines d'integrite)",
            'Correler les observations', 'Exporter un dossier JSON',
            "Retour au menu principal",
        ])
        if choix is None or choix == 'Retour au menu principal':
            return
        if choix == "Preuves (chaines d'integrite)":
            case = _selectionner_dossier('PREUVES')
            if case is not None:
                _gestion_preuves(case)
            continue
        if choix =="Correler les observations":
            case =_selectionner_dossier("CORRELATION")
            if case is not None:
                _correler_dossier(case)
            continue
        if choix == 'Créer un dossier':
            nom =Prompt.ask("Nom du dossier").strip()
            if not nom:
                warn('Le nom du dossier ne peut pas être vide.')
                continue
            description=Prompt.ask("Description (facultative)", default="").strip()
            case_id= creer_case(nom, description)
            ok(f"Dossier #{case_id} créé localement.")
            pause()
        elif choix =='Lister les dossiers':
            dossiers = lister_cases()
            if dossiers:
                tableau = Table(box=BX, border_style=ui.BORDURE, header_style='bold white')
                tableau.add_column("ID")
                tableau.add_column("Dossier")
                tableau.add_column('Mis à jour')
                for case in dossiers:
                    tableau.add_row(str(case["id"]), case["title"], case["updated_at"])
                console.print(tableau)
            else:
                warn("Aucun dossier enregistré.")
            pause()
        elif choix in {"Ajouter une note", "Ajouter une source", "Exporter un dossier JSON"}:
            case= _selectionner_dossier(choix.upper())
            if case is None:
                continue
            if choix == "Ajouter une note":
                kind= selectionner_option('TYPE DE NOTE', ['observation', 'hypothese', 'conclusion', 'note_libre'])
                if not kind:
                    continue
                contenu= Prompt.ask('Contenu de la note').strip()
                if contenu:
                    ajouter_note(case["id"], kind, contenu)
                    ok('Note ajoutée au dossier.')
                else:
                    warn("Note vide : aucune modification effectuée.")
                pause()
            elif choix =="Ajouter une source":
                valeur =Prompt.ask("Valeur / URL de la source").strip()
                if valeur:
                    type_source = Prompt.ask("Type de donnée", default="observation").strip()
                    outil = Prompt.ask("Outil d'origine (facultatif)", default="").strip()
                    ajouter_source(case['id'], data_type=type_source, value=valeur, tool_name=outil)
                    ok("Source ajoutée au dossier.")
                else:
                    warn('Source vide : aucune modification effectuée.')
                pause()
            else:
                donnee = exporter_case_json(case['id'])
                dossier =Path(EXPORTS_DIR)
                dossier.mkdir(parents=True, exist_ok=True)
                chemin = dossier / f"dossier-{case["id"]}.json"
                chemin.write_text(json.dumps(donnee, ensure_ascii=False, indent=2),
                                  encoding="utf-8")
                ok(f"Export JSON créé : {chemin}")
                pause()


def _gestion_preuves(case):
    """Registre de preuves chaine, verifications et exports."""
    while True:
        clear_screen()
        titre(f"PREUVES — #{case['id']} {case['title']}", C_GOLD)
        choix =selectionner_option('PREUVES', [
            "Ajouter un fichier", "Lister et verifier", "Verifier la chaine",
            "Historique des verifications", "Exporter JSON", "Exporter Markdown", "Retour",
        ])
        if choix is None or choix == "Retour":
            return
        if choix == 'Ajouter un fichier':
            chemin=Prompt.ask("Chemin du fichier local").strip()
            if not chemin:
                warn('Chemin vide.')
                pause()
                continue
            source= Prompt.ask('Source declaree (facultative)', default='').strip()
            note =Prompt.ask("Note (facultative)", default="").strip()
            try:
                preuve_id = ajouter_preuve(case['id'], chemin, source, note)
            except (ValueError, OSError) as exc:
                warn(str(exc))
            else:
                ok(f"Preuve #{preuve_id} enregistree (empreinte SHA-256).")
            pause()
        elif choix == 'Lister et verifier':
            preuves =lister_preuves(case["id"])
            if not preuves:
                warn('Aucune preuve enregistree.')
                pause()
                continue
            tableau = Table(box=BX, border_style=ui.BORDURE, header_style='bold white')
            tableau.add_column("#")
            tableau.add_column("Fichier")
            tableau.add_column('SHA-256')
            tableau.add_column("Etat")
            for preuve in preuves:
                etat =verifier_preuve(preuve['id'])
                tableau.add_row(str(preuve["id"]), preuve["path"], preuve["sha256"][:16] + "...",
                                "intact" if etat["intact"] else etat["motif"])
            console.print(tableau)
            pause()
        elif choix =="Verifier la chaine":
            resultat= verifier_chaine(case['id'])
            if resultat["valide"]:
                ok(f"Chaine coherente sur {resultat['entrees']} entree(s).")
            else:
                for anomalie in resultat["anomalies"]:
                    warn(f"Entree {anomalie['id']} : {anomalie['motif']}")
            console.print('[dim]Registre local : il detecte une alteration isolee, pas une '
                          "reecriture complete avec recalcul des empreintes.[/]")
            pause()
        elif choix == 'Historique des verifications':
            controles = lister_verifications(case_id=case["id"])
            if not controles:
                warn('Aucun controle enregistre.')
            else:
                tableau = Table(box=BX, border_style=ui.BORDURE, header_style="bold white")
                tableau.add_column('Preuve')
                tableau.add_column("Controle (UTC)")
                tableau.add_column("Etat")
                tableau.add_column('Detail')
                for controle in controles[:50]:
                    tableau.add_row(str(controle["evidence_id"]), controle["checked_at"],
                                    'intact' if controle['intact'] else 'modifie',
                                    controle["motif"])
                console.print(tableau)
            pause()
        elif choix in {"Exporter JSON", "Exporter Markdown"}:
            dossier = Path(EXPORTS_DIR)
            dossier.mkdir(parents=True, exist_ok=True)
            horodatage =time.strftime("%Y%m%d-%H%M%S")
            if choix =="Exporter JSON":
                contenu = json.dumps(exporter_preuves_json(case['id']), ensure_ascii=False, indent=2)
                chemin = dossier / f"preuves-{case['id']}-{horodatage}.json"
            else:
                contenu= exporter_preuves_markdown(case['id'])
                chemin = dossier / f"preuves-{case['id']}-{horodatage}.md"
            chemin.write_text(contenu + ("" if contenu.endswith("\n") else "\n"),
                              encoding='utf-8')
            ok(f"Export ecrit : {chemin}")
            pause()


def _correler_dossier(case):
    """Correlation des valeurs techniques presentes dans les sources et notes."""
    clear_screen()
    titre(f"CORRELATION — #{case['id']} {case['title']}", C_GOLD)
    try:
        resultat=correler_case(case["id"])
    except ValueError as exc:
        warn(str(exc))
        pause()
        return
    exactes=resultat['correspondances_exactes']
    if exactes:
        tableau = Table(box=BX, border_style=ui.BORDURE, header_style="bold white")
        tableau.add_column('Type')
        tableau.add_column("Valeur")
        tableau.add_column("Origines")
        for entite in exactes[:30]:
            origines =", ".join(f"{p['origine']} #{p['id']}" for p in entite["provenances"])
            tableau.add_row(entite["type"], entite["valeur"], origines)
        console.print(tableau)
    else:
        warn("Aucune valeur partagee entre plusieurs origines.")
    if resultat['rapprochements']:
        console.print("[bold]Rapprochements moins certains :[/]")
        for proche in resultat["rapprochements"][:15]:
            console.print(f"  - {proche["a"]} ~ {proche["b"]} ({proche["indice"]})")
    console.print(f"[dim]{resultat['avertissement']}[/]")
    if Confirm.ask("Exporter la correlation ?", default=False):
        dossier = Path(EXPORTS_DIR)
        dossier.mkdir(parents=True, exist_ok=True)
        horodatage = time.strftime("%Y%m%d-%H%M%S")
        chemin =dossier / f"correlation-{case["id"]}-{horodatage}.json"
        chemin.write_text(exporter_correlation_json(resultat), encoding="utf-8")
        ok(f"Export JSON ecrit : {chemin}")
    pause()


def _ouvrir_preuves():
    """Raccourci de recherche vers le registre de preuves d'un dossier."""
    case = _selectionner_dossier("PREUVES — CHOISIR UN DOSSIER")
    if case is None:
        return
    _gestion_preuves(case)


def _ouvrir_correlation():
    """Raccourci de recherche vers la correlation d'un dossier."""
    case= _selectionner_dossier("CORRELATION — CHOISIR UN DOSSIER")
    if case is None:
        return
    _correler_dossier(case)


def _afficher_historique():
    historique = charger_historique(50)
    titre('HISTORIQUE LOCAL', C_GOLD)
    if not historique:
        warn("Aucune activité enregistrée.")
    else:
        tableau= Table(box=BX, border_style=ui.BORDURE, header_style="bold white")
        tableau.add_column("Date (UTC)")
        tableau.add_column('Action')
        tableau.add_column("Détails")
        for entree in reversed(historique):
            details = json.dumps(entree.get('details', {}), ensure_ascii=False)
            tableau.add_row(entree.get("timestamp", ""), entree.get("action", ""), details)
        console.print(tableau)
    pause()


_SEARCH_ACTIONS =[
    {"num": "cases", "nom": "Gestion des dossiers", "desc": "Créer des dossiers, ajouter des notes/sources et exporter en JSON",
     "fn": _gestion_dossiers, "chemin_navigation": "DOSSIERS & RAPPORTS > Investigations"},
    {'num': 'history', 'nom': 'Historique local', 'desc': 'Consulter les dernières opérations enregistrées localement',
     "fn": _afficher_historique, "chemin_navigation": "DOSSIERS & RAPPORTS > Investigations"},
    {"num": "evidence", "nom": "Evidence Chain Ledger",
     'desc': 'Enregistrer un fichier local, calculer son SHA-256 et vérifier le registre chaîné',
     "fn": _ouvrir_preuves, "chemin_navigation": "DOSSIERS & RAPPORTS > Preuves"},
    {"num": "correlation", "nom": "Finding Correlator",
     'desc': "Rapprocher les domaines, URL, IP, e-mails et pseudos des sources d'un dossier",
     "fn": _ouvrir_correlation, "chemin_navigation":"DOSSIERS & RAPPORTS > Corrélation"},
]
ACTIONS.update({outil['num']:outil['fn'] for outil in _SEARCH_ACTIONS})

def rechercher_outils(terme, limite=20):
    """Recherche dans le catalogue et les actions transverses de l'interface."""
    return _moteur_recherche(terme, limite, _SEARCH_ACTIONS)


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
    table = Table(box=BX, border_style=ui.BORDURE, header_style="bold white")
    table.add_column('Outil')
    table.add_column("Catégorie")
    table.add_column("Description")
    for outil in resultats:
        table.add_row(outil["nom"], outil.get("chemin_navigation", ""), outil["desc"])
    console.print(table)
    libelles = {_libelle_resultat(outil): outil for outil in resultats}
    selection = selectionner_option("RESULTATS DE RECHERCHE", list(libelles))
    return libelles[selection]["num"] if selection else None


def _tronquer_menu(texte, largeur):
    """Tronque proprement une ligne de menu (jamais de retour a la ligne)."""
    texte = " ".join(str(texte or "").split())
    largeur= int(largeur)
    if largeur <= 0:
        return ""
    if len(texte) <=largeur:
        return texte
    return texte[:max(1, largeur - 1)].rstrip() + "\u2026"


def _couleurs_categories(palette):
    """Sept couleurs du theme, une par categorie, dans l'ordre du catalogue."""
    return [
        palette.get("principale", C_OSINT),
        palette.get("secondaire", C_RECON),
        palette.get('erreurs', C_CYBER),
        palette.get("avertissements", C_PENTEST),
        palette.get("secondaire", C_DISCORD),
        palette.get('succes', C_UTIL),
        palette.get("principale", C_ASTRO),
    ]


def _hauteur_entete(largeur, hauteur):
    """L'en-tete sobre tient sur deux lignes (marque + filet)."""
    return 2


def _entete_menu(largeur, hauteur, t=0.0):
    """Bandeau d'ecran : marque a gauche, contexte reel a droite, filet."""
    largeur = max(24, min(int(largeur) - 2, 150))
    outils= sum(len(opts) for _cat, _c, opts in CATALOGUE)
    tagline="SUITE D'INVESTIGATION" if largeur >= 72 else ""
    if largeur >= 96:
        details, contexte =_info_menu(), ligne_commit()
    elif largeur >= 60:
        info = info_commit()
        details = f"v2.0 | {outils} outils | {len(CATALOGUE)} modules"
        contexte = f"commit {info['court']}" if info.get("disponible") else ""
    else:
        details, contexte = f"v2.0 | {outils} outils", ""
    return Group(*ui.en_tete(largeur, "LEAKFR", tagline, details, contexte,
                             unicode=UNICODE))


def _vue_entrees(entrees, curseur, places):
    """Fenetre d'outils autour de la selection, categories toujours visibles."""
    places = max(1, int(places))
    if len(entrees) <= places:
        return list(entrees)
    centre = 0 if curseur is None else max(0, min(len(entrees) - 1, curseur))
    if places < 5:
        debut = max(0, min(len(entrees) - places, centre - places // 2))
        return list(entrees[debut:debut + places])
    corps =places - 2
    debut= max(0, min(len(entrees) - corps, centre - corps // 2))
    vue =([None] if debut > 0 else []) + list(entrees[debut:debut + corps])
    if debut + corps < len(entrees):
        vue.append(None)
    return vue


def construire_menu(sel, buf, t, msg="", tout=False):
    """Ecran principal : catalogue a gauche, details a droite, barre d'etat."""
    ui_cfg = obtenir_config_ui()
    palette = obtenir_theme()
    haut = console.height or 30
    largeur_ecran = console.width or 80
    accent = palette.get("principale", C_OSINT)
    gris= palette.get('texte_secondaire', '#888888')
    couleurs = _couleurs_categories(palette)

    parts = [_entete_menu(largeur_ecran, haut, t), Text('')]

    cat_sel = FLAT[sel]["cat"] if 0 <= sel < len(FLAT) else None
    item_sel =FLAT[sel] if 0<= sel < len(FLAT) else None

    style_ui = ui_cfg.get("style_interface", "dashboard")
    largeur_mode = ui_cfg.get('largeur_menu', 'auto')
    w_console= int(largeur_ecran)
    if largeur_mode== "large":
        w_console = max(w_console, 130)
    elif largeur_mode== "etroit":
        w_console= min(w_console, 78)
    w_console= max(20, min(w_console, largeur_ecran))
    largeur_totale =min(w_console - 2, 132)
    afficher_side =bool(style_ui == "dashboard"
                         and ui_cfg.get('afficher_panneau_lateral', True)
                         and largeur_totale >= 88 and not tout)
    if afficher_side:
        w_main= int(largeur_totale * 0.62)
        w_side = largeur_totale - w_main - 2
        if w_side < 30:
            w_side =30
            w_main= largeur_totale - 32
    else:
        w_main = min(largeur_totale, 96)
        w_side =0
    interne = max(10, w_main - 4)
    h_entete, h_pied =2, 2
    max_contenu =max(4, int(haut) - h_entete - 1 - h_pied - 2)
    places_items = max(1, max_contenu - (1 + len(CATALOGUE) + 1))
    largeur_nom = max(10, min(30, interne // 2 - 2))
    total_outils =sum(len(opts) for _cat, _c, opts in CATALOGUE)
    fleche = "\u25be" if UNICODE else "v"
    ferme= '\u25b8' if UNICODE else '>'
    branche = "\u251c" if UNICODE else "|-"
    coin ="\u2514" if UNICODE else "\\-"
    marker = '\u258c' if UNICODE else '|'
    pointeur = "\u276f" if UNICODE else ">"

    def _cat_ligne(nom, couleur, ouvert, compteur, actif):
        texte = Text(no_wrap=True, overflow="ellipsis")
        texte.append(f" {marker} " if actif else "   ", style=f"bold {couleur}")
        texte.append(f"{fleche if ouvert else ferme} ", style=f"bold {couleur}")
        texte.append(nom, style="bold white")
        reste = interne - texte.cell_len - len(compteur) - 1
        if reste > 0:
            texte.append(" " * reste)
        texte.append(compteur, style=ui.SECONDAIRE)
        return texte

    def _item(nom, desc, actif, dernier=False, couleur=None):
        couleur = couleur or accent
        texte= Text(no_wrap=True, overflow="ellipsis")
        if actif:
            fond = f"on {ui.FOND_SELECTION}"
            texte.append(f" {marker} ", style=f"bold {couleur} {fond}")
            texte.append(f"{pointeur} ", style=f"bold {couleur} {fond}")
            texte.append(f"{ui.tronquer(nom, largeur_nom):<{largeur_nom}}",
                         style=f"bold white {fond}")
            reste = max(4, interne - texte.cell_len - 2)
            texte.append('  ' + ui.tronquer(desc, reste),
                         style=f"{ui.SECONDAIRE} {fond}")
            texte.append(" " * max(0, interne - texte.cell_len), style=fond)
        else:
            texte.append(f"   {coin if dernier else branche} ", style=ui.BORDURE)
            texte.append(f"{ui.tronquer(nom, largeur_nom):<{largeur_nom}}",
                         style='white')
            reste = max(4, interne - texte.cell_len - 2)
            texte.append("  " + ui.tronquer(desc, reste), style=ui.SECONDAIRE)
        return texte

    arbre = [Text(" SUITE DE SECURITE & RECON", style=ui.SECONDAIRE,
                  no_wrap=True, overflow='ellipsis')]
    for ci, (cat, defaut, opts) in enumerate(CATALOGUE):
        couleur= couleurs[ci] if ci < len(couleurs) else defaut
        ouvert = tout or ci ==cat_sel
        arbre.append(_cat_ligne(cat, couleur, ouvert, str(len(opts)),
                                ci == cat_sel))
        if not ouvert:
            continue
        entrees =[e for e in FLAT if e["cat"]==ci]
        curseur = next((i for i, e in enumerate(entrees) if e is item_sel), None)
        vue = _vue_entrees(entrees, curseur, places_items)
        for index, entree in enumerate(vue):
            if entree is None:
                arbre.append(Text("    \u22ee", style=ui.FAIBLE, no_wrap=True))
                continue
            arbre.append(_item(entree['nom'], entree['desc'],
                               entree is item_sel, index == len(vue) - 1))
    arbre.append(_item("Quitter la suite", "Fermer LeakFr-Tools",
                       sel== NUM_IDX['0'], True,
                       couleur=palette.get("erreurs", C_CYBER)))

    if afficher_side:
        nom_cat= (CATALOGUE[cat_sel][0] if cat_sel is not None
                   and cat_sel < len(CATALOGUE) else "General")
        col_cat =(couleurs[cat_sel] if cat_sel is not None
                   and cat_sel < len(couleurs) else accent)
        isi = max(12, w_side - 4)
        side =[]
        if item_sel and item_sel["num"] != "0":
            side.append(ui.paire("Nom", item_sel["nom"], isi, "bold white"))
            side.append(ui.paire('Categorie', nom_cat, isi, f"bold {col_cat}"))
            side.append(ui.paire("Role", item_sel["desc"], isi, gris))
        elif item_sel:
            side.append(ui.paire('Nom', 'Quitter la suite', isi, 'bold white'))
            side.append(ui.paire("Role", "Fermer la console", isi, gris))
        else:
            side.append(ui.paire('Nom', 'Survolez un outil', isi, gris))
        side.append(Text(""))
        side.append(Text("SYSTEME", style=ui.FAIBLE, no_wrap=True))
        side.append(ui.paire('OS', platform.system(), isi))
        side.append(ui.paire("Outils", str(total_outils), isi))
        side.append(ui.paire("Modules", str(len(CATALOGUE)), isi))
        side.append(ui.paire('Terminal', f"{largeur_ecran}x{haut}", isi))
        side.append(Text(""))
        side.append(Text("SESSION", style=ui.FAIBLE, no_wrap=True))
        side.append(ui.paire('Version', '2.0', isi))
        side.append(ui.paire("Depot", ligne_commit(), isi, gris))
        hauteur_panneau = max_contenu
        arbre_panneau= list(arbre[:hauteur_panneau])
        arbre_panneau += [Text("")] * (hauteur_panneau - len(arbre_panneau))
        side = list(side[:hauteur_panneau])
        side += [Text('')] * (hauteur_panneau - len(side))
        panneau_catalogue= ui.panneau(
            arbre_panneau, w_main, titre="CATALOGUE",
            pied=f"{total_outils} OUTILS", unicode=UNICODE)
        panneau_details= ui.panneau(
            side, w_side, titre="DETAILS", pied="LOCAL", unicode=UNICODE)
        parts.append(Align.center(ui.grille(panneau_catalogue,
                                            panneau_details)))
    else:
        parts.append(Align.center(ui.panneau(
            arbre, w_main, titre="CATALOGUE",
            pied=f"{total_outils} OUTILS", unicode=UNICODE)))

    parts.append(Align.center(ui.regle(largeur_totale, ui.BORDURE, UNICODE)))
    raccourcis =[("\u2191\u2193" if UNICODE else "^v", "Naviguer"),
                  ('\u23ce' if UNICODE else 'Entree', 'Ouvrir'),
                  ("s", "Parametres"), ("/", "Recherche"), ("d", "Dossiers"),
                  ("h", "Historique"), ("q", "Quitter")]
    parts.append(Align.center(ui.barre_etat(raccourcis, largeur_totale, msg,
                                            UNICODE)))
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
            self.fd =sys.stdin.fileno()
            self.old = termios.tcgetattr(self.fd)
            tty.setcbreak(self.fd)
        return self

    def __exit__(self, *a):
        if os.name!= 'nt':
            import termios
            termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old)

    @staticmethod
    def _norm(c):
        if c in ('\r', '\n'):
            return "ENTER"
        if c =="\x1b":
            return 'ESC'
        if c in ("\x08", "\x7f"):
            return "BACK"
        if c =='\x03':
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
        r, _, _ =select.select([self.fd], [], [], timeout)
        if not r:
            return None
        c = os.read(self.fd, 1).decode(errors='ignore')
        if c== "\x1b":
            r2, _, _ = select.select([self.fd], [], [], 0.02)
            if r2:
                seq = os.read(self.fd, 2).decode(errors="ignore")
                return {"[A": "UP", "[B": "DOWN", "[C": "RIGHT", "[D": "LEFT",
                        'OA': 'UP', 'OB': 'DOWN'}.get(seq, '')
            return "ESC"
        return self._norm(c)

def menu_interactif():
    """Menu a fleches, redessine uniquement quand une touche est lue.

    Aucune animation : l'ecran ne se rafraichit pas tout seul, ce qui garde
    le processeur au repos et l'affichage parfaitement stable.
    """
    global SEL
    buf =""
    msg = ''
    n=len(FLAT)

    def _sous_ecran(T, live, fonction):
        """Suspend le menu, execute un ecran, puis redessine le menu."""
        T.__exit__(None, None, None)
        live.stop()
        try:
            return fonction()
        finally:
            clear_screen()
            T.__enter__()
            live.start()
            live.update(construire_menu(SEL, buf, 0.0, msg), refresh=True)

    with Touches() as T, Live(console=console, screen=True, auto_refresh=False) as live:
        live.update(construire_menu(SEL, buf, 0.0, msg), refresh=True)
        while True:
            k = T.lire(0.05)
            if not k:
                continue
            msg= ''
            if k== "UP":
                SEL =(SEL - 1) % n
                buf = ''
            elif k == "DOWN":
                SEL = (SEL + 1) % n
                buf =''
            elif k == "ENTER":
                return FLAT[SEL]["num"]
            elif k == 'ESC':
                buf =""
            elif k in ("s", "S"):
                _sous_ecran(T, live, _ecran_parametres)
                buf = ""
            elif k in ("/", "r", "R"):
                result =_sous_ecran(T, live, recherche_globale)
                if result:
                    return result
                buf =''
            elif k in ("d", "D"):
                _sous_ecran(T, live, _gestion_dossiers)
                buf = ''
            elif k in ("h", "H"):
                _sous_ecran(T, live, _afficher_historique)
                buf= ''
            elif k in ("q", "Q", "QUIT"):
                return "0"
            live.update(construire_menu(SEL, buf, 0.0, msg), refresh=True)

def menu_simple():
    """Fallback console conservant le parcours d'origine : catégorie puis outil."""
    categories =[nom for nom, _, _ in CATALOGUE]
    while True:
        _afficher_entete_menu()
        choix_categorie =selectionner_option(
            "MENU PRINCIPAL", categories + ["Recherche globale", "Dossiers & rapports",
                                             'Historique local', 'Parametres', 'Quitter']
        )
        if choix_categorie is None or choix_categorie== "Quitter":
            return '0'
        if choix_categorie == "Parametres":
            _ecran_parametres()
            continue
        if choix_categorie == "Recherche globale":
            result = recherche_globale()
            if result:
                return result
            continue
        if choix_categorie == 'Dossiers & rapports':
            _gestion_dossiers()
            continue
        if choix_categorie== 'Historique local':
            _afficher_historique()
            continue
        options =[nom for nom, _, _ in CATALOGUE[categories.index(choix_categorie)][2]]
        choix_outil = selectionner_option(choix_categorie, options + ["Retour"])
        if choix_outil is None or choix_outil == "Retour":
            continue
        for entree in FLAT:
            if entree["nom"] == choix_outil:
                return entree['num']
        bad("Outil introuvable dans le catalogue.")

def _initialiser_environnement(force=None):
    """Sélectionne l'environnement d'affichage et le persiste localement.

    Le choix ne modifie que les préférences d'interface : aucune variable
    système, aucun binaire et aucun système d'exploitation ne sont changés.
    """
    global _CONFIG
    detecte =detecter_environnement()
    if force:
        cle = normaliser_cle(force)
        console.print(f"Environnement d'affichage forcé : {libelle_environnement(cle)}")
    else:
        cle = select_environment(_CONFIG, detecte=detecte)
    plateforme = _CONFIG.setdefault("plateforme", {})
    plateforme["environnement"] = normaliser_cle(cle)
    plateforme['selectionne_le'] = resume_environnement(cle)['detecte_le']
    sauvegarder(_CONFIG)
    _appliquer_configuration_visuelle()
    return cle


def main():
    global _CONFIG
    parser = argparse.ArgumentParser(
        description='LeakFr-Tools : boîte à outils OSINT, réseau et cybersécurité.',
        epilog="Utilise les tests actifs uniquement sur des systèmes autorisés.",
    )
    parser.add_argument('--simple', action='store_true',
                        help="force les menus numériques (sans navigation aux flèches)")
    parser.add_argument("--dashboard", action="store_true",
                        help='menu a fleches (comportement par defaut ; conserve '
                             "pour compatibilite)")
    parser.add_argument("--ascii", action="store_true", help="privilégie un affichage compatible ASCII")
    parser.add_argument('--text', '--no-color', dest='text', action='store_true',
                        help="mode texte simple, sans couleur ni animation")
    parser.add_argument("--no-intro", action="store_true",
                        help="saute l'introduction animee du demarrage")
    parser.add_argument("--bot", action="store_true",
                        help="demarre le bot Discord et le laisse en ligne "
                             '(token dans LEAKFR_DISCORD_BOT_TOKEN)')
    parser.add_argument("--bot-interval", type=float, default=None, metavar="SECONDES",
                        help="intervalle d'actualisation de l'etat du bot "
                             '(1 a 300 s, defaut 5)')
    parser.add_argument("--phone", action="store_true",
                        help="force le rendu mobile et la pagination réduite")
    parser.add_argument('--env', choices=[cle for cle, _ in ENVIRONNEMENTS],
                        help="force l'environnement d'affichage sans changer le système réel")
    parser.add_argument("--version", action="version", version="LeakFr-Tools 2.0")
    args = parser.parse_args()
    global INTERACTIF, UNICODE, BX, CONN_T, CONN_L, PIPE
    INTERACTIF = (not args.simple and sys.stdin.isatty() and sys.stdout.isatty())
    if args.ascii:
        UNICODE= False
        BX = box.ASCII
        CONN_T, CONN_L, PIPE =('|-- ', '`-- ', '|   ')
    _appliquer_configuration_visuelle()
    if args.bot:
        from modules.discord.bot_runner import (
            INTERVALLE_DEFAUT, demarrer_bot, normaliser_intervalle,
        )
        return demarrer_bot(intervalle=normaliser_intervalle(
            args.bot_interval if args.bot_interval is not None else INTERVALLE_DEFAUT))
    _initialiser_environnement(args.env)
    try:
        _intro_ascii(_CONFIG)
    except QuitterApplication:
        return 0
    while True:
        try:
            choix=menu_interactif() if INTERACTIF else menu_simple()
        except QuitterApplication:
            break
        except KeyboardInterrupt:
            break
        if choix == "0":
            break
        clear_screen()
        try:
            ACTIONS[choix]()
        except QuitterApplication:
            break
        except KeyboardInterrupt:
            warn("Interrompu.")
        except Exception as e:
            bad(f"Erreur inattendue : {e}")
        try:
            from core.common import pause
            pause()
        except (KeyboardInterrupt, EOFError):
            break
    clear_screen()
    console.print(Align.center(Text("A bientot !", style="bold white")))
    console.print(Align.center(ui.regle(min(largeur_utile(), 40), ui.BORDURE,
                                        UNICODE)))

if __name__ == "__main__":
    sys.exit(main() or 0)