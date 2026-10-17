import importlib
import json

import pytest

import main
from modules.discord import permissions as perms
from modules.discord.discord_api import (
    DiscordAPI, DiscordAPIError, DiscordAuthError, DiscordForbiddenError,
    DiscordRateLimitError, redact,
)
from modules.discord.gateway_bot import DiscordGatewayClient

bot_panel_module = importlib.import_module("modules.discord.bot_panel")
journal_module = importlib.import_module("modules.discord.panel_journal")


class FakeResponse:
    def __init__(self, status=200, data=None, headers=None):
        self.status_code = status
        self._data = data if data is not None else {}
        self.headers = headers or {}

    def json(self):
        if isinstance(self._data, Exception):
            raise self._data
        return self._data


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.closed = False

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return self.responses.pop(0)

    def close(self):
        self.closed = True


def test_panel_snowflake_and_channel_validation():
    assert bot_panel_module._valid_snowflake("123456789012345678")
    assert not bot_panel_module._valid_snowflake("1234")
    assert not bot_panel_module._valid_snowflake("../channels")
    assert bot_panel_module._slug_channel_name("  Audit Sécurité / 2026 ") == "audit-securite-2026"
    with pytest.raises(ValueError):
        bot_panel_module._slug_channel_name(" !!! ")


def test_permission_summary_calculates_role_union():
    class FakeAPI:
        @staticmethod
        def guild_member(_guild_id, _bot_id):
            return {"user": {"id": "444444444444444444"},
                    "roles": ["222222222222222222"]}

    roles = [
        {"id": "111111111111111111", "permissions": "8"},
        {"id": "222222222222222222", "permissions": str(0x10 | 0x2000)},
    ]
    permissions, status = bot_panel_module._permission_summary(
        FakeAPI(), "333333333333333333", "444444444444444444", roles
    )
    assert status == 200
    assert permissions == 0x10 | 0x2000


def test_permissions_effectives_everyone_roles_admin_et_surcharges():
    guild = {"id": "1", "owner_id": "999"}
    roles = [
        {"id": "1", "permissions": str(perms.VIEW_CHANNEL)},
        {"id": "2", "permissions": str(perms.SEND_MESSAGES)},
    ]
    member = {"user": {"id": "42"}, "roles": ["2"]}
    base = perms.base_permissions(guild, member, roles)
    assert perms.has_permission(base, perms.VIEW_CHANNEL)
    assert perms.has_permission(base, perms.SEND_MESSAGES)

    salon = {"permission_overwrites": [
        {"id": "1", "allow": "0", "deny": str(perms.SEND_MESSAGES), "type": 0},
        {"id": "2", "allow": str(perms.SEND_MESSAGES), "deny": "0", "type": 0},
    ]}
    assert perms.has_permission(
        perms.effective_permissions(guild, member, roles, salon), perms.SEND_MESSAGES)

    membre_refuse = {"user": {"id": "42"}, "roles": ["2"]}
    salon_refus = {"permission_overwrites": [
        {"id": "42", "allow": "0", "deny": str(perms.SEND_MESSAGES), "type": 1},
    ]}
    assert not perms.has_permission(
        perms.effective_permissions(guild, membre_refuse, roles, salon_refus),
        perms.SEND_MESSAGES)

    proprietaire = {"user": {"id": "999"}, "roles": []}
    assert perms.est_admin(perms.base_permissions(guild, proprietaire, roles))
    assert perms.permissions_excessives({"permissions": "8"}) == ["Administrateur"]
    assert not perms.peut_gerer_role(0, 5, {"position": 6})
    assert perms.peut_gerer_role(perms.ADMINISTRATOR, 1, {"position": 99})


def test_api_respecte_429_puis_reussit_sans_fuite_de_token():
    attentes = []
    session = FakeSession([
        FakeResponse(429, {"retry_after": 0.1, "message": "rate limited"}),
        FakeResponse(200, {"id": "123456789012345678", "username": "bot"}),
    ])
    api = DiscordAPI("supersecret-token-value", session=session, sleep=attentes.append)
    resultat = api.me()
    assert resultat["username"] == "bot"
    assert attentes == [0.1]
    assert len(session.calls) == 2
    assert session.calls[0][2]["headers"]["Authorization"].startswith("Bot ")


def test_api_modifie_le_surnom_du_bot_sur_membres_at_me():
    session = FakeSession([FakeResponse(200, {"nick": "Audit"})])
    api = DiscordAPI("supersecret-token-value", session=session)
    api.modifier_propre_membre("123456789012345678", {"nick": "Audit"})
    assert session.calls[0][1].endswith("/guilds/123456789012345678/members/@me")
    assert session.calls[0][2]["json"] == {"nick": "Audit"}


def test_api_erreurs_401_403_et_429_persistante():
    api = DiscordAPI("supersecret-token-value",
                     session=FakeSession([FakeResponse(401, {"message": "401: Unauthorized"})]))
    with pytest.raises(DiscordAuthError) as erreur:
        api.me()
    assert "supersecret" not in str(erreur.value)

    api = DiscordAPI("supersecret-token-value",
                     session=FakeSession([FakeResponse(403, {"message": "Missing Access"})]))
    with pytest.raises(DiscordForbiddenError) as erreur:
        api.guild("123456789012345678")
    assert "HTTP 403" in str(erreur.value)
    assert "supersecret" not in str(erreur.value)

    api = DiscordAPI("supersecret-token-value",
                     session=FakeSession([FakeResponse(429, {"retry_after": 30}),
                                          FakeResponse(429, {"retry_after": 30})]),
                     sleep=lambda _secondes: None, max_retries=1)
    with pytest.raises(DiscordRateLimitError):
        api.me()


def test_reponse_api_non_json_est_une_erreur_explicite():
    api = DiscordAPI("supersecret-token-value",
                     session=FakeSession([FakeResponse(200, ValueError("pas du json"))]))
    with pytest.raises(DiscordAPIError) as erreur:
        api.me()
    assert "non JSON" in str(erreur.value)


def test_apercu_embed_est_construit():
    panneau = bot_panel_module._apercu_embed({
        "title": "Annonce", "description": "Contenu", "color": 0x5865F2,
        "footer": {"text": "pied"},
    })
    assert panneau is not None


def test_upload_multipart_et_erreur_http_sans_fuite():
    class PostSession:
        def __init__(self, response):
            self.response = response
            self.calls = []

        def post(self, url, **kwargs):
            self.calls.append((url, kwargs))
            return self.response

        def close(self):
            pass

    session = PostSession(FakeResponse(200, {"id": "123456789012345678"}))
    api = DiscordAPI("supersecret-token-value", session=session)
    message = api.envoyer_fichier("223456789012345678", "legende", "a.gif",
                                  b"GIF89a", "image/gif")
    assert message["id"] == "123456789012345678"
    url, kwargs = session.calls[0]
    assert url.endswith("/channels/223456789012345678/messages")
    assert kwargs["files"]["files[0]"] == ("a.gif", b"GIF89a", "image/gif")
    assert "payload_json" in kwargs["data"]
    assert "Authorization" in kwargs["headers"]

    api = DiscordAPI("supersecret-token-value",
                     session=PostSession(FakeResponse(403, {"message": "Missing Access"})))
    with pytest.raises(DiscordForbiddenError):
        api.envoyer_fichier("223456789012345678", "", "a.gif", b"GIF89a")


def test_webhook_creation_et_suppression_dans_le_panel(monkeypatch):
    ctx = {"guild": {"id": "1", "owner_id": "9"},
           "member": {"user": {"id": "2"}, "roles": ["5"]},
           "roles": [{"id": "1", "permissions": "0", "position": 0},
                     {"id": "5", "permissions": str(perms.MANAGE_WEBHOOKS), "position": 5}],
           "webhooks": [{"id": "77", "name": "ancien", "channel_id": "42"}]}
    etat = {"ctx": ctx, "selected": "1", "bot_id": "2"}
    monkeypatch.setattr(bot_panel_module, "_choisir_salon",
                        lambda *_args, **_kwargs: {"id": "42", "name": "general"})
    monkeypatch.setattr(bot_panel_module, "_verifier_salon", lambda *_args: True)
    monkeypatch.setattr(bot_panel_module, "choisir_option",
                        lambda *_args, **_kwargs: "ancien (77)")
    monkeypatch.setattr(bot_panel_module, "demander", lambda *_args, **_kwargs: "nouveau")
    monkeypatch.setattr(bot_panel_module.Confirm, "ask", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(bot_panel_module, "journaliser", lambda *_args, **_kwargs: None)

    class API:
        def __init__(self):
            self.created = []
            self.deleted = []

        def creer_webhook(self, channel_id, payload, reason=None):
            self.created.append((channel_id, payload))
            return {"id": "88", "name": "nouveau", "url": "https://discord.com/api/webhooks/88/token"}

        def guild_webhooks(self, _guild_id):
            return [{"id": "77", "name": "ancien", "channel_id": "42"}]

        def supprimer_webhook(self, webhook_id, reason=None):
            self.deleted.append(webhook_id)

    api = API()
    bot_panel_module._creer_webhook(api, etat, "token")
    assert api.created == [("42", {"name": "nouveau"})]
    bot_panel_module._supprimer_webhook(api, etat, "token")
    assert api.deleted == ["77"]


def test_redaction_des_jetons_et_journal_local(tmp_path, monkeypatch):
    monkeypatch.setattr(journal_module, "JOURNAL_FILE", tmp_path / "journal.json")
    token = "MTA123456789012345678.GaBcDe.abcdefghijklmnopqrstuvwxyz123456"
    entrees = journal_module.enregistrer(
        "timeout", "123456789012345678", "42", "erreur",
        f"Authorization: Bot {token}", ())
    assert token not in json.dumps(entrees)
    assert "[masque]" in entrees["detail"]
    assert journal_module.derniers(5)[0]["action"] == "timeout"
    journal_module.effacer()
    assert journal_module.charger_journal() == []


def test_guild_export_does_not_include_secrets_or_message_content(tmp_path, monkeypatch):
    monkeypatch.setattr(bot_panel_module, "EXPORTS_DIR", str(tmp_path))
    path = bot_panel_module._save_guild_audit(
        "123456789012345678",
        {
            "guild": {"id": "123", "name": "Lab", "owner_id": "456"},
            "channels": [{"id": "789", "name": "general", "token": "should-not-export"}],
            "roles": [{"id": "456", "name": "@everyone", "permissions": "0"}],
            "webhooks": [{"id": "1", "name": "hook", "token": "secret-webhook"}],
            "members": [{"content": "private message"}],
        },
    )
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["guild"]["name"] == "Lab"
    texte = path.read_text(encoding="utf-8")
    assert "should-not-export" not in texte
    assert "secret-webhook" not in texte
    assert "private message" not in texte
    assert data["members_loaded"] == 1
    assert data["permissions"] is None
    assert data["permission_names"] == []


def test_contexte_serveur_conserve_les_erreurs_partielles():
    class API:
        @staticmethod
        def guild(_guild_id):
            return {"id": "1", "name": "Lab", "owner_id": "9"}

        @staticmethod
        def guild_channels(_guild_id):
            return [{"id": "2", "name": "general", "type": 0}]

        @staticmethod
        def guild_roles(_guild_id):
            return [{"id": "1", "permissions": "0"}]

        @staticmethod
        def guild_member(_guild_id, _bot_id):
            raise DiscordForbiddenError("membre refuse", status=403)

        @staticmethod
        def guild_webhooks(_guild_id):
            raise DiscordForbiddenError("webhooks refuses", status=403)

    ctx = bot_panel_module.charger_contexte(API(), "123456789012345678",
                                            "223456789012345678")
    assert ctx["guild"]["name"] == "Lab"
    assert ctx["channels"] and ctx["roles"]
    assert ctx["member"] is None
    libelles = {libelle for libelle, _message in ctx["errors"]}
    assert {"membre du bot", "webhooks"} <= libelles
    assert bot_panel_module.permissions_du_bot(ctx) is None


def test_filtre_serveurs_et_etiquette_membres_honnete():
    guilds = [{"id": "1", "name": "Sécurité Lab"}, {"id": "2", "name": "Autre"}]
    assert [g["id"] for g in bot_panel_module.filtrer_guildes(guilds, "securite")] == ["1"]
    assert bot_panel_module.filtrer_guildes(guilds, "2")[0]["name"] == "Autre"
    etiquette = bot_panel_module.libelle_membres(100)
    assert "maximum 100" in etiquette and "tronquee" in etiquette
    assert "audit" not in etiquette.lower()
    assert "100 membre(s)" in bot_panel_module.libelle_membres(100)


def test_menus_reviennent_au_menu_principal(monkeypatch):
    monkeypatch.setattr(bot_panel_module, "choisir_option", lambda *_args, **_kwargs: "Retour")
    assert bot_panel_module.menu_serveurs(None, {}, "token") is None
    assert bot_panel_module.menu_communication(None, {}, "token") is None
    assert bot_panel_module.menu_salons(None, {}, "token") is None
    assert bot_panel_module.menu_roles(None, {}, "token") is None


def test_action_sensible_exige_une_confirmation(monkeypatch):
    ctx = {
        "guild": {"id": "1", "owner_id": "9"},
        "member": {"user": {"id": "2"}, "roles": ["5"]},
        "roles": [
            {"id": "1", "permissions": "0", "position": 0},
            {"id": "5", "permissions": str(perms.KICK_MEMBERS), "position": 5},
            {"id": "6", "permissions": "0", "position": 1},
        ],
    }
    etat = {"ctx": ctx, "selected": "1", "bot_id": "2"}
    cible = {"user": {"id": "42", "username": "cible"}, "roles": ["6"]}
    monkeypatch.setattr(bot_panel_module, "_membre_cible", lambda *_args: cible)
    monkeypatch.setattr(bot_panel_module, "demander", lambda *_args, **_kwargs: "raison")
    monkeypatch.setattr(bot_panel_module.Confirm, "ask", lambda *_args, **_kwargs: False)

    class API:
        def __init__(self):
            self.appels = []

        def expulser_membre(self, *args, **kwargs):
            self.appels.append((args, kwargs))

    api = API()
    bot_panel_module._expulser_membre(api, etat, "token")
    assert api.appels == []


def test_moderation_refuse_sans_permission(monkeypatch):
    ctx = {"guild": {"id": "1", "owner_id": "9"},
           "member": {"user": {"id": "2"}, "roles": []},
           "roles": [{"id": "1", "permissions": "0", "position": 0}]}
    etat = {"ctx": ctx, "selected": "1", "bot_id": "2"}
    monkeypatch.setattr(bot_panel_module, "_membre_cible",
                        lambda *_args: pytest.fail("la cible ne doit pas etre lue"))
    bot_panel_module._timeout_membre(object(), etat, "token")


def test_gateway_refuse_un_demarrage_sans_token_et_s_arrete_proprement():
    client = DiscordGatewayClient("")
    assert client.start() is False
    assert client.stop() is True
    assert client.connected is False


def test_gateway_masque_le_token_dans_les_erreurs():
    token = "supersecret-token-value-123"

    def factory(_intents):
        raise RuntimeError(f"echec avec {token}")

    client = DiscordGatewayClient(token, client_factory=factory)
    assert client.start(timeout=5) is False
    assert token not in (client.last_error or "")
    assert token not in "\n".join(client.log_messages)
    assert "RuntimeError" in (client.last_error or "")
    assert client.stop() is True


def test_gateway_presence_valide_hors_ligne():
    client = DiscordGatewayClient("token")
    assert client.update_presence("wrong")[0] is False
    assert client.update_presence("online", "x", 1, "")[0] is False
    assert client.update_presence("online", "x", 7, "")[0] is False
    succes, message = client.update_presence("online", "Audit", 0, "")
    assert succes is False and "non connectee" in message


def test_catalogue_contient_les_deux_panels_et_recherche_oauth2():
    noms = {outil["nom"] for outil in main.FLAT if outil["fn"]}
    assert {"Panel Bot Discord", "Discord Personal Panel", "Server Cloner",
            "Emoji Cloner", "GIF Studio", "Profile Studio"} <= noms
    assert main.rechercher_outils("oauth2")[0]["nom"] == "Discord Personal Panel"
    assert main.rechercher_outils("moderation")[0]["nom"] == "Panel Bot Discord"
    assert main.rechercher_outils("cloner structure")[0]["nom"] == "Server Cloner"
    assert main.rechercher_outils("emoji anime")[0]["nom"] == "Emoji Cloner"
    assert main.rechercher_outils("gif webp")[0]["nom"] == "GIF Studio"
    assert main.rechercher_outils("avatar banniere")[0]["nom"] == "Profile Studio"
