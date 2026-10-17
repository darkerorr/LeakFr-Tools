import json

import pytest

import modules.osint.archive_diff as archive


HTML_A = """
<html><head><style>body{color:red}</style><script>var x=1;</script></head>
<body><h1>Titre</h1><p>Prix : 10 EUR</p><p>Stock : disponible</p></body></html>
"""

HTML_B = """
<html><head><title>Titre</title></head>
<body><h1>Titre</h1><p>Prix : 12 EUR</p><p>Stock : epuise</p></body></html>
"""


class _Reponse:
    def __init__(self, payload=None, texte="", code=200):
        self._payload = payload
        self.text = texte
        self.status_code = code

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise archive.requests.HTTPError(f"HTTP {self.status_code}")


class _Session:
    def __init__(self, reponses):
        self._reponses = list(reponses)
        self.appels = []

    def get(self, url, **kwargs):
        self.appels.append((url, kwargs))
        return self._reponses.pop(0)


def test_extraction_du_texte_ignore_scripts_et_styles():
    texte = archive.extraire_texte(HTML_A)
    assert "Titre" in texte
    assert "Prix" in texte
    assert "var x=1" not in texte
    assert "body{color" not in texte


def test_comparaison_compte_ajouts_et_suppressions():
    different = archive.comparer_textes(archive.extraire_texte(HTML_A),
                                        archive.extraire_texte(HTML_B))
    assert different["identique"] is False
    assert different["ajouts"] >= 1
    assert different["suppressions"] >= 1
    assert different["diff"]

    identique = archive.comparer_textes("a\nb", "a\nb")
    assert identique["identique"] is True
    assert identique["ajouts"] == 0 and identique["suppressions"] == 0


def test_liste_des_captures_et_gestion_des_erreurs():
    charge = [["timestamp", "original", "statuscode", "mimetype"],
              ["20240101000000", "http://example.tld/", "200", "text/html"],
              ["20250101000000", "http://example.tld/", "200", "text/html"]]
    session = _Session([_Reponse(payload=charge)])
    captures = archive.lister_captures("example.tld", session=session)
    assert [capture["timestamp"] for capture in captures] == [
        "20240101000000", "20250101000000"]
    assert session.appels[0][1]["timeout"] == 20

    casse = _Session([_Reponse(payload=None, code=503)])
    with pytest.raises(ValueError):
        archive.lister_captures("example.tld", session=casse)


def test_analyse_de_deux_captures_et_exports():
    capture_a = {"timestamp": "20240101000000", "url": "http://example.tld/"}
    capture_b = {"timestamp": "20250101000000", "url": "http://example.tld/"}
    session = _Session([_Reponse(texte=HTML_A), _Reponse(texte=HTML_B)])

    resultat = archive.analyser("example.tld", capture_a, capture_b, session=session)
    assert resultat["comparaison"]["identique"] is False
    assert resultat["captures"][0]["timestamp"] == "20240101000000"
    assert "observation historique" in resultat["avertissement"]
    assert session.appels[0][0].endswith("20240101000000id_/http://example.tld/")
    assert session.appels[0][1]["stream"] is True
    assert [entree["timestamp"] for entree in resultat["chronologie"]] == [
        "20240101000000", "20250101000000"]
    assert resultat["chronologie"][0]["archive_url"].endswith(
        "/20240101000000/http://example.tld/")

    markdown = archive.exporter_markdown(resultat)
    assert "Archive Change Watcher" in markdown
    assert "20240101000000" in markdown
    assert "web.archive.org/web/20240101000000/http://example.tld/" in markdown
    json.loads(archive.exporter_json(resultat))


def test_capture_indisponible_leve_une_erreur_claire():
    session = _Session([_Reponse(code=404)])
    with pytest.raises(ValueError) as erreur:
        archive.recuperer_texte({"timestamp": "20240101000000",
                                 "url": "http://example.tld/"}, session=session)
    assert "indisponible" in str(erreur.value)


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
