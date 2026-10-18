"""Tests des comportements réels : clé NASA, réseau local, zéro simulation.

Les tests réseau de ce fichier n'appellent aucun service externe : ils ouvrent
une vraie socket locale ou s'en tiennent à des valeurs mesurées localement.
"""
import importlib
import json
import shutil
import socket
from pathlib import Path

import pytest

from modules.astro import nasa
from modules.pentest import local_network_scan as lan

RACINE = Path(__file__).resolve().parents[1]


def _port_ouvert():
    """Ouvre une vraie socket d'écoute locale et retourne (socket, port)."""
    serveur = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    serveur.bind(("127.0.0.1", 0))
    serveur.listen(1)
    return serveur, serveur.getsockname()[1]


def _port_ferme():
    """Port réellement libre : ouvert puis refermé avant le test."""
    serveur = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    serveur.bind(("127.0.0.1", 0))
    port = serveur.getsockname()[1]
    serveur.close()
    return port


def test_cle_nasa_priorite_environnement(tmp_path, monkeypatch):
    monkeypatch.setenv("LEAKFR_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("NASA_API_KEY", "cle-de-test-env")
    importlib.reload(importlib.import_module("core.config"))
    cle, source = nasa.cle_api()
    assert cle == "cle-de-test-env"
    assert "NASA_API_KEY" in source


def test_cle_nasa_utilise_le_reglage_local_puis_la_cle_publique(tmp_path, monkeypatch):
    monkeypatch.delenv("NASA_API_KEY", raising=False)
    monkeypatch.setenv("LEAKFR_DATA_DIR", str(tmp_path))
    importlib.reload(importlib.import_module("core.config"))
    (tmp_path / "settings.json").write_text(
        json.dumps({"api_keys": {"nasa_api_key": "cle-du-reglage"}}), encoding="utf-8")

    params, source = nasa.params_nasa({"date": "2026-10-18"})
    assert params["api_key"] == "cle-du-reglage"
    assert params["date"] == "2026-10-18"
    assert nasa.avertir_si_publique(source) is False

    (tmp_path / "settings.json").write_text(json.dumps({"api_keys": {}}), encoding="utf-8")
    params, source = nasa.params_nasa()
    assert params["api_key"] == nasa.CLE_PUBLIQUE
    assert nasa.avertir_si_publique(source) is True


def test_ip_locale_est_mesuree_et_reseau_deduit():
    adresse = lan.ip_locale()
    assert adresse is None or adresse.count(".") == 3
    assert lan.reseau_par_defaut(None) is None
    assert lan.reseau_par_defaut("192.168.4.37") == "192.168.4.0/24"
    if adresse:
        attendu = ".".join(adresse.split(".")[:3]) + ".0/24"
        assert lan.reseau_par_defaut(adresse) == attendu


def test_sonder_tcp_reel_sur_une_socket_locale():
    serveur, port = _port_ouvert()
    try:
        assert lan.sonder_tcp("127.0.0.1", ports=[port], timeout=1.0) == port
        actif, methode = lan.sonder_hote("127.0.0.1", utiliser_icmp=False,
                                         ports=[port], timeout=1.0)
        assert actif is True and methode == f"TCP {port}"
    finally:
        serveur.close()
    ferme = _port_ferme()
    assert lan.sonder_tcp("127.0.0.1", ports=[ferme], timeout=0.5) is None


def test_ping_icmp_reel_ne_leve_jamais_d_exception():
    resultat = lan.ping_icmp("127.0.0.1")
    if shutil.which("ping"):
        assert isinstance(resultat, bool)
    else:
        assert resultat is None
    # Adresse de documentation réservée : jamais d'exception, jamais True.
    assert lan.ping_icmp("192.0.2.1") in (False, None)


def test_aucune_simulation_dans_le_code_des_outils():
    """Garde-fou : les phrases de simulation bannies ne doivent pas revenir."""
    interdits = ("mode simulation", "purement visuel", "ICMP simulé",
                 "simulé via connect")
    for chemin in list((RACINE / "core").rglob("*.py")) + \
            list((RACINE / "modules").rglob("*.py")):
        texte = chemin.read_text(encoding="utf-8", errors="replace")
        for interdit in interdits:
            assert interdit not in texte, f"{interdit!r} encore présent dans {chemin}"


def test_cle_nasa_publique_limitee_au_module_dedie():
    """DEMO_KEY n'existe que dans le module de clé, jamais codée en dur ailleurs."""
    for chemin in list((RACINE / "core").rglob("*.py")) + \
            list((RACINE / "modules").rglob("*.py")):
        if chemin.name == "nasa.py":
            continue
        assert "DEMO_KEY" not in chemin.read_text(encoding="utf-8", errors="replace"), chemin


def test_le_scan_reseau_ne_suppose_aucune_adresse_par_defaut(monkeypatch):
    """Sans IP locale détectable, l'outil ne scanne pas un réseau inventé."""
    monkeypatch.setattr(lan, "ip_locale", lambda: None)
    demandes = []
    monkeypatch.setattr(lan, "demander",
                        lambda label, defaut=None: demandes.append(defaut) or "")
    lan.scan_reseau_local()
    assert demandes == [None]


def test_scan_reseau_local_sur_loopback_reel(monkeypatch):
    """Scan réel d'une plage loopback appartenant à la machine de test."""
    monkeypatch.setattr(lan, "demander",
                        lambda label, defaut=None: "127.0.0.0/29")
    monkeypatch.setattr(lan, "sonder_hote", lan.sonder_hote)
    lan.scan_reseau_local()
