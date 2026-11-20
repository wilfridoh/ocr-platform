"""Autenticación por X-API-Key y autorización por rol (docs/07 §3 y §5).

Cada API key identifica a un usuario con un rol. Además, la clave única del entorno (`API_KEY`)
sigue valiendo como **Administrador del sistema** sin fila en `Usuario`, para no romper los
despliegues existentes (ni el servidor MCP, que usa esa clave).
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import Settings, get_settings
from ..persistencia import modelos as m
from .dependencias import get_db

# Mayor número = más privilegios.
RANGO = {"Operador": 1, "Editor": 2, "Administrador": 3}


@dataclass(frozen=True)
class Principal:
    """Quién hace la petición. `usuario_id` es None para la clave del sistema."""

    usuario_id: int | None
    nombre: str
    rol: str

    def tiene_rol(self, minimo: str) -> bool:
        return RANGO.get(self.rol, 0) >= RANGO[minimo]


def hash_api_key(clave: str) -> str:
    """SHA-256 hexadecimal. Las claves son aleatorias y largas, así que un hash rápido basta."""
    return hashlib.sha256(clave.encode("utf-8")).hexdigest()


def generar_api_key() -> str:
    return "ocr_" + secrets.token_urlsafe(32)


def autenticar(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Principal:
    if not x_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="X-API-Key inválida o ausente")
    if hmac.compare_digest(x_api_key.encode("utf-8"), settings.API_KEY.encode("utf-8")):
        return Principal(usuario_id=None, nombre="Sistema", rol="Administrador")
    usuario = db.execute(select(m.Usuario).where(m.Usuario.ApiKeyHash == hash_api_key(x_api_key))).scalar_one_or_none()
    if usuario is None or not usuario.Activo:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="X-API-Key inválida o ausente")
    return Principal(usuario_id=usuario.UsuarioId, nombre=usuario.Nombre, rol=usuario.Rol)


# Compatibilidad: los routers existentes usan este nombre como dependencia de "clave válida".
verificar_api_key = autenticar


def requiere_rol(minimo: str):
    """Dependencia: exige al menos el rol `minimo` (403 si no)."""

    def _dep(principal: Principal = Depends(autenticar)) -> Principal:
        if not principal.tiene_rol(minimo):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Se requiere el rol {minimo} o superior (tu rol: {principal.rol})",
            )
        return principal

    return _dep


def exigir_edicion(principal: Principal, rol_minimo_recurso: str, base: str = "Editor") -> None:
    """Para editar una plantilla/flujo se exige el MAYOR entre el rol base de la ruta y el
    `RolMinimoEdicion` del recurso (una plantilla marcada 'Administrador' no la edita un Editor)."""
    exigido = max(base, rol_minimo_recurso, key=lambda r: RANGO.get(r, 0))
    if not principal.tiene_rol(exigido):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Este recurso solo lo puede editar el rol {exigido} o superior (tu rol: {principal.rol})",
        )


def autenticar_opcional(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Principal | None:
    """Para las (pocas) rutas con modo público: sin cabecera X-API-Key devuelve None (anónimo);
    con cabecera, la clave debe ser válida (una clave mala nunca se trata como anónimo).
    Si el acceso público está deshabilitado (PUBLICO_HABILITADO=false, por defecto) NO existe el modo anónimo:
    sin clave es 401, igual que en el resto de la API."""
    if x_api_key is None and settings.PUBLICO_HABILITADO:
        return None
    return autenticar(x_api_key=x_api_key, db=db, settings=settings)
