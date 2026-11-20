from app import config
from app.config import resolver_tessdata


def test_prefix_explicito_se_respeta():
    assert resolver_tessdata(r"D:\otro\tessdata", "spa") == r"D:\otro\tessdata"


def test_prefix_vacio_autodetecta_backend_tessdata(tmp_path, monkeypatch):
    (tmp_path / "spa.traineddata").write_bytes(b"x")
    monkeypatch.setattr(config, "_TESSDATA_LOCAL", tmp_path)
    assert resolver_tessdata("", "spa") == str(tmp_path)
    assert resolver_tessdata("", "spa+eng") == str(tmp_path)


def test_prefix_vacio_sin_idioma_devuelve_none(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "_TESSDATA_LOCAL", tmp_path)
    assert resolver_tessdata("", "spa") is None
