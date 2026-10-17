import importlib
import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

import modules.cyber.api_contract as api
import modules.cyber.tls_policy as tls


SPEC = {
    "openapi": "3.0.0",
    "info": {"title": "Lab API", "version": "1.0.0"},
    "paths": {
        "/items": {
            "get": {
                "operationId": "listItems",
                "parameters": [
                    {"name": "limit", "in": "query",
                     "schema": {"type": "integer", "minimum": 1, "maximum": 50}},
                ],
                "responses": {"200": {"description": "ok"}},
            },
            "post": {
                "operationId": "createItem",
                "requestBody": {"content": {"application/json": {"schema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "minLength": 3, "maxLength": 10},
                        "kind": {"type": "string", "enum": ["a", "b"]},
                    },
                }}}},
                "responses": {"201": {"description": "cree"}},
            },
        },
        "/items/{id}": {
            "get": {
                "parameters": [{"name": "id", "in": "path",
                                "schema": {"type": "string", "format": "uuid"}}],
                "responses": {"200": {"description": "ok"}},
            },
            "delete": {"responses": {}},
        },
    },
}


def test_chargement_et_validation_openapi(tmp_path):
    fichier = tmp_path / "spec.json"
    fichier.write_text(json.dumps(SPEC), encoding="utf-8")
    spec = api.charger_contrat(fichier)
    assert spec["info"]["title"] == "Lab API"

    problemes = api.valider_contrat(spec)
    assert any("aucune reponse" in p["message"] for p in problemes)
    assert any(p["element"] == "DELETE /items/{id}" for p in problemes)

    incomplet = {"openapi": "3.0.0", "paths": {}}
    messages = [p["message"] for p in api.valider_contrat(incomplet)]
    assert any("info" in message for message in messages)
    assert any("aucune route" in message for message in messages)

    reference = {"openapi": "3.0.0", "info": {"title": "x", "version": "1"},
                 "paths": {"/a": {"get": {"responses": {"200": {"description": "ok"}},
                                          "parameters": [{"name": "q", "in": "query",
                                                          "schema": {"$ref": "#/components/schemas/Absent"}}]}}}}
    assert any("reference absent" in p["message"] for p in api.valider_contrat(reference))

    defini = {"openapi": "3.0.0", "info": {"title": "x", "version": "1"},
              "components": {"schemas": {"Item": {"type": "object"}}},
              "paths": {"/a": {"get": {
                  "responses": {"200": {"description": "ok"}},
                  "parameters": [{"name": "q", "in": "query",
                                  "schema": {"$ref": "#/components/schemas/Item"}}]}}}}
    assert not any("reference absent" in p["message"] for p in api.valider_contrat(defini))


def test_chargement_refuse_les_entrees_invalides(tmp_path):
    with pytest.raises(ValueError):
        api.charger_contrat(tmp_path / "absent.json")
    casse = tmp_path / "casse.json"
    casse.write_text("{", encoding="utf-8")
    with pytest.raises(ValueError):
        api.charger_contrat(casse)
    liste = tmp_path / "liste.json"
    liste.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError):
        api.charger_contrat(liste)


def test_inventaire_et_fixtures_openapi(tmp_path):
    fichier = tmp_path / "spec.json"
    fichier.write_text(json.dumps(SPEC), encoding="utf-8")
    spec = api.charger_contrat(fichier)

    routes = api.inventaire_routes(spec)
    assert {(route["methode"], route["chemin"]) for route in routes} >= {
        ("GET", "/items"), ("POST", "/items"), ("GET", "/items/{id}"), ("DELETE", "/items/{id}")}
    assert all(route["reponses"] for route in routes if route["methode"] != "DELETE")

    cas = api.generer_cas(spec)
    assert cas
    assert any(c["valide"] and c["nom"] == "limit" for c in cas)
    assert any(not c["valide"] and c["variante"] == "sous-minimum" for c in cas)
    assert any(c["variante"] == "trop-court" for c in cas)
    assert any(c["variante"] == "enum-hors-liste" for c in cas)
    assert any(c["emplacement"] == "body" and c["nom"] == "name" for c in cas)

    rapport = api.rapport_contrat(spec)
    assert rapport["titre"] == "Lab API"
    assert rapport["routes"] and rapport["cas_de_test"]


def _certificat():
    return {
        "cert": {
            "serialNumber": "0A1B",
            "issuer": ((("commonName", "Autorite A"),),),
            "subject": ((("commonName", "example.tld"),),),
            "subjectAltName": (("DNS", "example.tld"), ("DNS", "www.example.tld")),
            "notBefore": "Jan  1 00:00:00 2026 GMT",
            "notAfter": "Jan  1 00:00:00 2027 GMT",
        },
        "der": b"certificat-brut",
        "version": "TLSv1.3",
        "cipher": ("TLS_AES_256_GCM_SHA384", 256, None),
    }


def test_instantane_et_comparaison_tls(monkeypatch, tmp_path):
    monkeypatch.setattr(tls, "HISTORY_FILE", tmp_path / "tls_history.json")

    premier = tls.instantane("example.tld", recuperer=lambda hote, port, timeout: _certificat())
    assert premier["serial"] == "0A1B"
    assert premier["sans"] == ["example.tld", "www.example.tld"]
    assert len(premier["fingerprint_sha256"]) == 64

    second = tls.instantane("example.tld", recuperer=lambda hote, port, timeout: _certificat())
    assert tls.comparer(premier, second)["modifie"] is False

    modifie = dict(second)
    modifie["serial"] = "0C2D"
    modifie["fingerprint_sha256"] = "b" * 64
    modifie["not_after"] = "Jan  1 00:00:00 2027 GMT"
    comparaison = tls.comparer(second, modifie)
    assert comparaison["modifie"] is True
    assert comparaison["renouvellement"] is True
    assert {change["champ"] for change in comparaison["changements"]} >= {
        "serial", "fingerprint_sha256"}

    tls.enregistrer(premier)
    tls.enregistrer(second)
    assert len(tls.charger_historique()) == 2
    assert "Comparaison TLS" in tls.exporter_markdown(comparaison)
    json.loads(tls.exporter_json(comparaison))


def test_comparaison_signale_les_risques():
    avant = {"hote": "h", "serial": "1", "fingerprint_sha256": "a",
             "issuer": "A", "tls_version": "TLSv1.3", "cipher": "X",
             "not_after": "Jan  1 00:00:00 2027 GMT"}
    apres = dict(avant, fingerprint_sha256="b", issuer="B", cipher="Y")
    resultat = tls.comparer(avant, apres)
    assert "changement d'autorite emettrice" in resultat["risques"]
    assert "suite de chiffrement modifiee" in resultat["risques"]
    assert "empreinte differente sans changement de numero de serie" in resultat["risques"]


def test_webhook_lab_posts_synthetic_payload_to_local_server():
    module = importlib.import_module("modules.cyber.webhook_lab")
    recu = {}

    class Recepteur(BaseHTTPRequestHandler):
        def do_POST(self):
            longueur = int(self.headers.get("Content-Length", "0"))
            recu["corps"] = json.loads(self.rfile.read(longueur))
            self.send_response(201)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok": true}')

        def log_message(self, *_args):
            pass

    serveur = ThreadingHTTPServer(("127.0.0.1", 0), Recepteur)
    thread = threading.Thread(target=serveur.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{serveur.server_port}/hook"
        resultat = module.envoyer_payload(url, module.payload_modele())
    finally:
        serveur.shutdown()
        serveur.server_close()

    assert resultat["ok"] is True
    assert resultat["statut"] == 201
    assert resultat["duree_ms"] >= 0
    assert resultat["erreur"] is None
    assert "ok" in resultat["corps"]
    assert recu["corps"]["event"] == "leakfr.webhook.test"
    assert set(recu["corps"]) == {"event", "message", "timestamp", "reference", "donnees"}


def test_webhook_lab_validates_input_and_reports_network_errors(monkeypatch):
    module = importlib.import_module("modules.cyber.webhook_lab")
    assert module.valider_url(" http://127.0.0.1:8000/hook ") == "http://127.0.0.1:8000/hook"
    for invalide in ("", "ftp://exemple.tld/hook", "http://", "http://exemple.tld/a b"):
        with pytest.raises(ValueError):
            module.valider_url(invalide)
    assert module.valider_timeout("2,5") == 2.5
    for invalide in ("zero", "0", "-1", "500"):
        with pytest.raises(ValueError):
            module.valider_timeout(invalide)

    payload = module.payload_modele()
    assert "hostname" not in json.dumps(payload).lower()
    assert "machine-id" not in json.dumps(payload)

    vide = socket.socket()
    vide.bind(("127.0.0.1", 0))
    port = vide.getsockname()[1]
    vide.close()
    refus = module.envoyer_payload(f"http://127.0.0.1:{port}/hook", payload, timeout=2)
    assert refus["ok"] is False
    assert refus["statut"] is None
    assert refus["erreur"]

    def delai_depasse(*_args, **_kwargs):
        raise module.requests.Timeout()

    monkeypatch.setattr(module.requests, "post", delai_depasse)
    expire = module.envoyer_payload("http://127.0.0.1:9/hook", payload, timeout=1)
    assert expire["ok"] is False
    assert "delai depasse" in expire["erreur"]
