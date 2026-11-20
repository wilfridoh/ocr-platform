"""Entrega 3 de la cuadrícula (docs/13 §2): extracción zona + etiqueta, desplazamiento global, tolerancia y advertencia
campo_fuera_de_zona; quitar el recorte manual. Plantilla y datos inventados, sin formato de documento real."""
from __future__ import annotations

import pytest

from app.dominio.modelos import CampoPlantillaDTO, DisenoPlantilla, PaginaOCR, PalabraOCR, ReglaCampo
from app.pipeline.ensamblador import construir_advertencias
from app.pipeline.extractor import extraer_campos
from app.pipeline.zonas import EtiquetaFija, buscar_etiqueta, calcular_marcos, palabras_relativas
from app.dominio.modelos import ZonaRelativa

W, H = 1000, 630
RECORTE = {"aplicado": True, "origen": "automatico", "esquinas": [[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9]],
           "relacion": 1.587, "orientacion": 0, "deskew": 0.0}
DISENO = DisenoPlantilla(
    formato="libre", relacion=1.587, tolerancia=0.03,
    elementos_fijos=[{"x": 0.30, "y": 0.02, "ancho": 0.40, "alto": 0.06, "texto_esperado": "TARJETA DE PRUEBA"}],
)

# Disposición base (relativa): etiqueta arriba, valor debajo
LABEL_AP = (0.10, 0.20)
VALOR_AP = (0.10, 0.28)
LABEL_NOM = (0.10, 0.40)
VALOR_NOM = (0.10, 0.48)


def _pagina(palabras: list[tuple[str, float, float]], recorte=RECORTE, dx=0.0, dy=0.0, conf=0.95) -> PaginaOCR:
    """Página con palabras en (x, y) relativos; el texto sigue el orden de la lista, una línea por palabra."""
    ps = [
        PalabraOCR(texto=t, x=int((x + dx) * W), y=int((y + dy) * H), ancho=int(0.012 * W * len(t)), alto=int(0.04 * H),
                   confianza=conf, linea=i, bloque=0)
        for i, (t, x, y) in enumerate(palabras)
    ]
    return PaginaOCR(numero=1, texto="\n".join(t for t, _, _ in palabras), palabras=ps, confianza_media=conf,
                     ancho=W, alto=H, motor="paddle", recorte=recorte)


def _campo(nombre: str, ancla: str, etiqueta_xy, valor_xy, metodo="ancla") -> CampoPlantillaDTO:
    regla = {"metodo": metodo, "ancla": ancla if metodo == "ancla" else None,
             "x": valor_xy[0] - 0.01, "y": valor_xy[1] - 0.01, "ancho": 0.40, "alto": 0.07,
             "zona_etiqueta": {"x": etiqueta_xy[0] - 0.01, "y": etiqueta_xy[1] - 0.01, "ancho": 0.25, "alto": 0.07,
                               "texto_esperado": ancla.upper()}}
    return CampoPlantillaDTO(nombre=nombre, etiqueta=ancla, tipo_dato="texto", obligatorio=True, regla=ReglaCampo(**regla))


CAMPOS = [_campo("apellidos", "Apellidos", LABEL_AP, VALOR_AP), _campo("nombres", "Nombres", LABEL_NOM, VALOR_NOM)]
BASE = [("TARJETA", 0.32, 0.03), ("DE", 0.42, 0.03), ("PRUEBA", 0.46, 0.03),
        ("APELLIDOS", *LABEL_AP), ("PEREZ", *VALOR_AP), ("NOMBRES", *LABEL_NOM), ("JUAN", *VALOR_NOM)]


def _extraer(paginas, diseno=DISENO, campos=CAMPOS, segunda=None) -> dict:
    return {c.nombre: c for c in extraer_campos(campos, paginas, segunda, 0.7, True, diseno)}


# ------------------------------------------------------------------ comportamiento sin diseño
def test_sin_diseno_la_zona_no_cambia_nada():
    sin = {c.nombre: c for c in extraer_campos(CAMPOS, [_pagina(BASE)])}
    con_none = _extraer([_pagina(BASE)], diseno=None)
    for n in ("apellidos", "nombres"):
        assert sin[n].model_dump() == con_none[n].model_dump()
        assert not sin[n].fuera_de_zona and sin[n].x is None


# ------------------------------------------------------------------ coinciden / rescate / discrepan
def test_etiqueta_y_zona_coinciden_suben_la_confianza():
    sin = {c.nombre: c for c in extraer_campos(CAMPOS, [_pagina(BASE)])}
    r = _extraer([_pagina(BASE)])
    assert r["apellidos"].valor == "PEREZ" and not r["apellidos"].fuera_de_zona
    assert r["apellidos"].confianza == pytest.approx(min(1.0, sin["apellidos"].confianza + 0.05), abs=0.001)
    assert r["apellidos"].x == pytest.approx(0.10, abs=0.002)  # la caja del valor queda informada


def test_etiqueta_ilegible_se_rescata_con_la_zona():
    palabras = [p if p[0] != "APELLIDOS" else ("AP3L1!D0S", *LABEL_AP) for p in BASE]
    sin = {c.nombre: c for c in extraer_campos(CAMPOS, [_pagina(palabras)])}
    assert sin["apellidos"].valor is None  # hoy: vacío
    r = _extraer([_pagina(palabras)])
    assert r["apellidos"].valor == "PEREZ" and r["apellidos"].confianza == pytest.approx(0.95 * 0.8, abs=0.001)


def _orden_engañoso(extra_labels=True):
    """El OCR pone justo después de APELLIDOS el apellido de OTRA persona impreso en otra parte; el valor real está en
    su zona."""
    palabras = [("TARJETA", 0.32, 0.03), ("DE", 0.42, 0.03), ("PRUEBA", 0.46, 0.03)] if extra_labels else []
    return palabras + [("APELLIDOS", *LABEL_AP), ("GOMEZ", 0.60, 0.80), ("PEREZ", *VALOR_AP),
                       ("NOMBRES", *LABEL_NOM), ("JUAN", *VALOR_NOM)]


def test_discrepan_con_diseno_verificado_gana_la_zona_con_advertencia():
    assert {c.nombre: c for c in extraer_campos(CAMPOS, [_pagina(_orden_engañoso())])}["apellidos"].valor == "GOMEZ"
    r = _extraer([_pagina(_orden_engañoso())])
    assert r["apellidos"].valor == "PEREZ" and r["apellidos"].fuera_de_zona
    assert r["apellidos"].confianza == pytest.approx(0.95 * 0.8, abs=0.001)
    assert "campo_fuera_de_zona:apellidos" in construir_advertencias(list(r.values()), {"apellidos"})
    assert "campo_fuera_de_zona:nombres" not in construir_advertencias(list(r.values()), set())


def test_discrepan_sin_diseno_verificado_gana_la_etiqueta_con_advertencia():
    # las etiquetas fijas no están en su sitio (otra variante del documento): no hay base para preferir la zona
    palabras = [("APELLIDOS", 0.60, 0.60), ("GOMEZ", 0.60, 0.68), ("PEREZ", *VALOR_AP), ("NOMBRES", 0.60, 0.75), ("JUAN", 0.6, 0.83)]
    r = _extraer([_pagina(palabras)])
    assert r["apellidos"].valor == "GOMEZ" and r["apellidos"].fuera_de_zona


def test_sin_recorte_fiable_la_zona_no_se_usa():
    for recorte in (None, {**RECORTE, "relacion": 2.4}, {**RECORTE, "aplicado": False, "origen": "ninguno", "relacion": 1.33}):
        r = _extraer([_pagina(_orden_engañoso(), recorte=recorte)])
        assert r["apellidos"].valor == "GOMEZ" and not r["apellidos"].fuera_de_zona, recorte


# ------------------------------------------------------------------ desplazamiento y tolerancia
def test_desplazamiento_global_se_corrige_con_las_etiquetas_fijas():
    # todo corrido 8 % abajo: el valor queda fuera de su zona + tolerancia (3 %), pero las etiquetas lo delatan
    palabras = [p for p in BASE if p[0] != "APELLIDOS"]  # el OCR no leyó la etiqueta: obliga a usar la zona
    assert calcular_marcos([_pagina(palabras)], CAMPOS, DISENO)[1].dy == 0  # en su sitio: nada que corregir
    marcos = calcular_marcos([_pagina(palabras, dy=0.08)], CAMPOS, DISENO)
    assert marcos[1].dx == 0 and marcos[1].dy == pytest.approx(0.045, abs=0.01)  # lo mínimo para que entren
    sin_corregir = calcular_marcos([_pagina(palabras, dy=0.08)], CAMPOS, DISENO)[1]
    sin_corregir.dy = 0
    from app.pipeline.zonas import texto_en_zona, zona_valor

    assert texto_en_zona(sin_corregir, zona_valor(CAMPOS[0]))[0] is None  # sin la corrección, la zona quedaba vacía
    assert _extraer([_pagina(palabras, dy=0.08)])["apellidos"].valor == "PEREZ"
    # con UNA sola etiqueta encontrada no se estima desplazamiento: la zona queda vacía y no se inventa nada
    solo = [("PEREZ", *VALOR_AP), ("NOMBRES", *LABEL_NOM)]
    marcos = calcular_marcos([_pagina(solo, dy=0.08)], CAMPOS, DISENO)
    assert marcos[1].dx == 0 and marcos[1].dy == 0
    assert _extraer([_pagina(solo, dy=0.08)])["apellidos"].valor is None


def test_tolerancia_admite_un_corrimiento_pequeno():
    # zona del valor: y de 0,27 a 0,34; con 3 % de tolerancia el centro de la palabra puede llegar a 0,37
    palabras = [("AP3L1!D0S", *LABEL_AP), ("PEREZ", VALOR_AP[0], VALOR_AP[1] + 0.04)]  # centro en 0,34
    assert _extraer([_pagina(palabras)])["apellidos"].valor == "PEREZ"
    palabras = [("AP3L1!D0S", *LABEL_AP), ("PEREZ", VALOR_AP[0], VALOR_AP[1] + 0.09)]  # centro en 0,39: fuera
    assert _extraer([_pagina(palabras)])["apellidos"].valor is None


def test_metodo_zona_con_diseno_usa_desplazamiento_y_sin_recorte_fiable_no_inventa():
    campo = _campo("apellidos", "Apellidos", LABEL_AP, VALOR_AP, metodo="zona")
    campos = [campo, CAMPOS[1]]
    assert _extraer([_pagina(BASE, dx=0.06, dy=0.05)], campos=campos)["apellidos"].valor == "PEREZ"
    assert _extraer([_pagina(BASE, recorte=None)], campos=campos)["apellidos"].valor is None
    # sin diseño, el método zona de siempre (sin tolerancia ni desplazamiento)
    assert {c.nombre: c for c in extraer_campos(campos, [_pagina(BASE)])}["apellidos"].valor == "PEREZ"


# ------------------------------------------------------------------ etiquetas fijas
def test_buscar_etiqueta_tolera_palabras_pegadas_y_elige_la_mas_cercana():
    zona = ZonaRelativa(x=0.1, y=0.2, ancho=0.3, alto=0.06)
    pag = _pagina([("FECHADE", 0.6, 0.8), ("NACIMIENTO", 0.7, 0.8), ("FECHA", 0.1, 0.2), ("DENACIMIENTO", 0.16, 0.2)])
    e = buscar_etiqueta(palabras_relativas(pag), EtiquetaFija("FECHA DE NACIMIENTO", zona))
    assert e.similitud >= 0.95 and e.cx < 0.5  # la que está en su sitio, no la de abajo a la derecha
    assert buscar_etiqueta(palabras_relativas(pag), EtiquetaFija("DOMICILIO", zona)).similitud == 0.0


def test_marco_verificado_requiere_la_mitad_de_las_etiquetas_en_su_sitio():
    assert calcular_marcos([_pagina(BASE)], CAMPOS, DISENO)[1].verificado
    movidas = [("TARJETA", 0.32, 0.6), ("DE", 0.42, 0.6), ("PRUEBA", 0.46, 0.6), ("APELLIDOS", 0.6, 0.9),
               ("NOMBRES", *LABEL_NOM)]
    assert not calcular_marcos([_pagina(movidas)], CAMPOS, DISENO)[1].verificado
    assert calcular_marcos([_pagina(BASE)], CAMPOS, None) == {}


# ------------------------------------------------------------------ segunda opinión
def test_la_segunda_opinion_hereda_el_recorte_y_usa_las_zonas():
    ilegible = [("AP3L1!D0S", *LABEL_AP), ("P3R", 0.10, 0.28), ("NOMBRES", *LABEL_NOM), ("JUAN", *VALOR_NOM)]
    alternativa = _pagina(BASE, recorte=None)  # el segundo motor no trae recorte: lo hereda de la página principal
    llamadas = []

    def segunda():
        llamadas.append(1)
        return [alternativa]

    principal = _pagina(ilegible, conf=0.5)
    r = _extraer([principal], segunda=segunda)
    assert llamadas == [1] and r["apellidos"].valor == "PEREZ"


def test_las_palabras_de_una_etiqueta_fija_no_se_cuelan_en_la_zona_del_valor():
    # la etiqueta queda a menos de la tolerancia de la zona del valor (impresa justo encima): no forma parte del valor
    campo = _campo("apellidos", "Apellidos", (0.10, 0.25), VALOR_AP, metodo="zona")
    palabras = [("TARJETA", 0.32, 0.03), ("DE", 0.42, 0.03), ("PRUEBA", 0.46, 0.03),
                ("APELLIDOS", 0.10, 0.25), ("PEREZ", *VALOR_AP), ("NOMBRES", *LABEL_NOM), ("JUAN", *VALOR_NOM)]
    assert _extraer([_pagina(palabras)], campos=[campo, CAMPOS[1]])["apellidos"].valor == "PEREZ"
    # sin diseño (método zona de siempre, sin tolerancia) la etiqueta ya quedaba fuera
    assert {c.nombre: c for c in extraer_campos([campo], [_pagina(palabras)])}["apellidos"].valor == "PEREZ"


# ------------------------------------------------------------------ por la API
from tests.test_posiciones import _planilla, entorno  # noqa: E402,F401  (fixture: OCR simulado APELLIDOS / PEREZ)

HDR = {"X-API-Key": "dev"}


def _subir_planilla(client, plantilla_id=None) -> str:
    from tests.conftest import imagen_a_bytes

    data = {"plantilla_id": str(plantilla_id)} if plantilla_id else {}
    r = client.post("/api/documentos", headers=HDR, data=data,
                    files={"archivo": ("doc.png", imagen_a_bytes(_planilla()), "image/png")})
    assert r.status_code == 201, r.text
    return r.json()


def test_el_procesamiento_usa_el_diseno_de_la_plantilla(entorno):
    client, _ = entorno
    # imagen de 1400 x 500 sin recorte (relación 2,8): con esa proporción en el diseño, la página es fiable
    plantilla = {
        "codigo": "doc_prueba_zonas", "nombre": "Doc prueba zonas", "umbral_confianza": 0.3,
        "palabras_clave": [{"texto": "apellidos", "peso": 3}],
        "diseno": {"relacion": 2.8, "tolerancia": 0.02},
        "campos": [{"nombre": "apellidos", "etiqueta": "Apellidos", "tipo_dato": "texto", "obligatorio": False,
                    # zona del valor en una esquina vacía: lo que lee la etiqueta queda "fuera de zona"
                    "regla": {"metodo": "ancla", "ancla": "Apellidos", "x": 0.8, "y": 0.8, "ancho": 0.1, "alto": 0.1}}],
    }
    pid = client.post("/api/plantillas", headers=HDR, json=plantilla).json()["id"]
    r = _subir_planilla(client, pid)
    assert r["campos"]["apellidos"]["valor"] == "PEREZ"  # sin etiquetas fijas no hay diseño verificado: gana la etiqueta
    assert "campo_fuera_de_zona:apellidos" in r["advertencias"]
    # la misma plantilla sin diseño: ni advertencia ni cambios
    sin = {**plantilla, "diseno": None}
    client.put(f"/api/plantillas/{pid}", headers=HDR, json=sin)
    r = _subir_planilla(client, pid)
    assert r["campos"]["apellidos"]["valor"] == "PEREZ" and not any("fuera_de_zona" in a for a in r["advertencias"])


def test_quitar_el_recorte_manual_vuelve_al_automatico(entorno):
    client, _ = entorno
    doc = _subir_planilla(client)["documento_id"]
    esquinas = [[0.05, 0.1], [0.95, 0.08], [0.96, 0.9], [0.04, 0.92]]
    assert client.post(f"/api/documentos/{doc}/paginas/1/recorte", headers=HDR, json={"esquinas": esquinas, "orientacion": 90}).status_code == 200
    assert client.get(f"/api/documentos/{doc}/paginas/1/palabras", headers=HDR).json()["recorte"]["origen"] == "manual"
    r = client.delete(f"/api/documentos/{doc}/paginas/1/recorte", headers=HDR)
    assert r.status_code == 200 and r.json()["documento_id"] == doc
    rec = client.get(f"/api/documentos/{doc}/paginas/1/palabras", headers=HDR).json()["recorte"]
    assert rec["origen"] == "ninguno" and rec["orientacion"] == 0 and rec["esquinas"] is None
    # y un reproceso posterior ya no lo recupera
    client.post(f"/api/documentos/{doc}/reprocesar", headers=HDR)
    assert client.get(f"/api/documentos/{doc}/paginas/1/palabras", headers=HDR).json()["recorte"]["origen"] == "ninguno"
    # sin recorte manual, quitar equivale a reprocesar; página fuera de rango: 404
    assert client.delete(f"/api/documentos/{doc}/paginas/1/recorte", headers=HDR).status_code == 200
    assert client.delete(f"/api/documentos/{doc}/paginas/2/recorte", headers=HDR).status_code == 404
