import threading
import time
from types import SimpleNamespace

import numpy as np

from app.pipeline import ocr as ocr_mod


def _settings(**kw):
    base = dict(OCR_SEGUNDA_OPINION="lento", OCR_SEGUNDA_OPINION_TIMEOUT_S=1, OCR_IDIOMA="spa", OCR_MAX_CONCURRENTES=2)
    base.update(kw)
    return SimpleNamespace(**base)


class _MotorLento:
    nombre = "lento"

    def __init__(self, espera):
        self.espera = espera

    def leer(self, imagen, idioma="spa"):
        time.sleep(self.espera)
        return ocr_mod.PaginaOCR(texto="ok")


def test_segunda_opinion_con_timeout_devuelve_none(monkeypatch):
    monkeypatch.setitem(ocr_mod._CACHE_MOTORES, "lento", _MotorLento(3))
    t0 = time.perf_counter()
    assert ocr_mod.segunda_opinion(np.zeros((5, 5, 3), np.uint8), _settings()) is None
    assert time.perf_counter() - t0 < 2.5


def test_segunda_opinion_rapida_devuelve_pagina(monkeypatch):
    monkeypatch.setitem(ocr_mod._CACHE_MOTORES, "lento", _MotorLento(0))
    assert ocr_mod.segunda_opinion(np.zeros((5, 5, 3), np.uint8), _settings()).texto == "ok"


def test_motor_se_inicializa_una_sola_vez_con_requests_concurrentes(monkeypatch):
    ocr_mod._CACHE_MOTORES.pop("x", None)
    creados = []

    def _crear(nombre, settings):
        creados.append(nombre)
        time.sleep(0.2)
        return _MotorLento(0)

    monkeypatch.setattr(ocr_mod, "_crear_motor", _crear)
    hilos = [threading.Thread(target=ocr_mod.obtener_motor, args=("x", _settings())) for _ in range(5)]
    [h.start() for h in hilos]
    [h.join() for h in hilos]
    ocr_mod._CACHE_MOTORES.pop("x", None)
    assert creados == ["x"]


def test_subida_lenta_no_bloquea_salud(monkeypatch):
    """El pipeline corre fuera del event loop: /salud responde mientras se procesa un documento."""
    import asyncio

    import httpx

    from app.api import documentos
    from app.main import app

    def _lento(*a, **k):
        time.sleep(1.5)
        raise RuntimeError("fin")

    monkeypatch.setattr(documentos, "procesar_documento", _lento)

    async def _escenario():
        transporte = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transporte, base_url="http://t") as c:
            subida = asyncio.create_task(
                c.post("/api/documentos", files={"archivo": ("a.png", b"x", "image/png")}, headers={"X-API-Key": "dev"})
            )
            await asyncio.sleep(0.2)
            t0 = time.perf_counter()
            r = await c.get("/api/salud")
            demora = time.perf_counter() - t0
            await subida
            return r.status_code, demora

    codigo, demora = asyncio.run(_escenario())
    assert codigo == 200 and demora < 1.0
