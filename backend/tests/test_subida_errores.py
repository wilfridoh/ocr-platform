"""Subida: nombre de archivo demasiado largo (400 limpio) y errores inesperados sin detalles internos (hallazgo de QA)."""
from app.api import documentos as api_documentos
from app.api import flujos as api_flujos
from app.almacen import AlmacenDisco
from app.config import get_settings
from tests.conftest import imagen_a_bytes
from tests.test_api import _DEF_BASICA, HEADERS, client  # noqa: F401  (fixture)

NOMBRE_LARGO = "a" * 300 + ".png"


def _flujo(client) -> str:  # noqa: F811
    pid = client.post("/api/plantillas", json=_DEF_BASICA, headers=HEADERS).json()["id"]
    client.post("/api/flujos-captura", json={"codigo": "f", "nombre": "F", "plantilla_ids": [pid]}, headers=HEADERS)
    return "/api/flujos-captura/f/documentos"


def test_nombre_de_archivo_demasiado_largo_es_400_y_no_guarda_nada(client, planilla_sintetica):  # noqa: F811
    datos = imagen_a_bytes(planilla_sintetica, "PNG")
    for url in ("/api/documentos", _flujo(client)):
        r = client.post(url, files={"archivo": (NOMBRE_LARGO, datos, "image/png")}, headers=HEADERS)
        assert r.status_code == 400, url
        assert "demasiado largo" in r.json()["detail"] and "260" in r.json()["detail"]
    assert client.get("/api/documentos", headers=HEADERS).json()["total"] == 0
    assert AlmacenDisco(get_settings().ALMACEN_RUTA).listar() == []  # ni registro ni archivo huérfano


def test_nombre_en_el_limite_no_se_rechaza_por_largo(client):  # noqa: F811
    nombre = "a" * 256 + ".png"  # 260 caracteres justos
    r = client.post("/api/documentos", files={"archivo": (nombre, b"no es una imagen", "image/png")}, headers=HEADERS)
    assert r.status_code == 400 and "demasiado largo" not in r.json()["detail"]  # falla por contenido, no por nombre


def test_el_limite_del_nombre_cuenta_unidades_utf16_como_sql_server(client):  # noqa: F811
    # hallazgo de QA: un emoji fuera del plano básico ocupa 2 unidades en NVARCHAR aunque len() diga 1
    def subir(nombre: str):
        return client.post("/api/documentos", files={"archivo": (nombre, b"no es una imagen", "image/png")}, headers=HEADERS)

    emoji = "\U0001FAAA"
    r = subir(emoji * 256 + ".png")  # 260 según len(), 516 unidades UTF-16
    assert r.status_code == 400 and "demasiado largo" in r.json()["detail"]
    assert "demasiado largo" not in subir(emoji * 128 + ".png").json()["detail"]  # 260 unidades justas
    assert "demasiado largo" in subir(emoji * 128 + "a.png").json()["detail"]  # 261
    assert "demasiado largo" not in subir("ñ" * 256 + ".png").json()["detail"]  # multibyte dentro del plano básico


def test_error_inesperado_es_500_sin_detalles_internos(client, monkeypatch):  # noqa: F811
    def falla(*a, **k):
        raise RuntimeError("[SQL Server] String data would be truncated in table 'dbo.Documento', column 'NombreArchivo'")

    url_flujo = _flujo(client)
    monkeypatch.setattr(api_documentos, "procesar_documento", falla)
    monkeypatch.setattr(api_flujos, "procesar_documento", falla)
    for url in ("/api/documentos", url_flujo):
        r = client.post(url, files={"archivo": ("x.png", b"x", "image/png")}, headers=HEADERS)
        assert r.status_code == 500, url
        assert r.json()["detail"] == "No se pudo procesar el documento"
        assert "dbo" not in r.text and "NombreArchivo" not in r.text
