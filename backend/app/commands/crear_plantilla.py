from __future__ import annotations

from sqlalchemy.orm import Session

from ..dominio.modelos import PlantillaCrear
from ..persistencia import modelos as m
from ..persistencia import repositorios as repo


class CodigoDuplicado(ValueError):
    pass


def crear_plantilla(db: Session, datos: PlantillaCrear) -> m.Plantilla:
    if repo.obtener_plantilla_por_codigo(db, datos.codigo):
        raise CodigoDuplicado(f"Ya existe una plantilla con código '{datos.codigo}'")
    return repo.crear_plantilla(db, datos)
