"""Preprocesado de imagen con OpenCV. Cada paso es desactivable."""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class OpcionesPreprocesado:
    deskew: bool = True
    denoise: bool = True
    binarizar: bool = True
    reescalar: bool = True
    altura_linea_objetivo: int = 30
    ancho_minimo: int = 1500


def a_gris(img: np.ndarray) -> np.ndarray:
    if img.ndim == 2:
        return img
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


def angulo_inclinacion(gris: np.ndarray) -> float:
    """Ángulo (grados) estimado con minAreaRect sobre los píxeles de tinta; 0 si no es fiable."""
    inv = cv2.bitwise_not(gris)
    _, bw = cv2.threshold(inv, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
    # Unir letras en líneas para que el rectángulo refleje la orientación del texto
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (30, 1))
    bw = cv2.dilate(bw, kernel, iterations=1)
    coords = cv2.findNonZero(bw)
    if coords is None or len(coords) < 50:
        return 0.0
    angulo = cv2.minAreaRect(coords)[-1]
    if angulo < -45:
        angulo = 90 + angulo
    elif angulo > 45:
        angulo = angulo - 90
    # Hough como segunda opinión cuando el ángulo es grande
    if abs(angulo) > 15:
        return 0.0
    return float(angulo)


def deskew(gris: np.ndarray) -> tuple[np.ndarray, float]:
    ang = angulo_inclinacion(gris)
    if abs(ang) < 0.3:
        return gris, 0.0
    h, w = gris.shape[:2]
    m = cv2.getRotationMatrix2D((w / 2, h / 2), ang, 1.0)
    rot = cv2.warpAffine(gris, m, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    return rot, ang


def denoise(gris: np.ndarray) -> np.ndarray:
    return cv2.fastNlMeansDenoising(gris, None, h=7, templateWindowSize=7, searchWindowSize=21)


def binarizar(gris: np.ndarray) -> tuple[np.ndarray, str]:
    """Otsu si el histograma es bimodal/limpio; adaptativa (gaussiana) si la iluminación es irregular."""
    desv_local = cv2.blur(gris.astype(np.float32), (51, 51))
    variacion = float(desv_local.std())
    if variacion > 25:  # iluminación muy desigual -> adaptativa
        bw = cv2.adaptiveThreshold(gris, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 15)
        return bw, "adaptativa"
    _, bw = cv2.threshold(gris, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
    return bw, "otsu"


def altura_linea_estimada(bw: np.ndarray) -> float:
    """Altura mediana de componentes conexas de tinta (aprox. altura de letra)."""
    inv = cv2.bitwise_not(bw) if bw.mean() > 127 else bw
    n, _, stats, _ = cv2.connectedComponentsWithStats(inv, connectivity=8)
    alturas = [s[cv2.CC_STAT_HEIGHT] for s in stats[1:] if 3 < s[cv2.CC_STAT_HEIGHT] < bw.shape[0] / 4]
    if not alturas:
        return 0.0
    return float(np.median(alturas))


def reescalar(img: np.ndarray, altura_objetivo: int = 30, ancho_minimo: int = 1500) -> tuple[np.ndarray, float]:
    h, w = img.shape[:2]
    factor = 1.0
    alt = altura_linea_estimada(img)
    if alt and alt < altura_objetivo:
        factor = min(3.0, altura_objetivo / alt)
    if w * factor < ancho_minimo:
        factor = max(factor, ancho_minimo / w)
    factor = min(factor, 3.0)
    if factor <= 1.05:
        return img, 1.0
    out = cv2.resize(img, None, fx=factor, fy=factor, interpolation=cv2.INTER_CUBIC)
    return out, factor


def preprocesar(img: np.ndarray, op: OpcionesPreprocesado | None = None) -> tuple[np.ndarray, list[str], float]:
    """Devuelve (imagen lista para OCR, pasos aplicados, factor de escala aplicado)."""
    op = op or OpcionesPreprocesado()
    pasos: list[str] = []
    gris = a_gris(img)
    pasos.append("gris")
    if op.deskew:
        gris, ang = deskew(gris)
        if ang:
            pasos.append(f"deskew({ang:.2f})")
    if op.denoise:
        gris = denoise(gris)
        pasos.append("denoise")
    factor = 1.0
    if op.reescalar:
        gris, factor = reescalar(gris, op.altura_linea_objetivo, op.ancho_minimo)
        if factor != 1.0:
            pasos.append(f"reescalado(x{factor:.2f})")
    salida = gris
    if op.binarizar:
        salida, metodo = binarizar(gris)
        pasos.append(f"binarizacion({metodo})")
    return salida, pasos, factor
