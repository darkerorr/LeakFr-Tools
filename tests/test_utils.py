from copy import deepcopy
import importlib
import io
import json
import re
import socket
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

import main
from modules.discord.gateway_bot import DiscordGatewayClient

bot_panel_module =importlib.import_module('modules.discord.bot_panel')


def test_http_edge_corpus_is_local_deterministic_and_includes_boundaries(tmp_path, monkeypatch):
    module = importlib.import_module("modules.utils.http_edge_corpus")
    corpus = module.construire_corpus_http()
    ids = {case['id'] for case in corpus['cases']}
    assert corpus["network_requests"] is False
    assert {"duplicate-conflicting", "crlf-in-value", "oversized-value-8k",
            'conflicting-framing', 'unicode-value'}<= ids
    assert corpus==module.construire_corpus_http()
    destination = tmp_path / "fixtures" / "http.json"
    monkeypatch.setattr(module, 'demander', lambda *_args, **_kwargs: str(destination))
    module.generer_corpus_http()
    generated = json.loads(destination.read_text(encoding="utf-8"))
    assert generated ==corpus


def test_system_audit_is_local_deterministic_and_exposes_no_secrets(monkeypatch):
    module = importlib.import_module("modules.utils.system_audit")

    def connexion_interdite(*_args, **_kwargs):
        raise AssertionError("l'audit ne doit ouvrir aucune connexion")

    monkeypatch.setattr(socket.socket, 'connect', connexion_interdite)
    monkeypatch.setattr(socket.socket, "connect_ex", connexion_interdite)
    infos = module.collecter_identite()
    assert infos['network_requests'] is False
    assert infos["hwid"] == module.calculer_hwid(infos["composants"])
    assert len(infos["hwid"].replace("-", ""))==32
    assert infos['hwid'] == module.collecter_identite()['hwid']
    assert infos["systeme"]["hote"]
    assert not hasattr(module, "requests")
    assert module.calculer_hwid({'machine-id':'abc'}) ==module.calculer_hwid({'machine-id': 'abc'})
    assert module.calculer_hwid({"machine-id": "abc"}) != module.calculer_hwid({"machine-id": "def"})


def test_encode_decode_tool_executes_selected_mode(monkeypatch):
    module=importlib.import_module("modules.utils.encode_decode")
    output = {}
    monkeypatch.setattr(module, "choisir_option", lambda *_args, **_kwargs: "Base64 encode")
    monkeypatch.setattr(module, "demander", lambda _label: "hello")
    monkeypatch.setattr(module, 'kv', lambda _title, rows, _color: output.update(rows))
    module.encode_decode()
    assert output["Sortie"] =="aGVsbG8="


def test_date_calculator_executes_selected_mode_with_local_input(monkeypatch):
    module= importlib.import_module('modules.utils.date_calculator')
    output = {}
    answers = iter(["2026-01-01", "2026-01-12"])
    monkeypatch.setattr(module, 'choisir_option', lambda _title, options: options[0])
    monkeypatch.setattr(module, "demander", lambda *_args, **_kwargs: next(answers))
    monkeypatch.setattr(module, "kv", lambda title, rows, _color: output.update({"title": title, **dict(rows)}))
    module.calculer_dates()
    assert output["Jours signes"] == 11
    assert output["Semaines completes"] ==1


def test_concurrent_modules_import_the_executor_explicitly():
    import ast
    import importlib

    for path in Path('modules').rglob('*.py'):
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
