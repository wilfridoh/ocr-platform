"""Paddle (oneDNN) falla con "could not execute a primitive" si se usa desde un hilo distinto al que lo creó."""
import threading
from concurrent.futures import ThreadPoolExecutor

import numpy as np

from app.pipeline.ocr import PaddleOCRMotor


class _PaddleFalso:
    creado_en: int | None = None

    def __init__(self, **_):
        type(self).creado_en = threading.get_ident()

    def ocr(self, imagen, cls=True):
        if threading.get_ident() != type(self).creado_en:
            raise RuntimeError("could not execute a primitive")
        return [[[[[0, 0], [10, 0], [10, 5], [0, 5]], ("HOLA", 0.9)]]]


def test_paddle_crea_e_infiere_siempre_en_el_mismo_hilo():
    motor = PaddleOCRMotor.__new__(PaddleOCRMotor)
    motor._PaddleOCR = _PaddleFalso
    motor._instancias = {}
    motor._hilo = ThreadPoolExecutor(max_workers=1)
    img = np.zeros((20, 20), dtype=np.uint8)
    # cada petición llega desde un hilo distinto (como el pool de la API)
    with ThreadPoolExecutor(max_workers=4) as pool:
        paginas = list(pool.map(lambda _: motor.leer(img), range(6)))
    assert all(p.texto == "HOLA" for p in paginas)
