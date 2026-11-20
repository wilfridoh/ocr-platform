"""Entrega 1 de la cuadrícula (docs/13 §1.3): el resultado guarda la posición de cada palabra y cómo se recortó la
imagen. Datos inventados."""
from __future__ import annotations

import json

import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.dominio.modelos import PaginaOCR, PalabraOCR
from app.pipeline import posiciones
from tests.conftest import imagen_a_bytes


def _pagina(numero=1, ancho=1000, alto=630, recorte=None):
    palabras = [
        PalabraOCR(texto="APELLIDOS", x=310, y=139, ancho=120, alto=19, confianza=0.97, linea=0, bloque=0),
        PalabraOCR(texto="PEREZ", x=310, y=170, ancho=80, alto=19, confianza=0.912345, linea=1, bloque=0),
    ]
    return PaginaOCR(numero=numero, texto="APELLIDOS\nPEREZ", palabras=palabras, confianza_media=0.94,
                     ancho=ancho, alto=alto, motor="paddle", recorte=recorte)


# ------------------------------------------------------------------ serialización
def test_palabras_en_coordenadas_relativas_compactas():
    texto = posiciones.palabras_json([_pagina()])
    datos = json.loads(texto)
    assert datos["v"] == 1
    pag = datos["paginas"][0]
    assert (pag["numero"], pag["motor"], pag["ancho"], pag["alto"]) == (1, "paddle", 1000, 630)
    assert pag["palabras"][0] == ["APELLIDOS", 0.31, 0.2206, 0.12, 0.0302, 0.97]
    assert pag["palabras"][1][5] == 0.912  # confianza con 3 decimales
    assert " " not in texto.replace("APELLIDOS PEREZ", "")  # separadores compactos


def test_ida_y_vuelta_de_palabras_y_recorte():
    recorte = {"aplicado": True, "origen": "automatico", "esquinas": [[0.1, 0.2], [0.9, 0.2], [0.9, 0.8], [0.1, 0.8]],
               "relacion": 1.587, "orientacion": 0, "deskew": 0.0}
    paginas = [_pagina(1, recorte=recorte), _pagina(2, recorte={**recorte, "aplicado": False, "esquinas": None})]
    palabras = posiciones.leer_palabras(posiciones.palabras_json(paginas))
    assert set(palabras) == {1, 2}
    assert palabras[1][1] == {"texto": "PEREZ", "x": 0.31, "y": 0.2698, "ancho": 0.08, "alto": 0.0302, "confianza": 0.912}
    rec = posiciones.leer_recorte(posiciones.recorte_json(paginas))
    assert rec[1] == recorte and rec[2]["aplicado"] is False


def test_sin_palabras_o_sin_dimensiones_no_se_guarda_nada():
    assert posiciones.palabras_json([]) is None
    assert posiciones.palabras_json([PaginaOCR(numero=1, texto="", ancho=1000, alto=600)]) is None
    assert posiciones.palabras_json([_pagina(ancho=0)]) is None  # sin dimensiones no hay coordenadas relativas
    assert posiciones.recorte_json([_pagina()]) is None
    assert posiciones.leer_palabras(None) == {} and posiciones.leer_recorte("") == {}


def test_tamano_de_una_cedula_tipica():
    # ~150 palabras: el JSON queda bien por debajo de 15 KB
    pagina = _pagina()
    pagina.palabras = [
        PalabraOCR(texto=f"PALABRA{i}", x=10 * i % 1000, y=4 * i % 630, ancho=90, alto=18, confianza=0.95,
                   linea=i, bloque=0)
        for i in range(150)
    ]
    assert len(posiciones.palabras_json([pagina]).encode("utf-8")) < 8_000


# ------------------------------------------------------------------ recorte en el preprocesado
def test_preprocesar_detalle_informa_las_esquinas_del_recorte():
    from app.pipeline.preprocesado import OpcionesPreprocesado, preprocesar, preprocesar_detalle
    from tests.test_preprocesado import _foto_en_angulo, _tarjeta_sintetica

    foto = _foto_en_angulo(_tarjeta_sintetica(), [[260, 200], [1250, 330], [1180, 960], [180, 880]])
    _, pasos, _, recorte = preprocesar_detalle(foto, OpcionesPreprocesado())
    assert "perspectiva" in pasos
    assert recorte["aplicado"] and recorte["origen"] == "automatico" and recorte["orientacion"] == 0
    esq = np.array(recorte["esquinas"])
    assert esq.shape == (4, 2) and (esq >= 0).all() and (esq <= 1).all()
    # las esquinas encontradas son las de la tarjeta en la foto (lienzo 1600 x 1200), en orden horario desde arriba-izq
    esperadas = np.array([[260, 200], [1250, 330], [1180, 960], [180, 880]]) / [1600, 1200]
    assert np.abs(esq - esperadas).max() < 0.03
    assert 1.45 <= recorte["relacion"] <= 1.75
    # preprocesar conserva su firma de siempre
    assert len(preprocesar(foto, OpcionesPreprocesado())) == 3


def test_preprocesar_detalle_sin_recorte():
    from app.pipeline.preprocesado import OpcionesPreprocesado, preprocesar_detalle
    from tests.conftest import imagen_a_bgr

    bgr = imagen_a_bgr(_planilla())  # documento que llena la imagen: no hay tarjeta que recortar
    _, _, _, recorte = preprocesar_detalle(bgr, OpcionesPreprocesado())
    assert recorte["aplicado"] is False and recorte["origen"] == "ninguno" and recorte["esquinas"] is None
    _, _, _, recorte = preprocesar_detalle(bgr, OpcionesPreprocesado(perspectiva=False))
    assert recorte["aplicado"] is False


def _planilla():
    from tests.conftest import renderizar_texto

    return renderizar_texto(["Total a pagar $ 45.320", "Vencimiento 30/11/2026"], ancho=1400, alto=500, tamano_fuente=36)


# ------------------------------------------------------------------ integración: se guarda con el resultado
@pytest.fixture
def entorno(tmp_path, monkeypatch):
    from app.api import dependencias
    from app.config import get_settings
    from app.main import app
    from app.persistencia import modelos  # noqa: F401
    from app.persistencia.db import Base
    from app.pipeline import ocr as ocr_mod

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool, future=True)
    Base.metadata.create_all(bind=engine)
    Sesion = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    def _db():
        db = Sesion()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[dependencias.get_db] = _db
    s = get_settings()
    s.API_KEY = "dev"
    s.ALMACEN_RUTA = str(tmp_path / "archivos")

    def ocr_falso(img, settings, idioma=None):
        h, w = img.shape[:2]
        pag = _pagina(ancho=w, alto=h)
        pag.palabras[0].x, pag.palabras[0].y = w // 4, h // 5
        return pag, "paddle"

    monkeypatch.setattr(ocr_mod, "leer_pagina", ocr_falso)
    with TestClient(app) as c:
        yield c, Sesion
    app.dependency_overrides.clear()


def test_subir_documento_guarda_palabras_y_recorte(entorno):
    from app.persistencia import modelos as m

    client, Sesion = entorno
    r = client.post("/api/documentos", headers={"X-API-Key": "dev"},
                    files={"archivo": ("doc.png", imagen_a_bytes(_planilla()), "image/png")})
    assert r.status_code == 201, r.text
    with Sesion() as db:
        res = db.execute(select(m.Resultado)).scalars().one()
        palabras = posiciones.leer_palabras(res.PalabrasJson)
        recorte = posiciones.leer_recorte(res.RecorteJson)
    assert [p["texto"] for p in palabras[1]] == ["APELLIDOS", "PEREZ"]
    assert palabras[1][0]["x"] == pytest.approx(0.25, abs=0.001) and palabras[1][0]["y"] == pytest.approx(0.2, abs=0.002)
    assert recorte[1]["aplicado"] is False and recorte[1]["origen"] == "ninguno"
    # y el contrato de la API no cambia en esta entrega
    doc_id = r.json()["documento_id"]
    cuerpo = client.get(f"/api/documentos/{doc_id}/resultado", headers={"X-API-Key": "dev"}).json()
    assert "PalabrasJson" not in json.dumps(cuerpo) and "palabras" not in cuerpo


def test_reprocesar_vuelve_a_guardar_posiciones(entorno):
    from app.persistencia import modelos as m

    client, Sesion = entorno
    r = client.post("/api/documentos", headers={"X-API-Key": "dev"},
                    files={"archivo": ("doc.png", imagen_a_bytes(_planilla()), "image/png")})
    doc_id = r.json()["documento_id"]
    with Sesion() as db:  # simula un resultado anterior a la migración 009
        res = db.execute(select(m.Resultado)).scalars().one()
        res.PalabrasJson = res.RecorteJson = None
        db.commit()
    assert client.post(f"/api/documentos/{doc_id}/reprocesar", headers={"X-API-Key": "dev"}).status_code == 200
    with Sesion() as db:
        res = db.execute(select(m.Resultado)).scalars().one()
        assert res.PalabrasJson and res.RecorteJson
