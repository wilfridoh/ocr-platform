"""Entrega 5 de la cuadrícula (docs/13 §5): sugerencia de palabras clave y etiquetas con 1 a 3 ejemplos.
Licencia bilingüe y planilla inventadas; ningún dato de personas reales."""
from __future__ import annotations

from app.pipeline.sugeridor_ejemplos import Ejemplo, ngramas, sugerir_palabras_clave_ejemplos, sugerir_zonas_etiquetas

LICENCIA_A = """REPUBLICA DE EJEMPLO
LICENCIA DE CONDUCIR
APELLIDOS / SURNAME
GARCIA LOPEZ
NOMBRES / NAMES
MARIA ELENA
SEXO / SEX FECHA DE NACIMIENTO / DATE OF BIRTH
F 15-02-1980
CATEGORIA / CLASS
B th"""
LICENCIA_B = """REPUBLICA DE EJEMPLO
LICENCIA DE CONDUCIR
APELLIDOS / SURNAME
PEREZ SOTO
NOMBRES / NAMES
JUAN CARLOS
SEXO / SEX FECHA DE NACIMIENTO / DATE OF BIRTH
M 03-10-1975
CATEGORIA / CLASS
A"""
OTRO_TIPO = "Planilla de servicio electrico\nTotal a pagar\nREPUBLICA DE EJEMPLO\nConsumo"


def _textos(sugerencias):
    return [s["texto"] for s in sugerencias]


def test_con_dos_ejemplos_quedan_las_etiquetas_y_no_los_datos_del_titular():
    s = sugerir_palabras_clave_ejemplos([Ejemplo(LICENCIA_A), Ejemplo(LICENCIA_B)], [OTRO_TIPO], 15)
    t = _textos(s)
    assert "licencia de conducir" in t and "apellidos" in t and "nombres" in t and "fecha de nacimiento" in t
    for dato in ("garcia", "lopez", "maria", "elena", "perez", "juan", "garcia lopez"):
        assert not any(dato in x for x in t), dato
    assert all(not x["revisar"] for x in s) and all(1 <= x["peso"] <= 5 for x in s)


def test_no_mezcla_las_mitades_de_una_etiqueta_bilingue_ni_deja_fragmentos():
    t = _textos(sugerir_palabras_clave_ejemplos([Ejemplo(LICENCIA_A), Ejemplo(LICENCIA_B)], [], 30))
    assert not any("sex fecha" in x or "sexo sex" in x for x in t)  # el fallo que motivó la entrega
    assert "th" not in t and not any(len(x) < 3 for x in t)
    # la mitad en inglés puede aparecer, pero detrás de la española
    if "surname" in t:
        assert t.index("apellidos") < t.index("surname")


def test_lo_que_tambien_aparece_en_otros_tipos_distingue_menos():
    t = _textos(sugerir_palabras_clave_ejemplos([Ejemplo(LICENCIA_A), Ejemplo(LICENCIA_B)], [OTRO_TIPO] * 3, 30))
    assert t.index("licencia de conducir") < t.index("republica de ejemplo")


def test_con_un_solo_ejemplo_solo_vocabulario_de_etiqueta_y_para_revisar():
    s = sugerir_palabras_clave_ejemplos([Ejemplo(LICENCIA_A)], [], 30)
    t = _textos(s)
    assert "licencia de conducir" in t and "apellidos" in t
    assert not any(d in x for x in t for d in ("garcia", "maria", "elena"))  # un dato del titular nunca
    assert all(x["revisar"] for x in s)


def _palabra(texto, x, y, conf=0.97):
    return {"texto": texto, "x": x, "y": y, "ancho": 0.012 * len(texto), "alto": 0.04, "confianza": conf}


def test_palabras_de_baja_confianza_no_se_sugieren_y_el_encabezado_pesa_mas():
    texto = "TITULO RARO\nAPELLIDOS\nXZQWR\nNOMBRES"
    palabras = [_palabra("TITULO", 0.3, 0.03), _palabra("RARO", 0.45, 0.03), _palabra("APELLIDOS", 0.1, 0.3),
                _palabra("XZQWR", 0.1, 0.4, conf=0.4), _palabra("NOMBRES", 0.1, 0.5)]
    ejemplo = Ejemplo(texto, palabras)
    assert "xzqwr" not in ngramas(ejemplo)
    t = _textos(sugerir_palabras_clave_ejemplos([ejemplo], [], 10))
    assert t[0] == "titulo raro"  # con un ejemplo vale por estar en el encabezado, y pesa más
    assert "apellidos" in t and "xzqwr" not in t


def test_zonas_de_etiquetas_para_precargar_la_cuadricula():
    palabras = [_palabra("LICENCIA", 0.3, 0.03), _palabra("DE", 0.41, 0.03), _palabra("CONDUCIR", 0.45, 0.03),
                _palabra("APELLIDOS", 0.1, 0.3), _palabra("GARCIA", 0.1, 0.36), _palabra("LOPEZ", 0.2, 0.36),
                _palabra("15-02-1980", 0.1, 0.6)]
    zonas = sugerir_zonas_etiquetas(Ejemplo(LICENCIA_A, palabras), ["licencia de conducir"])
    textos = [z["texto_esperado"] for z in zonas]
    assert textos == ["LICENCIA DE CONDUCIR", "APELLIDOS"]  # ni el nombre del titular ni la fecha
    z = zonas[1]
    assert z["x"] == 0.1 and z["y"] == 0.3 and 0 < z["ancho"] <= 1 and z["pagina"] == 1
    assert sugerir_zonas_etiquetas(Ejemplo(LICENCIA_A), []) == []  # sin posiciones guardadas, nada


def test_sin_ejemplos_o_mas_de_tres():
    assert sugerir_palabras_clave_ejemplos([], []) == []
    muchos = [Ejemplo(LICENCIA_A), Ejemplo(LICENCIA_B), Ejemplo(LICENCIA_A), Ejemplo("OTRA COSA DISTINTA")]
    assert "licencia de conducir" in _textos(sugerir_palabras_clave_ejemplos(muchos, []))  # solo cuentan los 3 primeros


# ------------------------------------------------------------------ por la API
from tests.test_posiciones import entorno  # noqa: E402,F401  (OCR simulado: "APELLIDOS" / "PEREZ" con posiciones)

HDR = {"X-API-Key": "dev"}


def _subir(client) -> str:
    from tests.conftest import imagen_a_bytes
    from tests.test_posiciones import _planilla

    r = client.post("/api/documentos", headers=HDR, files={"archivo": ("doc.png", imagen_a_bytes(_planilla()), "image/png")})
    assert r.status_code == 201, r.text
    return r.json()["documento_id"]


def test_endpoint_sugerir_con_uno_o_varios_ejemplos(entorno):
    client, _ = entorno
    a, b = _subir(client), _subir(client)
    r = client.post(f"/api/plantillas/sugerir?documento_id={a}", headers=HDR)
    assert r.status_code == 200, r.text
    uno = r.json()
    assert uno["documento_ids"] == [a] and uno["palabras_clave"] and all(p["revisar"] for p in uno["palabras_clave"])
    assert [z["texto_esperado"] for z in uno["zonas_sugeridas"]] == ["APELLIDOS"]  # con su caja, para la cuadrícula
    r = client.post(f"/api/plantillas/sugerir?documento_id={a}&documento_id={b}", headers=HDR)
    dos = r.json()
    assert r.status_code == 200 and dos["documento_ids"] == [a, b]
    assert "apellidos" in [p["texto"] for p in dos["palabras_clave"]] and not any(p["revisar"] for p in dos["palabras_clave"])
    # límites
    assert client.post(f"/api/plantillas/sugerir?{'&'.join(['documento_id=' + a] * 2 + ['documento_id=' + b] * 2)}", headers=HDR).status_code == 200  # repetidos cuentan una vez
    c, d = _subir(client), _subir(client)
    r = client.post(f"/api/plantillas/sugerir?documento_id={a}&documento_id={b}&documento_id={c}&documento_id={d}", headers=HDR)
    assert r.status_code == 400 and "3" in r.json()["detail"]
    assert client.post("/api/plantillas/sugerir?documento_id=no-existe", headers=HDR).status_code == 400
    assert client.post("/api/plantillas/sugerir", headers=HDR).status_code == 422
