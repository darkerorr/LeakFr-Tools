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


def test_menu_settings_key_opens_settings_and_returns_to_main_menu(monkeypatch):
    keys = iter(["s", "q"])
    transitions = []

    class FakeTouches:
        def __enter__(self):
            transitions.append("keyboard-enter")
            return self
        def __exit__(self, *args):
            transitions.append("keyboard-exit")
            return False
        def lire(self, timeout=0.04):
            return next(keys)

    class FakeLive:
        def __enter__(self):
            transitions.append("main-start")
            return self
        def __exit__(self, *args):
            transitions.append("main-exit")
            return False
        def update(self, *_args, **_kwargs):
            pass
        def stop(self):
            transitions.append("main-stop")
        def start(self):
            transitions.append("main-resume")

    monkeypatch.setattr(main, "Touches", FakeTouches)
    monkeypatch.setattr(main, "Live", lambda **_kwargs: FakeLive())
    monkeypatch.setattr(main, "_ecran_parametres", lambda: transitions.append("settings-open"))
    monkeypatch.setattr(main.console, "clear", lambda: None)
    assert main.menu_interactif() == "0"
    assert transitions == [
        "keyboard-enter", "main-start", "keyboard-exit", "main-stop",
        "settings-open", "keyboard-enter", "main-resume", "main-exit", "keyboard-exit",
    ]


def test_arrow_selector_moves_and_confirms_without_numeric_input(monkeypatch):
    import core.common as common_ui
    import os
    import select
    import termios
    import tty

    class FakeTTY:
        def isatty(self):
            return True
        def fileno(self):
            return 73

    class FakeLive:
        def __init__(self, **_kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *_args):
            return False
        def update(self, *_args, **_kwargs):
            pass

    keyboard = iter([b"\x1b", b"[B", b"\r"])
    monkeypatch.setattr(common_ui, "INTERACTIF", True)
    monkeypatch.setattr(common_ui.sys, "stdin", FakeTTY())
    monkeypatch.setattr(common_ui.sys, "stdout", FakeTTY())
    monkeypatch.setattr(common_ui, "Live", FakeLive)
    monkeypatch.setattr(select, "select", lambda *_args, **_kwargs: ([73], [], []))
    monkeypatch.setattr(os, "read", lambda _fd, _size: next(keyboard))
    monkeypatch.setattr(termios, "tcgetattr", lambda _fd: [])
    monkeypatch.setattr(termios, "tcsetattr", lambda *_args: None)
    monkeypatch.setattr(tty, "setcbreak", lambda _fd: None)

    assert common_ui.choisir_option("Test", ["Premier", "Second"]) == "Second"


def test_settings_screen_opens_submenu_and_applies_selection(monkeypatch):
    import core.common as common_ui
    from core.config import DEFAUTS

    monkeypatch.setattr(main, "_CONFIG", deepcopy(DEFAUTS))
    monkeypatch.setattr(main.console, "clear", lambda: None)
    monkeypatch.setattr(main, "sauvegarder", lambda _config: None)
    monkeypatch.setattr(main, "pause", lambda: None)
    choices = iter(["Style d'interface", "Compact", "Retour au menu principal"])
    seen_menus = []
    def choose(label, options, **_kwargs):
        seen_menus.append((label, list(options)))
        return next(choices)
    monkeypatch.setattr(main, "selectionner_option", choose)
    main._ecran_parametres()

    assert main._CONFIG["apparence"]["style_interface"] == "compact"
    assert common_ui.obtenir_config_ui()["style_interface"] == "compact"
    assert seen_menus[0][0] == "PARAMETRES"
    assert "Style d'interface" in seen_menus[0][1]
    assert seen_menus[1] == ("STYLE D'INTERFACE", ["Dashboard split", "Classique", "Compact"])


def test_encode_decode_tool_executes_selected_mode(monkeypatch):
    module = importlib.import_module("modules.utils.encode_decode")
    output = {}
    monkeypatch.setattr(module, "choisir_option", lambda *_args, **_kwargs: "Base64 encode")
    monkeypatch.setattr(module, "demander", lambda _label: "hello")
    monkeypatch.setattr(module, "kv", lambda _title, rows, _color: output.update(rows))
    module.encode_decode()
    assert output["Sortie"] == "aGVsbG8="


def test_date_calculator_executes_selected_mode_with_local_input(monkeypatch):
    module = importlib.import_module("modules.utils.date_calculator")
    output = {}
    answers = iter(["2026-01-01", "2026-01-12"])
    monkeypatch.setattr(module, "choisir_option", lambda _title, options: options[0])
    monkeypatch.setattr(module, "demander", lambda *_args, **_kwargs: next(answers))
    monkeypatch.setattr(module, "kv", lambda title, rows, _color: output.update({"title": title, **dict(rows)}))
    module.calculer_dates()
    assert output["Jours signes"] == 11
    assert output["Semaines completes"] == 1


def test_wordlist_generator_runs_and_writes_requested_file(monkeypatch, tmp_path):
    module = importlib.import_module("modules.pentest.wordlist_generator")
    destination = tmp_path / "wordlist.txt"
    answers = iter(["test", str(destination)])
    monkeypatch.setattr(module, "choisir_option", lambda *_args, **_kwargs: "Mutations d'un mot")
    monkeypatch.setattr(module, "demander", lambda *_args, **_kwargs: next(answers))
    module.wordlist_gen()
    generated = destination.read_text(encoding="utf-8").splitlines()
    assert "test" in generated
    assert "test123" in generated
    assert len(generated) > 10


def test_concurrent_modules_import_the_executor_explicitly():
    import ast
    import importlib

    for path in Path("modules").rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        if "concurrent.futures" not in source:
            continue
        tree = ast.parse(source)
        imports_concurrent = any(
            isinstance(node, ast.Import) and any(
                alias.name == "concurrent.futures" or alias.name == "concurrent"
                for alias in node.names
            )
            for node in ast.walk(tree)
        )
        assert imports_concurrent, f"{path} uses concurrent.futures without import"
        importlib.import_module(".".join(path.with_suffix("").parts))


def test_pseudo_search_runs_concurrently_with_mocked_responses(monkeypatch):
    from contextlib import contextmanager
    from types import SimpleNamespace
    from modules.osint import pseudo_search as search_module

    class Progress:
        def add_task(self, *args, **kwargs):
            return 1
        def advance(self, *args, **kwargs):
            pass

    @contextmanager
    def fake_barre():
        yield Progress()

    monkeypatch.setattr(search_module, "demander", lambda *_args, **_kwargs: "example_test")
    monkeypatch.setattr(search_module, "barre", fake_barre)
    monkeypatch.setattr(search_module.requests, "get", lambda *args, **kwargs: SimpleNamespace(status_code=404))
    search_module.recherche_pseudo()


def test_dns_bruteforce_runs_concurrently_with_mocked_resolver(monkeypatch, tmp_path):
    from contextlib import contextmanager
    import importlib
    dns_module = importlib.import_module("modules.pentest.dns_bruteforce")

    wordlist = tmp_path / "hosts.txt"
    wordlist.write_text("www\nmail\n", encoding="utf-8")

    class Progress:
        def add_task(self, *args, **kwargs):
            return 1
        def advance(self, *args, **kwargs):
            pass

    @contextmanager
    def fake_barre():
        yield Progress()

    monkeypatch.setattr(dns_module, "warn_pentest", lambda: True)
    answers = iter(["example.test", str(wordlist)])
    monkeypatch.setattr(dns_module, "demander", lambda *_args, **_kwargs: next(answers))
    monkeypatch.setattr(dns_module, "barre", fake_barre)
    def fake_resolve(host):
        if host.startswith("www."):
            return host, [], ["192.0.2.10"]
        raise OSError("not found")
    monkeypatch.setattr(dns_module.socket, "gethostbyname_ex", fake_resolve)
    dns_module.dns_bruteforce()


def test_directory_bruteforce_runs_concurrently_with_mocked_http(monkeypatch, tmp_path):
    from contextlib import contextmanager
    import importlib
    from types import SimpleNamespace
    dir_module = importlib.import_module("modules.pentest.dir_bruteforce")

    wordlist = tmp_path / "paths.txt"
    wordlist.write_text("admin\nrobots.txt\n", encoding="utf-8")

    class Progress:
        def add_task(self, *args, **kwargs):
            return 1
        def advance(self, *args, **kwargs):
            pass

    @contextmanager
    def fake_barre():
        yield Progress()

    monkeypatch.setattr(dir_module, "warn_pentest", lambda: True)
    answers = iter(["http://example.test", str(wordlist), "200"])
    monkeypatch.setattr(dir_module, "demander", lambda *_args, **_kwargs: next(answers))
    monkeypatch.setattr(dir_module, "barre", fake_barre)
    def fake_get(url, **_kwargs):
        status = 200 if url.endswith("/admin") else 404
        return SimpleNamespace(status_code=status, content=b"ok", headers={"Content-Type": "text/plain"})
    monkeypatch.setattr(dir_module.requests, "get", fake_get)
    dir_module.dir_bruteforce()


def test_screenshots_cover_every_module_and_readme_link():
    screenshots = Path("docs/screenshots")
    assert (screenshots / "menu-principal.svg").is_file()
    module_images = list((screenshots / "modules").rglob("*.svg"))
    assert len(module_images) == sum(len(options) for _, _, options in main.CATALOGUE)
    for readme in Path("modules").glob("*/README.md"):
        for link in re.findall(r"\]\(([^)]+\.svg)\)", readme.read_text(encoding="utf-8")):
            assert (readme.parent / link).resolve().is_file(), (readme, link)
