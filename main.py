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
    # Aucune commande shell : l'API Windows suffit et reste sans effet ailleurs.
    try:
        import ctypes
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
    except (AttributeError, OSError):
        pass
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
    CONN_T, CONN_L, PIPE, ARROW, FULL, EMPTY, OKC, ANIMATIONS,
    BANNER, BANNER_SOUS_TITRE, BANNER_TAGLINE,
    C_OSINT, C_RECON, C_CYBER, C_PENTEST, C_UTIL, C_ASTRO, C_GOLD, C_DISCORD,
    initialiser_theme, obtenir_theme, obtenir_config_ui, titre, pause,
    clear_screen, configurer_affichage, ask_number, est_ecran_etroit, demander,
    QuitterApplication,
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
        titre("PARAMETRES", C_GOLD)

        t = Table(box=BX, border_style=C_GOLD, header_style=f"bold {C_GOLD}")
        t.add_column("Reglage", width=40)
        t.add_column("Valeur actuelle")

        app = _CONFIG.get("apparence", {})
        reseau = _CONFIG.get("reseau", {})

        styles = {"dashboard": "Dashboard split", "classique": "Classique", "compact": "Compact"}
        largeurs = {"auto": "Automatique", "large": "Large", "etroit": "Etroit"}
        plateforme = _CONFIG.setdefault("plateforme", {})
        reglages = [
            "Palette de couleurs", "Style d'interface", "Couleur d'accent",
            "Couleur du texte shell", "Fond shell", "Largeur du menu",
            "Panneau lateral", "Badges de categories", "Banniere de demarrage",
            "Duree de l'introduction", "Animations", "Timeout reseau",
            "Environnement (affichage)",
            "Mode texte de secours", "Largeur de sortie", "Pagination",
            "Compatibilite des outils", "Restaurer les parametres par defaut",
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
        _duree = duree_intro(app)
        t.add_row("Duree de l'introduction",
                  "Instantane (0 s)" if _duree <= 0 else f"{_duree:.1f} s")
        t.add_row("Animations", str(app.get("animations", True)))
        t.add_row("Timeout reseau (s)", str(reseau.get("timeout", 8)))
        env_configure = str(plateforme.get("environnement") or "auto")
        if env_configure == "auto":
            env_configure = f"Automatique ({libelle_environnement(detecter_environnement()['cle'])})"
        else:
            env_configure = libelle_environnement(env_configure)
        t.add_row("Environnement (affichage)", env_configure)
        t.add_row("Mode texte de secours", str(plateforme.get("mode_texte", False)))
        t.add_row("Largeur de sortie", largeurs.get(plateforme.get("largeur_sortie"), "Automatique"))
        t.add_row("Pagination", f"{plateforme.get('pagination', 15)} resultats")
        t.add_row("Compatibilite des outils", "Diagnostic local")
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
        elif c == "Duree de l'introduction":
            brut = demander("Duree de l'introduction (0 a 10 secondes, 0 = instantane)",
                            f"{duree_intro(app):.1f}")
            try:
                valeur = float(str(brut).replace(",", "."))
            except ValueError:
                bad("Valeur invalide (nombres entre 0 et 10).")
                continue
            app["duree_intro"] = max(0.0, min(INTRO_DUREE_MAX, valeur))
            sauvegarder(_CONFIG)
            ok(f"Introduction reglee sur {app['duree_intro']:.1f} s.")
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
        elif c == "Environnement (affichage)":
            cle = select_environment(_CONFIG)
            plateforme["environnement"] = normaliser_cle(cle)
            plateforme["selectionne_le"] = resume_environnement(cle)["detecte_le"]
            sauvegarder(_CONFIG)
            _appliquer_configuration_visuelle()
            ok(f"Affichage adapte a {libelle_environnement(cle)} (systeme reel inchange).")
        elif c == "Mode texte de secours":
            plateforme["mode_texte"] = not plateforme.get("mode_texte", False)
            sauvegarder(_CONFIG)
            _appliquer_configuration_visuelle()
            ok("Mode texte active." if plateforme["mode_texte"] else "Mode texte desactive.")
        elif c == "Largeur de sortie":
            choix = selectionner_option("LARGEUR DE SORTIE",
                                        ["Automatique", "Large", "Etroit"])
            if choix is None:
                continue
            plateforme["largeur_sortie"] = {
                "Automatique": "auto", "Large": "large", "Etroit": "etroit"
            }[choix]
            sauvegarder(_CONFIG)
            _appliquer_configuration_visuelle()
            ok("Largeur de sortie appliquee.")
        elif c == "Pagination":
            valeur = ask_number("Resultats par page", 5, 50,
                                defaut=plateforme.get("pagination", 15))
            if valeur is not None:
                plateforme["pagination"] = valeur
                sauvegarder(_CONFIG)
                _appliquer_configuration_visuelle()
                ok(f"Pagination : {valeur} resultats par page.")
        elif c == "Compatibilite des outils":
            afficher_compatibilite()
            pause()
            continue
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
                     "Personnaliser les couleurs du theme", "Environnement (affichage)",
                     "Mode texte de secours", "Largeur de sortie", "Pagination"}:
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
        clear_screen()
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
        clear_screen()
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


# ---------------------------------------------------------------------------
# Introduction & banniere de demarrage
# ---------------------------------------------------------------------------
INTRO_DUREE_DEFAUT = 3.2
INTRO_DUREE_COURTE = 1.2
INTRO_DUREE_MAX = 10.0


def duree_intro(apparence):
    """Duree de l'introduction en secondes (0 = banniere instantanee).

    La valeur est bornee : une duree negative, enorme ou invalide ne peut pas
    bloquer le demarrage du toolkit.
    """
    apparence = apparence or {}
    brut = apparence.get("duree_intro")
    if brut is None:
        brut = (INTRO_DUREE_DEFAUT if apparence.get("introduction_longue", True)
                else INTRO_DUREE_COURTE)
    try:
        valeur = float(brut)
    except (TypeError, ValueError):
        valeur = INTRO_DUREE_DEFAUT
    if valeur != valeur:  # NaN
        valeur = INTRO_DUREE_DEFAUT
    return max(0.0, min(INTRO_DUREE_MAX, valeur))


def etapes_intro(config):
    """Etapes reelles du demarrage (aucune valeur inventee, aucun secret)."""
    from core.theme import nommer_theme
    nb_outils = sum(len(outils) for _cat, _couleur, outils in CATALOGUE)
    try:
        environnement = libelle_environnement(detecter_environnement()["cle"])
    except Exception:
        environnement = "inconnu"
    app = (config or {}).get("apparence", {}) or {}
    return [
        ("Catalogue", f"{nb_outils} outils / {len(CATALOGUE)} categories"),
        ("Environnement", environnement),
        ("Python", platform.python_version()),
        ("Theme", nommer_theme(app.get("theme_actif", "original"))),
        ("Modules", "prets"),
    ]


def resume_banniere(config):
    """Ligne d'information du pied de banniere, tronquee si l'ecran est etroit."""
    etapes = dict(etapes_intro(config))
    texte = (f"v2.0  |  {etapes['Catalogue']}  |  {etapes['Environnement']}"
             f"  |  theme {etapes['Theme']}")
    limite = max(20, (console.width or 80) - 4)
    return texte if len(texte) <= limite else texte[:limite - 3].rstrip() + "..."


def afficher_banniere(config):
    """Affiche le logo complet (degrade arc-en-ciel) et ses informations."""
    palette = obtenir_theme()
    t = time.time()
    for y, ligne in enumerate(BANNER):
        console.print(Align.center(texte_arc(ligne, t, y * 4)))
    console.print()
    console.print(Align.center(Text(
        BANNER_SOUS_TITRE, style=f"bold {palette.get('titres', C_GOLD)}")))
    console.print(Align.center(Text(
        BANNER_TAGLINE, style=f"dim {palette.get('texte_secondaire', '#888888')}")))
    console.print(Align.center(Text(resume_banniere(config), style="dim")))
    console.print()


def _animer_intro(config, duree):
    """Animation de demarrage : etapes, jauge puis revelation du logo."""
    palette = obtenir_theme()
    etapes = etapes_intro(config)
    seuils = (0.10, 0.28, 0.46, 0.62, 0.78)[:len(etapes)]
    largeur_jauge = max(12, min(34, (console.width or 80) - 34))
    debut = time.monotonic()

    def rendu():
        ecoule = time.monotonic() - debut
        progression = 1.0 if duree <= 0 else min(1.0, ecoule / duree)
        lignes = [Align.center(Text("INITIALISATION DU TOOLKIT",
                                   style=f"bold {palette.get('principale', C_OSINT)}")),
                  Text("")]
        for seuil, (nom, detail) in zip(seuils, etapes):
            fait = progression >= seuil
            ligne = Text()
            ligne.append(f"{OKC} " if fait else "- ",
                         style="bold green" if fait else "dim")
            ligne.append(f"{nom:<14}", style="bold white" if fait else "dim")
            ligne.append(detail, style="dim" if fait else "grey37")
            lignes.append(Align.center(ligne))
        lignes.append(Text(""))
        remplies = int(round(largeur_jauge * progression))
        jauge = Text()
        jauge.append(FULL * remplies, style=f"bold {palette.get('secondaire', C_RECON)}")
        jauge.append(EMPTY * (largeur_jauge - remplies), style="grey30")
        jauge.append(f"  {int(progression * 100):3d}%", style="bold white")
        lignes.append(Align.center(jauge))
        lignes.append(Text(""))
        revelees = int(len(BANNER) * max(0.0, (progression - 0.55) / 0.4))
        for y in range(len(BANNER)):
            if y < revelees:
                lignes.append(Align.center(texte_arc(BANNER[y], time.time(), y * 4)))
            else:
                lignes.append(Text(""))
        return Group(*lignes)

    with Live(rendu(), console=console, refresh_per_second=15, transient=True) as live:
        fin = debut + duree
        while time.monotonic() < fin:
            live.update(rendu())
            time.sleep(0.05)


def _intro_ascii(config):
    """Affiche l'introduction ASCII au demarrage."""
    app = (config or {}).get("apparence", {}) or {}
    if "--no-intro" in sys.argv or not app.get("banniere_demarrage", True):
        return

    palette = obtenir_theme()
    clear_screen()
    if (est_ecran_etroit() or "--text" in sys.argv
            or "--no-color" in sys.argv):
        console.print(Align.center(Text(
            "LeakFr-Tools 2.0",
            style=f"bold {palette.get('principale', C_OSINT)}")))
        console.print(Align.center(Text(BANNER_TAGLINE, style="dim")))
        console.print()
        return

    duree = duree_intro(app)
    # Sans terminal interactif (redirection, pipe, CI) l'animation n'a pas de sens.
    interactif = bool(getattr(sys.stdout, "isatty", lambda: False)())
    if ANIMATIONS and UNICODE and duree > 0 and interactif:
        try:
            _animer_intro(config, duree)
        except Exception:
            # Une animation ne doit jamais empecher l'outil de demarrer.
            pass
    afficher_banniere(config)


# Catalogue, navigation et moteur de recherche : voir core/catalogue.py.


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
        clear_screen()
        titre("DOSSIERS & RAPPORTS", C_GOLD)
        choix = selectionner_option("DOSSIERS & RAPPORTS", [
            "Lister les dossiers", "Créer un dossier", "Ajouter une note",
            "Ajouter une source", "Preuves (chaines d'integrite)",
            "Correler les observations", "Exporter un dossier JSON",
            "Retour au menu principal",
        ])
        if choix is None or choix == "Retour au menu principal":
            return
        if choix == "Preuves (chaines d'integrite)":
            case = _selectionner_dossier("PREUVES")
            if case is not None:
                _gestion_preuves(case)
            continue
        if choix == "Correler les observations":
            case = _selectionner_dossier("CORRELATION")
            if case is not None:
                _correler_dossier(case)
            continue
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
                dossier = Path(EXPORTS_DIR)
                dossier.mkdir(parents=True, exist_ok=True)
                chemin = dossier / f"dossier-{case['id']}.json"
                chemin.write_text(json.dumps(donnee, ensure_ascii=False, indent=2),
                                  encoding="utf-8")
                ok(f"Export JSON créé : {chemin}")
                pause()


def _gestion_preuves(case):
    """Registre de preuves chaine, verifications et exports."""
    while True:
        clear_screen()
        titre(f"PREUVES — #{case['id']} {case['title']}", C_GOLD)
        choix = selectionner_option("PREUVES", [
            "Ajouter un fichier", "Lister et verifier", "Verifier la chaine",
            "Historique des verifications", "Exporter JSON", "Exporter Markdown", "Retour",
        ])
        if choix is None or choix == "Retour":
            return
        if choix == "Ajouter un fichier":
            chemin = Prompt.ask("Chemin du fichier local").strip()
            if not chemin:
                warn("Chemin vide.")
                pause()
                continue
            source = Prompt.ask("Source declaree (facultative)", default="").strip()
            note = Prompt.ask("Note (facultative)", default="").strip()
            try:
                preuve_id = ajouter_preuve(case["id"], chemin, source, note)
            except (ValueError, OSError) as exc:
                warn(str(exc))
            else:
                ok(f"Preuve #{preuve_id} enregistree (empreinte SHA-256).")
            pause()
        elif choix == "Lister et verifier":
            preuves = lister_preuves(case["id"])
            if not preuves:
                warn("Aucune preuve enregistree.")
                pause()
                continue
            tableau = Table(box=BX, border_style=C_GOLD, header_style=f"bold {C_GOLD}")
            tableau.add_column("#")
            tableau.add_column("Fichier")
            tableau.add_column("SHA-256")
            tableau.add_column("Etat")
            for preuve in preuves:
                etat = verifier_preuve(preuve["id"])
                tableau.add_row(str(preuve["id"]), preuve["path"], preuve["sha256"][:16] + "...",
                                "intact" if etat["intact"] else etat["motif"])
            console.print(tableau)
            pause()
        elif choix == "Verifier la chaine":
            resultat = verifier_chaine(case["id"])
            if resultat["valide"]:
                ok(f"Chaine coherente sur {resultat['entrees']} entree(s).")
            else:
                for anomalie in resultat["anomalies"]:
                    warn(f"Entree {anomalie['id']} : {anomalie['motif']}")
            console.print("[dim]Registre local : il detecte une alteration isolee, pas une "
                          "reecriture complete avec recalcul des empreintes.[/]")
            pause()
        elif choix == "Historique des verifications":
            controles = lister_verifications(case_id=case["id"])
            if not controles:
                warn("Aucun controle enregistre.")
            else:
                tableau = Table(box=BX, border_style=C_GOLD, header_style=f"bold {C_GOLD}")
                tableau.add_column("Preuve")
                tableau.add_column("Controle (UTC)")
                tableau.add_column("Etat")
                tableau.add_column("Detail")
                for controle in controles[:50]:
                    tableau.add_row(str(controle["evidence_id"]), controle["checked_at"],
                                    "intact" if controle["intact"] else "modifie",
                                    controle["motif"])
                console.print(tableau)
            pause()
        elif choix in {"Exporter JSON", "Exporter Markdown"}:
            dossier = Path(EXPORTS_DIR)
            dossier.mkdir(parents=True, exist_ok=True)
            horodatage = time.strftime("%Y%m%d-%H%M%S")
            if choix == "Exporter JSON":
                contenu = json.dumps(exporter_preuves_json(case["id"]), ensure_ascii=False, indent=2)
                chemin = dossier / f"preuves-{case['id']}-{horodatage}.json"
            else:
                contenu = exporter_preuves_markdown(case["id"])
                chemin = dossier / f"preuves-{case['id']}-{horodatage}.md"
            chemin.write_text(contenu + ("" if contenu.endswith("\n") else "\n"),
                              encoding="utf-8")
            ok(f"Export ecrit : {chemin}")
            pause()


def _correler_dossier(case):
    """Correlation des valeurs techniques presentes dans les sources et notes."""
    clear_screen()
    titre(f"CORRELATION — #{case['id']} {case['title']}", C_GOLD)
    try:
        resultat = correler_case(case["id"])
    except ValueError as exc:
        warn(str(exc))
        pause()
        return
    exactes = resultat["correspondances_exactes"]
    if exactes:
        tableau = Table(box=BX, border_style=C_GOLD, header_style=f"bold {C_GOLD}")
        tableau.add_column("Type")
        tableau.add_column("Valeur")
        tableau.add_column("Origines")
        for entite in exactes[:30]:
            origines = ", ".join(f"{p['origine']} #{p['id']}" for p in entite["provenances"])
            tableau.add_row(entite["type"], entite["valeur"], origines)
        console.print(tableau)
    else:
        warn("Aucune valeur partagee entre plusieurs origines.")
    if resultat["rapprochements"]:
        console.print("[bold]Rapprochements moins certains :[/]")
        for proche in resultat["rapprochements"][:15]:
            console.print(f"  - {proche['a']} ~ {proche['b']} ({proche['indice']})")
    console.print(f"[dim]{resultat['avertissement']}[/]")
    if Confirm.ask("Exporter la correlation ?", default=False):
        dossier = Path(EXPORTS_DIR)
        dossier.mkdir(parents=True, exist_ok=True)
        horodatage = time.strftime("%Y%m%d-%H%M%S")
        chemin = dossier / f"correlation-{case['id']}-{horodatage}.json"
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
    case = _selectionner_dossier("CORRELATION — CHOISIR UN DOSSIER")
    if case is None:
        return
    _correler_dossier(case)


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
    {"num": "evidence", "nom": "Evidence Chain Ledger",
     "desc": "Enregistrer un fichier local, calculer son SHA-256 et vérifier le registre chaîné",
     "fn": _ouvrir_preuves, "chemin_navigation": "DOSSIERS & RAPPORTS > Preuves"},
    {"num": "correlation", "nom": "Finding Correlator",
     "desc": "Rapprocher les domaines, URL, IP, e-mails et pseudos des sources d'un dossier",
     "fn": _ouvrir_correlation, "chemin_navigation": "DOSSIERS & RAPPORTS > Corrélation"},
]
ACTIONS.update({outil["num"]: outil["fn"] for outil in _SEARCH_ACTIONS})

# Mots-clés métier complémentaires aux noms/descriptions (recherche sans accents).
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
                l.append(f" {f['nom']} ", style=f"bold black on {arc(ln * 4, t, 0.35)}")
                l.append(f"  {f['desc']}", style="white")
            else:
                l.append(f"{f['nom']}", style="white")
                l.append(f"  {f['desc']}", style="grey50")
            arbre.append(l)

    ln += 1
    l = texte_arc(CONN_L, t, ln * 4)
    quit_idx = NUM_IDX["0"]
    if sel == quit_idx:
        l.append("  Quitter la suite ", style=f"bold black on {arc(ln * 4, t, 0.35)}")
    else:
        l.append(" Quitter", style="red")
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
    side_elements.append(Text.from_markup(f"[bold white]s[/]       : Parametres"))
    side_elements.append(Text.from_markup(f"[bold white]/[/]       : Recherche globale"))
    side_elements.append(Text.from_markup(f"[bold white]d[/]       : Dossiers & rapports"))
    side_elements.append(Text.from_markup(f"[bold white]h[/]       : Historique"))
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
        aide = Text("Fleches haut/bas : naviguer   Entree : executer   s : parametres   / : recherche   d : dossiers   q : quitter", justify="center")
        if msg:
            aide.append(f"   ! {msg}", style="bold red")
        parts.append(Align.center(Panel(aide, box=BX, border_style="grey42", width=min(w_console, 90))))

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
                return FLAT[SEL]["num"]
            elif k == "ESC":
                buf = ""
            elif k in ("s", "S"):
                T.__exit__(None, None, None)
                live.stop()
                try:
                    _ecran_parametres()
                finally:
                    clear_screen()
                    T.__enter__()
                    live.start()
                buf = ""
            elif k in ("/", "r", "R"):
                T.__exit__(None, None, None)
                live.stop()
                try:
                    result = recherche_globale()
                finally:
                    clear_screen()
                    T.__enter__()
                    live.start()
                if result:
                    return result
                buf = ""
            elif k in ("d", "D"):
                T.__exit__(None, None, None)
                live.stop()
                try:
                    _gestion_dossiers()
                finally:
                    clear_screen()
                    T.__enter__()
                    live.start()
                buf = ""
            elif k in ("h", "H"):
                T.__exit__(None, None, None)
                live.stop()
                try:
                    _afficher_historique()
                finally:
                    clear_screen()
                    T.__enter__()
                    live.start()
                buf = ""
            elif k in ("q", "Q", "QUIT"):
                return "0"

def menu_simple():
    """Fallback console conservant le parcours d'origine : catégorie puis outil."""
    categories = [nom for nom, _, _ in CATALOGUE]
    while True:
        choix_categorie = selectionner_option(
            "MENU PRINCIPAL", categories + ["Recherche globale", "Dossiers & rapports",
                                             "Historique local", "Parametres", "Quitter"]
        )
        if choix_categorie is None or choix_categorie == "Quitter":
            return "0"
        if choix_categorie == "Parametres":
            _ecran_parametres()
            continue
        if choix_categorie == "Recherche globale":
            result = recherche_globale()
            if result:
                return result
            continue
        if choix_categorie == "Dossiers & rapports":
            _gestion_dossiers()
            continue
        if choix_categorie == "Historique local":
            _afficher_historique()
            continue
        options = [nom for nom, _, _ in CATALOGUE[categories.index(choix_categorie)][2]]
        choix_outil = selectionner_option(choix_categorie, options + ["Retour"])
        if choix_outil is None or choix_outil == "Retour":
            continue
        for entree in FLAT:
            if entree["nom"] == choix_outil:
                return entree["num"]
        bad("Outil introuvable dans le catalogue.")

def _initialiser_environnement(force=None):
    """Sélectionne l'environnement d'affichage et le persiste localement.

    Le choix ne modifie que les préférences d'interface : aucune variable
    système, aucun binaire et aucun système d'exploitation ne sont changés.
    """
    global _CONFIG
    detecte = detecter_environnement()
    if force:
        cle = normaliser_cle(force)
        console.print(f"Environnement d'affichage forcé : {libelle_environnement(cle)}")
    else:
        cle = select_environment(_CONFIG, detecte=detecte)
    plateforme = _CONFIG.setdefault("plateforme", {})
    plateforme["environnement"] = normaliser_cle(cle)
    plateforme["selectionne_le"] = resume_environnement(cle)["detecte_le"]
    sauvegarder(_CONFIG)
    _appliquer_configuration_visuelle()
    return cle


def main():
    global _CONFIG
    parser = argparse.ArgumentParser(
        description="LeakFr-Tools : boîte à outils OSINT, réseau et cybersécurité.",
        epilog="Utilise les tests actifs uniquement sur des systèmes autorisés.",
    )
    parser.add_argument("--simple", action="store_true",
                        help="force les menus numériques non interactifs (déjà par défaut)")
    parser.add_argument("--dashboard", action="store_true",
                        help="active l'ancien tableau de bord à flèches (desktop uniquement)")
    parser.add_argument("--ascii", action="store_true", help="privilégie un affichage compatible ASCII")
    parser.add_argument("--text", "--no-color", dest="text", action="store_true",
                        help="mode texte simple, sans couleur ni animation")
    parser.add_argument("--no-intro", action="store_true",
                        help="saute l'introduction animee du demarrage")
    parser.add_argument("--bot", action="store_true",
                        help="demarre le bot Discord et le laisse en ligne "
                             "(token dans LEAKFR_DISCORD_BOT_TOKEN)")
    parser.add_argument("--phone", action="store_true",
                        help="force le rendu mobile et la pagination réduite")
    parser.add_argument("--env", choices=[cle for cle, _ in ENVIRONNEMENTS],
                        help="force l'environnement d'affichage sans changer le système réel")
    parser.add_argument("--version", action="version", version="LeakFr-Tools 2.0")
    args = parser.parse_args()
    global INTERACTIF, UNICODE, BX, CONN_T, CONN_L, PIPE
    # Le parcours numérique est le comportement par défaut sur tous les OS.
    INTERACTIF = (bool(args.dashboard) and not args.simple
                  and sys.stdin.isatty() and sys.stdout.isatty())
    if args.ascii:
        UNICODE = False
        BX = box.ASCII
        CONN_T, CONN_L, PIPE = ("|-- ", "`-- ", "|   ")
    if args.bot:
        # Mode service : aucun menu, aucune animation, le bot reste en ligne.
        from modules.discord.bot_runner import demarrer_bot
        return demarrer_bot()
    _intro_ascii(_CONFIG)
    _initialiser_environnement(args.env)
    while True:
        try:
            choix = menu_interactif() if INTERACTIF else menu_simple()
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
    console.print(texte_arc("A bientot !", time.time(), 0), justify="center")

if __name__ == "__main__":
    sys.exit(main() or 0)