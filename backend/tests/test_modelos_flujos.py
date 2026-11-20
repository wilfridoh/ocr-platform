"""Modelo de datos de docs/07: usuarios/roles, flujos de captura y columnas nuevas."""
import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.persistencia import modelos as m
from app.persistencia.db import Base, _migrar_sqlite_dev


@pytest.fixture
def db():
    motor = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(motor)
    with Session(motor) as s:
        yield s


def _plantilla(db, codigo="cedula_identidad"):
    p = m.Plantilla(Codigo=codigo, Nombre=codigo)
    db.add(p)
    db.commit()
    return p


def test_plantilla_rol_minimo_por_defecto_es_editor(db):
    assert _plantilla(db).RolMinimoEdicion == "Editor"


def test_usuario_rol_valido_y_hash_unico(db):
    db.add(m.Usuario(Nombre="Ana", ApiKeyHash="a" * 64, Rol="Operador"))
    db.commit()
    db.add(m.Usuario(Nombre="Otra", ApiKeyHash="a" * 64, Rol="Editor"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    db.add(m.Usuario(Nombre="Mala", ApiKeyHash="b" * 64, Rol="Superman"))
    with pytest.raises(IntegrityError):
        db.commit()


def test_flujo_con_plantillas_permitidas(db):
    ced, luz = _plantilla(db), _plantilla(db, "planilla_servicio")
    flujo = m.FlujoCaptura(Codigo="alta_cliente", Nombre="Alta", AceptaPdf=False, plantillas=[ced, luz])
    db.add(flujo)
    db.commit()
    db.refresh(flujo)
    assert {p.Codigo for p in flujo.plantillas} == {"cedula_identidad", "planilla_servicio"}
    assert flujo.Activo is True and flujo.AceptaCamara is True and flujo.AceptaPdf is False
    assert flujo.RolMinimoEdicion == "Editor"


def test_documento_por_flujo_y_estado_no_coincide(db):
    u = m.Usuario(Nombre="Ana", ApiKeyHash="c" * 64, Rol="Operador")
    f = m.FlujoCaptura(Codigo="f1", Nombre="F1")
    db.add_all([u, f])
    db.commit()
    d = m.Documento(
        NombreArchivo="x.png", TipoMime="image/png", TamanoBytes=1, HashSha256="d" * 64, RutaAlmacen="x",
        Estado="NO_COINCIDE", FlujoCapturaId=f.FlujoCapturaId, CreadoPorId=u.UsuarioId,
    )
    db.add(d)
    db.commit()
    assert d.FlujoCapturaId == f.FlujoCapturaId and d.CreadoPorId == u.UsuarioId
    db.add(m.Documento(NombreArchivo="y", TipoMime="x", TamanoBytes=1, HashSha256="e" * 64, RutaAlmacen="y", Estado="OTRO"))
    with pytest.raises(IntegrityError):
        db.commit()


def test_migracion_sqlite_agrega_columnas_a_base_existente_sin_perder_datos():
    """Una dev.db anterior (sin las columnas de docs/07) se actualiza sin tocar sus filas."""
    motor = create_engine("sqlite:///:memory:", poolclass=StaticPool, connect_args={"check_same_thread": False})
    with motor.begin() as con:
        con.execute(text(
            'CREATE TABLE "Plantilla" ("PlantillaId" INTEGER PRIMARY KEY, "Codigo" VARCHAR(100) NOT NULL, '
            '"Nombre" VARCHAR(200) NOT NULL, "Descripcion" VARCHAR(1000), "Activa" BOOLEAN NOT NULL, '
            '"VersionActualId" INTEGER, "CreadoEn" DATETIME NOT NULL, "ActualizadoEn" DATETIME NOT NULL)'
        ))
        con.execute(text(
            'CREATE TABLE "Documento" ("DocumentoId" VARCHAR(36) PRIMARY KEY, "NombreArchivo" VARCHAR(260) NOT NULL, '
            '"TipoMime" VARCHAR(100) NOT NULL, "TamanoBytes" INTEGER NOT NULL, "HashSha256" VARCHAR(64) NOT NULL, '
            '"RutaAlmacen" VARCHAR(500) NOT NULL, "Paginas" INTEGER NOT NULL, "Estado" VARCHAR(20) NOT NULL, '
            '"PlantillaForzadaId" INTEGER, "MensajeError" VARCHAR(2000), "RecibidoEn" DATETIME NOT NULL, "ProcesadoEn" DATETIME)'
        ))
        con.execute(text("INSERT INTO Plantilla VALUES (1,'p','P',NULL,1,NULL,'2026-01-01','2026-01-01')"))
        con.execute(text("INSERT INTO Documento VALUES ('d1','a.png','image/png',1,'h','r',1,'COMPLETADO',NULL,NULL,'2026-01-01',NULL)"))
    Base.metadata.create_all(motor)  # crea las tablas nuevas (Usuario, FlujoCaptura, ...)
    _migrar_sqlite_dev(motor)
    _migrar_sqlite_dev(motor)  # idempotente
    insp = inspect(motor)
    assert "RolMinimoEdicion" in {c["name"] for c in insp.get_columns("Plantilla")}
    assert {"FlujoCapturaId", "CreadoPorId"} <= {c["name"] for c in insp.get_columns("Documento")}
    with motor.connect() as con:
        assert con.execute(text('SELECT "RolMinimoEdicion" FROM "Plantilla"')).scalar() == "Editor"
        assert con.execute(text('SELECT COUNT(*) FROM "Documento" WHERE "FlujoCapturaId" IS NULL')).scalar() == 1
