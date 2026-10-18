"""Panel personnel Discord : OAuth2 officiel, outils locaux et historique.

Le panel ne demande jamais de token utilisateur copie manuellement. Les
jetons OAuth2 restent en memoire et les outils locaux fonctionnent hors ligne.
"""
from pathlib import Path

from rich.markup import escape
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from core.common import (
    BX, C_DISCORD, bad, choisir_option, console, demander, kv, ok,
    pause, titre, warn,
)
from modules.discord.personal import auth, local_tools
from modules.discord.personal.api import PersonalAPI
from modules.discord.personal.errors import OAuthError, PersonalAPIError, StorageError, TokenExpiredError
from modules.discord.personal.models import (
    filtrer_serveurs, parse_profil, parse_serveurs, trier_serveurs,
)
from modules.discord.personal.render import afficher_serveurs, render_historique, render_profil
from modules.discord.personal.store import PersonalStore

MENU =[
    'Connexion OAuth2',
    "Profil autorise",
    "Serveurs accessibles",
    'Outils locaux',
    "Modeles & preferences",
    "Historique local",
    'Ouvrir le panel Bot',
    "Quitter",
]


def _configurer_client():
    warn('Aucune configuration OAuth2 trouvee (DISCORD_CLIENT_ID ou fichier local).')
    client_id = demander("Client ID de l'application Discord").strip()
    try:
        client_id = auth.valider_client_id(client_id)
    except OAuthError as exc:
        bad(str(exc))
        return None
    secret= Prompt.ask("Client secret (facultatif, laisse vide pour PKCE public)",
                        password=True, default="").strip()
    redirect= demander('URI de redirection loopback', auth.REDIRECT_DEFAUT).strip()
    config = auth.OAuthConfig(client_id=client_id, client_secret=secret,
                              redirect_uri=redirect or auth.REDIRECT_DEFAUT)
    try:
        config.url_redirigee()
    except OAuthError as exc:
        bad(str(exc))
        return None
    if Confirm.ask("Enregistrer cette configuration locale (secret en clair, chmod 600) ?",
                   default=False):
        try:
            chemin= auth.sauvegarder_config(config)
        except OSError as exc:
            warn(f"Configuration non enregistree : {exc}")
        else:
            ok(f"Configuration ecrite dans {chemin} (permissions restreintes).")
    return config


def _connexion(etat, store):
    config =etat["config"] or _configurer_client()
    if config is None:
        return
    etat["config"] = config
    verificateur, challenge = auth.pkce_pair()
    etat_oauth = auth.nouvel_etat()
    try:
        url =auth.authorization_url(config, etat_oauth, challenge)
    except OAuthError as exc:
        bad(str(exc))
        return
    console.print(Panel(url, title="Ouvre cette URL dans ton navigateur",
                        border_style=C_DISCORD))
    console.print('[dim]Scopes demandes : identify, guilds. '
                  "Aucun token utilisateur n'est demande dans le terminal.[/]")
    try:
        code = auth.attendre_callback(config, etat_oauth)
        jeton =auth.echanger_code(config, code, verificateur)
    except OAuthError as exc:
        bad(f"Autorisation impossible : {exc}")
        return
    etat["jeton"] =jeton
    etat['profil'] = None
    etat["serveurs"]= []
    etat["serveur_choisi"]=None
    try:
        store.enregistrer("connexion_oauth2", f"scopes {', '.join(jeton['scope'])}")
    except StorageError as exc:
        warn(str(exc))
    ok("Connexion OAuth2 etablie. Le jeton reste en memoire uniquement.")


def _deconnexion(etat, store):
    if not etat.get("jeton"):
        warn('Aucune session OAuth2 active.')
        return
    if not Confirm.ask("Revoquer le jeton OAuth2 et fermer la session ?", default=False):
        return
    jeton = etat["jeton"]
    revoque=False
    if etat.get('config'):
        revoque = auth.revoquer(etat["config"], jeton.get("access_token", ""))
        if jeton.get("refresh_token"):
            revoque =auth.revoquer(etat['config'], jeton['refresh_token'],
                                    hint="refresh_token") and revoque
    etat["jeton"]=None
    etat['profil']= None
    etat["serveurs"] = []
    etat["serveur_choisi"] =None
    try:
        store.enregistrer("deconnexion_oauth2", "jeton revoque" if revoque
                          else "jeton efface localement, revocation non confirmee")
    except StorageError as exc:
        warn(str(exc))
    ok("Session fermee." if revoque else "Jeton efface localement ; verifiez la revocation cote Discord.")


def _api(etat):
    if not etat.get('jeton'):
        warn("Connexion OAuth2 requise pour cette action.")
        return None
    return PersonalAPI(etat['jeton']['access_token'])


def _afficher_profil(etat, store):
    api= _api(etat)
    if api is None:
        return
    try:
        profil = parse_profil(api.me())
    except TokenExpiredError:
        etat["jeton"] = None
        bad("Jeton expire ou revoque : reconnectez-vous.")
        return
    except (PersonalAPIError, ValueError) as exc:
        bad(f"Profil indisponible : {exc}")
        return
    finally:
        api.close()
    etat['profil'] = profil
    console.print(render_profil(profil))
    try:
        store.enregistrer('consultation_profil', f"profil {profil.id}")
    except StorageError as exc:
        warn(str(exc))


def _serveurs(etat, store):
    api = _api(etat)
    if api is None:
        return
    try:
        etat["serveurs"]= parse_serveurs(api.guildes())
    except TokenExpiredError:
        etat['jeton']= None
        bad("Jeton expire ou revoque : reconnectez-vous.")
        return
    except PersonalAPIError as exc:
        bad(f"Serveurs indisponibles : {exc}")
        return
    finally:
        api.close()
    try:
        store.enregistrer('consultation_serveurs', f"{len(etat["serveurs"])} serveur(s)")
    except StorageError as exc:
        warn(str(exc))

    while True:
        serveurs = trier_serveurs(etat["serveurs"], etat.get("tri", "nom"))
        afficher_serveurs(serveurs)
        choix = choisir_option("SERVEURS OAuth2", [
            "Rechercher", "Trier", "Choisir pour le panel Bot", "Retour"])
        if choix in (None, 'Retour'):
            return
        if choix== "Rechercher":
            requete =demander('Filtre (nom ou ID)', '')
            serveurs = filtrer_serveurs(etat["serveurs"], requete)
            afficher_serveurs(serveurs, f"Resultats pour '{requete}'")
        elif choix == 'Trier':
            critere =choisir_option("TRI", ["Nom", "ID", "Permissions"])
            if critere:
                etat['tri'] = {'Nom': 'nom', 'ID': 'id', 'Permissions': 'permissions'}[critere]
        elif choix == "Choisir pour le panel Bot":
            if not serveurs:
                warn('Aucun serveur a selectionner.')
                continue
            libelles =[f"{serveur.nom} ({serveur.id})" for serveur in serveurs]
            cible = choisir_option('SERVEUR CIBLE', libelles + ['Retour'])
            if cible in (None, "Retour"):
                continue
            serveur = serveurs[libelles.index(cible)]
            etat["serveur_choisi"] = serveur
            ok(f"Serveur retenu : {serveur.nom}. Le panel Bot verifiera l'installation du bot.")
            try:
                store.enregistrer("selection_serveur", f"{serveur.id}")
            except StorageError as exc:
                warn(str(exc))
        pause()


def _outils_locaux(etat, store):
    while True:
        choix = choisir_option('OUTILS LOCAUX (hors ligne)', [
            "Decoder un Snowflake", "Lien d'invitation de bot",
            "Lien application developpeur", "Apercu de message",
            "Apercu d'embed", 'Modeles de messages', 'Retour'])
        if choix in (None, "Retour"):
            return
        if choix == 'Decoder un Snowflake':
            try:
                details = local_tools.decoder_snowflake(demander("Snowflake Discord"))
            except ValueError as exc:
                bad(str(exc))
            else:
                kv('Snowflake', [(cle, str(valeur)) for cle, valeur in details.items()],
                   C_DISCORD)
        elif choix== "Lien d'invitation de bot":
            defaut = etat['config'].client_id if etat.get('config') else ''
            client_id = demander("Client ID / Application ID", defaut).strip()
            permissions =demander("Permissions (entier, 0 par defaut)", "0").strip()
            try:
                lien = local_tools.lien_invitation_bot(client_id, permissions)
            except ValueError as exc:
                bad(str(exc))
            else:
                console.print(Panel(escape(lien), title="Lien d'installation",
                                    border_style=C_DISCORD))
        elif choix =="Lien application developpeur":
            try:
                lien = local_tools.lien_application(demander('Application ID'))
            except ValueError as exc:
                bad(str(exc))
            else:
                console.print(Panel(escape(lien), border_style=C_DISCORD))
        elif choix == "Apercu de message":
            try:
                contenu= local_tools.valider_message(demander("Message"))
            except ValueError as exc:
                bad(str(exc))
            else:
                console.print(Panel(escape(contenu), title="Apercu de message",
                                    border_style=C_DISCORD))
        elif choix == "Apercu d'embed":
            try:
                embed= local_tools.construire_embed(
                    demander("Titre (facultatif)", ""),
                    demander("Description (facultatif)", ""),
                    demander('Couleur #RRGGBB (facultatif)', ''),
                    demander("Pied de page (facultatif)", ""),
                )
            except ValueError as exc:
                bad(str(exc))
            else:
                table =Table(title="Apercu d'embed", box=BX, border_style=C_DISCORD)
                table.add_column("Champ")
                table.add_column("Valeur")
                for cle, valeur in embed.items():
                    table.add_row(cle, str(valeur))
                console.print(table)
        elif choix =='Modeles de messages':
            _modeles(store)
        pause()


def _modeles(store):
    while True:
        choix= choisir_option("MODELES LOCAUX", [
            "Lister", "Ajouter", "Supprimer", "Retour"])
        if choix in (None, 'Retour'):
            return
        modeles = store.modeles()
        if choix == 'Lister':
            if not modeles:
                warn("Aucun modele enregistre.")
            for modele in modeles:
                console.print(Panel(escape(modele["contenu"]),
                                    title=escape(modele["nom"]), border_style=C_DISCORD))
        elif choix == 'Ajouter':
            nom= demander("Nom du modele").strip()
            contenu =demander("Contenu").strip()
            try:
                store.ajouter_modele(nom, contenu)
            except (ValueError, StorageError) as exc:
                bad(str(exc))
            else:
                store.enregistrer("ajout_modele", nom)
                ok('Modele enregistre localement.')
        elif choix =="Supprimer":
            if not modeles:
                warn('Aucun modele a supprimer.')
                continue
            nom =choisir_option("MODELE A SUPPRIMER",
                                 [modele['nom'] for modele in modeles] + ['Retour'])
            if nom in (None, "Retour"):
                continue
            try:
                supprime = store.supprimer_modele(nom)
            except StorageError as exc:
                bad(str(exc))
            else:
                ok("Modele supprime." if supprime else "Modele introuvable.")
        pause()


def _preferences(etat, store):
    while True:
        choix= choisir_option("PREFERENCES & MODELES", [
            'Modeles de messages', 'Tri par defaut des serveurs',
            "Supprimer la configuration client locale", "Retour"])
        if choix in (None, "Retour"):
            return
        if choix == "Modeles de messages":
            _modeles(store)
            continue
        if choix== "Tri par defaut des serveurs":
            critere =choisir_option("TRI PAR DEFAUT", ["Nom", "ID", "Permissions"])
            if critere:
                etat["tri"] = {"Nom": "nom", "ID":"id", "Permissions": "permissions"}[critere]
                try:
                    store.definir_preference('tri_serveurs', etat['tri'])
                except StorageError as exc:
                    bad(str(exc))
                else:
                    ok("Preference enregistree.")
        elif choix == "Supprimer la configuration client locale":
            if not Confirm.ask('Supprimer le client ID/secret local ?', default=False):
                continue
            try:
                Path(auth.CONFIG_FILE).unlink(missing_ok=True)
            except OSError as exc:
                bad(f"Suppression impossible : {exc}")
            else:
                etat["config"] =auth.charger_config()
                ok("Configuration locale supprimee.")
        pause()


def _historique(store):
    entrees = store.historique(30)
    if not entrees:
        warn('Historique vide.')
        return
    console.print(render_historique(entrees))


def _ouvrir_panel_bot(etat, store):
    serveur = etat.get('serveur_choisi')
    if serveur is None:
        warn("Choisissez d'abord un serveur dans « Serveurs accessibles ».")
        return
    if not Confirm.ask(f"Ouvrir le panel Bot pour {serveur.nom} ? "
                       "Le bot doit y etre installe.", default=False):
        return
    try:
        store.enregistrer("ouverture_panel_bot", serveur.id)
    except StorageError as exc:
        warn(str(exc))
    from modules.discord.bot_panel import bot_panel
    bot_panel(guild_id_initial=serveur.id)


def personal_panel():
    titre("DISCORD PERSONAL PANEL (OAuth2)", C_DISCORD)
    store = PersonalStore()
    etat = {
        "config": auth.charger_config(),
        "jeton": None,
        'profil': None,
        "serveurs": [],
        "serveur_choisi": None,
        'tri': store.preference('tri_serveurs', 'nom'),
    }
    if etat["config"] is None:
        warn('Aucune configuration OAuth2 : les outils locaux restent disponibles.')
    console.print("[dim]OAuth2 officiel · scopes identify/guilds · jetons en memoire · "
                  "aucun token utilisateur copie.[/]")

    while True:
        options= list(MENU)
        options[0] = 'Deconnexion / revocation' if etat.get('jeton') else 'Connexion OAuth2'
        choix = choisir_option("DISCORD PERSONAL PANEL", options)
        if choix in (None, "Quitter"):
            if etat.get('jeton'):
                warn("Le jeton en memoire sera oublie ; utilisez « Deconnexion » "
                     "pour le revoquer proprement.")
            return
        if choix == "Connexion OAuth2":
            _connexion(etat, store)
        elif choix == 'Deconnexion / revocation':
            _deconnexion(etat, store)
        elif choix == "Profil autorise":
            _afficher_profil(etat, store)
        elif choix == "Serveurs accessibles":
            _serveurs(etat, store)
        elif choix == 'Outils locaux':
            _outils_locaux(etat, store)
        elif choix== "Modeles & preferences":
            _preferences(etat, store)
        elif choix == "Historique local":
            _historique(store)
        elif choix == 'Ouvrir le panel Bot':
            _ouvrir_panel_bot(etat, store)
        pause()
