"""Modelos de entrada/salida de flujos de captura, usuarios y permisos (docs/07)."""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

Rol = Literal["Administrador", "Editor", "Operador"]


class PlantillaResumen(BaseModel):
    id: int
    codigo: str
    nombre: str
    activa: bool = True


class FlujoCapturaCrear(BaseModel):
    codigo: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9_]+$")
    nombre: str = Field(min_length=1, max_length=200)
    instruccion: Optional[str] = Field(default=None, max_length=500)
    acepta_camara: bool = True
    acepta_pdf: bool = True
    activo: bool = True
    plantilla_ids: list[int] = Field(min_length=1)  # plantillas permitidas (al menos una)


class FlujoCapturaDTO(BaseModel):
    id: int
    codigo: str
    nombre: str
    instruccion: Optional[str] = None
    acepta_camara: bool
    acepta_pdf: bool
    activo: bool
    rol_minimo_edicion: Rol
    acceso_publico: bool = False
    plantillas: list[PlantillaResumen]
    creado_por_id: Optional[int] = None
    creado_en: Optional[datetime] = None
    actualizado_en: Optional[datetime] = None


class EstadoEntrada(BaseModel):
    activo: bool


class AccesoPublicoEntrada(BaseModel):
    acceso_publico: bool


class FlujoPublicoDTO(BaseModel):
    """Lo único que se expone sin API key de un flujo: lo necesario para pintar la pantalla de captura."""

    codigo: str
    nombre: str
    instruccion: Optional[str] = None
    acepta_camara: bool
    acepta_pdf: bool
    retencion_dias: int = 0  # 0 = sin caducidad automática
    aviso_version: str = "1"


class PermisosEntrada(BaseModel):
    rol_minimo_edicion: Rol


class UsuarioCrear(BaseModel):
    nombre: str = Field(min_length=1, max_length=200)
    rol: Rol = "Operador"


class UsuarioActualizar(BaseModel):
    nombre: Optional[str] = Field(default=None, min_length=1, max_length=200)
    rol: Optional[Rol] = None
    activo: Optional[bool] = None


class UsuarioDTO(BaseModel):
    id: int
    nombre: str
    rol: Rol
    activo: bool
    creado_en: Optional[datetime] = None


class UsuarioConClave(UsuarioDTO):
    """Respuesta al crear o regenerar: la clave en claro se entrega UNA sola vez y no se puede recuperar."""

    api_key: str
