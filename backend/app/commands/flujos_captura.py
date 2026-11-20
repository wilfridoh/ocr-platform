"""Comandos de flujos de captura (docs/07): crear, editar, activar/desactivar y fijar permisos."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..dominio.flujos import FlujoCapturaCrear
from ..persistencia import modelos as m
from ..persistencia import utilidades_flujos as uf


class FlujoNoExiste(ValueError):
    pass


class CodigoFlujoDuplicado(ValueError):
    pass


class PlantillasInvalidas(ValueError):
    pass


def _plantillas(db: Session, ids: list[int]) -> list[m.Plantilla]:
    unicos = sorted(set(ids))
    encontradas = list(db.execute(select(m.Plantilla).where(m.Plantilla.PlantillaId.in_(unicos))).scalars())
    if len(encontradas) != len(unicos):
        faltan = sorted(set(unicos) - {p.PlantillaId for p in encontradas})
        raise PlantillasInvalidas(f"Las plantillas {faltan} no existen")
    return encontradas


def obtener(db: Session, flujo_id: int) -> m.FlujoCaptura:
    flujo = db.get(m.FlujoCaptura, flujo_id)
    if flujo is None:
        raise FlujoNoExiste(f"El flujo {flujo_id} no existe")
    return flujo


def crear_flujo(db: Session, datos: FlujoCapturaCrear, creado_por_id: int | None) -> m.FlujoCaptura:
    if uf.flujo_por_codigo(db, datos.codigo):
        raise CodigoFlujoDuplicado(f"Ya existe un flujo con el código '{datos.codigo}'")
    flujo = m.FlujoCaptura(
        Codigo=datos.codigo,
        Nombre=datos.nombre,
        Instruccion=datos.instruccion,
        AceptaCamara=datos.acepta_camara,
        AceptaPdf=datos.acepta_pdf,
        Activo=datos.activo,
        CreadoPorId=creado_por_id,
        plantillas=_plantillas(db, datos.plantilla_ids),
    )
    db.add(flujo)
    db.commit()
    db.refresh(flujo)
    return flujo


def actualizar_flujo(db: Session, flujo: m.FlujoCaptura, datos: FlujoCapturaCrear) -> m.FlujoCaptura:
    if datos.codigo != flujo.Codigo and uf.flujo_por_codigo(db, datos.codigo):
        raise CodigoFlujoDuplicado(f"Ya existe un flujo con el código '{datos.codigo}'")
    flujo.Codigo = datos.codigo
    flujo.Nombre = datos.nombre
    flujo.Instruccion = datos.instruccion
    flujo.AceptaCamara = datos.acepta_camara
    flujo.AceptaPdf = datos.acepta_pdf
    flujo.Activo = datos.activo
    flujo.plantillas = _plantillas(db, datos.plantilla_ids)
    db.commit()
    db.refresh(flujo)
    return flujo


def cambiar_estado(db: Session, flujo: m.FlujoCaptura, activo: bool) -> m.FlujoCaptura:
    flujo.Activo = activo
    db.commit()
    db.refresh(flujo)
    return flujo


def fijar_acceso_publico(db: Session, flujo: m.FlujoCaptura, acceso_publico: bool) -> m.FlujoCaptura:
    flujo.AccesoPublico = acceso_publico
    db.commit()
    db.refresh(flujo)
    return flujo


def fijar_permisos(db: Session, flujo: m.FlujoCaptura, rol_minimo_edicion: str) -> m.FlujoCaptura:
    flujo.RolMinimoEdicion = rol_minimo_edicion
    db.commit()
    db.refresh(flujo)
    return flujo
