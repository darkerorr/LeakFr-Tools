import importlib
import json
from urllib.parse import parse_qs, urlparse

import pytest

from modules.discord.personal import auth, local_tools
from modules.discord.personal.api import PersonalAPI
from modules.discord.personal.errors import OAuthError, PersonalAPIError, ScopeError, TokenExpiredError
from modules.discord.personal.models import (
    filtrer_serveurs, parse_profil, parse_serveurs, trier_serveurs,
)
from modules.discord.personal.store import PersonalStore

personal_panel_module = importlib.import_module('modules.discord.personal.panel')


class Reponse:
    def __init__(self, status=200, data=None):
        self.status_code= status
        self._data = data if data is not None else {}

    def json(self):
        return self._data


class Session:
    def __init__(self, reponses=None):
        self.reponses =list(reponses or [])
        self.appels= []

    def post(self, url, data=None, headers=None, timeout=None):
        self.appels.append(('POST', url, data, headers))
        return self.reponses.pop(0)

    def request(self, method, url, headers=None, timeout=None):
        self.appels.append((method, url, headers))
        return self.reponses.pop(0)

    def close(self):
        pass


def test_pkce_et_url_autorisation_sans_secret():
    config = auth.OAuthConfig(client_id='123456789012345678',
                              client_secret="client-secret-a-ne-pas-exposer")
    verificateur, challenge =auth.pkce_pair()
    assert 43 <=len(verificateur) <= 128
    url = auth.authorization_url(config, "etat-test", challenge)
    params = parse_qs(urlparse(url).query)
    assert params['client_id']==['123456789012345678']
    assert params["scope"]== ["identify guilds"]
    assert params["state"] == ["etat-test"]
    assert params['code_challenge_method'] == ['S256']
    assert "client_secret" not in params
    assert "client-secret" not in url


def test_validation_des_scopes_et_client_id():
    assert auth.valider_scopes(('identify', 'guilds'), ('guilds', 'identify')) == [
        "guilds", "identify"]
    with pytest.raises(ScopeError):
        auth.valider_scopes(('identify', 'guilds'), ('identify', 'guilds', 'email'))
    with pytest.raises(ScopeError):
        auth.valider_scopes(("identify", "connections"), ())
    with pytest.raises(OAuthError):
        auth.valider_client_id("abc")


def test_echange_de_code_et_erreurs_sans_fuite():
    config= auth.OAuthConfig(client_id="123456789012345678")
    session= Session([Reponse(200, {'access_token':'jeton', 'token_type': 'Bearer',
                                     "refresh_token":"refresh", "expires_in":604800,
                                     "scope": "identify guilds"})])
    jeton= auth.echanger_code(config, 'code', 'verificateur', session=session)
    assert jeton["access_token"] == "jeton"
    assert jeton["scope"] == ("identify", "guilds")
    corps = session.appels[0][2]
    assert corps["code_verifier"]== "verificateur"
    assert "client_secret" not in corps

    echec = Session([Reponse(400, {"error": "invalid_grant",
                                   "error_description": "code expire"})])
    with pytest.raises(OAuthError) as erreur:
        auth.echanger_code(config, "code", "verificateur", session=echec)
    assert "code expire" in str(erreur.value)


def test_revocation_envoie_le_bon_type_de_jeton():
    config = auth.OAuthConfig(client_id='123456789012345678')
    session =Session([Reponse(200, {}), Reponse(200, {})])
    assert auth.revoquer(config, "access", session=session) is True
    assert auth.revoquer(config, 'refresh', session=session, hint='refresh_token') is True
    assert session.appels[0][2]["token_type_hint"] == "access_token"
    assert session.appels[1][2]["token_type_hint"] =="refresh_token"


def test_configuration_depuis_environnement(tmp_path):
    absent = tmp_path / 'absent-leakfr.json'
    config =auth.charger_config(environ={"DISCORD_CLIENT_ID": "123456789012345678",
                                          "DISCORD_CLIENT_SECRET":""},
                                 path=str(absent))
    assert config.client_id== "123456789012345678"
    assert config.client_secret == ""
    assert auth.charger_config(environ={}, path=str(absent)) is None


def test_api_personnelle_refuse_401_et_respecte_429():
    session = Session([Reponse(401, {"message": "401: Unauthorized"})])
    api = PersonalAPI("jeton-secret", session=session)
    with pytest.raises(TokenExpiredError):
        api.me()

    session = Session([Reponse(429, {'retry_after': 0.0}),
                       Reponse(200, {"id": "42", "username":"alice"})])
    api = PersonalAPI("jeton-secret", session=session, sleep=lambda _s:None)
    assert api.me()['username']== 'alice'
    assert session.appels[0][2]["Authorization"] == "Bearer jeton-secret"

    with pytest.raises(PersonalAPIError):
        PersonalAPI("", session=Session())


def test_modeles_profil_serveurs_filtre_et_tri():
    profil = parse_profil({"id": "42", "username":"alice", "global_name": "Alice",
                           'locale':'fr', 'mfa_enabled': True})
    assert profil.libelle == "Alice" and profil.mfa is True
    with pytest.raises(ValueError):
        parse_profil({})

    serveurs = parse_serveurs([
        {'id': '123456789012345678', 'name': 'Sécurité Lab', 'permissions': '8'},
        {"id": "223456789012345678", "name": "Autre", "permissions":"1024"},
        {"id":"absent"},
    ])
    assert len(serveurs) == 2
    assert [s.nom for s in filtrer_serveurs(serveurs, "securite")]== ["Sécurité Lab"]
    assert [s.nom for s in trier_serveurs(serveurs, 'nom')][0]== 'Autre'
    assert [s.nom for s in trier_serveurs(serveurs, "permissions")] == ["Sécurité Lab", "Autre"]


def test_outils_locaux_hors_ligne():
    details =local_tools.decoder_snowflake("175928847299117063")
    assert details['snowflake'] == '175928847299117063'
    assert details["creation_utc"].endswith("+00:00")
    with pytest.raises(ValueError):
        local_tools.decoder_snowflake('abc')

    lien= local_tools.lien_invitation_bot("123456789012345678", 8)
    assert 'client_id=123456789012345678' in lien
    assert "permissions=8" in lien
    with pytest.raises(ValueError):
        local_tools.lien_invitation_bot('123', 8)
    with pytest.raises(ValueError):
        local_tools.lien_invitation_bot("123456789012345678", 8, ("bot", "email"))

    embed =local_tools.construire_embed("Titre", "Description", "#5865F2", "pied")
    assert embed["color"] == 0x5865F2
    with pytest.raises(ValueError):
        local_tools.construire_embed("", "", "", "")
    with pytest.raises(ValueError):
        local_tools.construire_embed('x', '', 'bleu')
    with pytest.raises(ValueError):
        local_tools.valider_message("   ")


def test_stockage_local_ne_conserve_aucun_secret(tmp_path):
    chemin =tmp_path / 'personal.json'
    chemin.write_text(json.dumps({
        "preferences": {"access_token": "secret", "tri_serveurs":"nom"},
        'history': [{'action': 'test',
                     "detail": "Authorization: Bearer abcdefghijklmnopqrstuvwxyz"}],
    }), encoding="utf-8")
    store = PersonalStore(chemin)
    assert store.preference("access_token") is None
    assert store.preference("tri_serveurs") == "nom"
    assert 'abcdefghijklmnopqrstuvwxyz' not in str(store.historique())

    store.enregistrer("connexion", "jeton MTA123456789012345678.GaBcDe.abcdefghijklmnopqrstuvwxyz")
    contenu = chemin.read_text(encoding='utf-8')
    assert "abcdefghijklmnopqrstuvwxyz" not in contenu
    assert "[masque]" in contenu

    store.ajouter_modele("accueil", "Bonjour")
    assert store.modeles()[0]["nom"] =="accueil"
    assert store.supprimer_modele('absent') is False
    assert store.supprimer_modele("accueil") is True


def test_panel_personnel_revient_sans_connexion(monkeypatch):
    monkeypatch.setattr(personal_panel_module, "choisir_option",
                        lambda *_args, **_kwargs: 'Quitter')
    assert personal_panel_module.personal_panel() is None
