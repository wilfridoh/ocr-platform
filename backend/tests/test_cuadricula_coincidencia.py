"""Entrega 4 de la cuadrícula (docs/13 §3 y §4.3): coincidencia de DISEÑO (no autenticidad), orientación 90°/180°,
/probar con posiciones guardadas y diseño sin guardar. Plantillas y datos inventados."""
from __future__ import annotations

import json
from types import SimpleNamespace

import numpy as np
import pytest

from app.dominio.modelos import DisenoPlantilla, PaginaOCR, PalabraOCR
from app.pipeline.ensamblador import ensamblar
from app.pipeline.extractor import extraer_campos
from app.pipeline.zonas import advertencias_coincidencia, calcular_coincidencia, orientar_paginas
from app.dominio.modelos import Clasificacion
from tests.test_cuadricula_extraccion import BASE, CAMPOS, DISENO, RECORTE, _pagina

DISENO_80 = DISENO.model_copy(update={"umbral_coincidencia": 0.8})


def _coincidencia(paginas, diseno=DISENO_80, campos=CAMPOS):
    extraidos = extraer_campos(campos, paginas, diseno=diseno)
    return calcular_coincidencia(paginas, campos, diseno, extraidos)


# ------------------------------------------------------------------ puntaje
def test_documento_con_el_diseno_de_la_plantilla_coincide():
    c = _coincidencia([_pagina(BASE)])
    assert c["verificable"] and c["veredicto"] == "coincide" and c["puntaje"] == pytest.approx(1.0, abs=0.01)
    assert (c["etiquetas_ok"], c["etiquetas_total"]) == (3, 3) and c["desplazamiento_medio"] == 0
    assert (c["valores_legibles"], c["valores_total"]) == (2, 2)
    assert c["recorte_confiable"] and c["recorte_origen"] == "automatico" and c["orientacion"] == 0
    etiquetas = [z for z in c["zonas"] if z["tipo"] == "etiqueta"]
    assert {z["estado"] for z in etiquetas} == {"coincide"} and etiquetas[0]["esperado"] and etiquetas[0]["leido"]
    valores = [z for z in c["zonas"] if z["tipo"] == "valor"]
    # las zonas de valor no repiten el dato del titular: solo si se leyó algo válido
    assert all("leido" not in z and z["leido_ok"] for z in valores)
    assert advertencias_coincidencia(c) == []


def test_etiqueta_mal_leida_queda_parcial_con_su_similitud():
    palabras = [p if p[0] != "APELLIDOS" else ("APELIDOS", *p[1:]) for p in BASE]
    c = _coincidencia([_pagina(palabras)])
    ap = next(z for z in c["zonas"] if z["tipo"] == "etiqueta" and z["campo"] == "apellidos")
    assert ap["estado"] in ("coincide", "parcial") and 0.8 <= ap["similitud"] < 1.0
    palabras = [p if p[0] != "APELLIDOS" else ("APLXDS", *p[1:]) for p in BASE]
    c = _coincidencia([_pagina(palabras)])
    ap = next(z for z in c["zonas"] if z["tipo"] == "etiqueta" and z["campo"] == "apellidos")
    assert ap["estado"] == "parcial" and 0.6 <= ap["similitud"] < 0.8
    assert c["puntaje"] < 1.0


def test_otra_variante_del_documento_no_coincide():
    # las mismas etiquetas, pero impresas en otra disposición
    otra = [("TARJETA", 0.32, 0.50), ("DE", 0.42, 0.50), ("PRUEBA", 0.46, 0.50), ("APELLIDOS", 0.60, 0.60),
            ("PEREZ", 0.60, 0.68), ("NOMBRES", 0.60, 0.80), ("JUAN", 0.60, 0.88)]
    c = _coincidencia([_pagina(otra)])
    assert c["verificable"] and c["veredicto"] == "no_coincide" and c["etiquetas_ok"] == 0
    assert c["desplazamiento_medio"] > 0.1
    assert advertencias_coincidencia(c) == ["diseno_no_coincide"]


def test_veredicto_parcial_entre_umbral_menos_015_y_umbral():
    alta = DISENO.model_copy(update={"umbral_coincidencia": 1.0})  # 1,0 exige perfección; el documento da < 1
    palabras = [p if p[0] != "APELLIDOS" else ("APELIDOS", *p[1:]) for p in BASE]
    c = _coincidencia([_pagina(palabras)], diseno=alta)
    assert 0.85 <= c["puntaje"] < 1.0 and c["veredicto"] == "parcial"


def test_sin_recorte_fiable_no_hay_puntaje():
    c = _coincidencia([_pagina(BASE, recorte={**RECORTE, "relacion": 2.4})])
    assert not c["verificable"] and c["puntaje"] is None and c["veredicto"] is None
    assert advertencias_coincidencia(c) == ["diseno_no_verificable"]


def test_con_la_mayoria_de_las_etiquetas_ilegibles_no_es_verificable():
    borroso = [("XX", 0.32, 0.03), ("APELLIDOS", 0.10, 0.20), ("PEREZ", 0.10, 0.28), ("JUAN", 0.10, 0.48)]
    c = _coincidencia([_pagina(borroso)])
    assert not c["verificable"] and c["veredicto"] is None  # "no verificable", no "no coincide"


def test_sin_diseno_no_hay_bloque_ni_advertencias():
    assert calcular_coincidencia([_pagina(BASE)], CAMPOS, None) is None
    assert advertencias_coincidencia(None) == []
    r = ensamblar([_pagina(BASE)], Clasificacion(tipo="x"), [], [], set(), {}, "paddle")
    assert r.coincidencia is None and r.a_contrato("d", "a")["coincidencia"] is None


def test_ensamblar_incluye_la_coincidencia_y_su_advertencia():
    otra = [("TARJETA", 0.32, 0.50), ("APELLIDOS", 0.60, 0.60), ("NOMBRES", 0.60, 0.80)]
    c = _coincidencia([_pagina(otra)])
    r = ensamblar([_pagina(otra)], Clasificacion(tipo="x"), [], [], set(), {}, "paddle", c)
    assert "diseno_no_coincide" in r.advertencias and r.a_contrato("d", "a")["coincidencia"]["veredicto"] == "no_coincide"


# ------------------------------------------------------------------ orientación
def _girada_180(palabras):
    """Lo que entrega el OCR de una foto cabeza abajo: el texto bien leído, las cajas invertidas."""
    return [(t, 1 - x - 0.012 * len(t), 1 - y - 0.04) for t, x, y in palabras]


def test_documento_cabeza_abajo_se_gira_180_con_las_etiquetas_fijas():
    pagina = _pagina(_girada_180(BASE))
    assert _coincidencia([_pagina(_girada_180(BASE))])["veredicto"] is not None
    giradas = orientar_paginas([pagina], CAMPOS, DISENO)
    assert giradas == {1} and pagina.recorte["orientacion"] == 180 and pagina.recorte["orientacion_auto"]
    r = {c.nombre: c for c in extraer_campos(CAMPOS, [_pagina(_girada_180(BASE))], diseno=DISENO)}
    assert r["apellidos"].valor == "PEREZ" and r["apellidos"].x == pytest.approx(0.10, abs=0.01)
    # derecho: no se toca
    derecha = _pagina(BASE)
    assert orientar_paginas([derecha], CAMPOS, DISENO) == set() and derecha.recorte["orientacion"] == 0
    # sin diseño no se decide nada
    assert orientar_paginas([_pagina(_girada_180(BASE))], CAMPOS, None) == set()


def test_texto_de_lado_se_gira_90_y_se_relee(monkeypatch):
    from app.config import get_settings
    from app.pipeline import ocr as ocr_mod
    from app.pipeline.orquestador import fraccion_vertical, procesar_bytes
    from tests.conftest import imagen_a_bytes
    from tests.test_posiciones import _planilla

    lecturas = []

    def ocr_falso(img, settings, idioma=None):
        h, w = img.shape[:2]
        lecturas.append((w, h))
        if w > h:  # tal como llegó: el texto sale "de pie" (cajas altas y angostas)
            palabras = [PalabraOCR(texto=f"PALABRA{i}", x=40 * i, y=10, ancho=20, alto=90, confianza=0.6, linea=i, bloque=0) for i in range(8)]
        else:  # girada 90°: cajas horizontales normales
            palabras = [PalabraOCR(texto=f"PALABRA{i}", x=10, y=40 * i, ancho=90, alto=20, confianza=0.95, linea=i, bloque=0) for i in range(8)]
        return PaginaOCR(numero=1, texto="\n".join(p.texto for p in palabras), palabras=palabras, confianza_media=0.9, ancho=w, alto=h), "paddle"

    monkeypatch.setattr(ocr_mod, "leer_pagina", ocr_falso)
    s = get_settings()
    doc, paginas, _, _ = procesar_bytes("doc.png", imagen_a_bytes(_planilla()), s)
    assert len(lecturas) == 2 and lecturas[1] == (lecturas[0][1], lecturas[0][0])
    assert paginas[0].recorte["orientacion"] == 90 and paginas[0].recorte["orientacion_auto"]
    assert paginas[0].recorte["orientacion_manual"] == 0 and "giro(90,auto)" in paginas[0].pasos_preprocesado
    h, w = doc.imagenes_procesadas[0].shape[:2]
    assert h > w  # la segunda opinión leerá la imagen ya girada
    assert fraccion_vertical(paginas[0]) == 0
    # con un giro manual pedido, no se decide solo
    lecturas.clear()
    _, paginas, _, _ = procesar_bytes("doc.png", imagen_a_bytes(_planilla()), s, recortes_manuales={1: {"esquinas": None, "orientacion": 180}})
    assert len(lecturas) == 1 and paginas[0].recorte["orientacion"] == 180


def test_pocas_palabras_no_deciden_la_orientacion():
    from app.pipeline.orquestador import fraccion_vertical

    p = PaginaOCR(numero=1, palabras=[PalabraOCR(texto="ABC", x=0, y=0, ancho=10, alto=90, confianza=1, linea=0, bloque=0)], ancho=100, alto=100)
    assert fraccion_vertical(p) == 0


def test_reproceso_no_fija_los_giros_automaticos():
    from app.commands.reprocesar_documento import recortes_manuales_guardados

    def doc(paginas):
        return SimpleNamespace(resultado=SimpleNamespace(RecorteJson=json.dumps({"v": 1, "paginas": paginas})))

    esq = [[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9]]
    assert recortes_manuales_guardados(doc([{"numero": 1, "origen": "automatico", "orientacion": 90, "orientacion_auto": True, "orientacion_manual": 0}])) == {}
    assert recortes_manuales_guardados(doc([{"numero": 1, "origen": "automatico", "orientacion": 270, "orientacion_auto": True, "orientacion_manual": 90}])) == {
        1: {"esquinas": None, "orientacion": 90}}
    assert recortes_manuales_guardados(doc([{"numero": 1, "origen": "manual", "esquinas": esq, "orientacion": 90, "orientacion_auto": True, "orientacion_manual": 0}])) == {
        1: {"esquinas": esq, "orientacion": 0}}
    # resultado de la entrega 2 (sin orientacion_manual): la orientación guardada era la manual
    assert recortes_manuales_guardados(doc([{"numero": 1, "origen": "automatico", "orientacion": 90}])) == {1: {"esquinas": None, "orientacion": 90}}


# ------------------------------------------------------------------ por la API
from tests.test_posiciones import entorno  # noqa: E402,F401  (OCR simulado: APELLIDOS (1/4, 1/5), PEREZ)

HDR = {"X-API-Key": "dev"}


def _plantilla_con_diseno(client, codigo="doc_zonas_coinc", peso=3, etiqueta_xy=(0.25, 0.2), otra_clave=None) -> int:
    # la imagen de prueba es de 1400 x 500 (relación 2,8) y el OCR simulado pone APELLIDOS en (1/4, 1/5)
    x, y = etiqueta_xy
    plantilla = {
        "codigo": codigo, "nombre": codigo, "umbral_confianza": 0.3,
        "palabras_clave": [{"texto": "apellidos", "peso": peso}] + ([{"texto": otra_clave, "peso": 1}] if otra_clave else []),
        "diseno": {"relacion": 2.8, "umbral_coincidencia": 0.8},
        "campos": [{"nombre": "apellidos", "etiqueta": "Apellidos", "tipo_dato": "texto", "obligatorio": False,
                    "regla": {"metodo": "ancla", "ancla": "Apellidos",
                              "zona_etiqueta": {"x": x - 0.01, "y": y - 0.01, "ancho": 0.12, "alto": 0.1, "texto_esperado": "APELLIDOS"}}}],
    }
    r = client.post("/api/plantillas", headers=HDR, json=plantilla)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _subir(client, plantilla_id=None):
    from tests.conftest import imagen_a_bytes
    from tests.test_posiciones import _planilla

    data = {"plantilla_id": str(plantilla_id)} if plantilla_id else {}
    r = client.post("/api/documentos", headers=HDR, data=data, files={"archivo": ("doc.png", imagen_a_bytes(_planilla()), "image/png")})
    assert r.status_code == 201, r.text
    return r.json()


def test_el_resultado_trae_la_coincidencia_y_se_guarda(entorno):
    client, _ = entorno
    pid = _plantilla_con_diseno(client)
    r = _subir(client, pid)
    c = r["coincidencia"]
    assert c["verificable"] and c["veredicto"] == "coincide" and c["etiquetas_ok"] == 1
    guardado = client.get(f"/api/documentos/{r['documento_id']}/resultado", headers=HDR).json()["coincidencia"]
    assert guardado["veredicto"] == "coincide" and guardado["zonas"][0]["esperado"] == "APELLIDOS"
    # sin cuadrícula: null
    sin = client.post("/api/plantillas", headers=HDR, json={"codigo": "sin_cuad", "nombre": "x", "umbral_confianza": 0.3,
                                                             "palabras_clave": [], "campos": []}).json()["id"]
    assert _subir(client, sin)["coincidencia"] is None


def test_si_no_coincide_sugiere_otra_plantilla_con_diseno(entorno):
    client, _ = entorno
    # su etiqueta está donde el OCR la lee, pero pierde la clasificación (le falta una palabra clave)
    _plantilla_con_diseno(client, "variante_que_calza", peso=3, otra_clave="palabra ausente")
    _plantilla_con_diseno(client, "variante_equivocada", peso=3, etiqueta_xy=(0.7, 0.7))  # gana la clasificación
    r = _subir(client)
    assert r["clasificacion"]["tipo"] == "variante_equivocada"
    c = r["coincidencia"]
    assert c["veredicto"] == "no_coincide" and "diseno_no_coincide" in r["advertencias"]
    assert c["sugerencia"]["codigo"] == "variante_que_calza" and c["sugerencia"]["puntaje"] >= 0.8


def test_probar_usa_posiciones_guardadas_y_un_diseno_sin_guardar(entorno):
    client, _ = entorno
    sin = client.post("/api/plantillas", headers=HDR, json={
        "codigo": "probar_cuad", "nombre": "x", "umbral_confianza": 0.3, "palabras_clave": [{"texto": "apellidos", "peso": 3}],
        "campos": [{"nombre": "apellidos", "etiqueta": "Apellidos", "tipo_dato": "texto", "obligatorio": False,
                    "regla": {"metodo": "ancla", "ancla": "Apellidos"}}]}).json()["id"]
    doc = _subir(client, sin)["documento_id"]
    r = client.post(f"/api/plantillas/{sin}/probar?documento_id={doc}", headers=HDR)
    assert r.status_code == 200 and r.json()["coincidencia"] is None  # la plantilla guardada no tiene cuadrícula
    # vista previa del editor: diseño y zonas aún sin guardar
    cuerpo = {
        "diseno": {"relacion": 2.8, "umbral_coincidencia": 0.8},
        "campos": [{"nombre": "apellidos", "etiqueta": "Apellidos", "tipo_dato": "texto", "obligatorio": False,
                    "regla": {"metodo": "ancla", "ancla": "Apellidos",
                              "zona_etiqueta": {"x": 0.24, "y": 0.19, "ancho": 0.12, "alto": 0.1, "texto_esperado": "APELLIDOS"}}}],
    }
    r = client.post(f"/api/plantillas/{sin}/probar?documento_id={doc}", headers=HDR, json=cuerpo)
    assert r.status_code == 200, r.text
    c = r.json()["coincidencia"]
    assert c["veredicto"] == "coincide" and c["zonas"][0]["leido"] == "APELLIDOS"
    assert r.json()["campos"]["apellidos"]["valor"] == "PEREZ"
    # nada quedó guardado
    assert client.get(f"/api/plantillas/{sin}", headers=HDR).json()["diseno"] is None


def test_con_una_sola_etiqueta_no_se_gira_por_azar():
    from tests.test_cuadricula_extraccion import _campo

    una = [_campo("apellidos", "Apellidos", (0.10, 0.20), (0.10, 0.28))]
    solo = DisenoPlantilla(relacion=1.587)
    # girada, su única etiqueta caería en su zona: no basta para girar el documento
    pagina = _pagina([("APELLIDOS", 1 - 0.10 - 0.108, 1 - 0.20 - 0.04)])
    assert orientar_paginas([pagina], una, solo) == set()
