"""Consultas y conversión a DTO de flujos de captura y usuarios (docs/07)."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..dominio.flujos import FlujoCapturaDTO, PlantillaResumen, UsuarioDTO
from . import modelos as m


def flujo_por_codigo(db: Session, codigo: str) -> m.FlujoCaptura | None:
    return db.execute(select(m.FlujoCaptura).where(m.FlujoCaptura.Codigo == codigo)).scalar_one_or_none()


def listar_flujos(db: Session, solo_activos: bool = True) -> list[m.FlujoCaptura]:
    q = select(m.FlujoCaptura).order_by(m.FlujoCaptura.Nombre)
    if solo_activos:
        q = q.where(m.FlujoCaptura.Activo == True)  # noqa: E712 - `.is_(True)` compila a "IS 1", inválido en T-SQL
    return list(db.execute(q).scalars())


def flujo_a_dto(f: m.FlujoCaptura) -> FlujoCapturaDTO:
    return FlujoCapturaDTO(
        id=f.FlujoCapturaId,
        codigo=f.Codigo,
        nombre=f.Nombre,
        instruccion=f.Instruccion,
        acepta_camara=f.AceptaCamara,
        acepta_pdf=f.AceptaPdf,
        activo=f.Activo,
        rol_minimo_edicion=f.RolMinimoEdicion,
        acceso_publico=f.AccesoPublico,
        plantillas=[
            PlantillaResumen(id=p.PlantillaId, codigo=p.Codigo, nombre=p.Nombre, activa=p.Activa)
            for p in sorted(f.plantillas, key=lambda p: p.Nombre)
        ],
        creado_por_id=f.CreadoPorId,
        creado_en=f.CreadoEn,
        actualizado_en=f.ActualizadoEn,
    )


def usuario_a_dto(u: m.Usuario) -> UsuarioDTO:
    return UsuarioDTO(id=u.UsuarioId, nombre=u.Nombre, rol=u.Rol, activo=u.Activo, creado_en=u.CreadoEn)
