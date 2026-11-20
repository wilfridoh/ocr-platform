"""Purga automática diaria de documentos vencidos (DOC_RETENCION_DIAS), en un hilo de fondo.

Pensado para este despliegue de UN solo proceso: sin scheduler externo. Si algún día hay varias réplicas, cada una
ejecutaría la purga, lo cual es inofensivo (es idempotente). También se puede disparar a mano: POST /api/purga.
"""
from __future__ import annotations

import logging
import threading

from .almacen import AlmacenDisco
from .commands.purgar_documentos import purgar
from .config import Settings
from .persistencia.db import SessionLocal

logger = logging.getLogger(__name__)

_DETENER = threading.Event()
_hilo: threading.Thread | None = None


def ejecutar_una_vez(settings: Settings, fabrica_sesion=SessionLocal) -> dict[str, int] | None:
    """Purga los documentos vencidos una vez. Nunca lanza: un fallo se registra y se reintenta en el próximo ciclo."""
    if settings.DOC_RETENCION_DIAS <= 0:
        return None
    try:
        with fabrica_sesion() as db:
            return purgar(db, AlmacenDisco(settings.ALMACEN_RUTA), "vencidos", settings.DOC_RETENCION_DIAS).a_dict()
    except Exception:  # noqa: BLE001
        logger.exception("Falló la purga automática de documentos")
        return None


def _bucle(settings: Settings, espera_inicial_s: float) -> None:
    if _DETENER.wait(espera_inicial_s):
        return
    while not _DETENER.is_set():
        ejecutar_una_vez(settings)
        if _DETENER.wait(max(1, settings.DOC_PURGA_INTERVALO_HORAS) * 3600):
            return


def iniciar(settings: Settings, espera_inicial_s: float = 60.0) -> bool:
    """Arranca el hilo si la purga automática está encendida y hay retención. Devuelve si lo arrancó."""
    global _hilo
    if not settings.DOC_PURGA_AUTOMATICA or settings.DOC_RETENCION_DIAS <= 0:
        return False
    if _hilo is not None and _hilo.is_alive():
        return False
    _DETENER.clear()
    _hilo = threading.Thread(target=_bucle, args=(settings, espera_inicial_s), daemon=True, name="purga-documentos")
    _hilo.start()
    logger.info("Purga automática de documentos activa: cada %s h, retención %s días", settings.DOC_PURGA_INTERVALO_HORAS, settings.DOC_RETENCION_DIAS)
    return True


def detener() -> None:
    _DETENER.set()
