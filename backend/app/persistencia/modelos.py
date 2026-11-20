"""Modelos ORM. Deben coincidir EXACTAMENTE con las tablas/columnas de
docs/04-base-de-datos.md (nombres en PascalCase tal cual). Usa tipos
portables (String/Integer/Boolean/DateTime/Numeric/Text) para poder correr
tests con SQLite en memoria; el esquema real en SQL Server lo crea otro
agente con scripts SQL (db/schema.sql), no Alembic ni create_all."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _nuevo_guid() -> str:
    return str(uuid.uuid4())


# Roles de docs/07 §3, de mayor a menor privilegio.
ROLES = ("Administrador", "Editor", "Operador")


class Plantilla(Base):
    __tablename__ = "Plantilla"

    PlantillaId: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    Codigo: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    Nombre: Mapped[str] = mapped_column(String(200), nullable=False)
    Descripcion: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    Activa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    VersionActualId: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("PlantillaVersion.PlantillaVersionId"), nullable=True
    )
    CreadoEn: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)
    ActualizadoEn: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)
    # Rol mínimo que puede editar esta plantilla (docs/07 §3); en BD: schema_flujos_captura.sql
    RolMinimoEdicion: Mapped[str] = mapped_column(
        String(20), nullable=False, default="Editor", server_default=text("'Editor'")
    )

    versiones: Mapped[list["PlantillaVersion"]] = relationship(
        "PlantillaVersion", back_populates="plantilla", foreign_keys="PlantillaVersion.PlantillaId"
    )
    version_actual: Mapped["PlantillaVersion"] = relationship(
        "PlantillaVersion", foreign_keys=[VersionActualId], post_update=True
    )


class PlantillaVersion(Base):
    __tablename__ = "PlantillaVersion"
    __table_args__ = (UniqueConstraint("PlantillaId", "Numero", name="UQ_PlantillaVersion_Plantilla_Numero"),)

    PlantillaVersionId: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    PlantillaId: Mapped[int] = mapped_column(Integer, ForeignKey("Plantilla.PlantillaId"), nullable=False)
    Numero: Mapped[int] = mapped_column(Integer, nullable=False)
    UmbralConfianza: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False, default=0.600)
    DocumentoEjemploId: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("Documento.DocumentoId"), nullable=True
    )
    CreadoEn: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)
    CreadoPor: Mapped[str | None] = mapped_column(String(100), nullable=True)

    plantilla: Mapped["Plantilla"] = relationship(
        "Plantilla", back_populates="versiones", foreign_keys=[PlantillaId]
    )
    palabras_clave: Mapped[list["PalabraClave"]] = relationship(
        "PalabraClave", back_populates="version", cascade="all, delete-orphan"
    )
    campos: Mapped[list["CampoPlantilla"]] = relationship(
        "CampoPlantilla", back_populates="version", cascade="all, delete-orphan", order_by="CampoPlantilla.Orden"
    )


class PalabraClave(Base):
    __tablename__ = "PalabraClave"

    PalabraClaveId: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    PlantillaVersionId: Mapped[int] = mapped_column(
        Integer, ForeignKey("PlantillaVersion.PlantillaVersionId"), nullable=False
    )
    Texto: Mapped[str] = mapped_column(String(200), nullable=False)
    Peso: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    __table_args__ = (CheckConstraint("Peso >= 1 AND Peso <= 5", name="CK_PalabraClave_Peso"),)

    version: Mapped["PlantillaVersion"] = relationship("PlantillaVersion", back_populates="palabras_clave")


class CampoPlantilla(Base):
    __tablename__ = "CampoPlantilla"
    __table_args__ = (
        UniqueConstraint("PlantillaVersionId", "Nombre", name="UQ_CampoPlantilla_Version_Nombre"),
        CheckConstraint(
            "TipoDato IN ('texto','numero','monto','fecha','rut','cedula','email','telefono')",
            name="CK_CampoPlantilla_TipoDato",
        ),
        CheckConstraint("Metodo IN ('regex','ancla','zona')", name="CK_CampoPlantilla_Metodo"),
    )

    CampoPlantillaId: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    PlantillaVersionId: Mapped[int] = mapped_column(
        Integer, ForeignKey("PlantillaVersion.PlantillaVersionId"), nullable=False
    )
    Nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    Etiqueta: Mapped[str] = mapped_column(String(200), nullable=False)
    TipoDato: Mapped[str] = mapped_column(String(20), nullable=False)
    Obligatorio: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    Metodo: Mapped[str] = mapped_column(String(10), nullable=False)
    ReglaJson: Mapped[str] = mapped_column(Text, nullable=False)
    Orden: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    version: Mapped["PlantillaVersion"] = relationship("PlantillaVersion", back_populates="campos")


class Documento(Base):
    __tablename__ = "Documento"
    __table_args__ = (
        CheckConstraint(
            "Estado IN ('RECIBIDO','PROCESANDO','COMPLETADO','ERROR','NO_COINCIDE')", name="CK_Documento_Estado"
        ),
    )

    DocumentoId: Mapped[str] = mapped_column(String(36), primary_key=True, default=_nuevo_guid)
    NombreArchivo: Mapped[str] = mapped_column(String(260), nullable=False)
    TipoMime: Mapped[str] = mapped_column(String(100), nullable=False)
    TamanoBytes: Mapped[int] = mapped_column(Integer, nullable=False)
    HashSha256: Mapped[str] = mapped_column(String(64), nullable=False)
    RutaAlmacen: Mapped[str] = mapped_column(String(500), nullable=False)
    Paginas: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    Estado: Mapped[str] = mapped_column(String(20), nullable=False)
    PlantillaForzadaId: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("Plantilla.PlantillaId"), nullable=True
    )
    MensajeError: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    RecibidoEn: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)
    ProcesadoEn: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Si llegó por un flujo de captura dirigido, y quién lo subió (None = clave del sistema). docs/07 §4
    FlujoCapturaId: Mapped[int | None] = mapped_column(Integer, ForeignKey("FlujoCaptura.FlujoCapturaId"), nullable=True)
    CreadoPorId: Mapped[int | None] = mapped_column(Integer, ForeignKey("Usuario.UsuarioId"), nullable=True)
    # Constancia de que la persona vio y aceptó el aviso de privacidad (flujo público): cuándo y qué versión del aviso
    ConsentimientoEn: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    AvisoVersion: Mapped[str | None] = mapped_column(String(20), nullable=True)

    resultado: Mapped["Resultado"] = relationship(
        "Resultado", back_populates="documento", uselist=False, cascade="all, delete-orphan"
    )


class Resultado(Base):
    __tablename__ = "Resultado"

    ResultadoId: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    DocumentoId: Mapped[str] = mapped_column(String(36), ForeignKey("Documento.DocumentoId"), unique=True, nullable=False)
    PlantillaVersionId: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("PlantillaVersion.PlantillaVersionId"), nullable=True
    )
    TipoDetectado: Mapped[str] = mapped_column(String(100), nullable=False)
    ConfianzaClasificacion: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False, default=0)
    ConfianzaGlobal: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False, default=0)
    TextoCompleto: Mapped[str] = mapped_column(Text, nullable=True)
    PalabrasClaveJson: Mapped[str] = mapped_column(Text, nullable=True)
    AlternativasJson: Mapped[str] = mapped_column(Text, nullable=True)
    AdvertenciasJson: Mapped[str] = mapped_column(Text, nullable=True)
    TiemposJson: Mapped[str] = mapped_column(Text, nullable=True)
    MotorOcr: Mapped[str] = mapped_column(String(30), nullable=True)
    # posición de las palabras y datos del recorte (docs/13 §1.3; migracion_009). NULL en resultados anteriores.
    PalabrasJson: Mapped[str | None] = mapped_column(Text, nullable=True)
    RecorteJson: Mapped[str | None] = mapped_column(Text, nullable=True)
    CreadoEn: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)

    documento: Mapped["Documento"] = relationship("Documento", back_populates="resultado")
    campos: Mapped[list["CampoExtraido"]] = relationship(
        "CampoExtraido", back_populates="resultado", cascade="all, delete-orphan"
    )


class CampoExtraido(Base):
    __tablename__ = "CampoExtraido"

    CampoExtraidoId: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ResultadoId: Mapped[int] = mapped_column(Integer, ForeignKey("Resultado.ResultadoId"), nullable=False)
    CampoPlantillaId: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("CampoPlantilla.CampoPlantillaId"), nullable=True
    )
    Nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    ValorTexto: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    ValorNormalizadoJson: Mapped[str | None] = mapped_column(Text, nullable=True)
    Confianza: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False, default=0)
    Pagina: Mapped[int | None] = mapped_column(Integer, nullable=True)
    X: Mapped[float | None] = mapped_column(Numeric(6, 5), nullable=True)
    Y: Mapped[float | None] = mapped_column(Numeric(6, 5), nullable=True)
    Ancho: Mapped[float | None] = mapped_column(Numeric(6, 5), nullable=True)
    Alto: Mapped[float | None] = mapped_column(Numeric(6, 5), nullable=True)
    Valido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    Motor: Mapped[str | None] = mapped_column(String(20), nullable=True)

    resultado: Mapped["Resultado"] = relationship("Resultado", back_populates="campos")


class LogProcesamiento(Base):
    __tablename__ = "LogProcesamiento"

    LogId: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    DocumentoId: Mapped[str] = mapped_column(String(36), ForeignKey("Documento.DocumentoId"), nullable=False)
    Paso: Mapped[str] = mapped_column(String(30), nullable=False)
    Nivel: Mapped[str] = mapped_column(String(10), nullable=False)
    Mensaje: Mapped[str] = mapped_column(String(2000), nullable=False)
    DuracionMs: Mapped[int | None] = mapped_column(Integer, nullable=True)
    RegistradoEn: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)


# --------------------------------------------------------------------- Flujos de captura y permisos (docs/07)
class Usuario(Base):
    """Una API key = un usuario con un rol. Solo se guarda el hash SHA-256 de la clave."""

    __tablename__ = "Usuario"
    __table_args__ = (CheckConstraint("Rol IN ('Administrador','Editor','Operador')", name="CK_Usuario_Rol"),)

    UsuarioId: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    Nombre: Mapped[str] = mapped_column(String(200), nullable=False)
    ApiKeyHash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    Rol: Mapped[str] = mapped_column(String(20), nullable=False)
    Activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    CreadoEn: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)


class FlujoCaptura(Base):
    __tablename__ = "FlujoCaptura"
    __table_args__ = (
        CheckConstraint(
            "RolMinimoEdicion IN ('Administrador','Editor','Operador')", name="CK_FlujoCaptura_RolMinimoEdicion"
        ),
    )

    FlujoCapturaId: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    Codigo: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    Nombre: Mapped[str] = mapped_column(String(200), nullable=False)
    Instruccion: Mapped[str | None] = mapped_column(String(500), nullable=True)
    AceptaCamara: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    AceptaPdf: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    Activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    RolMinimoEdicion: Mapped[str] = mapped_column(
        String(20), nullable=False, default="Editor", server_default=text("'Editor'")
    )
    # Opt-in: solo un flujo activo con AccesoPublico acepta subidas sin API key (lo fija un Administrador)
    AccesoPublico: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("0")
    )
    CreadoPorId: Mapped[int | None] = mapped_column(Integer, ForeignKey("Usuario.UsuarioId"), nullable=True)
    CreadoEn: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)
    ActualizadoEn: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)

    plantillas: Mapped[list["Plantilla"]] = relationship("Plantilla", secondary="FlujoCapturaPlantilla")


class FlujoCapturaPlantilla(Base):
    """Plantillas permitidas por flujo (M:N)."""

    __tablename__ = "FlujoCapturaPlantilla"

    FlujoCapturaId: Mapped[int] = mapped_column(Integer, ForeignKey("FlujoCaptura.FlujoCapturaId"), primary_key=True)
    PlantillaId: Mapped[int] = mapped_column(Integer, ForeignKey("Plantilla.PlantillaId"), primary_key=True)
