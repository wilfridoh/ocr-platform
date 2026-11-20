from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..dominio.modelos import PlantillaDTO
from ..persistencia import modelos as m
from ..persistencia import repositorios as repo
from .._convertir_a_dto import plantilla_a_dto


def listar_plantillas(db: Session, solo_activas: bool = False) -> list[PlantillaDTO]:
    plantillas = repo.listar_plantillas(db, solo_activas)
    # documentos por plantilla, en una sola consulta (Resultado -> PlantillaVersion -> Plantilla)
    filas = db.execute(
        select(m.PlantillaVersion.PlantillaId, func.count(m.Resultado.ResultadoId))
        .join(m.Resultado, m.Resultado.PlantillaVersionId == m.PlantillaVersion.PlantillaVersionId)
        .group_by(m.PlantillaVersion.PlantillaId)
    ).all()
    totales = {pid: int(n) for pid, n in filas}
    dtos = []
    for p in plantillas:
        dto = plantilla_a_dto(p)
        dto.total_documentos = totales.get(p.PlantillaId, 0)
        dtos.append(dto)
    return dtos


def obtener_plantilla(db: Session, plantilla_id: int) -> PlantillaDTO | None:
    p = repo.obtener_plantilla(db, plantilla_id)
    return plantilla_a_dto(p) if p else None
