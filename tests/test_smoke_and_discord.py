from copy import deepcopy
import importlib
import io
import json
import re
import socket
from pathlib import Path

import pytest

import main
from modules.discord.gateway_bot import DiscordGatewayClient

bot_panel_module = importlib.import_module("modules.discord.bot_panel")


def test_catalogue_contains_all_modules_and_maps_actions():
    total = sum(len(options) for _, _, options in main.CATALOGUE)
    assert len(main.CATALOGUE) == 7
    assert total == 81
    assert len(main.ACTIONS) == total
    assert main.SEL == main.NUM_IDX["1"]
    assert main.FLAT[main.SEL]["nom"] == "Recherche de pseudo"
    utility_names = {name for name, _, _ in main.CATALOGUE[5][2]}
    assert {"Generateur de mot de passe", "Formateur JSON", "Analyseur de texte",
            "Generateur UUID", "Convertisseur de bases", "Calculateur de dates"} <= utility_names


def test_help_and_version_cli(capsys, monkeypatch):
    monkeypatch.setattr("sys.argv", ["main.py", "--help"])
    with pytest.raises(SystemExit) as help_exit:
        main.main()
    assert help_exit.value.code == 0
    assert "--simple" in capsys.readouterr().out

    monkeypatch.setattr("sys.argv", ["main.py", "--version"])
    with pytest.raises(SystemExit) as version_exit:
        main.main()
    assert version_exit.value.code == 0
    assert "LeakFr-Tools 2.0" in capsys.readouterr().out


def test_panel_snowflake_and_channel_validation():
    assert bot_panel_module._valid_snowflake("123456789012345678")
    assert not bot_panel_module._valid_snowflake("1234")
    assert not bot_panel_module._valid_snowflake("../channels")
    assert bot_panel_module._slug_channel_name("  Audit Sécurité / 2026 ") == "audit-securite-2026"
    with pytest.raises(ValueError):
        bot_panel_module._slug_channel_name(" !!! ")


def test_permission_summary_calculates_role_union(monkeypatch):
    class Response:
        status_code = 200

        @staticmethod
        def json():
            return {"roles": ["222222222222222222"]}

    monkeypatch.setattr(bot_panel_module, "_request", lambda *args, **kwargs: Response())
    roles = [
        {"id": "111111111111111111", "permissions": "8"},
        {"id": "222222222222222222", "permissions": str(0x10 | 0x2000)},
    ]
    permissions, status = bot_panel_module._permission_summary(
        {}, "333333333333333333", "444444444444444444", roles
    )
    assert status == 200
    assert permissions == 0x10 | 0x2000


def test_guild_export_does_not_include_secrets_or_message_content(tmp_path, monkeypatch):
    monkeypatch.setattr(bot_panel_module, "EXPORTS_DIR", str(tmp_path))
    path = bot_panel_module._save_guild_audit(
        "123456789012345678",
        {
            "guild": {"id": "123", "name": "Lab", "owner_id": "456"},
            "channels": [{"id": "789", "name": "general", "token": "should-not-export"}],
            "roles": [{"id": "456", "name": "@everyone", "permissions": "0"}],
            "members": [{"content": "private message"}],
        },
    )
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["guild"]["name"] == "Lab"
    assert "token" not in path.read_text(encoding="utf-8")
    assert "private message" not in path.read_text(encoding="utf-8")
    assert data["members_loaded"] == 1


def test_websocket_frame_roundtrip_with_buffered_frames():
    client_socket, server_socket = socket.socketpair()
    try:
        client = DiscordGatewayClient("test-token")
        client.sock = client_socket
        server_socket.sendall(b"\x81\x02hi\x81\x02ok")
        opcode, payload, rest = client._recv_frame()
        assert (opcode, payload) == (1, b"hi")
        opcode, payload, rest = client._recv_frame(rest)
        assert (opcode, payload) == (1, b"ok")
    finally:
        client_socket.close()
        server_socket.close()


def test_websocket_control_frame_masks_ping_payload():
    class FakeSocket:
        sent = b""

        def sendall(self, frame):
            self.sent = bytes(frame)

    client = DiscordGatewayClient("test-token")
    fake = FakeSocket()
    client.sock = fake
    client._send_control_frame(0xA, b"ping")
    frame = fake.sent
    assert frame[0] == 0x8A
    assert frame[1] & 0x80
    mask = frame[2:6]
    assert bytes(byte ^ mask[i % 4] for i, byte in enumerate(frame[6:])) == b"ping"


def test_visual_settings_are_persistent_and_apply_to_rendered_menu(monkeypatch):
    from core.config import DEFAUTS
    from core.common import obtenir_config_ui, obtenir_theme

    config = deepcopy(DEFAUTS)
    config["apparence"].update({
        "theme_actif": "bleu_electrique",
        "style_interface": "compact",
        "couleur_accent": "#12abef",
        "afficher_badges_categories": False,
        "afficher_panneau_lateral": False,
    })
    monkeypatch.setattr(main, "_CONFIG", config)
    main._appliquer_configuration_visuelle()
    assert obtenir_config_ui()["style_interface"] == "compact"
    assert obtenir_theme()["principale"] == "#12abef"
    rendered = main.construire_menu(main.NUM_IDX["1"], "", 0)
    from rich.console import Console
    terminal = Console(file=io.StringIO(), width=100, force_terminal=True, record=True)

    terminal.print(rendered)
    assert "INSPECTEUR" not in terminal.export_text()
    monkeypatch.setattr(main, "_CONFIG", deepcopy(DEFAUTS))
    main._appliquer_configuration_visuelle()


def test_screenshots_cover_every_module_and_readme_link():
    screenshots = Path("docs/screenshots")
    assert (screenshots / "menu-principal.svg").is_file()
    module_images = list((screenshots / "modules").rglob("*.svg"))
    assert len(module_images) == sum(len(options) for _, _, options in main.CATALOGUE)
    for readme in Path("modules").glob("*/README.md"):
        for link in re.findall(r"\]\(([^)]+\.svg)\)", readme.read_text(encoding="utf-8")):
            assert (readme.parent / link).resolve().is_file(), (readme, link)
