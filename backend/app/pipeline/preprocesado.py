"""Preprocesado de imagen con OpenCV. Cada paso es desactivable."""
from __future__ import annotations

import logging
from dataclasses import dataclass

import cv2
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class OpcionesPreprocesado:
    perspectiva: bool = True
    deskew: bool = True
    denoise: bool = True
    binarizar: bool = True
    reescalar: bool = True
    altura_linea_objetivo: int = 30
    ancho_minimo: int = 1500


def _ordenar_esquinas(pts: np.ndarray) -> np.ndarray:
    """4 puntos -> [arriba-izq, arriba-der, abajo-der, abajo-izq]."""
    suma = pts.sum(axis=1)
    resta = np.diff(pts, axis=1).ravel()
    return np.array([pts[np.argmin(suma)], pts[np.argmin(resta)], pts[np.argmax(suma)], pts[np.argmax(resta)]], dtype=np.float32)


def _angulos_razonables(q: np.ndarray, minimo: float = 55.0, maximo: float = 125.0) -> bool:
    """Los 4 ángulos interiores de un rectángulo visto en perspectiva moderada están lejos de 0 y de 180."""
    for i in range(4):
        a, b, c = q[i - 1], q[i], q[(i + 1) % 4]
        v1, v2 = a - b, c - b
        cos = float(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-9))
        ang = np.degrees(np.arccos(np.clip(cos, -1.0, 1.0)))
        if not (minimo <= ang <= maximo):
            return False
    return True


def _apoyo_en_bordes(q: np.ndarray, bordes: np.ndarray) -> float:
    """Fracción del perímetro del cuadrilátero que cae sobre bordes reales de la imagen."""
    h, w = bordes.shape
    total = ok = 0
    for i in range(4):
        a, b = q[i], q[(i + 1) % 4]
        for t in np.linspace(0.0, 1.0, max(20, int(np.linalg.norm(b - a) / 4))):
            x, y = (a + (b - a) * t).round().astype(int)
            total += 1
            if 0 <= x < w and 0 <= y < h and bordes[y, x]:
                ok += 1
    return ok / total if total else 0.0


APOYO_MINIMO_BORDES = 0.6


def _cuadrilatero_documento(peq: np.ndarray) -> np.ndarray | None:
    """Esquinas (en coordenadas de `peq`) del documento/tarjeta que domina la foto, o None si no hay uno confiable.
    Se separa primer plano y fondo con GrabCut (más robusto que buscar rectas cuando el fondo tiene otros bordes:
    teclado, mesa, otra hoja) y se ajusta un cuadrilátero al contorno del primer plano."""
    ph, pw = peq.shape[:2]
    mascara = np.zeros((ph, pw), np.uint8)
    cv2.grabCut(
        peq, mascara, (int(pw * 0.04), int(ph * 0.04), int(pw * 0.92), int(ph * 0.92)),
        np.zeros((1, 65)), np.zeros((1, 65)), 4, cv2.GC_INIT_WITH_RECT,
    )
    fg = np.where((mascara == cv2.GC_FGD) | (mascara == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)
    fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9)))
    contornos, _ = cv2.findContours(fg, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contornos:
        return None
    c = max(contornos, key=cv2.contourArea)
    area_img = float(ph * pw)
    area_c = cv2.contourArea(c)
    if not (0.2 * area_img <= area_c <= 0.92 * area_img):
        return None  # chico, o el documento ya llena la imagen (escaneo): nada que corregir
    casco = cv2.convexHull(c)
    area_casco = cv2.contourArea(casco)
    if area_c / (area_casco + 1e-9) < 0.9:
        return None  # forma irregular (no es un documento)
    for eps in (0.02, 0.03, 0.05):
        aprox = cv2.approxPolyDP(casco, eps * cv2.arcLength(casco, True), True)
        if len(aprox) == 4:
            break
    else:
        return None
    q = _ordenar_esquinas(aprox.reshape(4, 2).astype(np.float32))
    area_q = cv2.contourArea(q)
    if not (0.9 <= area_q / (area_casco + 1e-9) <= 1.15) or not _angulos_razonables(q):
        return None
    # las esquinas redondeadas de una tarjeta meten el cuadrilátero un poco hacia adentro: se compensa
    centro = q.mean(axis=0)
    q = centro + (q - centro) * 1.015
    # un documento real tiene borde visible alrededor; un recuadro "inventado" dentro de una página (márgenes
    # de un escaneo, un recuadro de texto) no
    gris = cv2.GaussianBlur(a_gris(peq), (5, 5), 0)
    bordes = cv2.dilate(cv2.Canny(gris, 40, 120), cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7)))
    apoyo = _apoyo_en_bordes(q, bordes)
    logger.debug("Perspectiva: apoyo en bordes %.2f", apoyo)
    if apoyo < APOYO_MINIMO_BORDES:
        return None
    # y el entorno debe distinguirse del documento (un fondo distinto): en un escaneo el "exterior" de un bloque de
    # texto es el mismo papel
    dentro = np.zeros((ph, pw), np.uint8)
    cv2.fillConvexPoly(dentro, q.astype(np.int32), 255)
    anillo = cv2.dilate(dentro, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (31, 31))) & ~dentro
    if cv2.countNonZero(anillo) < 200:
        return q  # el documento toca los bordes de la foto: no hay entorno que comparar
    contraste = abs(float(gris[dentro > 0].mean()) - float(gris[anillo > 0].mean()))
    logger.debug("Perspectiva: contraste con el entorno %.1f", contraste)
    return q if contraste >= 50.0 else None


def corregir_perspectiva(img: np.ndarray, lado_deteccion: int = 400) -> tuple[np.ndarray, bool]:
    """Si la imagen es una foto de un documento/tarjeta tomada en ángulo (sobre un fondo), la "aplana": detecta el
    cuadrilátero del documento y lo proyecta a un rectángulo. Si no hay uno confiable (o el documento ya llena la
    imagen, como un escaneo), devuelve la imagen tal cual y False: nunca fuerza una transformación dudosa."""
    h, w = img.shape[:2]
    if h < 100 or w < 100:
        return img, False
    if img.ndim == 2:
        return img, False  # sin color GrabCut no es fiable; las imágenes en gris suelen ser escaneos
    esc = min(1.0, lado_deteccion / max(h, w))
    peq = cv2.resize(img, None, fx=esc, fy=esc, interpolation=cv2.INTER_AREA) if esc < 1.0 else img
    try:
        q = _cuadrilatero_documento(peq)
    except cv2.error:
        return img, False
    if q is None:
        return img, False
    q = q / esc
    q[:, 0] = np.clip(q[:, 0], 0, w - 1)
    q[:, 1] = np.clip(q[:, 1], 0, h - 1)
    esquinas_imagen = np.array([[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]], dtype=np.float32)
    if np.linalg.norm(q - esquinas_imagen, axis=1).max() < 0.05 * max(h, w):
        return img, False  # el documento ya ocupa todo el encuadre: no hay perspectiva que corregir
    ancho = max(np.linalg.norm(q[0] - q[1]), np.linalg.norm(q[3] - q[2]))
    alto = max(np.linalg.norm(q[0] - q[3]), np.linalg.norm(q[1] - q[2]))
    if ancho < 200 or alto < 100 or not (1.0 <= max(ancho, alto) / min(ancho, alto) <= 2.2):
        return img, False  # proporciones que no son de un documento/tarjeta
    destino = np.array([[0, 0], [ancho - 1, 0], [ancho - 1, alto - 1], [0, alto - 1]], dtype=np.float32)
    m = cv2.getPerspectiveTransform(q.astype(np.float32), destino)
    return cv2.warpPerspective(img, m, (int(round(ancho)), int(round(alto))), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE), True


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
    if op.perspectiva:
        img, aplicada = corregir_perspectiva(img)
        if aplicada:
            pasos.append("perspectiva")
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
