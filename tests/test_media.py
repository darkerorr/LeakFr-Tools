import importlib
from pathlib import Path

import pytest
from PIL import Image

gif_module = importlib.import_module("modules.media.gif_studio")
from modules.media.gif_studio import (
    MediaLibrary, analyser_media, detecter_format, publier_discord, valider_url,
)
from modules.media.panel import frames_apercu


def creer_gif(path, images=3):
    frames = [Image.new('RGB', (32, 24), couleur)
              for couleur in [(255, 0, 0), (0, 255, 0), (0, 0, 255)][:images]]
    frames[0].save(path, save_all=True, append_images=frames[1:], duration=100, loop=0)
    return path


def creer_png(path):
    Image.new("RGBA", (40, 20), (10, 20, 30, 255)).save(path, format="PNG")
    return path


def test_import_gif_metadonnees_et_doublon(tmp_path):
    source = creer_gif(tmp_path / 'animation.gif')
    library = MediaLibrary(tmp_path / "library")
    entree = library.importer_fichier(source, "Animation")
    assert entree['format'] =='gif'
    assert entree["anime"] is True
    assert entree["images"] == 3
    assert entree['duree_ms'] == 300
    assert Path(library.root / entree["chemin"]).is_file()

    doublon = library.importer_fichier(source, 'Copie')
    assert doublon["doublon"] is True
    assert doublon["id"] == entree["id"]
    assert len(library.lister()) == 1


def test_import_refuse_fichier_invalide_et_trop_volumineux(tmp_path, monkeypatch):
    library =MediaLibrary(tmp_path / "library")
    invalide = tmp_path / "faux.gif"
    invalide.write_bytes(b'pas un gif')
    with pytest.raises(ValueError):
        library.importer_fichier(invalide)
    with pytest.raises(ValueError):
        library.importer_fichier(tmp_path / "absent.gif")

    png =creer_png(tmp_path / 'image.png')
    monkeypatch.setattr(gif_module, "TAILLE_MAX", 4)
    with pytest.raises(ValueError):
        library.importer_fichier(png)


def test_detection_et_validation_url(tmp_path):
    png= creer_png(tmp_path / "leakfr-test.png")
    assert detecter_format(png.read_bytes()) == "png"
    for url in ('file:///etc/passwd', 'http://127.0.0.1/a.gif',
                "http://localhost/a.gif", "http://10.0.0.1/a.gif",
                "ftp://example.com/a.gif"):
        with pytest.raises(ValueError):
            valider_url(url)
    png.unlink()


class FakeResponse:
    def __init__(self, contenu, status=200, headers=None):
        self.contenu =contenu
        self.status_code = status
        self.headers = headers or {'Content-Length':str(len(contenu))}

    def iter_content(self, _taille):
        yield self.contenu


class FakeSession:
    def __init__(self, reponses):
        self.reponses = list(reponses)

    def get(self, _url, **_kwargs):
        return self.reponses.pop(0)


def test_import_url_reel_et_redirection_interne_refusee(tmp_path, monkeypatch):
    library=MediaLibrary(tmp_path / 'library')
    donnees = creer_gif(tmp_path / "source.gif").read_bytes()

    def valider(url):
        if "127.0.0.1" in url or "localhost" in url:
            raise ValueError("adresse privee refusee")
        return url

    monkeypatch.setattr(gif_module, "valider_url", valider)
    entree=library.importer_url('https://example.com/a.gif',
                                  session=FakeSession([FakeResponse(donnees)]))
    assert entree["format"]=="gif" and entree["anime"]

    session = FakeSession([FakeResponse(b"", status=302,
                                        headers={"Location": "http://127.0.0.1/x.gif"})])
    with pytest.raises(ValueError):
        library.importer_url("https://example.com/a.gif", session=session)


def test_conversion_gif_vers_webp_et_mp4_non_supporte(tmp_path):
    library=MediaLibrary(tmp_path / "library")
    source =creer_gif(tmp_path / 'animation.gif')
    entree = library.importer_fichier(source)
    converti =library.convertir(entree["id"], "webp")
    assert converti['format'] == 'webp'
    assert converti["anime"] is True
    assert Path(library.root / converti["chemin"]).is_file()
    assert converti['conversion_de'] == entree['id']
    with pytest.raises(ValueError):
        library.convertir(entree["id"], "mp4")

    video = tmp_path / "video.mp4"
    video.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"0" * 32)
    assert analyser_media(video)['format'] == 'mp4'
    entree_video = library.importer_fichier(video)
    with pytest.raises(ValueError):
        library.convertir(entree_video['id'], 'gif')


def test_copie_suppression_et_refus_ecrasement(tmp_path):
    library=MediaLibrary(tmp_path / "library")
    entree =library.importer_fichier(creer_gif(tmp_path / "a.gif"))
    destination = tmp_path / 'sortie' / 'copie.gif'
    copie= library.copier(entree["id"], destination)
    assert copie.read_bytes() == Path(library.root / entree["chemin"]).read_bytes()
    with pytest.raises(ValueError):
        library.copier(entree["id"], destination)
    library.copier(entree["id"], destination, remplacer=True)
    library.supprimer(entree['id'])
    assert library.obtenir(entree["id"]) is None
    assert not Path(library.root / entree["chemin"]).exists()


def test_publication_distincte_de_import_et_mime(tmp_path):
    library = MediaLibrary(tmp_path / 'library')
    entree = library.importer_fichier(creer_gif(tmp_path / "a.gif"))

    class API:
        def __init__(self):
            self.appels = []

        def envoyer_fichier(self, *args, **kwargs):
            self.appels.append((args, kwargs))
            return {'id':'123456789012345678'}

    api = API()
    message = publier_discord(api, '223456789012345678', entree['id'], library, 'test')
    assert message["id"] == "123456789012345678"
    args, kwargs = api.appels[0]
    assert args[0] == '223456789012345678'
    assert args[1] == "test"
    assert kwargs.get("content_type")== "image/gif" or args[4] =="image/gif"


def test_apercu_extrait_les_images(tmp_path):
    library= MediaLibrary(tmp_path / 'library')
    entree = library.importer_fichier(creer_gif(tmp_path / "a.gif"))
    frames =frames_apercu(library.chemin(entree["id"]), largeur=16)
    assert len(frames) == 3
    assert all("▀" in frame for frame in frames)

    from io import BytesIO
    unique = frames_apercu(BytesIO(library.chemin(entree["id"]).read_bytes()),
                           largeur=16, max_images=1)
    assert len(unique) ==1
