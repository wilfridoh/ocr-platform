"""Comando: reprocesar todos los documentos clasificados bajo una plantilla (tras editarla)."""
from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..almacen import AlmacenDisco
from ..persistencia import modelos as m
from ..persistencia import repositorios as repo
from .actualizar_plantilla import PlantillaNoExiste
from .reprocesar_documento import reprocesar_documento

logger = logging.getLogger(__name__)


def documentos_de_plantilla(db: Session, plantilla_id: int) -> list[str]:
    """Ids de documentos cuyo resultado se generó con alguna versión de la plantilla."""
    stmt = (
        select(m.Resultado.DocumentoId)
        .join(m.PlantillaVersion, m.PlantillaVersion.PlantillaVersionId == m.Resultado.PlantillaVersionId)
        .where(m.PlantillaVersion.PlantillaId == plantilla_id)
    )
    return list(db.execute(stmt).scalars().all())


def reprocesar_documentos_de_plantilla(
    db: Session, almacen: AlmacenDisco, settings, plantilla_id: int
) -> dict[str, int]:
    """Reprocesa cada documento con la versión vigente de la plantilla.

    Devuelve {"total": reprocesados con éxito, "errores": fallidos}. Un fallo individual no
    detiene el lote (el documento queda en estado ERROR y se informa en `errores`).
    """
    if not repo.obtener_plantilla(db, plantilla_id):
        raise PlantillaNoExiste(f"La plantilla {plantilla_id} no existe")
    total = errores = 0
    for documento_id in documentos_de_plantilla(db, plantilla_id):
        try:
            reprocesar_documento(db, almacen, settings, documento_id, plantilla_id)
            total += 1
        except Exception:  # noqa: BLE001
            logger.exception("Falló el reproceso del documento %s", documento_id)
            errores += 1
    return {"total": total, "errores": errores}
