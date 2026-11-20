"""Purga de documentos (retención de datos personales). Solo Administrador."""
from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..almacen import AlmacenDisco
from ..commands import purgar_documentos as cmd
from ..config import Settings, get_settings
from .dependencias import get_almacen, get_db
from .seguridad import Principal, requiere_rol

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/purga", tags=["purga de documentos"])


class PurgaEntrada(BaseModel):
    alcance: Literal["vencidos", "todos"]
    # Salvaguarda: borrar es irreversible, la petición debe decir explícitamente que se confirma
    confirmar: bool = False


@router.get("")
def vista_previa(
    db: Session = Depends(get_db),
    almacen: AlmacenDisco = Depends(get_almacen),
    settings: Settings = Depends(get_settings),
    _: Principal = Depends(requiere_rol("Administrador")),
) -> dict:
    """Política vigente y cuánto se eliminaría con cada alcance, SIN borrar nada."""
    return {
        "retencion_dias": settings.DOC_RETENCION_DIAS,
        "automatica": settings.DOC_PURGA_AUTOMATICA and settings.DOC_RETENCION_DIAS > 0,
        "vencidos": (
            cmd.vista_previa(db, almacen, "vencidos", settings.DOC_RETENCION_DIAS).a_dict()
            if settings.DOC_RETENCION_DIAS > 0
            else {"documentos": 0, "archivos": 0, "bytes": 0}
        ),
        "todos": cmd.vista_previa(db, almacen, "todos", settings.DOC_RETENCION_DIAS).a_dict(),
    }


@router.post("")
def purgar(
    datos: PurgaEntrada,
    db: Session = Depends(get_db),
    almacen: AlmacenDisco = Depends(get_almacen),
    settings: Settings = Depends(get_settings),
    principal: Principal = Depends(requiere_rol("Administrador")),
) -> dict:
    """Elimina documentos (archivo + registros): `vencidos` (más viejos que la retención) o `todos`.
    Irreversible: exige `confirmar: true`."""
    if not datos.confirmar:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La purga es irreversible: envía confirmar=true")
    try:
        resumen = cmd.purgar(db, almacen, datos.alcance, settings.DOC_RETENCION_DIAS)
    except cmd.PurgaNoDisponible as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    logger.warning("Purga manual (%s) ejecutada por %s", datos.alcance, principal.nombre)
    return resumen.a_dict()
