"""Comandos de usuarios (docs/07 §3, §5): alta con API key, cambio de rol/estado, regenerar clave."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..api.seguridad import generar_api_key, hash_api_key
from ..dominio.flujos import UsuarioActualizar, UsuarioCrear
from ..persistencia import modelos as m


class UsuarioNoExiste(ValueError):
    pass


class OperacionNoPermitida(ValueError):
    """Evita dejar el sistema sin administración (p. ej. un usuario que se degrada a sí mismo)."""


def obtener(db: Session, usuario_id: int) -> m.Usuario:
    u = db.get(m.Usuario, usuario_id)
    if u is None:
        raise UsuarioNoExiste(f"El usuario {usuario_id} no existe")
    return u


def listar(db: Session) -> list[m.Usuario]:
    return list(db.execute(select(m.Usuario).order_by(m.Usuario.Nombre)).scalars())


def crear_usuario(db: Session, datos: UsuarioCrear) -> tuple[m.Usuario, str]:
    """Devuelve (usuario, api_key en claro). La clave en claro no se vuelve a poder consultar."""
    clave = generar_api_key()
    u = m.Usuario(Nombre=datos.nombre, Rol=datos.rol, ApiKeyHash=hash_api_key(clave), Activo=True)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u, clave


def actualizar_usuario(
    db: Session, usuario: m.Usuario, datos: UsuarioActualizar, actor_usuario_id: int | None
) -> m.Usuario:
    if actor_usuario_id is not None and usuario.UsuarioId == actor_usuario_id:
        if datos.activo is False or (datos.rol is not None and datos.rol != "Administrador"):
            raise OperacionNoPermitida("No puedes desactivarte ni quitarte el rol de Administrador a ti mismo")
    if datos.nombre is not None:
        usuario.Nombre = datos.nombre
    if datos.rol is not None:
        usuario.Rol = datos.rol
    if datos.activo is not None:
        usuario.Activo = datos.activo
    db.commit()
    db.refresh(usuario)
    return usuario


def regenerar_clave(db: Session, usuario: m.Usuario) -> str:
    """Invalida la clave anterior y devuelve la nueva en claro (una sola vez)."""
    clave = generar_api_key()
    usuario.ApiKeyHash = hash_api_key(clave)
    db.commit()
    return clave

