"""Flujos de captura, usuarios y permisos por rol (docs/07 §5)."""
import pytest
from sqlalchemy import select

from app.api import dependencias
from app.api.seguridad import hash_api_key
from app.main import app
from app.persistencia import modelos as m
from tests.conftest import imagen_a_bytes
from tests.test_api import _DEF_BASICA, HEADERS, _tesseract_disponible, client  # noqa: F401  (fixture)

ADMIN = HEADERS  # la clave del entorno ("dev") es el Administrador del sistema


def _h(clave: str) -> dict:
    return {"X-API-Key": clave}


def _usuario(client, nombre: str, rol: str) -> tuple[int, dict]:
    r = client.post("/api/usuarios", json={"nombre": nombre, "rol": rol}, headers=ADMIN)
    assert r.status_code == 201, r.text
    return r.json()["id"], _h(r.json()["api_key"])


def _plantilla(client, codigo="planilla_servicio_electrico") -> int:
    r = client.post("/api/plantillas", json={**_DEF_BASICA, "codigo": codigo}, headers=ADMIN)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _flujo_json(plantilla_ids, codigo="alta_cliente", **extra) -> dict:
    return {"codigo": codigo, "nombre": "Alta de cliente", "instruccion": "Sube tu cédula", "plantilla_ids": plantilla_ids, **extra}


def _fila(model, **filtro):
    """Lee directamente de la BD de prueba (la misma que usa la API)."""
    db = next(app.dependency_overrides[dependencias.get_db]())
    try:
        return db.execute(select(model).filter_by(**filtro)).scalars().first()
    finally:
        db.close()


# ------------------------------------------------------------------ autenticación
def test_clave_invalida_o_ausente_es_401(client):
    assert client.get("/api/flujos-captura").status_code == 401
    assert client.get("/api/flujos-captura", headers=_h("clave-mala")).status_code == 401


def test_usuario_con_su_clave_y_usuario_inactivo(client):
    uid, h = _usuario(client, "Ana", "Operador")
    assert client.get("/api/flujos-captura", headers=h).status_code == 200
    assert client.patch(f"/api/usuarios/{uid}", json={"activo": False}, headers=ADMIN).status_code == 200
    assert client.get("/api/flujos-captura", headers=h).status_code == 401  # inactivo: la clave deja de valer


def test_la_clave_se_guarda_solo_como_hash(client):
    r = client.post("/api/usuarios", json={"nombre": "Ana", "rol": "Editor"}, headers=ADMIN).json()
    fila = _fila(m.Usuario, UsuarioId=r["id"])
    assert r["api_key"].startswith("ocr_") and fila.ApiKeyHash == hash_api_key(r["api_key"])
    assert r["api_key"] not in fila.ApiKeyHash
    # al listar nunca vuelve la clave
    lista = client.get("/api/usuarios", headers=ADMIN).json()
    assert all("api_key" not in u and "ApiKeyHash" not in u for u in lista)


def test_regenerar_clave_invalida_la_anterior(client):
    uid, h_vieja = _usuario(client, "Ana", "Operador")
    nueva = client.post(f"/api/usuarios/{uid}/clave", headers=ADMIN).json()["api_key"]
    assert client.get("/api/flujos-captura", headers=h_vieja).status_code == 401
    assert client.get("/api/flujos-captura", headers=_h(nueva)).status_code == 200


# ------------------------------------------------------------------ roles
def test_operador_lee_pero_no_escribe_plantillas(client):
    _, op = _usuario(client, "Op", "Operador")
    assert client.get("/api/plantillas", headers=op).status_code == 200
    r = client.post("/api/plantillas", json=_DEF_BASICA, headers=op)
    assert r.status_code == 403 and "Editor" in r.json()["detail"]


def test_editor_crea_y_edita_plantillas_pero_no_gestiona_usuarios_ni_permisos(client):
    _, ed = _usuario(client, "Ed", "Editor")
    pid = client.post("/api/plantillas", json=_DEF_BASICA, headers=ed).json()["id"]
    assert client.put(f"/api/plantillas/{pid}", json=_DEF_BASICA, headers=ed).status_code == 200
    assert client.patch(f"/api/plantillas/{pid}/estado", json={"activa": False}, headers=ed).status_code == 200
    assert client.patch(f"/api/plantillas/{pid}/permisos", json={"rol_minimo_edicion": "Operador"}, headers=ed).status_code == 403
    assert client.get("/api/usuarios", headers=ed).status_code == 403
    assert client.post("/api/usuarios", json={"nombre": "X", "rol": "Operador"}, headers=ed).status_code == 403


def test_rol_minimo_edicion_de_la_plantilla_se_suma_al_rol_de_la_ruta(client):
    _, ed = _usuario(client, "Ed", "Editor")
    pid = _plantilla(client)
    assert client.get(f"/api/plantillas/{pid}", headers=ed).json()["rol_minimo_edicion"] == "Editor"
    r = client.patch(f"/api/plantillas/{pid}/permisos", json={"rol_minimo_edicion": "Administrador"}, headers=ADMIN)
    assert r.status_code == 200 and r.json()["rol_minimo_edicion"] == "Administrador"
    # ahora el Editor no puede tocarla (editar ni activar), el Administrador sí
    assert client.put(f"/api/plantillas/{pid}", json=_DEF_BASICA, headers=ed).status_code == 403
    assert client.patch(f"/api/plantillas/{pid}/estado", json={"activa": False}, headers=ed).status_code == 403
    assert client.put(f"/api/plantillas/{pid}", json=_DEF_BASICA, headers=ADMIN).status_code == 200


def test_permisos_con_rol_invalido_o_plantilla_inexistente(client):
    pid = _plantilla(client)
    assert client.patch(f"/api/plantillas/{pid}/permisos", json={"rol_minimo_edicion": "Superman"}, headers=ADMIN).status_code == 422
    assert client.patch("/api/plantillas/9999/permisos", json={"rol_minimo_edicion": "Editor"}, headers=ADMIN).status_code == 404


def test_no_te_puedes_degradar_ni_desactivar_a_ti_mismo(client):
    uid, adm = _usuario(client, "Otro admin", "Administrador")
    assert client.patch(f"/api/usuarios/{uid}", json={"rol": "Editor"}, headers=adm).status_code == 400
    assert client.patch(f"/api/usuarios/{uid}", json={"activo": False}, headers=adm).status_code == 400
    # la clave del sistema (sin fila de usuario) sí puede cambiarle el rol
    assert client.patch(f"/api/usuarios/{uid}", json={"rol": "Editor"}, headers=ADMIN).status_code == 200


# ------------------------------------------------------------------ flujos de captura (CRUD)
def test_crud_de_flujos_y_visibilidad_por_rol(client):
    pid = _plantilla(client)
    _, ed = _usuario(client, "Ed", "Editor")
    _, op = _usuario(client, "Op", "Operador")

    assert client.post("/api/flujos-captura", json=_flujo_json([pid]), headers=op).status_code == 403
    r = client.post("/api/flujos-captura", json=_flujo_json([pid]), headers=ed)
    assert r.status_code == 201, r.text
    flujo = r.json()
    assert flujo["codigo"] == "alta_cliente" and flujo["activo"] and flujo["rol_minimo_edicion"] == "Editor"
    assert [p["id"] for p in flujo["plantillas"]] == [pid] and flujo["creado_por_id"] is not None

    # Operador: ve el detalle y la lista de activos; no puede pedir inactivos
    assert client.get("/api/flujos-captura/alta_cliente", headers=op).status_code == 200
    assert client.get("/api/flujos-captura?todos=true", headers=op).status_code == 403

    # desactivar: el Operador deja de verlo; el Editor lo sigue viendo con ?todos=true
    r = client.patch(f"/api/flujos-captura/{flujo['id']}/estado", json={"activo": False}, headers=ed)
    assert r.status_code == 200 and r.json()["activo"] is False
    assert client.get("/api/flujos-captura", headers=op).json() == []
    assert client.get("/api/flujos-captura/alta_cliente", headers=op).status_code == 404
    assert len(client.get("/api/flujos-captura?todos=true", headers=ed).json()) == 1
    assert client.get("/api/flujos-captura/alta_cliente", headers=ed).status_code == 200

    # editar
    r = client.put(f"/api/flujos-captura/{flujo['id']}", json=_flujo_json([pid], nombre="Otro nombre", activo=True), headers=ed)
    assert r.status_code == 200 and r.json()["activo"] is True


def test_validaciones_de_flujos(client):
    pid = _plantilla(client)
    assert client.post("/api/flujos-captura", json=_flujo_json([pid]), headers=ADMIN).status_code == 201
    assert client.post("/api/flujos-captura", json=_flujo_json([pid]), headers=ADMIN).status_code == 400  # código duplicado
    assert client.post("/api/flujos-captura", json=_flujo_json([9999], codigo="otro"), headers=ADMIN).status_code == 400
    assert client.post("/api/flujos-captura", json=_flujo_json([], codigo="otro"), headers=ADMIN).status_code == 422
    assert client.post("/api/flujos-captura", json=_flujo_json([pid], codigo="Código Malo"), headers=ADMIN).status_code == 422
    assert client.get("/api/flujos-captura/no_existe", headers=ADMIN).status_code == 404
    assert client.put("/api/flujos-captura/9999", json=_flujo_json([pid]), headers=ADMIN).status_code == 404


def test_rol_minimo_edicion_del_flujo(client):
    pid = _plantilla(client)
    _, ed = _usuario(client, "Ed", "Editor")
    fid = client.post("/api/flujos-captura", json=_flujo_json([pid]), headers=ADMIN).json()["id"]
    assert client.patch(f"/api/flujos-captura/{fid}/permisos", json={"rol_minimo_edicion": "Administrador"}, headers=ed).status_code == 403
    assert client.patch(f"/api/flujos-captura/{fid}/permisos", json={"rol_minimo_edicion": "Administrador"}, headers=ADMIN).status_code == 200
    assert client.put(f"/api/flujos-captura/{fid}", json=_flujo_json([pid]), headers=ed).status_code == 403
    assert client.patch(f"/api/flujos-captura/{fid}/estado", json={"activo": False}, headers=ed).status_code == 403


# ------------------------------------------------------------------ procesar con flujo
def test_flujo_sin_pdf_rechaza_pdf_antes_de_procesar(client):
    pid = _plantilla(client)
    client.post("/api/flujos-captura", json=_flujo_json([pid], acepta_pdf=False), headers=ADMIN)
    r = client.post("/api/flujos-captura/alta_cliente/documentos", files={"archivo": ("a.pdf", b"%PDF-1.4", "application/pdf")}, headers=ADMIN)
    assert r.status_code == 400 and "PDF" in r.json()["detail"]


def test_procesar_con_flujo_inexistente_o_inactivo_es_404(client):
    pid = _plantilla(client)
    client.post("/api/flujos-captura", json=_flujo_json([pid], activo=False), headers=ADMIN)
    f = {"archivo": ("a.png", b"x", "image/png")}
    assert client.post("/api/flujos-captura/alta_cliente/documentos", files=f, headers=ADMIN).status_code == 404
    assert client.post("/api/flujos-captura/no_existe/documentos", files=f, headers=ADMIN).status_code == 404


@pytest.mark.skipif(not _tesseract_disponible(), reason="Tesseract no disponible en este entorno")
def test_procesar_con_flujo_clasifica_solo_entre_sus_plantillas(client, planilla_sintetica):
    datos = imagen_a_bytes(planilla_sintetica, "PNG")
    pid_luz = _plantilla(client)  # palabras clave: "total a pagar", "vencimiento": coincide con la planilla
    otra = {**_DEF_BASICA, "codigo": "cedula_x", "palabras_clave": [{"texto": "republica del ecuador", "peso": 3}]}
    pid_otra = client.post("/api/plantillas", json=otra, headers=ADMIN).json()["id"]
    _, op = _usuario(client, "Op", "Operador")

    client.post("/api/flujos-captura", json=_flujo_json([pid_luz], codigo="servicios"), headers=ADMIN)
    client.post("/api/flujos-captura", json=_flujo_json([pid_otra], codigo="solo_cedula"), headers=ADMIN)

    # flujo que SÍ permite la plantilla de la planilla
    r = client.post("/api/flujos-captura/servicios/documentos", files={"archivo": ("p.png", datos, "image/png")}, headers=op)
    assert r.status_code == 201, r.text
    cuerpo = r.json()
    assert cuerpo["estado"] == "COMPLETADO" and cuerpo["clasificacion"]["tipo"] == "planilla_servicio_electrico"
    assert cuerpo["flujo_captura"] == "servicios"
    doc = _fila(m.Documento, DocumentoId=cuerpo["documento_id"])
    assert doc.FlujoCapturaId is not None and doc.CreadoPorId is not None  # trazabilidad: flujo y quién lo subió

    # flujo que NO la permite: aunque la plantilla de luz existe y coincidiría, no se elige -> NO_COINCIDE
    r = client.post("/api/flujos-captura/solo_cedula/documentos", files={"archivo": ("p.png", datos, "image/png")}, headers=op)
    assert r.status_code == 201, r.text
    cuerpo = r.json()
    assert cuerpo["estado"] == "NO_COINCIDE" and cuerpo["clasificacion"]["tipo"] == "desconocido"
    assert _fila(m.Documento, DocumentoId=cuerpo["documento_id"]).Estado == "NO_COINCIDE"

    # reprocesar un documento de flujo mantiene la restricción
    r = client.post(f"/api/documentos/{cuerpo['documento_id']}/reprocesar", headers=op)
    assert r.status_code == 200 and r.json()["clasificacion"]["tipo"] == "desconocido"
    assert _fila(m.Documento, DocumentoId=cuerpo["documento_id"]).Estado == "NO_COINCIDE"

    # el modo genérico (sin flujo) sigue clasificando contra todas las plantillas
    r = client.post("/api/documentos", files={"archivo": ("p.png", datos, "image/png")}, headers=op)
    assert r.status_code == 201 and r.json()["estado"] == "COMPLETADO"
    assert r.json()["clasificacion"]["tipo"] == "planilla_servicio_electrico"
    assert _fila(m.Documento, DocumentoId=r.json()["documento_id"]).CreadoPorId is not None


def test_ninguna_ruta_queda_sin_proteger_con_la_configuracion_por_defecto(client):
    """Con PUBLICO_HABILITADO apagado (lo que se despliega por defecto) TODAS las rutas, salvo /salud, exigen clave."""
    import re

    from app.main import app

    revisadas = 0
    for ruta in app.routes:
        if not hasattr(ruta, "methods") or not ruta.path.startswith("/api"):
            continue
        for metodo in sorted(ruta.methods - {"HEAD", "OPTIONS"}):
            if (metodo, ruta.path) == ("GET", "/api/salud"):
                continue
            r = client.request(metodo, re.sub(r"\{[^}]+\}", "1", ruta.path))
            revisadas += 1
            assert r.status_code == 401, f"{metodo} {ruta.path} respondió {r.status_code} sin X-API-Key"
    assert revisadas >= 30


def test_yo_devuelve_la_identidad_de_la_clave(client):
    base = {"usuario_id": None, "nombre": "Sistema", "rol": "Administrador", "publico_habilitado": False}
    assert client.get("/api/yo", headers=ADMIN).json() == base  # apagado de fábrica
    uid, h = _usuario(client, "Ana", "Operador")
    assert client.get("/api/yo", headers=h).json() == {"usuario_id": uid, "nombre": "Ana", "rol": "Operador", "publico_habilitado": False}
    assert client.get("/api/yo").status_code == 401


def test_yo_informa_si_el_acceso_publico_esta_habilitado(client, monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "PUBLICO_HABILITADO", True)
    assert client.get("/api/yo", headers=ADMIN).json()["publico_habilitado"] is True
