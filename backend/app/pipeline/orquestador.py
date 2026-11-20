"""Orquesta ingesta -> preprocesado -> OCR. No conoce plantillas ni BD."""
from __future__ import annotations

import time

from ..dominio.modelos import PaginaOCR
from . import ocr as ocr_mod
from .ingesta import DocumentoIngresado, ingerir
from .preprocesado import OpcionesPreprocesado, preprocesar_detalle


class ErrorPipeline(RuntimeError):
    pass


def procesar_bytes(
    nombre: str, datos: bytes, settings, idioma: str | None = None, recortes_manuales: dict[int, dict] | None = None
) -> tuple[DocumentoIngresado, list[PaginaOCR], str, dict[str, int]]:
    """Ejecuta el pipeline completo de lectura (sin clasificación/extracción).

    `recortes_manuales`: {numero_pagina: {"esquinas": [...] | None, "orientacion": 0|90|180|270}} marcados por una
    persona (docs/13 §4.2); esas páginas no pasan por la detección automática del recorte.

    Devuelve (documento ingresado, páginas OCR, motor OCR usado, tiempos_ms parciales).
    """
    recortes_manuales = recortes_manuales or {}
    tiempos: dict[str, int] = {}
    idioma = idioma or settings.OCR_IDIOMA

    t0 = time.perf_counter()
    doc = ingerir(
        nombre,
        datos,
        max_mb=settings.MAX_TAMANO_MB,
        dpi=settings.OCR_DPI,
        max_megapixeles=settings.OCR_MAX_MEGAPIXELES,
        megapixeles_procesado=settings.OCR_MEGAPIXELES_PROCESADO,
        max_paginas=settings.OCR_MAX_PAGINAS,
    )
    tiempos["ingesta"] = int((time.perf_counter() - t0) * 1000)

    if doc.es_pdf_nativo:
        tiempos["preprocesado"] = 0
        tiempos["ocr"] = 0
        for p in doc.paginas_nativas:
            p.motor = "pdf-nativo"
            p.recorte = {"aplicado": False, "origen": "pdf", "esquinas": None, "orientacion": 0, "deskew": 0.0,
                         "relacion": round(max(p.ancho, p.alto) / max(1, min(p.ancho, p.alto)), 3)}
        return doc, doc.paginas_nativas, "pdf-nativo", tiempos

    op = OpcionesPreprocesado(
        perspectiva=settings.PRE_PERSPECTIVA,
        deskew=settings.PRE_DESKEW,
        denoise=settings.PRE_DENOISE,
        binarizar=settings.PRE_BINARIZAR,
        reescalar=settings.PRE_REESCALAR,
    )

    t0 = time.perf_counter()
    imagenes_proc = []
    pasos_por_pagina = []
    recortes = []
    for i, img in enumerate(doc.imagenes):
        proc, pasos, _factor, recorte = preprocesar_detalle(img, op, recortes_manuales.get(i + 1))
        imagenes_proc.append(proc)
        pasos_por_pagina.append(pasos)
        recortes.append(recorte)
    tiempos["preprocesado"] = int((time.perf_counter() - t0) * 1000)
    doc.imagenes_procesadas = imagenes_proc

    t0 = time.perf_counter()
    paginas: list[PaginaOCR] = []
    motor_usado = ""
    try:
        for i, img in enumerate(imagenes_proc):
            pagina, motor_usado = ocr_mod.leer_pagina(img, settings, idioma)
            pagina.numero = i + 1
            pagina.motor = motor_usado
            pagina.pasos_preprocesado = pasos_por_pagina[i]
            pagina.recorte = recortes[i]
            for p in pagina.palabras:
                p.pagina = i + 1
            paginas.append(pagina)
    except ocr_mod.MotorNoDisponible as e:
        raise ErrorPipeline(f"OCR no disponible: {e}") from e
    tiempos["ocr"] = int((time.perf_counter() - t0) * 1000)

    return doc, paginas, motor_usado, tiempos


def proveedor_segunda_opinion(doc: DocumentoIngresado, settings, motor_usado: str, idioma: str | None = None):
    """Devuelve un callable perezoso que lee el documento con el motor de segunda opinión.

    El callable devuelve list[PaginaOCR] o None (sin motor / no disponible / PDF nativo / mismo
    motor que el principal). Solo se ejecuta si el extractor detecta campos bajo umbral, y su
    resultado se cachea para no releer el documento por cada campo.
    """
    nombre = settings.OCR_SEGUNDA_OPINION
    if not nombre or nombre == "ninguno" or nombre == motor_usado or not doc.imagenes_procesadas:
        return None
    cache: dict[str, list[PaginaOCR] | None] = {}

    def _leer() -> list[PaginaOCR] | None:
        if "paginas" not in cache:
            paginas: list[PaginaOCR] = []
            for i, img in enumerate(doc.imagenes_procesadas):
                pag = ocr_mod.segunda_opinion(img, settings, idioma)
                if pag is None:
                    cache["paginas"] = None
                    break
                pag.numero = i + 1
                pag.motor = nombre
                for p in pag.palabras:
                    p.pagina = i + 1
                paginas.append(pag)
            else:
                cache["paginas"] = paginas
        return cache["paginas"]

    return _leer
