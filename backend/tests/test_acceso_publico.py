"""Acceso PÚBLICO (sin API key) a flujos de captura: la única excepción de la API, acotada y protegida."""
import re
import threading

import pytest
from sqlalchemy import select

from app.api import dependencias, limitador as lim
from app.config import get_settings
from app.main import app
from app.persistencia import modelos as m
from tests.conftest import imagen_a_bytes
from tests.test_api import _DEF_BASICA, HEADERS, _tesseract_disponible, client  # noqa: F401  (fixture)

ADMIN = HEADERS


@pytest.fixture(autouse=True)
def _limites_limpios(monkeypatch):
    """Cada test arranca con contadores vacíos y límites conocidos."""
    lim.limitador.reiniciar()
    s = get_settings()
    monkeypatch.setattr(s, "PUBLICO_HABILITADO", True)  # estos tests ejercitan el modo público
    monkeypatch.setattr(s, "PUBLICO_LIMITE_IP_POR_MINUTO", 10)
    monkeypatch.setattr(s, "PUBLICO_LIMITE_GLOBAL_POR_MINUTO", 60)
    monkeypatch.setattr(s, "PUBLICO_LIMITE_INFO_POR_MINUTO", 60)
    monkeypatch.setattr(s, "PUBLICO_MAX_CONCURRENTES", 2)
    monkeypatch.setattr(s, "PUBLICO_CONFIAR_PROXY", False)
    yield
    lim.limitador.reiniciar()


def _flujo(client, *, publico: bool, activo: bool = True, acepta_pdf: bool = True, codigo: str = "alta_cliente") -> int:
    r = client.post("/api/plantillas", json=_DEF_BASICA, headers=ADMIN)
    if r.status_code == 201:
        pid = r.json()["id"]
    else:  # la plantilla de prueba ya existe (el test crea varios flujos)
        pid = next(p["id"] for p in client.get("/api/plantillas", headers=ADMIN).json() if p["codigo"] == _DEF_BASICA["codigo"])
    body = {"codigo": codigo, "nombre": "Alta", "instruccion": "Sube tu cédula", "plantilla_ids": [pid],
            "acepta_pdf": acepta_pdf, "activo": activo}
    fid = client.post("/api/flujos-captura", json=body, headers=ADMIN).json()["id"]
    if publico:
        r = client.patch(f"/api/flujos-captura/{fid}/acceso-publico", json={"acceso_publico": True}, headers=ADMIN)
        assert r.status_code == 200 and r.json()["acceso_publico"] is True
    return fid


def _fila(model, **filtro):
    db = next(app.dependency_overrides[dependencias.get_db]())
    try:
        return db.execute(select(model).filter_by(**filtro)).scalars().first()
    finally:
        db.close()


def _logs(documento_id: str) -> list[str]:
    db = next(app.dependency_overrides[dependencias.get_db]())
    try:
        return [l.Mensaje for l in db.execute(select(m.LogProcesamiento).filter_by(DocumentoId=documento_id)).scalars()]
    finally:
        db.close()


CONSENT = {"consentimiento": "true", "aviso_version": "1"}  # aviso de privacidad aceptado
PNG = ("a.png", b"\x89PNG\r\n\x1a\n" + b"0" * 64, "image/png")
PDF = ("a.pdf", b"%PDF-1.4", "application/pdf")


# ------------------------------------------------------------------ la excepción es acotada
def test_ninguna_ruta_queda_sin_proteger(client):
    """Recorre TODAS las rutas de la app sin X-API-Key: solo las 3 permitidas pueden responder algo distinto de 401."""
    permitidas = {
        ("GET", "/api/salud"),
        ("GET", "/api/flujos-captura/{codigo}/publico"),
        ("POST", "/api/flujos-captura/{codigo}/documentos"),
    }
    revisadas = 0
    for ruta in app.routes:
        if not hasattr(ruta, "methods") or not ruta.path.startswith("/api"):
            continue  # /docs, /openapi.json, /redoc (Swagger)
        for metodo in sorted(ruta.methods - {"HEAD", "OPTIONS"}):
            url = re.sub(r"\{[^}]+\}", "1", ruta.path)
            r = client.request(metodo, url)
            revisadas += 1
            if (metodo, ruta.path) in permitidas:
                assert r.status_code != 401, (metodo, ruta.path)  # estas 3 SÍ son accesibles sin clave
            else:
                assert r.status_code == 401, f"{metodo} {ruta.path} respondió {r.status_code} sin X-API-Key"
    assert revisadas >= 30  # sanity: de verdad se recorrió la API


def test_clave_invalida_en_ruta_publica_es_401_no_anonimo(client):
    _flujo(client, publico=True)
    r = client.post("/api/flujos-captura/alta_cliente/documentos", data=CONSENT, files={"archivo": PNG}, headers={"X-API-Key": "mala"})
    assert r.status_code == 401
    assert client.get("/api/flujos-captura/alta_cliente/publico", headers={"X-API-Key": "mala"}).status_code == 401


def test_solo_un_administrador_abre_el_acceso_publico(client):
    fid = _flujo(client, publico=False)
    ed = client.post("/api/usuarios", json={"nombre": "Ed", "rol": "Editor"}, headers=ADMIN).json()["api_key"]
    r = client.patch(f"/api/flujos-captura/{fid}/acceso-publico", json={"acceso_publico": True}, headers={"X-API-Key": ed})
    assert r.status_code == 403
    assert client.get("/api/flujos-captura/alta_cliente", headers=ADMIN).json()["acceso_publico"] is False
    # un Editor que edita el flujo no puede abrirlo por la puerta de atrás
    body = {"codigo": "alta_cliente", "nombre": "X", "plantilla_ids": [1], "acceso_publico": True}
    assert client.put(f"/api/flujos-captura/{fid}", json=body, headers={"X-API-Key": ed}).status_code == 200
    assert client.get("/api/flujos-captura/alta_cliente", headers=ADMIN).json()["acceso_publico"] is False


def test_flujo_privado_inactivo_o_inexistente_son_indistinguibles_para_un_anonimo(client):
    _flujo(client, publico=False, codigo="privado")
    _flujo(client, publico=True, activo=False, codigo="inactivo")
    for codigo in ("privado", "inactivo", "no_existe"):
        a = client.post(f"/api/flujos-captura/{codigo}/documentos", data=CONSENT, files={"archivo": PNG})
        b = client.get(f"/api/flujos-captura/{codigo}/publico")
        assert (a.status_code, b.status_code) == (404, 404), codigo
        assert a.json() == {"detail": "Flujo de captura no encontrado"}  # mismo mensaje: no se puede enumerar


def test_info_publica_solo_expone_lo_minimo(client):
    _flujo(client, publico=True)
    r = client.get("/api/flujos-captura/alta_cliente/publico")  # sin clave
    assert r.status_code == 200
    assert set(r.json()) == {"codigo", "nombre", "instruccion", "acepta_camara", "acepta_pdf", "retencion_dias", "aviso_version"}
    # el detalle completo (con plantillas e ids) sigue exigiendo clave
    assert client.get("/api/flujos-captura/alta_cliente").status_code == 401


def test_el_resto_de_la_api_sigue_cerrado_aunque_exista_un_flujo_publico(client):
    _flujo(client, publico=True)
    for metodo, url in [("GET", "/api/flujos-captura"), ("GET", "/api/plantillas"), ("GET", "/api/documentos"),
                        ("GET", "/api/usuarios"), ("POST", "/api/documentos")]:
        assert client.request(metodo, url).status_code == 401, (metodo, url)


# ------------------------------------------------------------------ límites
def test_pdf_rechazado_en_flujo_que_no_lo_acepta_aun_siendo_publico(client):
    _flujo(client, publico=True, acepta_pdf=False)
    r = client.post("/api/flujos-captura/alta_cliente/documentos", data=CONSENT, files={"archivo": PDF})
    assert r.status_code == 400 and "PDF" in r.json()["detail"]


def test_limite_por_ip_devuelve_429_con_retry_after(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "PUBLICO_LIMITE_IP_POR_MINUTO", 3)
    _flujo(client, publico=True, acepta_pdf=False)  # el PDF se rechaza rápido (400): sirve para contar intentos
    codigos = [client.post("/api/flujos-captura/alta_cliente/documentos", data=CONSENT, files={"archivo": PDF}).status_code for _ in range(5)]
    assert codigos == [400, 400, 400, 429, 429]
    r = client.post("/api/flujos-captura/alta_cliente/documentos", data=CONSENT, files={"archivo": PDF})
    assert r.status_code == 429 and int(r.headers["Retry-After"]) >= 1


def test_los_intentos_contra_flujos_inexistentes_tambien_cuentan(client, monkeypatch):
    """Si no contaran, se podrían enumerar códigos de flujo sin límite."""
    monkeypatch.setattr(get_settings(), "PUBLICO_LIMITE_IP_POR_MINUTO", 2)
    codigos = [client.post("/api/flujos-captura/x/documentos", data=CONSENT, files={"archivo": PNG}).status_code for _ in range(4)]
    assert codigos == [404, 404, 429, 429]


def test_limite_global_protege_aunque_cambie_la_ip(client, monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "PUBLICO_CONFIAR_PROXY", True)
    monkeypatch.setattr(s, "PUBLICO_LIMITE_GLOBAL_POR_MINUTO", 3)
    codigos = []
    for i in range(5):  # cinco IP distintas, una petición cada una
        r = client.post("/api/flujos-captura/x/documentos", data=CONSENT, files={"archivo": PNG}, headers={"X-Forwarded-For": f"9.9.9.{i}"})
        codigos.append(r.status_code)
    assert codigos == [404, 404, 404, 429, 429]


def test_la_ip_sale_del_ultimo_x_forwarded_for_solo_si_se_confia_en_el_proxy(client, monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "PUBLICO_LIMITE_IP_POR_MINUTO", 1)

    def post(xff):
        return client.post("/api/flujos-captura/x/documentos", data=CONSENT, files={"archivo": PNG}, headers={"X-Forwarded-For": xff}).status_code

    # sin confiar en el proxy, falsear X-Forwarded-For no sirve para esquivar el límite
    monkeypatch.setattr(s, "PUBLICO_CONFIAR_PROXY", False)
    assert [post("1.1.1.1"), post("2.2.2.2")] == [404, 429]
    lim.limitador.reiniciar()
    # confiando en el proxy se usa la ÚLTIMA entrada (la que agregó nginx), no las que escribió el cliente
    monkeypatch.setattr(s, "PUBLICO_CONFIAR_PROXY", True)
    assert post("6.6.6.6, 8.8.8.8") == 404
    assert post("7.7.7.7, 8.8.8.8") == 429  # mismo cliente real (8.8.8.8) aunque cambie la parte falsificable
    assert post("7.7.7.7, 5.5.5.5") == 404  # otro cliente real


def test_tope_de_concurrencia_publica_devuelve_503(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "PUBLICO_MAX_CONCURRENTES", 1)
    _flujo(client, publico=True)
    with lim.CupoConcurrencia(get_settings()):  # otro procesamiento público en curso ocupa el único cupo
        r = client.post("/api/flujos-captura/alta_cliente/documentos", data=CONSENT, files={"archivo": PNG})
    assert r.status_code == 503 and r.headers["Retry-After"] == "5"
    assert lim.ocupados_ahora() == 0  # el cupo se libera


def test_el_cupo_se_libera_aunque_el_procesamiento_falle(client):
    _flujo(client, publico=True)
    r = client.post("/api/flujos-captura/alta_cliente/documentos", data=CONSENT, files={"archivo": ("a.png", b"no es una imagen", "image/png")})
    assert r.status_code == 400
    assert lim.ocupados_ahora() == 0


def test_archivo_demasiado_grande_es_413_antes_de_procesar(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "MAX_TAMANO_MB", 1)
    _flujo(client, publico=True)
    grande = ("g.png", b"0" * (3 * 1024 * 1024), "image/png")
    r = client.post("/api/flujos-captura/alta_cliente/documentos", data=CONSENT, files={"archivo": grande})
    assert r.status_code == 413
    assert lim.ocupados_ahora() == 0


def test_limitador_ventana_deslizante():
    l = lim.LimitadorVentana(ventana_s=60)
    assert [l.intentar("a", 2, ahora=t) for t in (0, 1)] == [None, None]
    assert l.intentar("a", 2, ahora=2) == pytest.approx(58)  # cuánto falta para poder reintentar
    assert l.intentar("b", 2, ahora=2) is None  # otra clave, otro contador
    assert l.intentar("a", 2, ahora=61) is None  # el primer evento salió de la ventana


def test_el_limitador_no_crece_sin_limite():
    l = lim.LimitadorVentana(ventana_s=10, max_claves=50)
    for i in range(500):
        l.intentar(f"ip{i}", 5, ahora=float(i))  # cada IP aparece una sola vez y caduca
    assert len(l._eventos) < 100


# ------------------------------------------------------------------ flujo completo
@pytest.mark.skipif(not _tesseract_disponible(), reason="Tesseract no disponible en este entorno")
def test_subida_publica_completa_respuesta_reducida_y_auditoria(client, planilla_sintetica):
    _flujo(client, publico=True)
    datos = imagen_a_bytes(planilla_sintetica, "PNG")
    r = client.post("/api/flujos-captura/alta_cliente/documentos", data=CONSENT, files={"archivo": ("p.png", datos, "image/png")})
    assert r.status_code == 201, r.text
    cuerpo = r.json()
    assert cuerpo["estado"] == "COMPLETADO" and cuerpo["clasificacion"]["tipo"] == "planilla_servicio_electrico"
    # respuesta reducida: sin texto OCR completo, tiempos, palabras clave ni datos internos
    for interno in ("texto_completo", "tiempos_ms", "palabras_clave", "paginas"):
        assert interno not in cuerpo
    assert set(cuerpo["clasificacion"]) == {"tipo", "confianza"}
    assert all(set(c) == {"valor", "confianza", "etiqueta"} for c in cuerpo["campos"].values())
    assert cuerpo["campos"]["total_pagar"]["etiqueta"] == "Total a pagar"  # rótulo legible, no el nombre técnico
    # trazabilidad: sin usuario identificado, y el log lo dice explícitamente
    doc = _fila(m.Documento, DocumentoId=cuerpo["documento_id"])
    assert doc.CreadoPorId is None and doc.FlujoCapturaId is not None
    origen = [l for l in _logs(cuerpo["documento_id"]) if l.startswith("Origen:")]
    assert len(origen) == 1 and "PÚBLICO sin usuario identificado" in origen[0]
    assert "127.0.0.1" not in origen[0] and "testclient" not in origen[0]  # no se guarda la IP en claro
    # el resultado completo NO se puede leer sin clave
    assert client.get(f"/api/documentos/{cuerpo['documento_id']}/resultado").status_code == 401


@pytest.mark.skipif(not _tesseract_disponible(), reason="Tesseract no disponible en este entorno")
def test_con_clave_se_ve_el_resultado_completo_y_el_origen_interno(client, planilla_sintetica):
    _flujo(client, publico=True)
    datos = imagen_a_bytes(planilla_sintetica, "PNG")
    uid = client.post("/api/usuarios", json={"nombre": "Ana", "rol": "Operador"}, headers=ADMIN).json()
    r = client.post("/api/flujos-captura/alta_cliente/documentos", data=CONSENT, files={"archivo": ("p.png", datos, "image/png")},
                    headers={"X-API-Key": uid["api_key"]})
    assert r.status_code == 201 and "texto_completo" in r.json()
    origen = [l for l in _logs(r.json()["documento_id"]) if l.startswith("Origen:")]
    assert origen and f"usuario #{uid['id']}" in origen[0] and "PÚBLICO" not in origen[0]
    # con clave sí funciona también en un flujo NO público
    _flujo_priv = client.post("/api/plantillas", json={**_DEF_BASICA, "codigo": "otra"}, headers=ADMIN).json()["id"]
    client.post("/api/flujos-captura", json={"codigo": "priv", "nombre": "P", "plantilla_ids": [_flujo_priv]}, headers=ADMIN)
    r = client.post("/api/flujos-captura/priv/documentos", data=CONSENT, files={"archivo": ("p.png", datos, "image/png")},
                    headers={"X-API-Key": uid["api_key"]})
    assert r.status_code == 201


def test_subida_publica_tiene_un_tope_de_tamano_menor_que_la_interna(client, monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "MAX_TAMANO_MB", 20)
    monkeypatch.setattr(s, "PUBLICO_MAX_TAMANO_MB", 1)
    _flujo(client, publico=True)
    medio = ("g.png", b"0" * (1536 * 1024), "image/png")  # 1.5 MB: bajo el tope interno, sobre el público
    assert client.post("/api/flujos-captura/alta_cliente/documentos", data=CONSENT, files={"archivo": medio}).status_code == 413
    # con clave el tope es el normal: llega a procesarse (y falla por no ser una imagen válida, no por tamaño)
    clave = client.post("/api/usuarios", json={"nombre": "Ana", "rol": "Operador"}, headers=ADMIN).json()["api_key"]
    r = client.post("/api/flujos-captura/alta_cliente/documentos", data=CONSENT, files={"archivo": medio}, headers={"X-API-Key": clave})
    assert r.status_code == 400


# ------------------------------------------------------------------ interruptor global (apagado por defecto)
def test_con_el_interruptor_apagado_no_existe_el_modo_anonimo(client, monkeypatch):
    _flujo(client, publico=True)  # abierto mientras el interruptor estaba encendido
    monkeypatch.setattr(get_settings(), "PUBLICO_HABILITADO", False)
    assert client.get("/api/flujos-captura/alta_cliente/publico").status_code == 401
    assert client.post("/api/flujos-captura/alta_cliente/documentos", data=CONSENT, files={"archivo": PNG}).status_code == 401
    # con clave todo sigue funcionando igual
    assert client.get("/api/flujos-captura/alta_cliente/publico", headers=ADMIN).status_code == 200


def test_con_el_interruptor_apagado_no_se_puede_abrir_un_flujo(client, monkeypatch):
    fid = _flujo(client, publico=False)
    monkeypatch.setattr(get_settings(), "PUBLICO_HABILITADO", False)
    r = client.patch(f"/api/flujos-captura/{fid}/acceso-publico", json={"acceso_publico": True}, headers=ADMIN)
    assert r.status_code == 409 and "deshabilitado" in r.json()["detail"]


def test_el_interruptor_viene_apagado_de_fabrica():
    from app.config import Settings

    assert Settings.model_fields["PUBLICO_HABILITADO"].default is False


def test_bomba_de_pixeles_por_la_ruta_publica_es_400_rapido_y_no_ocupa_cupo(client):
    """Hallazgo de QA: un PNG de ~250 KB con 9000x9000 px tumbaba los 2 cupos públicos ~50 s."""
    import io
    import time

    import numpy as np
    from PIL import Image

    _flujo(client, publico=True)
    buf = io.BytesIO()
    Image.fromarray(np.full((9000, 9000), 255, dtype=np.uint8)).save(buf, format="PNG", compress_level=9)
    assert len(buf.getvalue()) < 500 * 1024
    t0 = time.perf_counter()
    r = client.post("/api/flujos-captura/alta_cliente/documentos", data=CONSENT, files={"archivo": ("b.png", buf.getvalue(), "image/png")})
    assert r.status_code == 400 and "demasiado grande" in r.json()["detail"]
    assert time.perf_counter() - t0 < 5
    assert lim.ocupados_ahora() == 0


# ------------------------------------------------------------------ aviso de privacidad y consentimiento
def test_sin_consentimiento_no_se_recibe_nada(client):
    _flujo(client, publico=True)
    url = "/api/flujos-captura/alta_cliente/documentos"
    for datos in ({}, {"consentimiento": "false", "aviso_version": "1"}, {"consentimiento": "true"}, {"consentimiento": "true", "aviso_version": "0"}):
        r = client.post(url, files={"archivo": PNG}, data=datos)
        assert r.status_code == 400, datos
        assert "aviso de privacidad" in r.json()["detail"]
    assert _fila(m.Documento, NombreArchivo="a.png") is None  # no se creó ningún registro


def test_publico_informa_retencion_y_version_del_aviso(client, monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "DOC_RETENCION_DIAS", 45)
    monkeypatch.setattr(s, "AVISO_PRIVACIDAD_VERSION", "3")
    _flujo(client, publico=True)
    r = client.get("/api/flujos-captura/alta_cliente/publico").json()
    assert r["retencion_dias"] == 45 and r["aviso_version"] == "3"


def test_un_aviso_desactualizado_se_rechaza(client, monkeypatch):
    """Si el texto cambió (versión nueva), una pantalla vieja no vale como consentimiento."""
    _flujo(client, publico=True)
    monkeypatch.setattr(get_settings(), "AVISO_PRIVACIDAD_VERSION", "2")
    r = client.post("/api/flujos-captura/alta_cliente/documentos", files={"archivo": PNG}, data=CONSENT)  # versión "1"
    assert r.status_code == 400 and "cambió" in r.json()["detail"]


@pytest.mark.skipif(not _tesseract_disponible(), reason="Tesseract no disponible en este entorno")
def test_el_consentimiento_queda_registrado_en_el_documento_y_en_el_log(client, planilla_sintetica, monkeypatch):
    monkeypatch.setattr(get_settings(), "DOC_RETENCION_DIAS", 30)
    _flujo(client, publico=True)
    datos = imagen_a_bytes(planilla_sintetica, "PNG")
    r = client.post("/api/flujos-captura/alta_cliente/documentos", files={"archivo": ("p.png", datos, "image/png")}, data=CONSENT)
    assert r.status_code == 201, r.text
    doc = _fila(m.Documento, DocumentoId=r.json()["documento_id"])
    assert doc.AvisoVersion == "1" and doc.ConsentimientoEn is not None
    origen = [l for l in _logs(doc.DocumentoId) if l.startswith("Origen:")][0]
    assert "consentimiento al aviso de privacidad v1" in origen and "retención 30 días" in origen


@pytest.mark.skipif(not _tesseract_disponible(), reason="Tesseract no disponible en este entorno")
def test_lo_que_sube_el_personal_no_exige_ni_registra_consentimiento(client, planilla_sintetica):
    _flujo(client, publico=True)
    datos = imagen_a_bytes(planilla_sintetica, "PNG")
    r = client.post("/api/flujos-captura/alta_cliente/documentos", files={"archivo": ("i.png", datos, "image/png")}, headers=ADMIN)
    assert r.status_code == 201  # sin enviar consentimiento
    doc = _fila(m.Documento, DocumentoId=r.json()["documento_id"])
    assert doc.ConsentimientoEn is None and doc.AvisoVersion is None
