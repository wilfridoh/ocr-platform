from __future__ import annotations

from collections.abc import Generator

from fastapi import Depends
from sqlalchemy.orm import Session

from ..almacen import AlmacenDisco
from ..config import Settings, get_settings
from ..persistencia.db import SessionLocal


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_almacen(settings: Settings = Depends(get_settings)) -> AlmacenDisco:
    return AlmacenDisco(settings.ALMACEN_RUTA)
