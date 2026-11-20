"""Entrega 2 de la cuadrícula (docs/13): diseño por posición en la plantilla, recorte manual/giro y endpoints del editor
(imagen enderezada, palabras con posición, recorte). Datos inventados."""
from __future__ import annotations

import cv2
import numpy as np
import pytest
from pydantic import ValidationError
from sqlalchemy import select

from app.dominio.modelos import DisenoPlantilla, ReglaCampo, ZonaEtiqueta
from app.pipeline import posiciones
from app.pipeline.preprocesado import (
    EsquinasInvalidas,
    OpcionesPreprocesado,
    preprocesar_detalle,
    reconstruir_enderezada,
    validar_esquinas,
)
from tests.test_posiciones import _planilla, entorno  # noqa: F401  (fixture)
from tests.test_preprocesado import _foto_en_angulo, _tarjeta_sintetica

H = {"X-API-Key": "dev"}
ESQ_FOTO = [[260, 200], [1250, 330], [1180, 960], [180, 880]]  # en un lienzo de 1600 x 1200
ESQ_REL = [[x / 1600, y / 1200] for x, y in ESQ_FOTO]


def _foto() -> np.ndarray:
    return _foto_en_angulo(_tarjeta_sintetica(), ESQ_FOTO)


def _png(img: np.ndarray) -> bytes:
    return cv2.imencode(".png", img)[1].tobytes()


# ------------------------------------------------------------------ modelo
def test_diseno_y_zona_de_etiqueta_validan_coordenadas():
    d = DisenoPlantilla(relacion=1.586, densidad_rejilla="12x8",
                        elementos_fijos=[{"x": 0.3, "y": 0.02, "ancho": 0.4, "alto": 0.06, "texto_esperado": "ENCABEZADO"}])
    assert d.umbral_coincidencia == 0.8 and d.tolerancia == 0.03 and d.formato == "libre"
    with pytest.raises(ValidationError):
        ZonaEtiqueta(x=0.8, y=0.1, ancho=0.3, alto=0.1, texto_esperado="X")  # se sale por la derecha
    with pytest.raises(ValidationError):
        ZonaEtiqueta(x=0.1, y=0.95, ancho=0.3, alto=0.1, texto_esperado="X")  # se sale por abajo
    with pytest.raises(ValidationError):
        ZonaEtiqueta(x=0.1, y=0.1, ancho=0.3, alto=0.1, texto_esperado="")
    with pytest.raises(ValidationError):
        DisenoPlantilla(densidad_rejilla="doce")
    with pytest.raises(ValidationError):
        DisenoPlantilla(relacion=0.5)  # lado mayor / menor: >= 1
    r = ReglaCampo(metodo="ancla", ancla="Apellidos", x=0.3, y=0.27, ancho=0.4, alto=0.1,
                   zona_etiqueta={"x": 0.3, "y": 0.21, "ancho": 0.14, "alto": 0.05, "texto_esperado": "APELLIDOS"})
    assert r.zona_etiqueta.texto_esperado == "APELLIDOS"
    assert ReglaCampo(metodo="regex", regex="x").zona_etiqueta is None  # reglas anteriores siguen valiendo


def _definicion(diseno: dict | None) -> dict:
    d = {
        "codigo": "tarjeta_prueba", "nombre": "Tarjeta de prueba", "umbral_confianza": 0.3,
        "palabras_clave": [{"texto": "apellidos", "peso": 3}],
        "campos": [{
            "nombre": "apellidos", "etiqueta": "Apellidos", "tipo_dato": "texto", "obligatorio": True,
            "regla": {"metodo": "ancla", "ancla": "Apellidos", "x": 0.3, "y": 0.27, "ancho": 0.4, "alto": 0.1,
                      "zona_etiqueta": {"x": 0.3, "y": 0.21, "ancho": 0.14, "alto": 0.05, "texto_esperado": "APELLIDOS"}},
        }],
    }
    if diseno is not None:
        d["diseno"] = diseno
    return d


def test_plantilla_guarda_y_devuelve_el_diseno_por_version(entorno):
    client, _ = entorno
    diseno = {"formato": "ID-1", "relacion": 1.586, "umbral_coincidencia": 0.8, "densidad_rejilla": "12x8",
              "elementos_fijos": [{"x": 0.3, "y": 0.02, "ancho": 0.4, "alto": 0.06, "texto_esperado": "ENCABEZADO"}]}
    r = client.post("/api/plantillas", headers=H, json=_definicion(diseno))
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    p = client.get(f"/api/plantillas/{pid}", headers=H).json()
    assert p["diseno"]["relacion"] == 1.586 and p["diseno"]["elementos_fijos"][0]["texto_esperado"] == "ENCABEZADO"
    assert p["campos"][0]["regla"]["zona_etiqueta"]["texto_esperado"] == "APELLIDOS"
    assert p["campos"][0]["regla"]["x"] == 0.3
    # un cliente que no conoce la cuadrícula (sin la clave "diseno") no la borra: la versión nueva la hereda
    r = client.put(f"/api/plantillas/{pid}", headers=H, json=_definicion(None))
    assert r.status_code == 200, r.text
    p2 = client.get(f"/api/plantillas/{pid}", headers=H).json()
    assert p2["version"] == p["version"] + 1 and p2["diseno"]["relacion"] == 1.586
    # para quitarla hay que pedirlo explícitamente con "diseno": null (el diseño anterior sigue en su versión)
    r = client.put(f"/api/plantillas/{pid}", headers=H, json={**_definicion(None), "diseno": None})
    assert r.status_code == 200, r.text
    assert client.get(f"/api/plantillas/{pid}", headers=H).json()["diseno"] is None
    # diseño inválido: 422 sin crear versión
    malo = {**diseno, "elementos_fijos": [{"x": 0.9, "y": 0, "ancho": 0.4, "alto": 0.1, "texto_esperado": "X"}]}
    assert client.put(f"/api/plantillas/{pid}", headers=H, json=_definicion(malo)).status_code == 422


# ------------------------------------------------------------------ esquinas y recorte manual
def test_validar_esquinas():
    assert validar_esquinas(ESQ_REL)[0] == [0.1625, 0.1667]
    with pytest.raises(EsquinasInvalidas):
        validar_esquinas([[0, 0], [1, 0], [1, 1]])  # 3 puntos
    with pytest.raises(EsquinasInvalidas):
        validar_esquinas([[0, 0], [1, 0], [1, 1.2], [0, 1]])  # fuera de 0-1
    with pytest.raises(EsquinasInvalidas, match="convexo"):
        validar_esquinas([ESQ_REL[0], ESQ_REL[3], ESQ_REL[2], ESQ_REL[1]])  # sentido contrario
    with pytest.raises(EsquinasInvalidas, match="convexo"):
        validar_esquinas([ESQ_REL[0], ESQ_REL[2], ESQ_REL[1], ESQ_REL[3]])  # cruzado
    with pytest.raises(EsquinasInvalidas, match="pequeño"):
        validar_esquinas([[0.5, 0.5], [0.55, 0.5], [0.55, 0.55], [0.5, 0.55]])
    with pytest.raises(EsquinasInvalidas, match="deformado"):
        validar_esquinas([[0.4, 0.45], [0.6, 0.45], [0.99, 0.55], [0.01, 0.55]])  # ángulos de ~166°
    with pytest.raises(EsquinasInvalidas):
        validar_esquinas("no")


def test_recorte_manual_reemplaza_la_deteccion_y_gira():
    op = OpcionesPreprocesado(reescalar=False, binarizar=False, denoise=False)
    salida, pasos, _, rec = preprocesar_detalle(_foto(), op, {"esquinas": ESQ_REL, "orientacion": 0})
    assert rec["origen"] == "manual" and rec["aplicado"] and rec["esquinas"] == ESQ_REL and "perspectiva(manual)" in pasos
    h, w = salida.shape[:2]
    assert 1.45 <= w / h <= 1.75
    _, pasos, _, girada = preprocesar_detalle(_foto(), op, {"esquinas": ESQ_REL, "orientacion": 90})
    assert girada["orientacion"] == 90 and "giro(90)" in pasos and girada["relacion"] == rec["relacion"]
    # solo giro, sin esquinas: la detección automática sigue funcionando
    _, _, _, auto = preprocesar_detalle(_foto(), op, {"esquinas": None, "orientacion": 180})
    assert auto["origen"] == "automatico" and auto["orientacion"] == 180


def test_imagen_enderezada_reconstruida_tiene_el_mismo_marco_que_el_ocr():
    # sin reescalar ni binarizar, lo que leyó el OCR y la reconstrucción en color deben medir lo mismo
    op = OpcionesPreprocesado(reescalar=False, binarizar=False, denoise=False)
    for manual in (None, {"esquinas": ESQ_REL, "orientacion": 90}):
        gris, _, _, rec = preprocesar_detalle(_foto(), op, manual)
        color = reconstruir_enderezada(_foto(), rec)
        assert color.ndim == 3 and abs(color.shape[0] - gris.shape[0]) <= 2 and abs(color.shape[1] - gris.shape[1]) <= 2
        diferencia = np.abs(cv2.cvtColor(color, cv2.COLOR_BGR2GRAY).astype(int)[: gris.shape[0], : gris.shape[1]]
                            - gris[: color.shape[0], : color.shape[1]].astype(int))
        assert np.median(diferencia) < 10  # misma imagen (salvo bordes por las esquinas redondeadas a 4 decimales)
    assert reconstruir_enderezada(_foto(), None).shape == _foto().shape


def test_recorte_confiable_segun_la_proporcion_de_la_plantilla():
    auto = {"aplicado": True, "origen": "automatico", "relacion": 1.58}
    assert posiciones.recorte_confiable(auto)  # sin proporción esperada: basta con que se haya recortado
    assert posiciones.recorte_confiable(auto, 1.586)
    assert not posiciones.recorte_confiable(auto, 1.414)  # recortó, pero no tiene la forma de la plantilla
    escaneo = {"aplicado": False, "origen": "ninguno", "relacion": 1.42}
    assert not posiciones.recorte_confiable(escaneo)
    assert posiciones.recorte_confiable(escaneo, 1.414)  # la imagen ya es el documento (A4 escaneado)
    assert posiciones.recorte_confiable({"aplicado": True, "origen": "manual", "esquinas": ESQ_REL, "relacion": 3}, 1.586)
    assert not posiciones.recorte_confiable(None)


# ------------------------------------------------------------------ endpoints
def _subir(client, img: np.ndarray) -> str:
    r = client.post("/api/documentos", headers=H, files={"archivo": ("tarjeta.png", _png(img), "image/png")})
    assert r.status_code == 201, r.text
    return r.json()["documento_id"]


def test_endpoints_palabras_y_enderezada(entorno):
    client, _ = entorno
    doc = _subir(client, _foto())
    r = client.get(f"/api/documentos/{doc}/paginas/1/palabras", headers=H)
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert cuerpo["pagina"] == 1 and [p["texto"] for p in cuerpo["palabras"]] == ["APELLIDOS", "PEREZ"]
    assert set(cuerpo["palabras"][0]) == {"texto", "x", "y", "ancho", "alto", "confianza"}
    rec = cuerpo["recorte"]
    assert rec["aplicado"] and rec["origen"] == "automatico" and rec["confiable"] and len(rec["esquinas"]) == 4
    # con la proporción de otra plantilla (p. ej. un ticket alargado, 2:1) el mismo recorte no es confiable
    assert client.get(f"/api/documentos/{doc}/paginas/1/palabras?relacion=2.0", headers=H).json()["recorte"]["confiable"] is False
    assert client.get(f"/api/documentos/{doc}/paginas/1/palabras?relacion=1.586", headers=H).json()["recorte"]["confiable"]

    r = client.get(f"/api/documentos/{doc}/paginas/1/enderezada", headers=H)
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    assert r.headers["x-recorte-confiable"] == "true" and r.headers["x-recorte-origen"] == "automatico"
    assert r.headers["x-orientacion"] == "0"
    img = cv2.imdecode(np.frombuffer(r.content, np.uint8), cv2.IMREAD_COLOR)
    assert img.ndim == 3 and 1.45 <= img.shape[1] / img.shape[0] <= 1.75  # la tarjeta, ya sin el fondo

    # JPEG para móvil: mismo marco, bastante más liviano
    rj = client.get(f"/api/documentos/{doc}/paginas/1/enderezada?formato=jpeg", headers=H)
    assert rj.status_code == 200 and rj.headers["content-type"] == "image/jpeg"
    jpg = cv2.imdecode(np.frombuffer(rj.content, np.uint8), cv2.IMREAD_COLOR)
    assert jpg.shape == img.shape and len(rj.content) < len(r.content)
    assert client.get(f"/api/documentos/{doc}/paginas/1/enderezada?formato=gif", headers=H).status_code == 422

    assert client.get(f"/api/documentos/{doc}/paginas/2/palabras", headers=H).status_code == 404
    assert client.get(f"/api/documentos/{doc}/paginas/2/enderezada", headers=H).status_code == 404
    assert client.get("/api/documentos/no-existe/paginas/1/palabras", headers=H).status_code == 404


def test_documento_sin_posiciones_pide_reprocesar(entorno):
    from app.persistencia import modelos as m

    client, Sesion = entorno
    doc = _subir(client, _foto())
    with Sesion() as db:  # resultado anterior a la migración 009
        res = db.execute(select(m.Resultado)).scalars().one()
        res.PalabrasJson = res.RecorteJson = None
        db.commit()
    r = client.get(f"/api/documentos/{doc}/paginas/1/palabras", headers=H)
    assert r.status_code == 404 and "Reprocese el documento" in r.json()["detail"]
    r = client.get(f"/api/documentos/{doc}/paginas/1/enderezada", headers=H)  # la imagen original, sin recorte
    assert r.status_code == 200 and r.headers["x-recorte-origen"] == "desconocido" and r.headers["x-recorte-confiable"] == "false"


def test_recorte_manual_por_api_se_guarda_y_se_conserva_al_reprocesar(entorno):
    client, _ = entorno
    # documento que la detección automática no recorta (llena la imagen)
    doc = _subir(client, cv2.cvtColor(np.array(_planilla()), cv2.COLOR_RGB2BGR))
    assert client.get(f"/api/documentos/{doc}/paginas/1/palabras", headers=H).json()["recorte"]["origen"] == "ninguno"

    esquinas = [[0.05, 0.1], [0.95, 0.08], [0.96, 0.9], [0.04, 0.92]]
    r = client.post(f"/api/documentos/{doc}/paginas/1/recorte", headers=H, json={"esquinas": esquinas})
    assert r.status_code == 200, r.text
    assert r.json()["documento_id"] == doc
    rec = client.get(f"/api/documentos/{doc}/paginas/1/palabras", headers=H).json()["recorte"]
    assert rec["origen"] == "manual" and rec["esquinas"] == esquinas and rec["confiable"]

    # solo girar: conserva las esquinas marcadas
    r = client.post(f"/api/documentos/{doc}/paginas/1/recorte", headers=H, json={"orientacion": 90})
    assert r.status_code == 200, r.text
    rec = client.get(f"/api/documentos/{doc}/paginas/1/palabras", headers=H).json()["recorte"]
    assert rec["origen"] == "manual" and rec["esquinas"] == esquinas and rec["orientacion"] == 90
    assert client.get(f"/api/documentos/{doc}/paginas/1/enderezada", headers=H).headers["x-orientacion"] == "90"

    # un reproceso normal no vuelve al recorte automático
    assert client.post(f"/api/documentos/{doc}/reprocesar", headers=H).status_code == 200
    rec = client.get(f"/api/documentos/{doc}/paginas/1/palabras", headers=H).json()["recorte"]
    assert rec["origen"] == "manual" and rec["orientacion"] == 90

    # errores
    r = client.post(f"/api/documentos/{doc}/paginas/1/recorte", headers=H, json={"esquinas": [[0, 0], [1, 0], [0, 1], [1, 1]]})
    assert r.status_code == 422 and "convexo" in r.json()["detail"]
    assert client.post(f"/api/documentos/{doc}/paginas/1/recorte", headers=H, json={"orientacion": 45}).status_code == 422
    assert client.post(f"/api/documentos/{doc}/paginas/3/recorte", headers=H, json={"orientacion": 90}).status_code == 404
