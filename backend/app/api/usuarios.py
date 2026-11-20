"""Gestión de usuarios y sus API keys (docs/07 §5, §6.4). Solo Administrador."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..commands import usuarios as cmd
from ..dominio.flujos import UsuarioActualizar, UsuarioConClave, UsuarioCrear
from ..persistencia.utilidades_flujos import usuario_a_dto
from ..config import Settings, get_settings
from .dependencias import get_db
from .seguridad import Principal, autenticar, requiere_rol

router = APIRouter(prefix="/usuarios", tags=["usuarios"])
router_yo = APIRouter(tags=["usuarios"])


@router_yo.get("/yo")
def quien_soy(principal: Principal = Depends(autenticar), settings: Settings = Depends(get_settings)) -> dict:
    """Identidad de la clave usada (para que la UI muestre u oculte opciones según el rol). Cualquier rol."""
    return {
        "usuario_id": principal.usuario_id,
        "nombre": principal.nombre,
        "rol": principal.rol,
        # ¿este servidor tiene habilitado el acceso público sin clave? (la UI solo ofrece abrir un flujo si es así)
        "publico_habilitado": settings.PUBLICO_HABILITADO,
    }


def _o_404(db: Session, usuario_id: int):
    try:
        return cmd.obtener(db, usuario_id)
    except cmd.UsuarioNoExiste as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.get("")
def listar(db: Session = Depends(get_db), _: Principal = Depends(requiere_rol("Administrador"))) -> list[dict]:
    return [usuario_a_dto(u).model_dump(mode="json") for u in cmd.listar(db)]


@router.post("", status_code=status.HTTP_201_CREATED)
def crear(
    datos: UsuarioCrear, db: Session = Depends(get_db), _: Principal = Depends(requiere_rol("Administrador"))
) -> dict:
    """Crea el usuario y devuelve su API key en claro: es la ÚNICA vez que se puede ver."""
    usuario, clave = cmd.crear_usuario(db, datos)
    return UsuarioConClave(**usuario_a_dto(usuario).model_dump(), api_key=clave).model_dump(mode="json")


@router.patch("/{usuario_id}")
def actualizar(
    usuario_id: int,
    datos: UsuarioActualizar,
    db: Session = Depends(get_db),
    principal: Principal = Depends(requiere_rol("Administrador")),
) -> dict:
    usuario = _o_404(db, usuario_id)
    try:
        usuario = cmd.actualizar_usuario(db, usuario, datos, principal.usuario_id)
    except cmd.OperacionNoPermitida as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    return usuario_a_dto(usuario).model_dump(mode="json")


@router.post("/{usuario_id}/clave")
def regenerar_clave(
    usuario_id: int, db: Session = Depends(get_db), _: Principal = Depends(requiere_rol("Administrador"))
) -> dict:
    """Genera una API key nueva (la anterior deja de valer) y la devuelve una sola vez."""
    usuario = _o_404(db, usuario_id)
    clave = cmd.regenerar_clave(db, usuario)
    return UsuarioConClave(**usuario_a_dto(usuario).model_dump(), api_key=clave).model_dump(mode="json")
