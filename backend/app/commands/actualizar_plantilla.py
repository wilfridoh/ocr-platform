from __future__ import annotations

from sqlalchemy.orm import Session

from ..dominio.modelos import PlantillaCrear
from ..persistencia import modelos as m
from ..persistencia import repositorios as repo


class PlantillaNoExiste(ValueError):
    pass


def actualizar_plantilla(db: Session, plantilla_id: int, datos: PlantillaCrear) -> m.Plantilla:
    plantilla = repo.obtener_plantilla(db, plantilla_id)
    if not plantilla:
        raise PlantillaNoExiste(f"La plantilla {plantilla_id} no existe")
    return repo.nueva_version_plantilla(db, plantilla, datos)


def cambiar_estado(db: Session, plantilla_id: int, activa: bool) -> m.Plantilla:
    plantilla = repo.obtener_plantilla(db, plantilla_id)
    if not plantilla:
        raise PlantillaNoExiste(f"La plantilla {plantilla_id} no existe")
    return repo.cambiar_estado_plantilla(db, plantilla, activa)
