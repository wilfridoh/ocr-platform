"""Retención y purga de documentos: una política para todo documento; archivos compartidos por hash; roles."""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import purga_automatica
from app.almacen import AlmacenDisco
from app.api import dependencias
from app.commands import purgar_documentos as cmd
from app.config import Settings, get_settings
from app.main import app
from app.persistencia import modelos as m
from app.persistencia.db import Base
from tests.test_api import HEADERS, client  # noqa: F401  (fixture)

ADMIN = HEADERS


def _hace(dias: int) -> datetime:
    return (datetime.now(timezone.utc) - timedelta(days=dias)).replace(tzinfo=None)


@pytest.fixture
def db():
    motor = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(motor)
    with Session(motor) as s:
        yield s


@pytest.fixture
def almacen(tmp_path):
    return AlmacenDisco(str(tmp_path / "archivos"))


def _doc(db, almacen, nombre: str, dias: int, contenido: bytes | None = None, con_resultado: bool = True) -> m.Documento:
    """Documento recibido hace `dias` días, con su archivo en el almacén (mismo contenido = mismo archivo)."""
    datos = contenido if contenido is not None else nombre.encode() * 10
    import hashlib

    h = hashlib.sha256(datos).hexdigest()
    ruta = almacen.guardar(h, "png", datos)
    d = m.Documento(NombreArchivo=nombre, TipoMime="image/png", TamanoBytes=len(datos), HashSha256=h, RutaAlmacen=ruta,
                    Estado="COMPLETADO", RecibidoEn=_hace(dias))
    db.add(d)
    db.flush()
    if con_resultado:
        r = m.Resultado(DocumentoId=d.DocumentoId, TipoDetectado="x", TextoCompleto="texto personal")
        db.add(r)
        db.flush()
        db.add(m.CampoExtraido(ResultadoId=r.ResultadoId, Nombre="c", ValorTexto="12345", Confianza=0.9))
    db.add(m.LogProcesamiento(DocumentoId=d.DocumentoId, Paso="ocr", Nivel="INFO", Mensaje="ok"))
    db.commit()
    return d


def _cuenta(db, modelo) -> int:
    return db.execute(select(func.count()).select_from(modelo)).scalar_one()


# ------------------------------------------------------------------ vencidos
def test_vencidos_borra_solo_lo_que_pasa_el_plazo(db, almacen):
    viejo = _doc(db, almacen, "viejo.png", 40)
    justo = _doc(db, almacen, "justo.png", 29)  # dentro del plazo
    nuevo = _doc(db, almacen, "nuevo.png", 0)
    id_viejo, ruta_vieja = viejo.DocumentoId, viejo.RutaAlmacen  # el objeto deja de existir tras la purga
    r = cmd.purgar(db, almacen, "vencidos", 30)
    assert (r.documentos, r.archivos) == (1, 1) and r.bytes > 0
    assert db.get(m.Documento, id_viejo) is None
    assert db.get(m.Documento, justo.DocumentoId) and db.get(m.Documento, nuevo.DocumentoId)
    assert not almacen.ruta_absoluta(ruta_vieja).exists()  # el archivo original también se va
    assert almacen.ruta_absoluta(justo.RutaAlmacen).exists() and almacen.ruta_absoluta(nuevo.RutaAlmacen).exists()


def test_se_borra_todo_lo_que_cuelga_del_documento(db, almacen):
    _doc(db, almacen, "viejo.png", 90)
    _doc(db, almacen, "nuevo.png", 1)
    cmd.purgar(db, almacen, "vencidos", 30)
    # quedan solo los datos del documento reciente: ni resultado, ni campos extraídos, ni log del viejo
    assert (_cuenta(db, m.Documento), _cuenta(db, m.Resultado), _cuenta(db, m.CampoExtraido), _cuenta(db, m.LogProcesamiento)) == (1, 1, 1, 1)


def test_un_archivo_compartido_por_hash_solo_se_borra_cuando_nadie_lo_usa(db, almacen):
    """El almacén guarda por hash: la misma cédula subida dos veces es UN archivo con dos registros."""
    viejo = _doc(db, almacen, "a.png", 50, contenido=b"misma cedula")
    nuevo = _doc(db, almacen, "b.png", 2, contenido=b"misma cedula")
    assert viejo.RutaAlmacen == nuevo.RutaAlmacen
    r = cmd.purgar(db, almacen, "vencidos", 30)
    assert r.documentos == 1 and r.archivos == 0  # el archivo lo sigue usando el documento reciente
    assert almacen.ruta_absoluta(nuevo.RutaAlmacen).read_bytes() == b"misma cedula"
    # cuando el último documento que lo usa también vence, ahora sí se borra
    ruta = nuevo.RutaAlmacen
    nuevo.RecibidoEn = _hace(60)
    db.commit()
    r = cmd.purgar(db, almacen, "vencidos", 30)
    assert r.documentos == 1 and r.archivos == 1
    assert not almacen.ruta_absoluta(ruta).exists()


def test_retencion_cero_desactiva_vencidos(db, almacen):
    _doc(db, almacen, "viejo.png", 400)
    with pytest.raises(cmd.PurgaNoDisponible):
        cmd.purgar(db, almacen, "vencidos", 0)
    assert _cuenta(db, m.Documento) == 1


# ------------------------------------------------------------------ todos
def test_todos_borra_todo_y_conserva_las_plantillas(db, almacen):
    d1 = _doc(db, almacen, "uno.png", 0)
    _doc(db, almacen, "dos.png", 100)
    p = m.Plantilla(Codigo="cedula", Nombre="Cédula")
    db.add(p)
    db.flush()
    v = m.PlantillaVersion(PlantillaId=p.PlantillaId, Numero=1, DocumentoEjemploId=d1.DocumentoId)  # documento de ejemplo
    db.add(v)
    db.commit()
    r = cmd.purgar(db, almacen, "todos", 30)
    assert (r.documentos, r.archivos) == (2, 2)
    assert _cuenta(db, m.Documento) == 0
    db.refresh(v)
    assert v.DocumentoEjemploId is None  # la referencia se limpia
    assert db.get(m.Plantilla, p.PlantillaId) is not None and db.get(m.PlantillaVersion, v.PlantillaVersionId) is not None
    assert not any(almacen.raiz.rglob("*.png"))


def test_vista_previa_no_borra_nada(db, almacen):
    _doc(db, almacen, "viejo.png", 50)
    _doc(db, almacen, "nuevo.png", 1)
    v = cmd.vista_previa(db, almacen, "vencidos", 30)
    t = cmd.vista_previa(db, almacen, "todos", 30)
    assert (v.documentos, v.archivos) == (1, 1) and (t.documentos, t.archivos) == (2, 2) and v.bytes > 0
    assert _cuenta(db, m.Documento) == 2 and len(list(almacen.raiz.rglob("*.png"))) == 2


def test_purga_en_lotes_grandes(db, almacen, monkeypatch):
    monkeypatch.setattr(cmd, "_LOTE", 3)  # fuerza varios lotes
    for i in range(10):
        _doc(db, almacen, f"d{i}.png", 90, con_resultado=(i % 2 == 0))
    assert cmd.purgar(db, almacen, "vencidos", 30).documentos == 10
    assert _cuenta(db, m.Documento) == 0 and _cuenta(db, m.CampoExtraido) == 0


def test_el_almacen_no_borra_fuera_de_su_raiz(almacen, tmp_path):
    fuera = tmp_path / "secreto.txt"
    fuera.write_text("x")
    with pytest.raises(ValueError):
        almacen.eliminar("../secreto.txt")
    assert fuera.exists()


# ------------------------------------------------------------------ API (solo Administrador)
def _doc_api(almacen_ruta: str, nombre: str, dias: int) -> str:
    db = next(app.dependency_overrides[dependencias.get_db]())
    try:
        return _doc(db, AlmacenDisco(almacen_ruta), nombre, dias).DocumentoId
    finally:
        db.close()


def test_api_solo_administrador_y_exige_confirmar(client, monkeypatch):  # noqa: F811
    s = get_settings()
    monkeypatch.setattr(s, "DOC_RETENCION_DIAS", 30)
    ruta = s.ALMACEN_RUTA
    _doc_api(ruta, "viejo.png", 60)
    _doc_api(ruta, "nuevo.png", 1)
    operador = {"X-API-Key": client.post("/api/usuarios", json={"nombre": "Op", "rol": "Operador"}, headers=ADMIN).json()["api_key"]}
    editor = {"X-API-Key": client.post("/api/usuarios", json={"nombre": "Ed", "rol": "Editor"}, headers=ADMIN).json()["api_key"]}

    for h in (operador, editor):  # ni lo ven ni lo ejecutan
        assert client.get("/api/purga", headers=h).status_code == 403
        assert client.post("/api/purga", json={"alcance": "todos", "confirmar": True}, headers=h).status_code == 403
    assert client.get("/api/purga").status_code == 401
    assert client.post("/api/purga", json={"alcance": "todos", "confirmar": True}).status_code == 401

    vp = client.get("/api/purga", headers=ADMIN).json()
    assert vp["retencion_dias"] == 30 and vp["vencidos"]["documentos"] == 1 and vp["todos"]["documentos"] == 2
    # sin confirmar no se borra nada
    assert client.post("/api/purga", json={"alcance": "vencidos"}, headers=ADMIN).status_code == 400
    assert client.get("/api/purga", headers=ADMIN).json()["todos"]["documentos"] == 2
    # alcance inválido
    assert client.post("/api/purga", json={"alcance": "lo-que-sea", "confirmar": True}, headers=ADMIN).status_code == 422

    r = client.post("/api/purga", json={"alcance": "vencidos", "confirmar": True}, headers=ADMIN)
    assert r.status_code == 200 and r.json()["documentos"] == 1
    r = client.post("/api/purga", json={"alcance": "todos", "confirmar": True}, headers=ADMIN)
    assert r.json()["documentos"] == 1
    assert client.get("/api/purga", headers=ADMIN).json()["todos"]["documentos"] == 0


def test_api_vencidos_con_retencion_cero_es_400(client, monkeypatch):  # noqa: F811
    monkeypatch.setattr(get_settings(), "DOC_RETENCION_DIAS", 0)
    assert client.post("/api/purga", json={"alcance": "vencidos", "confirmar": True}, headers=ADMIN).status_code == 400
    vp = client.get("/api/purga", headers=ADMIN).json()
    assert vp["retencion_dias"] == 0 and vp["automatica"] is False and vp["vencidos"]["documentos"] == 0


# ------------------------------------------------------------------ purga automática
def test_purga_automatica_una_vez_borra_solo_los_vencidos(db, almacen):
    _doc(db, almacen, "viejo.png", 50)
    _doc(db, almacen, "nuevo.png", 1)
    s = Settings(DOC_RETENCION_DIAS=30, ALMACEN_RUTA=str(almacen.raiz))
    assert purga_automatica.ejecutar_una_vez(s, fabrica_sesion=lambda: db) == {"documentos": 1, "archivos": 1, "bytes": pytest.approx(len(b"viejo.png" * 10))}
    assert _cuenta(db, m.Documento) == 1


def test_purga_automatica_no_hace_nada_sin_retencion_y_nunca_lanza(db, almacen):
    _doc(db, almacen, "viejo.png", 500)
    assert purga_automatica.ejecutar_una_vez(Settings(DOC_RETENCION_DIAS=0, ALMACEN_RUTA=str(almacen.raiz)), lambda: db) is None
    assert _cuenta(db, m.Documento) == 1

    def falla():
        raise RuntimeError("BD caída")

    assert purga_automatica.ejecutar_una_vez(Settings(DOC_RETENCION_DIAS=30), fabrica_sesion=falla) is None  # se registra, no revienta


def test_el_hilo_de_purga_solo_arranca_si_esta_habilitado():
    assert purga_automatica.iniciar(Settings(DOC_PURGA_AUTOMATICA=False, DOC_RETENCION_DIAS=30)) is False  # apagada de fábrica
    assert purga_automatica.iniciar(Settings(DOC_PURGA_AUTOMATICA=True, DOC_RETENCION_DIAS=0)) is False  # sin retención
    try:
        assert purga_automatica.iniciar(Settings(DOC_PURGA_AUTOMATICA=True, DOC_RETENCION_DIAS=30), espera_inicial_s=3600) is True
        assert purga_automatica.iniciar(Settings(DOC_PURGA_AUTOMATICA=True, DOC_RETENCION_DIAS=30), espera_inicial_s=3600) is False  # ya corre
    finally:
        purga_automatica.detener()
    assert Settings.model_fields["DOC_PURGA_AUTOMATICA"].default is False
    assert Settings.model_fields["DOC_RETENCION_DIAS"].default == 30
