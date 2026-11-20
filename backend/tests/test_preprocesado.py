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


# ----------------------------------------------------------------- perspectiva
def _tarjeta_sintetica(w=1000, h=630) -> np.ndarray:
    import cv2

    tarjeta = np.full((h, w, 3), 245, dtype=np.uint8)
    cv2.rectangle(tarjeta, (0, 0), (w - 1, h - 1), (40, 40, 40), 6)
    for i in range(8):
        cv2.putText(tarjeta, f"CAMPO {i} VALOR {i * 37}", (40, 80 + i * 65), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (20, 20, 20), 2)
    return tarjeta


def _foto_en_angulo(tarjeta: np.ndarray, destino: list[list[float]], lienzo=(1200, 1600)) -> np.ndarray:
    import cv2

    h, w = tarjeta.shape[:2]
    origen = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    m = cv2.getPerspectiveTransform(origen, np.float32(destino))
    fondo = np.full((*lienzo, 3), 70, dtype=np.uint8)
    return cv2.warpPerspective(tarjeta, m, (lienzo[1], lienzo[0]), dst=fondo, borderMode=cv2.BORDER_TRANSPARENT)


def test_perspectiva_aplana_tarjeta_fotografiada_en_angulo():
    from app.pipeline.preprocesado import corregir_perspectiva

    foto = _foto_en_angulo(_tarjeta_sintetica(), [[260, 200], [1250, 330], [1180, 960], [180, 880]])
    salida, aplicada = corregir_perspectiva(foto)
    assert aplicada
    h, w = salida.shape[:2]
    assert 1.45 <= w / h <= 1.75  # proporción de la tarjeta (1000/630 = 1.59), ya sin deformación
    # lo que queda es (casi) solo la tarjeta: fondo oscuro mínimo en los bordes
    assert salida[h // 2, 20:60].mean() > 150


def test_perspectiva_no_toca_un_documento_que_ya_llena_la_imagen():
    from app.pipeline.preprocesado import corregir_perspectiva

    tarjeta = _tarjeta_sintetica()
    salida, aplicada = corregir_perspectiva(tarjeta)
    assert not aplicada and salida is tarjeta


def test_perspectiva_sin_contorno_confiable_devuelve_la_imagen_igual():
    from app.pipeline.preprocesado import corregir_perspectiva

    ruido = np.random.default_rng(1).integers(0, 255, (800, 1200, 3), dtype=np.uint8)
    salida, aplicada = corregir_perspectiva(ruido)
    assert not aplicada and salida is ruido


def test_preprocesar_registra_el_paso_perspectiva():
    foto = _foto_en_angulo(_tarjeta_sintetica(), [[260, 200], [1250, 330], [1180, 960], [180, 880]])
    _, pasos, _ = preprocesar(foto, OpcionesPreprocesado())
    assert "perspectiva" in pasos
    _, pasos2, _ = preprocesar(foto, OpcionesPreprocesado(perspectiva=False))
    assert "perspectiva" not in pasos2
