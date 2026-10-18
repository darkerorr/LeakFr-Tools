import base64
import json

import pytest

from modules.discord.emoji_cloner import (
    OptionsEmoji, detecter_format, exporter_emojis, importer_entrees,
    importer_manifeste, limite_emojis, normaliser_nom, planifier_import,
    resoudre_nom, telecharger_emoji, verifier_url,
)
from modules.discord.discord_api import DiscordForbiddenError

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64
GIF= b"GIF89a" + b"0" * 64


class FakeDownloadResponse:
    def __init__(self, status=200, contenu=PNG, headers=None):
        self.status_code = status
        self.contenu = contenu
        self.headers= headers or {'Content-Length': str(len(contenu))}

    def iter_content(self, _taille):
        yield self.contenu


class FakeSession:
    def __init__(self, reponses):
        self.reponses =list(reponses)
        self.urls = []
        self.closed =False

    def get(self, url, **_kwargs):
        self.urls.append(url)
        return self.reponses.pop(0)

    def close(self):
        self.closed = True


def emoji(identifiant, nom, anime=False):
    return {'id':str(identifiant), 'name': nom, 'animated': anime}


def test_detection_et_validation_des_urls():
    assert detecter_format(PNG) =="png"
    assert detecter_format(GIF)== "gif"
    assert detecter_format(b'pas une image') is None
    assert verifier_url("https://cdn.discordapp.com/emojis/123.png")
    for url in ("http://cdn.discordapp.com/emojis/1.png",
                'https://evil.example/emojis/1.png',
                "https://discord.com.evil.example/emojis/1.png"):
        with pytest.raises(ValueError):
            verifier_url(url)


def test_telechargement_borne_refuse_les_echecs_et_les_formats_inconnus():
    session = FakeSession([FakeDownloadResponse(404)])
    with pytest.raises(ValueError):
        telecharger_emoji(session, emoji(1, 'test'))
    session = FakeSession([FakeDownloadResponse(contenu=b"pas une image")])
    with pytest.raises(ValueError):
        telecharger_emoji(session, emoji(1, 'test'))
    session = FakeSession([FakeDownloadResponse(
        contenu=PNG, headers={"Content-Length": str(3 * 1024 * 1024)})])
    with pytest.raises(ValueError):
        telecharger_emoji(session, emoji(1, "test"))


def test_noms_et_conflits():
    assert normaliser_nom("Mon Emoji !")== "Mon_Emoji"
    assert normaliser_nom('é') == 'emoji'
    assert resoudre_nom("test", ["test"], "ignorer") is None
    assert resoudre_nom("test", ["test"], "renommer")== "test_2"
    assert resoudre_nom('test', ['test'], 'renommer', 'lab_') == 'lab_test'
    assert limite_emojis(0, False) == 50 and limite_emojis(3, True) == 250


def test_planifie_statique_anime_et_capacite():
    source =[emoji(1, "statique"), emoji(2, "anime", True), emoji(3, "libre")]
    destination= [emoji(9, 'statique'), emoji(8, 'anime', True)]
    appels = []

    def telecharger(item):
        appels.append(item["name"])
        return (GIF if item.get("animated") else PNG), ("gif" if item.get("animated") else "png"), ""

    entrees = planifier_import(source, destination, telecharger,
                               OptionsEmoji(conflits="ignorer"), premium_tier=0)
    assert [entree.statut for entree in entrees] == ['ignore', 'ignore', 'pret']
    assert all(entree.raison for entree in entrees[:2])
    assert entrees[2].nom_cible== "libre"
    assert appels== ['statique', 'anime', 'libre']

    entrees =planifier_import(source, destination, telecharger,
                               OptionsEmoji(conflits='renommer', prefixe='src_'))
    assert entrees[0].nom_cible== "src_statique"
    assert entrees[1].nom_cible =="src_anime"
    assert all(entree.statut== 'pret' for entree in entrees)


def test_capacite_atteinte_marque_les_emojis_ignores():
    source = [emoji(index, f"e{index}") for index in range(52)]
    destination = [emoji(1000 + index, f"d{index}") for index in range(50)]
    entrees = planifier_import(source, destination,
                               lambda _emoji: (PNG, "png", ""),
                               OptionsEmoji(), premium_tier=0)
    assert sum(1 for entree in entrees if entree.statut == 'pret') == 0
    assert any("capacite" in entree.raison for entree in entrees)


class FakeEmojiAPI:
    def __init__(self, refuse=None):
        self.refuse = refuse or set()
        self.created = []

    def creer_emoji(self, guild_id, payload, reason=None):
        self.created.append(payload)
        if payload["name"] in self.refuse:
            raise DiscordForbiddenError('emoji refuse', status=403)
        return {"id":str(900 + len(self.created)), "name": payload["name"]}

    def guild_emojis(self, guild_id):
        return []


def test_import_reel_compte_les_succes_et_les_echecs():
    source =[emoji(1, "ok_statique"), emoji(2, "refuse", True)]
    entrees = planifier_import(source, [],
                               lambda item: ((GIF, "gif", "") if item.get("animated")
                                             else (PNG, "png", "")),
                               OptionsEmoji())
    api= FakeEmojiAPI(refuse={"refuse"})
    resultat =importer_entrees(api, "123456789012345678", entrees)
    assert [item['nom'] for item in resultat['importes']] == ['ok_statique']
    assert resultat["erreurs"][0]["nom"]== "refuse"
    assert entrees[1].statut =="erreur"
    prefixes=[payload['image'].split(',')[0] for payload in api.created]
    assert prefixes == ["data:image/png;base64", "data:image/gif;base64"]


def test_export_ecrit_les_fichiers_et_un_manifeste_sans_secret(tmp_path):
    class API:
        def guild_emojis(self, guild_id):
            return [emoji(1, "statique"), emoji(2, "anime", True)]

    session=FakeSession([FakeDownloadResponse(contenu=PNG),
                           FakeDownloadResponse(contenu=GIF)])
    manifeste, chemin =exporter_emojis(API(), session, "123456789012345678", tmp_path)
    assert manifeste['counts'] == {'total': 2, 'telecharges': 2, 'erreurs':0}
    assert chemin.is_file()
    texte = chemin.read_text(encoding="utf-8")
    assert 'Authorization' not in texte
    for entree in manifeste["emojis"]:
        assert entree["fichier"]
        assert base64.b64encode(PNG).decode() not in texte


def test_permission_manquante_et_arret_sur_limite_de_debit():
    class PermissionAPI:
        def guild(self, guild_id):
            return {'id': guild_id, 'owner_id':'1'}

        def guild_roles(self, guild_id):
            return [{'id': guild_id, 'permissions': '0', 'position': 0}]

        def guild_member(self, guild_id, bot_id):
            return {'user': {'id': bot_id}, 'roles': []}

    from modules.discord.emoji_cloner import verifier_permission_import
    manquantes = verifier_permission_import(PermissionAPI(), '9', '2')
    assert "Gerer les emojis et autocollants" in manquantes

    from modules.discord.discord_api import DiscordRateLimitError

    class LimiteAPI:
        def creer_emoji(self, guild_id, payload, reason=None):
            raise DiscordRateLimitError("limite simulee", status=429)

    entrees = planifier_import([emoji(1, 'un'), emoji(2, 'deux')], [],
                               lambda _emoji: (PNG, "png", ""), OptionsEmoji())
    resultat =importer_entrees(LimiteAPI(), "9", entrees)
    assert resultat['interrompu'] == 'limite de debit Discord'
    assert resultat["importes"] == []
    assert [entree.statut for entree in entrees] ==["erreur", "ignore"]


def test_import_manifeste_refuse_un_fichier_absent(tmp_path, monkeypatch):
    import importlib
    emoji_module =importlib.import_module("modules.discord.emoji_cloner")
    monkeypatch.setattr(emoji_module, "EXPORTS_DIR", str(tmp_path))

    class API:
        def guild_emojis(self, guild_id):
            return []

    manifeste ={
        'format': 'leakfr-discord-emojis',
        "version": 1,
        "emojis": [{"source_id": "1", "nom_source": "absent", "anime":False,
                    'fichier': str(tmp_path / 'emojis' / 'absent.png')}],
    }
    entrees =importer_manifeste(API(), manifeste, "123456789012345678")
    assert entrees[0].statut== 'erreur'
    assert "introuvable" in entrees[0].raison
