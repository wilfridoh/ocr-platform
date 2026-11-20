"""Motor y sesión de SQLAlchemy. El esquema lo crea otro agente con scripts SQL
(db/schema.sql) contra SQL Server; aquí NO se usa Alembic ni create_all en
producción. create_all solo se activa si settings.CREAR_TABLAS es verdadero
(pensado para SQLite en desarrollo/tests)."""
from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from ..config import get_settings


class Base(DeclarativeBase):
    pass


def _crear_engine():
    settings = get_settings()
    connect_args = {}
    if settings.DATABASE_URL.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
    return create_engine(settings.DATABASE_URL, connect_args=connect_args, future=True)


engine = _crear_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def inicializar_esquema() -> None:
    """Crea las tablas solo si settings.CREAR_TABLAS es True (desarrollo/tests con SQLite)."""
    settings = get_settings()
    if settings.CREAR_TABLAS:
        from . import modelos  # noqa: F401  (registra las tablas en Base.metadata)

        Base.metadata.create_all(bind=engine)
        _migrar_sqlite_dev()


def _migrar_sqlite_dev(motor=None) -> None:
    """create_all no altera tablas existentes: agrega a las bases SQLite de desarrollo las columnas
    nuevas del modelo (en SQL Server lo hacen db/schema*.sql). Solo columnas simples (nullable o con
    server_default); no toca datos."""
    motor = motor or engine
    if motor.dialect.name != "sqlite":
        return
    from sqlalchemy import inspect, text

    insp = inspect(motor)
    with motor.begin() as con:
        for tabla in Base.metadata.sorted_tables:
            if not insp.has_table(tabla.name):
                continue
            existentes = {c["name"] for c in insp.get_columns(tabla.name)}
            for col in tabla.columns:
                if col.name in existentes or col.primary_key:
                    continue
                tipo = col.type.compile(dialect=motor.dialect)
                defecto = f" DEFAULT {col.server_default.arg.text}" if col.server_default is not None else ""
                if not col.nullable and not defecto:
                    continue  # no se puede agregar NOT NULL sin valor por defecto en SQLite
                con.execute(text(f'ALTER TABLE "{tabla.name}" ADD COLUMN "{col.name}" {tipo}{defecto}'))


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
