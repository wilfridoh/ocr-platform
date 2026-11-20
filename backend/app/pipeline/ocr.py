"""Motores de OCR.

Jerarquía (docs/02-backend.md §3, actualizada por docs/06-investigacion-ocr-engines.md):
  - PaddleOCRMotor: motor principal por defecto (PP-OCRv5, CPU).
  - DocTRMotor: segunda opinión / validación cruzada vía OnnxTR, se invoca solo
    para campos cuya confianza cae bajo OCR_UMBRAL_SEGUNDA_OPINION.
  - TesseractOCR: fallback ligero si los motores deep-learning no están
    disponibles en el entorno (no instalados, o fallan en tiempo de ejecución).

Todas las implementaciones son perezosas: no importan sus dependencias pesadas
hasta que se usan, para que el resto de la app funcione sin ellas instaladas.
"""
from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturoTimeout
from typing import Protocol

import numpy as np

from ..dominio.modelos import PaginaOCR, PalabraOCR

logger = logging.getLogger(__name__)


class MotorOCR(Protocol):
    nombre: str

    def leer(self, imagen: np.ndarray, idioma: str = "spa") -> PaginaOCR: ...


class MotorNoDisponible(RuntimeError):
    """El motor no está instalado o falló al inicializarse en este entorno."""


# --------------------------------------------------------------------- Tesseract
class TesseractOCR:
    """Fallback ligero. Siempre debería poder usarse (binario nativo, sin deep learning)."""

    nombre = "tesseract"

    def __init__(self, cmd: str | None = None, tessdata_prefix: str | None = None) -> None:
        import pytesseract

        self._pytesseract = pytesseract
        if cmd:
            pytesseract.pytesseract.tesseract_cmd = cmd
        import os

        if tessdata_prefix:
            os.environ["TESSDATA_PREFIX"] = tessdata_prefix

    def leer(self, imagen: np.ndarray, idioma: str = "spa") -> PaginaOCR:
        from pytesseract import Output

        try:
            datos = self._pytesseract.image_to_data(
                imagen, lang=idioma, config="--oem 1 --psm 6", output_type=Output.DICT
            )
        except Exception as e:  # noqa: BLE001
            raise MotorNoDisponible(f"Tesseract falló: {e}") from e
        palabras: list[PalabraOCR] = []
        textos = []
        confs = []
        n = len(datos.get("text", []))
        for i in range(n):
            texto = (datos["text"][i] or "").strip()
            if not texto:
                continue
            conf_raw = float(datos["conf"][i])
            conf = max(conf_raw, 0.0) / 100.0
            palabras.append(
                PalabraOCR(
                    texto=texto,
                    x=int(datos["left"][i]),
                    y=int(datos["top"][i]),
                    ancho=int(datos["width"][i]),
                    alto=int(datos["height"][i]),
                    confianza=conf,
                    linea=int(datos["line_num"][i]),
                    bloque=int(datos["block_num"][i]),
                )
            )
            textos.append(texto)
            confs.append(conf)
        texto_completo = _reconstruir_texto(palabras)
        confianza_media = sum(confs) / len(confs) if confs else 0.0
        alto, ancho = imagen.shape[:2]
        return PaginaOCR(texto=texto_completo, palabras=palabras, confianza_media=confianza_media, ancho=ancho, alto=alto)


# --------------------------------------------------------------------- PaddleOCR
class PaddleOCRMotor:
    """Motor principal: PaddleOCR (PP-OCRv5), CPU-only."""

    nombre = "paddle"
    _MAPA_IDIOMA = {"spa": "latin", "es": "latin", "eng": "en", "en": "en"}

    def __init__(self) -> None:
        try:
            from paddleocr import PaddleOCR
        except Exception as e:  # noqa: BLE001
            raise MotorNoDisponible(f"PaddleOCR no está instalado/disponible: {e}") from e
        self._PaddleOCR = PaddleOCR
        self._instancias: dict[str, object] = {}
        # Paddle (oneDNN) ata sus predictores al hilo que los crea/calienta: ejecutarlos desde OTRO hilo falla con
        # "could not execute a primitive". Como la API atiende cada petición en un hilo distinto del pool, TODO el
        # uso de Paddle (crear + inferir) va a un único hilo dedicado.
        self._hilo = ThreadPoolExecutor(max_workers=1, thread_name_prefix="paddle")

    def _motor(self, idioma: str):
        clave = self._MAPA_IDIOMA.get(idioma, "latin")
        if clave not in self._instancias:
            self._instancias[clave] = self._PaddleOCR(use_angle_cls=True, lang=clave, show_log=False)
        return self._instancias[clave]

    def leer(self, imagen: np.ndarray, idioma: str = "spa") -> PaginaOCR:
        def _inferir():
            return self._motor(idioma).ocr(imagen, cls=True)

        try:
            resultado = self._hilo.submit(_inferir).result()
        except Exception as e:  # noqa: BLE001
            raise MotorNoDisponible(f"PaddleOCR falló en tiempo de ejecución: {e}") from e
        palabras: list[PalabraOCR] = []
        confs = []
        lineas = resultado[0] if resultado else []
        for i, linea in enumerate(lineas or []):
            caja, (texto, conf) = linea[0], linea[1]
            xs = [p[0] for p in caja]
            ys = [p[1] for p in caja]
            x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
            for palabra in texto.split():
                palabras.append(
                    PalabraOCR(
                        texto=palabra,
                        x=int(x0),
                        y=int(y0),
                        ancho=int(x1 - x0),
                        alto=int(y1 - y0),
                        confianza=float(conf),
                        linea=i,
                        bloque=0,
                    )
                )
            confs.append(float(conf))
        texto_completo = "\n".join(l[1][0] for l in (lineas or []))
        confianza_media = sum(confs) / len(confs) if confs else 0.0
        alto, ancho = imagen.shape[:2]
        return PaginaOCR(texto=texto_completo, palabras=palabras, confianza_media=confianza_media, ancho=ancho, alto=alto)


# --------------------------------------------------------------------- docTR
class DocTRMotor:
    """Segunda opinión: docTR vía backend OnnxTR (evita cargar PyTorch/TF completos)."""

    nombre = "doctr"

    def __init__(self) -> None:
        try:
            from onnxtr.models import ocr_predictor
        except Exception as e:  # noqa: BLE001
            raise MotorNoDisponible(f"docTR/OnnxTR no está instalado/disponible: {e}") from e
        try:
            # OnnxTR siempre carga pesos preentrenados (no acepta `pretrained`).
            self._predictor = ocr_predictor(det_arch="fast_base", reco_arch="vitstr_base")
        except Exception as e:  # noqa: BLE001
            raise MotorNoDisponible(f"docTR/OnnxTR no pudo inicializarse: {e}") from e

    def leer(self, imagen: np.ndarray, idioma: str = "spa") -> PaginaOCR:
        try:
            if imagen.ndim == 2:  # el preprocesado entrega gris/binarizada: docTR exige 3 canales
                rgb = np.repeat(imagen[:, :, None], 3, axis=2)
            else:
                rgb = np.ascontiguousarray(imagen[:, :, ::-1])
            resultado = self._predictor([rgb])
            doc = resultado.export()
        except Exception as e:  # noqa: BLE001
            raise MotorNoDisponible(f"docTR falló en tiempo de ejecución: {e}") from e
        alto, ancho = imagen.shape[:2]
        palabras: list[PalabraOCR] = []
        confs = []
        textos = []
        for pagina in doc.get("pages", []):
            for bloque_idx, bloque in enumerate(pagina.get("blocks", [])):
                for linea_idx, linea in enumerate(bloque.get("lines", [])):
                    for palabra in linea.get("words", []):
                        (x0r, y0r), (x1r, y1r) = palabra["geometry"]
                        conf = float(palabra.get("confidence", 0.0))
                        texto = palabra.get("value", "")
                        palabras.append(
                            PalabraOCR(
                                texto=texto,
                                x=int(x0r * ancho),
                                y=int(y0r * alto),
                                ancho=int((x1r - x0r) * ancho),
                                alto=int((y1r - y0r) * alto),
                                confianza=conf,
                                linea=linea_idx,
                                bloque=bloque_idx,
                            )
                        )
                        confs.append(conf)
                        textos.append(texto)
        texto_completo = _reconstruir_texto(palabras)
        confianza_media = sum(confs) / len(confs) if confs else 0.0
        return PaginaOCR(texto=texto_completo, palabras=palabras, confianza_media=confianza_media, ancho=ancho, alto=alto)


def _reconstruir_texto(palabras: list[PalabraOCR]) -> str:
    por_linea: dict[tuple[int, int], list[PalabraOCR]] = {}
    for p in palabras:
        por_linea.setdefault((p.bloque, p.linea), []).append(p)
    lineas = []
    for clave in sorted(por_linea.keys()):
        ps = sorted(por_linea[clave], key=lambda p: p.x)
        lineas.append(" ".join(p.texto for p in ps))
    return "\n".join(lineas)


_CACHE_MOTORES: dict[str, MotorOCR] = {}


def _crear_motor(nombre: str, settings) -> MotorOCR:
    if nombre == "paddle":
        return PaddleOCRMotor()
    if nombre == "doctr":
        return DocTRMotor()
    if nombre == "tesseract":
        from ..config import resolver_tessdata

        return TesseractOCR(
            cmd=settings.TESSERACT_CMD,
            tessdata_prefix=resolver_tessdata(settings.TESSDATA_PREFIX, settings.OCR_IDIOMA),
        )
    raise ValueError(f"Motor OCR desconocido: {nombre}")


_LOCK_MOTORES = threading.Lock()
_SEM_OCR: threading.BoundedSemaphore | None = None
_EJECUTOR_SEGUNDA_OPINION = ThreadPoolExecutor(max_workers=2, thread_name_prefix="ocr-2da-opinion")


def _semaforo_ocr(settings) -> threading.BoundedSemaphore:
    global _SEM_OCR
    with _LOCK_MOTORES:
        if _SEM_OCR is None:
            _SEM_OCR = threading.BoundedSemaphore(max(1, int(settings.OCR_MAX_CONCURRENTES)))
        return _SEM_OCR


def obtener_motor(nombre: str, settings) -> MotorOCR:
    """Devuelve el motor (cacheado). El lock evita que dos requests simultáneos inicialicen
    —y descarguen modelos de— el mismo motor a la vez."""
    with _LOCK_MOTORES:
        if nombre not in _CACHE_MOTORES:
            _CACHE_MOTORES[nombre] = _crear_motor(nombre, settings)
        return _CACHE_MOTORES[nombre]


def precargar_motores(settings) -> None:
    """Inicializa los motores configurados (principal + segunda opinión) sin leer nada."""
    for nombre in {settings.OCR_MOTOR, settings.OCR_SEGUNDA_OPINION} - {"", "ninguno"}:
        try:
            obtener_motor(nombre, settings)
            logger.info("Motor OCR '%s' precargado", nombre)
        except Exception as e:  # noqa: BLE001
            logger.warning("No se pudo precargar el motor '%s': %s", nombre, e)


def leer_pagina(imagen: np.ndarray, settings, idioma: str | None = None) -> tuple[PaginaOCR, str]:
    """Intenta el motor principal (settings.OCR_MOTOR); si no está disponible, cae a tesseract.

    Devuelve (página OCR, nombre del motor efectivamente usado).
    """
    idioma = idioma or settings.OCR_IDIOMA
    orden = [settings.OCR_MOTOR]
    if settings.OCR_MOTOR != "tesseract":
        orden.append("tesseract")
    ultimo_error: Exception | None = None
    for nombre in orden:
        try:
            motor = obtener_motor(nombre, settings)
            with _semaforo_ocr(settings):
                return motor.leer(imagen, idioma), nombre
        except MotorNoDisponible as e:
            logger.warning("Motor OCR '%s' no disponible, probando siguiente: %s", nombre, e)
            ultimo_error = e
            continue
    raise MotorNoDisponible(f"Ningún motor OCR disponible (último error: {ultimo_error})")


def segunda_opinion(imagen: np.ndarray, settings, idioma: str | None = None) -> PaginaOCR | None:
    """Lee con el motor de segunda opinión (docTR por defecto); None si no está configurado/disponible."""
    nombre = settings.OCR_SEGUNDA_OPINION
    if not nombre or nombre == "ninguno":
        return None

    def _tarea() -> PaginaOCR:
        motor = obtener_motor(nombre, settings)  # puede descargar/cargar modelos: dentro del timeout
        with _semaforo_ocr(settings):
            return motor.leer(imagen, idioma or settings.OCR_IDIOMA)

    futuro = _EJECUTOR_SEGUNDA_OPINION.submit(_tarea)
    try:
        return futuro.result(timeout=settings.OCR_SEGUNDA_OPINION_TIMEOUT_S)
    except FuturoTimeout:
        # El hilo no se puede matar; sigue en segundo plano pero el request continúa con el motor principal.
        logger.warning("Segunda opinión '%s' excedió %ss; se omite", nombre, settings.OCR_SEGUNDA_OPINION_TIMEOUT_S)
        return None
    except MotorNoDisponible as e:
        logger.warning("Motor de segunda opinión '%s' no disponible: %s", nombre, e)
        return None
