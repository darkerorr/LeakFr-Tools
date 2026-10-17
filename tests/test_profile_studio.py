import json
from pathlib import Path

import pytest
from PIL import Image

from modules.profile_studio.store import ProfileStore
from modules.profile_studio.templates import (
    appliquer_modele, lister_modeles, placeholders,
)


def image(path, taille=(300, 200), couleur=(20, 40, 60)):
    Image.new("RGB", taille, couleur).save(path, format="PNG")
    return path


def test_import_et_recadrage_avatar_et_banniere(tmp_path):
    store = ProfileStore(tmp_path / "studio")
    source = image(tmp_path / "avatar.png")
    avatar = store.importer_image(source, "avatar")
    assert avatar["largeur"] == 300 and avatar["hauteur"] == 200
    assert avatar["doublon"] is False
    assert store.importer_image(source, "avatar")["doublon"] is True

    prepare = store.recadrer(avatar["id"], "avatar", (10, 20, 100, 100))
    assert (prepare["largeur"], prepare["hauteur"]) == (512, 512)
    assert Path(store.root / prepare["chemin"]).is_file()

    banniere = store.importer_image(source, "banner")
    preparee = store.recadrer(banniere["id"], "banner")
    assert (preparee["largeur"], preparee["hauteur"]) == (960, 540)


def test_recadrage_invalide_est_refuse(tmp_path):
    store = ProfileStore(tmp_path / "studio")
    avatar = store.importer_image(image(tmp_path / "a.png"), "avatar")
    with pytest.raises(ValueError):
        store.recadrer(avatar["id"], "avatar", (0, 0, 9999, 9999))
    with pytest.raises(ValueError):
        store.recadrer(avatar["id"], "avatar", "mauvaise boite")
    with pytest.raises(ValueError):
        store.importer_image(tmp_path / "absent.png", "avatar")


def test_variantes_comparaison_historique_et_export(tmp_path):
    store = ProfileStore(tmp_path / "studio")
    avatar = store.importer_image(image(tmp_path / "a.png"), "avatar")
    banniere = store.importer_image(image(tmp_path / "b.png", (800, 300)), "banner")

    une = store.sauvegarder_config("Sobre", {
        "display_name": "Audit", "bio": "Labs autorises", "status_text": "Disponible",
        "avatar_id": avatar["id"], "banner_id": None,
    })
    deux = store.sauvegarder_config("Complete", {
        "display_name": "Audit 2", "bio": "Labs autorises", "status_text": "Occupe",
        "avatar_id": avatar["id"], "banner_id": banniere["id"],
    })
    assert une["applique_sur_discord"] is False
    assert len(store.configs()) == 2
    comparaison = store.comparer(une["id"], deux["id"])
    assert set(comparaison["differences"]) == {"display_name", "status_text", "banner_id"}
    assert len(store.historique()) == 2

    path = store.exporter_config(une["id"], tmp_path / "export.json")
    donnees = json.loads(path.read_text(encoding="utf-8"))
    assert donnees["format"] == "leakfr-profile-variant"
    assert "appliquee a Discord" in donnees["avertissement"]

    restauree = store.importer_config(path)
    assert restauree["nom"] == "Sobre"
    assert store.supprimer_config(restauree["id"])["nom"] == "Sobre"


def test_textes_limites_et_modeles(tmp_path):
    store = ProfileStore(tmp_path / "studio")
    with pytest.raises(ValueError):
        store.sauvegarder_config("Trop long", {"bio": "x" * 191})
    with pytest.raises(ValueError):
        store.sauvegarder_config("", {})
    with pytest.raises(ValueError):
        store.sauvegarder_config("Image absente", {"avatar_id": "inconnu"})

    modeles = lister_modeles()
    assert len(modeles) >= 5
    modele = next(item for item in modeles if item["nom"] == "Developpement")
    assert set(placeholders(modele)) == {"role", "stack", "projets", "contact"}
    texte = appliquer_modele(modele, {"role": "Dev", "stack": "Python",
                                      "projets": "LeakFr", "contact": "mail"})
    assert "Dev" in texte and "Python" in texte and "{" not in texte


def test_aucune_reference_a_un_jeton_ou_selfbot():
    from modules.profile_studio import panel
    texte = Path(panel.__file__).read_text(encoding="utf-8").casefold()
    assert "selfbot" in texte  # la limite est documentee
    assert "user_token" not in texte
    assert "appliquer sur discord" not in texte
