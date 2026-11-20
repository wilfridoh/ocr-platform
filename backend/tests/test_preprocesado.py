import numpy as np

from app.pipeline.preprocesado import OpcionesPreprocesado, a_gris, binarizar, preprocesar
from tests.conftest import imagen_a_bgr


def test_a_gris_reduce_canales(planilla_sintetica):
    bgr = imagen_a_bgr(planilla_sintetica)
    gris = a_gris(bgr)
    assert gris.ndim == 2


def test_binarizar_devuelve_imagen_binaria(planilla_sintetica):
    bgr = imagen_a_bgr(planilla_sintetica)
    gris = a_gris(bgr)
    bw, metodo = binarizar(gris)
    valores = set(np.unique(bw).tolist())
    assert valores <= {0, 255}
    assert metodo in ("otsu", "adaptativa")


def test_preprocesar_pipeline_completo(planilla_sintetica):
    bgr = imagen_a_bgr(planilla_sintetica)
    salida, pasos, factor = preprocesar(bgr, OpcionesPreprocesado())
    assert salida.ndim == 2
    assert "gris" in pasos
    assert factor > 0
