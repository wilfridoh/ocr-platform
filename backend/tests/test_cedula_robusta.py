"""Iteración «robustecer cédula»: variantes reales de cédula ecuatoriana leídas por OCR. Datos inventados."""
from app.dominio.modelos import PaginaOCR, PalabraOCR
from app.pipeline.clasificador import PlantillaCandidata, clasificar
from app.pipeline.extractor import extraer_campos
from tests.test_seed_reglas import _campos, _palabras_clave_seed

# Tercera variante: "CÉDULA DE IDENTIDAD" nueva. El encabezado sale partido en líneas, "APELLIDOS" va seguido de la
# etiqueta de otro dato ("CONDICIÓN CIUDADANÍA"), los dos apellidos van en dos líneas y el número es "NUI.<10 dígitos>".
TEXTO_CEDULA_NUEVA = """CEDULA DE
REPUBLICA DEL ECUADOR
IDENTIDAD
DIRECCION GENERAL DE REGISTRO CIVIL IDENTIFICACIONY CEDULACION
APELLIDOS
CONDICION CIUDADANIA
PEREZ
SOTO
NOMBRES
JUAN CARLOS
NACIONALIDAD
ECUATORIANA
FECHA DE NACIMIENTO
SEXO
16 OCT 1990
HOMBRE
LUGAR DE NACIMIENTO
AUTOIDENTIFICACION
PICHINCHA QUITO
MESTIZO/A
FECHA DE VENCIMIENTO
FIRMA DEL TITULAR
03 OCT 2036
NUI.1234567890
"""


def _extraer(texto: str) -> dict:
    pagina = PaginaOCR(numero=1, texto=texto, confianza_media=0.9, ancho=1000, alto=700)
    return {c.nombre: c for c in extraer_campos(_campos("cedula_identidad"), [pagina])}


def _pagina_con_palabras(texto: str, confianza: float = 0.97) -> PaginaOCR:
    """Página como la entrega el OCR real: además del texto, cada palabra con su confianza."""
    palabras = [
        PalabraOCR(texto=palabra, x=10 * j, y=20 * i, ancho=9, alto=18, confianza=confianza, linea=i, bloque=0)
        for i, linea in enumerate(texto.splitlines())
        for j, palabra in enumerate(linea.split())
    ]
    return PaginaOCR(numero=1, texto=texto, palabras=palabras, confianza_media=confianza, ancho=1000, alto=700)


def _clasificar(texto: str):
    cand = PlantillaCandidata(
        plantilla_id=3, version_id=3, codigo="cedula_identidad", umbral_confianza=0.6,
        palabras_clave=_palabras_clave_seed("cedula_identidad"),
    )
    return clasificar(texto, [cand])[0]


def test_cedula_nueva_clasifica_y_extrae():
    assert _clasificar(TEXTO_CEDULA_NUEVA).tipo == "cedula_identidad"
    r = _extraer(TEXTO_CEDULA_NUEVA)
    assert r["apellidos"].valor == "PEREZ SOTO"  # dos líneas; "CONDICION CIUDADANIA" es otra etiqueta, no el valor
    assert r["nombres"].valor == "JUAN CARLOS"
    assert r["numero_documento"].valor == "1234567890"
    assert r["fecha_nacimiento"].valor == "1990-10-16"
    assert r["fecha_vencimiento"].valor == "2036-10-03"
    assert r["nacionalidad"].valor == "ECUATORIANA" and r["sexo"].valor == "HOMBRE"


def test_cedula_nueva_clasifica_aunque_el_ocr_rompa_varias_etiquetas():
    # nacionalidad, sexo y fecha de nacimiento ilegibles: bastan el encabezado y "NUI"
    texto = (
        "CEDULA DE\nREPUBLICA DEL ECUADOR\nIDENTIDAD\nDIRECCION GENERAL DE REGISTRO CIVEL IDENTIFICACIONY CEDULACION\n"
        "APELLIDOS\nPEREZ\nNACK NAl fDA\nLCUATORIAA\nHOUDRE\nNUI.1234567890"
    )
    assert _clasificar(texto).tipo == "cedula_identidad"


def test_apellido_en_una_sola_linea_no_absorbe_la_etiqueta_siguiente():
    r = _extraer("APELLIDOS\nPEREZ\nNOMBRES\nJUAN CARLOS")
    assert r["apellidos"].valor == "PEREZ" and r["nombres"].valor == "JUAN CARLOS"


def test_etiqueta_seguida_solo_de_ruido_toma_la_linea_siguiente():
    r = _extraer("APELLIDOS Ma\nPEREZ\nSOTO - Dn\n>| NOMBRES ..\nJUAN CARLOS")
    assert r["apellidos"].valor == "PEREZ SOTO" and r["nombres"].valor == "JUAN CARLOS"


def test_etiqueta_combinada_con_error_de_ocr_en_la_etiqueta():
    r = _extraer("CEDULA DE CIUDADANIA\nAPELLIDOS Y NOM8RES\nPEREZ SOTO\nJUAN CARLOS\nLUGAR DE NACIMIENTO\nQUITO")
    assert r["apellidos"].valor == "PEREZ SOTO" and r["nombres"].valor == "JUAN CARLOS"


def test_fecha_nacimiento_sin_etiqueta_legible_usa_la_fecha_que_no_es_de_vencimiento():
    texto = "APELLIDOS\nPEREZ\nIl l I4A lNAr\nl6 OCT 1990\nFECHA DE VENCIMIENTO\n03 OCT 2036"
    r = _extraer(texto)
    assert r["fecha_nacimiento"].valor == "1990-10-16"  # "l6" es un 16 mal leído
    assert r["fecha_nacimiento"].confianza < 0.7  # es una inferencia: queda para revisión
    assert r["fecha_vencimiento"].valor == "2036-10-03"


def test_fecha_nacimiento_sin_etiqueta_no_inventa_con_fechas_futuras_o_de_vencimiento():
    assert _extraer("FECHA DE VENCIMIENTO\n03 OCT 2020")["fecha_nacimiento"].valor is None
    assert _extraer("APELLIDOS\nPEREZ\n03 OCT 2036")["fecha_nacimiento"].valor is None
    assert _extraer("APELLIDOS\nPEREZ\n16 OCT 1290")["fecha_nacimiento"].valor is None  # año mal leído: no se adivina


def test_numero_con_la_etiqueta_nui_mal_leida_por_el_ocr():
    # rendimiento: Paddle lee "NUI" como "NU1"; si el número queda vacío se dispara la segunda opinión (lenta)
    for etiqueta in ("NUI.", "NU1.", "NUl.", "NU|.", "NU!", "NU1 ", "nui: "):
        pagina = _pagina_con_palabras(TEXTO_CEDULA_NUEVA.replace("NUI.", etiqueta))
        r = {c.nombre: c for c in extraer_campos(_campos("cedula_identidad"), [pagina])}
        assert r["numero_documento"].valor == "1234567890", etiqueta
        # el número va pegado a la etiqueta en una sola palabra del OCR: aun así toma la confianza de esa palabra
        assert r["numero_documento"].confianza >= 0.9, etiqueta
    # una palabra cualquiera terminada en "nu1"/"nui" pegada a otra cosa no es la etiqueta
    assert _extraer("APELLIDOS\nPEREZ\nMENU1234567890")["numero_documento"].valor is None


def test_cedula_bien_leida_no_pide_segunda_opinion():
    from app.pipeline.extractor import extraer_campos as extraer

    llamadas = []

    def segunda_opinion():
        llamadas.append(1)
        return None

    pagina = _pagina_con_palabras(TEXTO_CEDULA_NUEVA.replace("NUI.", "NU1."))
    campos = extraer(_campos("cedula_identidad"), [pagina], segunda_opinion, 0.7)
    assert llamadas == [], [(c.nombre, c.confianza) for c in campos if c.confianza < 0.7]
    # y si de verdad falta un campo, sí se pide
    extraer(_campos("cedula_identidad"), [_pagina_con_palabras(TEXTO_CEDULA_NUEVA.replace("NUI.1234567890", ""))], segunda_opinion, 0.7)
    assert llamadas == [1]


def test_campo_sin_valor_no_toma_el_valor_del_campo_siguiente():
    # hallazgo de QA: la etiqueta de OTRO campo corta la búsqueda; no se salta como si fuera ruido
    assert _extraer("APELLIDOS\nFECHA DE NACIMIENTO\n16 OCT 1990")["apellidos"].valor is None
    assert _extraer("NOMBRES\nNACIONALIDAD\nECUATORIANA")["nombres"].valor is None
