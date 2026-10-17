import json

import pytest

from modules.discord import permissions as perms
from modules.discord.cloner.executor import executer_plan
from modules.discord.cloner.manifest import (
    construire_manifeste, charger_manifeste, sauvegarder_manifeste,
    valider_manifeste,
)
from modules.discord.cloner.panel import charger_destination
from modules.discord.cloner.planner import OptionsClonage, construire_plan
from modules.discord.discord_api import DiscordForbiddenError


GUILD = {"id": "100000000000000001", "name": "Source"}


def source_manifest():
    channels = [
        {"id": "200000000000000001", "name": "Audit", "type": 4, "position": 1,
         "permission_overwrites": [
             {"id": "300000000000000001", "type": 0,
              "allow": str(perms.VIEW_CHANNEL), "deny": "0"},
         ]},
        {"id": "200000000000000002", "name": "general", "type": 0, "position": 2,
         "parent_id": "200000000000000001", "topic": "Sujet",
         "permission_overwrites": [
             {"id": "100000000000000001", "type": 0,
              "allow": str(perms.VIEW_CHANNEL), "deny": "0"},
             {"id": "300000000000000001", "type": 0,
              "allow": str(perms.SEND_MESSAGES), "deny": "0"},
             {"id": "400000000000000001", "type": 1,
              "allow": str(perms.VIEW_CHANNEL), "deny": "0"},
         ]},
        {"id": "200000000000000003", "name": "vocal", "type": 2, "position": 3,
         "parent_id": "200000000000000001", "bitrate": 64000, "user_limit": 5},
        {"id": "200000000000000004", "name": "forum", "type": 15, "position": 4,
         "available_tags": [{"name": "bug", "moderated": False}]},
    ]
    roles = [
        {"id": GUILD["id"], "name": "@everyone", "permissions": "0", "position": 0},
        {"id": "300000000000000001", "name": "Auditeur", "color": 0x5865F2,
         "hoist": True, "mentionable": True, "permissions": str(perms.VIEW_CHANNEL),
         "position": 1},
        {"id": "300000000000000002", "name": "Bot integration", "managed": True,
         "permissions": "8", "position": 5},
    ]
    return construire_manifeste(GUILD, channels, roles, exported_at="2026-01-01T00:00:00+00:00")


def test_manifest_exports_structure_without_secrets_or_members():
    manifeste = source_manifest()
    assert manifeste["counts"] == {"roles": 1, "categories": 1, "channels": 3}
    assert [role["name"] for role in manifeste["roles"]] == ["Auditeur"]
    texte = json.dumps(manifeste)
    assert "Bot integration" not in texte
    assert "token" not in texte.casefold()
    assert "400000000000000001" in texte  # surcharge membre conservee mais non applicable
    salle = next(canal for canal in manifeste["channels"] if canal["name"] == "general")
    kinds = {surcharge["target"]["kind"] for surcharge in salle["permission_overwrites"]}
    assert kinds == {"everyone", "role", "member"}
    assert any("membres" in limite.casefold() for limite in manifeste["limitations"])


def test_manifest_validation_rejects_invalid_and_saves_atomically(tmp_path):
    manifeste = source_manifest()
    with pytest.raises(ValueError):
        valider_manifeste({"format": "autre", "version": 1})
    casse = json.loads(json.dumps(manifeste))
    casse["channels"][0]["type"] = 99
    with pytest.raises(ValueError):
        valider_manifeste(casse)
    casse = json.loads(json.dumps(manifeste))
    casse["channels"][0]["parent_id"] = "999999999999999999"
    with pytest.raises(ValueError):
        valider_manifeste(casse)
    path = sauvegarder_manifeste(manifeste, tmp_path / "structure.json")
    assert charger_manifeste(path)["source_guild"]["id"] == GUILD["id"]
    assert not list(tmp_path.glob("*.tmp"))


def test_plan_ignores_existing_and_renames_conflicts():
    manifeste = source_manifest()
    dest_guild = {"id": "500000000000000001", "name": "Destination"}
    dest_roles = [{"id": "500000000000000002", "name": "Auditeur", "position": 1}]
    dest_channels = [
        {"id": "600000000000000001", "name": "Audit", "type": 4, "position": 0},
        {"id": "600000000000000002", "name": "general", "type": 0, "position": 1,
         "parent_id": "600000000000000001"},
    ]
    plan = construire_plan(manifeste, dest_guild, dest_channels, dest_roles,
                           OptionsClonage(), bot_top_position=5)
    assert plan.correspondances["roles"]["300000000000000001"] == "500000000000000002"
    assert plan.correspondances["categories"]["200000000000000001"] == "600000000000000001"
    actions = {(action["kind"], action["name"]): action for action in plan.actions}
    assert actions[("role", "Auditeur")]["mode"] == "ignorer"
    assert actions[("salon", "general")]["mode"] == "ignorer"
    assert actions[("salon", "vocal")]["mode"] == "creer"
    assert actions[("salon", "vocal")]["payload"]["parent_id"] == "600000000000000001"

    plan_renomme = construire_plan(manifeste, dest_guild, dest_channels, dest_roles,
                                   OptionsClonage(conflits="renommer"), bot_top_position=5)
    noms = [action["name"] for action in plan_renomme.actions
            if action["kind"] == "salon" and action["mode"] == "creer"]
    assert "general - copie" in noms

    plan_exclu = construire_plan(
        manifeste, dest_guild, dest_channels, dest_roles,
        OptionsClonage(salons_exclus=("vocal",), roles_exclus=("Auditeur",)),
        bot_top_position=5)
    assert not any(action["name"] == "vocal" and action["mode"] == "creer"
                   for action in plan_exclu.actions)
    assert any("exclu par selection" in ignore for ignore in plan_exclu.ignores)


def test_plan_blocks_role_creation_without_hierarchy_room():
    manifeste = source_manifest()
    plan = construire_plan(manifeste, {"id": "500000000000000001", "name": "Dest"},
                           [], [], OptionsClonage(), bot_top_position=1)
    role = next(action for action in plan.actions if action["kind"] == "role")
    assert role["mode"] == "bloquer"
    assert plan.avertissements


class FakeCloneAPI:
    def __init__(self, fail_on=None, rate_limit_on=None):
        self.calls = []
        self.fail_on = fail_on
        self.rate_limit_on = rate_limit_on
        self.counter = 0

    def creer_role(self, guild_id, payload, reason=None):
        self.calls.append(("role", payload))
        return {"id": "700000000000000001", **payload}

    def creer_salon(self, guild_id, payload, reason=None):
        self.calls.append(("salon", payload))
        self.counter += 1
        if self.fail_on and payload.get("name") == self.fail_on:
            raise DiscordForbiddenError("refus simule", status=403)
        if self.rate_limit_on and payload.get("name") == self.rate_limit_on:
            from modules.discord.discord_api import DiscordRateLimitError
            raise DiscordRateLimitError("limite simulee", status=429)
        return {"id": f"8000000000000000{self.counter:02d}", **payload}


def test_executor_maps_created_roles_to_channel_overwrites():
    manifeste = source_manifest()
    plan = construire_plan(manifeste, {"id": "500000000000000001", "name": "Dest"},
                           [], [], OptionsClonage(), bot_top_position=5)
    api = FakeCloneAPI()
    resultat = executer_plan(api, plan)
    assert resultat.statut == "reussi"
    assert resultat.compter() == {"roles": 1, "categories": 1, "salons": 3}
    assert resultat.correspondances["roles"]["300000000000000001"] == "700000000000000001"
    categorie = next(payload for kind, payload in api.calls
                     if kind == "salon" and payload.get("name") == "Audit")
    assert categorie["type"] == 4
    assert categorie["permission_overwrites"][0]["id"] == "700000000000000001"
    general = next(payload for kind, payload in api.calls
                   if kind == "salon" and payload.get("name") == "general")
    cibles = {surcharge["id"] for surcharge in general["permission_overwrites"]}
    assert "700000000000000001" in cibles  # role source remappe
    assert "500000000000000001" in cibles  # @everyone -> guild destination
    assert "400000000000000001" not in cibles  # membre jamais copie


def test_executor_reports_partial_failure_and_continues():
    manifeste = source_manifest()
    plan = construire_plan(manifeste, {"id": "500000000000000001", "name": "Dest"},
                           [], [], OptionsClonage(), bot_top_position=5)
    resultat = executer_plan(FakeCloneAPI(fail_on="vocal"), plan)
    assert resultat.statut == "partiel"
    assert "vocal" not in resultat.crees["salons"]
    assert any("vocal" in erreur for erreur in resultat.erreurs)
    assert "forum" in resultat.crees["salons"]
    rapport = resultat.rapport()
    assert rapport["statut"] == "partiel"
    assert "erreurs" in rapport


def test_executor_stops_on_rate_limit_without_claiming_success():
    manifeste = source_manifest()
    plan = construire_plan(manifeste, {"id": "500000000000000001", "name": "Dest"},
                           [], [], OptionsClonage(), bot_top_position=5)
    resultat = executer_plan(FakeCloneAPI(rate_limit_on="vocal"), plan)
    assert resultat.statut == "partiel"
    assert "forum" not in resultat.crees["salons"]
    assert any("limite" in note.casefold() for note in resultat.notes)


def test_executor_can_be_cancelled_between_actions():
    manifeste = source_manifest()
    plan = construire_plan(manifeste, {"id": "500000000000000001", "name": "Dest"},
                           [], [], OptionsClonage(), bot_top_position=5)
    appels = {"n": 0}

    def annulation():
        appels["n"] += 1
        return appels["n"] > 1

    resultat = executer_plan(FakeCloneAPI(), plan, annulation=annulation)
    assert resultat.statut == "annule"
    assert any("Annulation" in note for note in resultat.notes)


class FakeGuildAPI:
    def __init__(self, permissions_value):
        self.permissions_value = permissions_value

    def guild(self, guild_id):
        return {"id": guild_id, "name": "Dest", "owner_id": "1"}

    def guild_channels(self, guild_id):
        return []

    def guild_roles(self, guild_id):
        return [{"id": guild_id, "name": "@everyone", "permissions": "0", "position": 0},
                {"id": "2", "name": "bot", "permissions": str(self.permissions_value),
                 "position": 5}]

    def guild_member(self, guild_id, bot_id):
        return {"user": {"id": bot_id}, "roles": ["2"]}


def test_destination_permission_check_reports_missing_bits():
    infos = charger_destination(FakeGuildAPI(perms.MANAGE_CHANNELS), "9", "2")
    assert "Gerer les roles" in infos["manquantes"]
    assert "Gerer les salons" not in infos["manquantes"]

    infos_admin = charger_destination(FakeGuildAPI(perms.ADMINISTRATOR), "9", "2")
    assert infos_admin["manquantes"] == []
    assert infos_admin["bot_top"] == 5
