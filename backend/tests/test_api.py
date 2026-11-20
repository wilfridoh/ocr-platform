"""Pruebas de integración de la API con SQLite en memoria (StaticPool) y
Tesseract forzado (motor_ocr por defecto en settings es 'paddle', que puede
no estar instalado en el entorno de pruebas)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings
from app.persistencia.db import Base

from tests.conftest import imagen_a_bytes
from tests.test_pipeline_e2e import _tesseract_disponible


@pytest.fixture
def client(tmp_path, monkeypatch):
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool, future=True
    )
    from app.persistencia import modelos  # noqa: F401  registra las tablas

    Base.metadata.create_all(bind=engine)
    TestSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    from app.api import dependencias
    from app.main import app

    def _get_db_override():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[dependencias.get_db] = _get_db_override

    settings = get_settings()
    settings.API_KEY = "dev"
    settings.OCR_MOTOR = "tesseract"
    settings.ALMACEN_RUTA = str(tmp_path / "archivos")

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


HEADERS = {"X-API-Key": "dev"}


def test_salud_no_requiere_api_key(client):
    r = client.get("/api/salud")
    assert r.status_code == 200
    assert r.json()["api"] == "ok"


def test_documentos_requiere_api_key(client):
    r = client.get("/api/documentos")
    assert r.status_code == 401


def test_crear_plantilla_y_listar(client):
    definicion = {
        "codigo": "planilla_servicio_electrico",
        "nombre": "Planilla servicio eléctrico",
        "umbral_confianza": 0.3,
        "palabras_clave": [{"texto": "total a pagar", "peso": 3}, {"texto": "n cliente", "peso": 2}],
        "campos": [
            {
                "nombre": "numero_cliente",
                "etiqueta": "Número de cliente",
                "tipo_dato": "texto",
                "obligatorio": True,
                "regla": {"metodo": "ancla", "ancla": "N Cliente", "regex": r"[\d.-]+"},
            },
            {
                "nombre": "total_pagar",
                "etiqueta": "Total a pagar",
                "tipo_dato": "monto",
                "obligatorio": True,
                "regla": {"metodo": "regex", "regex": r"Total a pagar\s*\$?\s*([\d.,]+)"},
            },
        ],
    }
    r = client.post("/api/plantillas", json=definicion, headers=HEADERS)
    assert r.status_code == 201, r.text
    plantilla = r.json()
    assert plantilla["codigo"] == "planilla_servicio_electrico"

    r2 = client.get("/api/plantillas", headers=HEADERS)
    assert r2.status_code == 200
    assert any(p["codigo"] == "planilla_servicio_electrico" for p in r2.json())


@pytest.mark.skipif(not _tesseract_disponible(), reason="Tesseract no disponible en este entorno")
def test_subir_documento_y_obtener_resultado(client, planilla_sintetica):
    definicion = {
        "codigo": "planilla_servicio_electrico",
        "nombre": "Planilla servicio eléctrico",
        "umbral_confianza": 0.2,
        "palabras_clave": [{"texto": "total a pagar", "peso": 3}, {"texto": "vencimiento", "peso": 2}],
        "campos": [
            {
                "nombre": "numero_cliente",
                "etiqueta": "Número de cliente",
                "tipo_dato": "texto",
                "obligatorio": True,
                "regla": {"metodo": "ancla", "ancla": "N Cliente", "regex": r"[\d.-]+"},
            },
            {
                "nombre": "total_pagar",
                "etiqueta": "Total a pagar",
                "tipo_dato": "monto",
                "obligatorio": True,
                "regla": {"metodo": "regex", "regex": r"Total a pagar\s*\$?\s*([\d.,]+)"},
            },
            {
                "nombre": "fecha_vencimiento",
                "etiqueta": "Vencimiento",
                "tipo_dato": "fecha",
                "obligatorio": True,
                "regla": {"metodo": "ancla", "ancla": "Vencimiento"},
            },
        ],
    }
    r = client.post("/api/plantillas", json=definicion, headers=HEADERS)
    assert r.status_code == 201, r.text

    datos = imagen_a_bytes(planilla_sintetica, "PNG")
    r2 = client.post(
        "/api/documentos",
        files={"archivo": ("planilla_luz.png", datos, "image/png")},
        headers=HEADERS,
    )
    assert r2.status_code == 201, r2.text
    cuerpo = r2.json()
    assert cuerpo["estado"] == "COMPLETADO"
    assert cuerpo["clasificacion"]["tipo"] == "planilla_servicio_electrico"
    assert cuerpo["campos"]["total_pagar"]["valor"] == 45320.0
    assert cuerpo["campos"]["total_pagar"]["motor"] == "tesseract"

    documento_id = cuerpo["documento_id"]
    r3 = client.get(f"/api/documentos/{documento_id}/resultado", headers=HEADERS)
    assert r3.status_code == 200
    assert r3.json()["campos"]["total_pagar"]["valor"] == 45320.0
    assert r3.json()["campos"]["total_pagar"]["motor"] == "tesseract"


_DEF_BASICA = {
    "codigo": "planilla_servicio_electrico",
    "nombre": "Planilla servicio eléctrico",
    "umbral_confianza": 0.2,
    "palabras_clave": [{"texto": "total a pagar", "peso": 3}, {"texto": "vencimiento", "peso": 2}],
    "campos": [
        {
            "nombre": "total_pagar",
            "etiqueta": "Total a pagar",
            "tipo_dato": "monto",
            "obligatorio": True,
            "regla": {"metodo": "regex", "regex": r"Total a pagar\s*\$?\s*([\d.,]+)"},
        }
    ],
}


def test_versiones_plantilla(client):
    r = client.post("/api/plantillas", json=_DEF_BASICA, headers=HEADERS)
    pid = r.json()["id"]
    assert client.put(f"/api/plantillas/{pid}", json=_DEF_BASICA, headers=HEADERS).status_code == 200
    r2 = client.get(f"/api/plantillas/{pid}/versiones", headers=HEADERS)
    assert r2.status_code == 200
    vs = r2.json()
    assert [v["version"] for v in vs] == [1, 2]
    assert vs[0]["comentario"] == "Versión inicial" and vs[0]["fecha"]
    assert client.get("/api/plantillas/9999/versiones", headers=HEADERS).status_code == 404


def test_reprocesar_plantilla_inexistente(client):
    assert client.post("/api/plantillas/9999/reprocesar", headers=HEADERS).status_code == 404


@pytest.mark.skipif(not _tesseract_disponible(), reason="Tesseract no disponible en este entorno")
def test_reprocesar_documentos_de_plantilla(client, planilla_sintetica):
    pid = client.post("/api/plantillas", json=_DEF_BASICA, headers=HEADERS).json()["id"]
    datos = imagen_a_bytes(planilla_sintetica, "PNG")
    r = client.post("/api/documentos", files={"archivo": ("p.png", datos, "image/png")}, headers=HEADERS)
    assert r.status_code == 201, r.text
    client.put(f"/api/plantillas/{pid}", json=_DEF_BASICA, headers=HEADERS)
    r2 = client.post(f"/api/plantillas/{pid}/reprocesar", headers=HEADERS)
    assert r2.status_code == 200, r2.text
    assert r2.json() == {"total": 1, "errores": 0}


@pytest.mark.skipif(not _tesseract_disponible(), reason="Tesseract no disponible en este entorno")
def test_resultado_trae_plantilla_y_lista_cuenta_documentos(client, planilla_sintetica):
    """El resultado leído de la BD incluye plantilla_id/plantilla_version y el listado cuenta documentos."""
    pid = client.post("/api/plantillas", json=_DEF_BASICA, headers=HEADERS).json()["id"]
    datos = imagen_a_bytes(planilla_sintetica, "PNG")
    r = client.post("/api/documentos", files={"archivo": ("p.png", datos, "image/png")}, headers=HEADERS)
    assert r.status_code == 201, r.text
    doc_id = r.json()["documento_id"]

    res = client.get(f"/api/documentos/{doc_id}/resultado", headers=HEADERS).json()
    assert res["clasificacion"]["plantilla_id"] == pid
    assert res["clasificacion"]["plantilla_version"] == 1

    lista = client.get("/api/plantillas", headers=HEADERS).json()
    assert next(p for p in lista if p["id"] == pid)["total_documentos"] == 1


def test_lista_plantillas_sin_documentos_cuenta_cero(client):
    pid = client.post("/api/plantillas", json=_DEF_BASICA, headers=HEADERS).json()["id"]
    lista = client.get("/api/plantillas", headers=HEADERS).json()
    assert next(p for p in lista if p["id"] == pid)["total_documentos"] == 0


def test_documentos_devuelve_los_nombres_que_adapta_el_frontend(client, planilla_sintetica):
    """Contrato que consume frontend/src/api/adaptadores.ts (adaptarDocumento): si cambia, hay que cambiar el adaptador."""
    client.post("/api/plantillas", json=_DEF_BASICA, headers=HEADERS)
    datos = imagen_a_bytes(planilla_sintetica, "PNG")
    r = client.post("/api/documentos", files={"archivo": ("p.png", datos, "image/png")}, headers=HEADERS)
    if r.status_code != 201:
        pytest.skip("OCR no disponible en este entorno")
    item = client.get("/api/documentos", headers=HEADERS).json()["items"][0]
    for clave in ("id", "nombre_archivo", "recibido_en", "tipo_detectado", "confianza_global", "estado", "paginas"):
        assert clave in item
