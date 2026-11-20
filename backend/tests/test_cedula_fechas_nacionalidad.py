"""Cédula: gentilicio con un carácter mal leído y fechas implausibles o en conflicto entre motores. Datos inventados."""
from datetime import date

import pytest

from app.dominio.modelos import CampoPlantillaDTO, ReglaCampo
from app.pipeline.extractor import _en_catalogo, _fechas_en_conflicto, extraer_campos
from tests.test_cedula_robusta import _pagina_con_palabras
from tests.test_seed_reglas import _campos


def _extraer(texto: str, alternativa: str | None = None) -> tuple[dict, int]:
    llamadas = []

    def segunda_opinion():
        llamadas.append(1)
        return [_pagina_con_palabras(alternativa)] if alternativa else None

    campos = extraer_campos(_campos("cedula_identidad"), [_pagina_con_palabras(texto)], segunda_opinion, 0.7, True)
    return {c.nombre: c for c in campos}, len(llamadas)


# ------------------------------------------------------------------ nacionalidad
@pytest.mark.parametrize(
    "leido, canonico",
    [
        ("LCUATORIANA", "ECUATORIANA"), ("CCUATORIANA", "ECUATORIANA"), ("FCUATORIANA", "ECUATORIANA"),
        ("BCUATORIANA", "ECUATORIANA"), ("ECUATOR1ANA", "ECUATORIANA"), ("ECUATORlANA", "ECUATORIANA"),
        ("ECUAT0RIANO", "ECUATORIANO"), ("ecuatorianA", "ECUATORIANA"), ("COLOMBlANA", "COLOMBIANA"),
        ("ESPANOLA", "ESPAÑOLA"),
    ],
)
def test_gentilicio_con_un_caracter_mal_leido_se_guarda_canonico(leido, canonico):
    # la etiqueta NACIONALIDAD salió ilegible: solo queda la palabra del gentilicio
    r, _ = _extraer(f"APELLIDOS\nPEREZ\nNOMBRES\nJUAN\nNACK NAl fDA\n{leido}\nSEXO\nHOMBRE")
    assert r["nacionalidad"].valor == canonico and r["nacionalidad"].valido
    assert r["nacionalidad"].valor_texto == leido  # se conserva lo que leyó el OCR
    assert r["nacionalidad"].confianza >= 0.9  # la confianza es la de la palabra leída: no dispara la segunda opinión


def test_gentilicio_corregido_con_poca_confianza_no_dispara_la_segunda_opinion():
    # latencia: nacionalidad es opcional y su valor canónico es de un conjunto cerrado; docTR no lo mejoraría
    from tests.test_cedula_robusta import TEXTO_CEDULA_NUEVA

    pagina = _pagina_con_palabras(TEXTO_CEDULA_NUEVA.replace("ECUATORIANA", "LCUATORIANA"))
    for p in pagina.palabras:
        if p.texto == "LCUATORIANA":
            p.confianza = 0.6
    llamadas = []
    campos = extraer_campos(_campos("cedula_identidad"), [pagina], lambda: llamadas.append(1), 0.7, True)
    nac = next(c for c in campos if c.nombre == "nacionalidad")
    assert nac.valor == "ECUATORIANA" and nac.confianza < 0.7 and llamadas == []
    # con dos caracteres mal leídos no hay valor: es un opcional vacío y tampoco la dispara (paso 1b)
    pagina = _pagina_con_palabras(TEXTO_CEDULA_NUEVA.replace("ECUATORIANA", "LCUATOR1ANA"))
    for p in pagina.palabras:
        if p.texto == "LCUATOR1ANA":
            p.confianza = 0.6
    extraer_campos(_campos("cedula_identidad"), [pagina], lambda: llamadas.append(1), 0.7, True)
    assert llamadas == []  # sin valor (dos errores): opcional vacío, tampoco dispara


def test_gentilicio_con_etiqueta_legible_tambien_se_normaliza():
    r, _ = _extraer("NACIONALIDAD: LCUATORIANA\nSEXO\nHOMBRE")
    assert r["nacionalidad"].valor == "ECUATORIANA"


@pytest.mark.parametrize(
    "texto",
    [
        "REPUBLICA DEL ECUADOR\nCEDULACION\nIDENTIFICACIONY\nAUTOIDENTIFICACION",  # palabras reales del documento
        "LCUATOR1ANA",  # dos caracteres mal leídos: ya no se adivina
        "ECUATORIANX",  # a un carácter de ECUATORIANA y de ECUATORIANO: no se elige
        "CUBAMA",  # gentilicio corto: un carácter cambia la palabra, sin tolerancia
        "ARGENTINITA",
    ],
)
def test_gentilicio_sin_falsos_positivos(texto):
    r, _ = _extraer(f"APELLIDOS\nPEREZ\n{texto}")
    assert r["nacionalidad"].valor is None


def test_catalogo_es_generico_de_la_regla():
    assert _en_catalogo("PlCHINCHA", ["PICHINCHA", "GUAYAS"]) == "PICHINCHA"
    assert _en_catalogo("GUAYAZ", ["PICHINCHA", "GUAYAS"]) is None  # < 7 letras: solo exacto
    assert _en_catalogo("guayas", ["PICHINCHA", "GUAYAS"]) == "GUAYAS"
    campo = CampoPlantillaDTO(
        nombre="provincia", etiqueta="Provincia", tipo_dato="texto",
        regla=ReglaCampo(metodo="regex", regex=r"PROVINCIA:\s*(\w+)", catalogo=["PICHINCHA", "GUAYAS"]),
    )
    (c,) = extraer_campos([campo], [_pagina_con_palabras("PROVINCIA: PlCHINCHA")])
    assert c.valor == "PICHINCHA" and c.valor_texto == "PlCHINCHA"
    (c,) = extraer_campos([campo], [_pagina_con_palabras("Lugar\nPlCHINCHA QUITO")])  # sin etiqueta: se busca
    assert c.valor == "PICHINCHA"


# ------------------------------------------------------------------ fechas plausibles
def _hace(anios: int) -> int:
    return date.today().year - anios


@pytest.mark.parametrize(
    "fecha, valida",
    [
        ("16 OCT 1990", True),
        ("16 OCT 1320", False),  # año imposible (mal leído)
        (f"16 OCT {_hace(121)}", False),  # más de 120 años
        (f"16 OCT {_hace(119)}", True),
        (f"16 OCT {date.today().year + 1}", False),  # nacimiento futuro
        ("31 FEB 1990", False),  # día inexistente
        ("1990-13-02", False),  # mes inexistente
    ],
)
def test_fecha_de_nacimiento_implausible_queda_no_valida(fecha, valida):
    r, _ = _extraer(f"APELLIDOS\nPEREZ\nNOMBRES\nJUAN\nFECHA DE NACIMIENTO\n{fecha}\nNUI.1234567890")
    f = r["fecha_nacimiento"]
    assert f.valido is valida, fecha
    if not valida:
        assert f.valor_texto and f.valor == f.valor_texto  # lo leído, marcado no válido: no una fecha ISO inventada
        assert f.confianza < 0.7


@pytest.mark.parametrize(
    "fecha, valida",
    [
        ("03 OCT 2036", True),
        ("03 OCT 2020", True),  # cédula vencida: sigue siendo una fecha real
        (f"03 OCT {date.today().year + 31}", False),  # vigencia imposible
        ("31 SEP 2030", False),  # día inexistente
        ("03 OCT 1320", False),
    ],
)
def test_fecha_de_vencimiento_debe_ser_real_y_plausible(fecha, valida):
    r, _ = _extraer(f"FECHA DE VENCIMIENTO\n{fecha}")
    assert r["fecha_vencimiento"].valido is valida, fecha


def test_fecha_inferida_con_dia_sustituido_no_se_adivina():
    # etiqueta ilegible y día "1l": antes se guardaba como 11; ahora queda tal cual, no válida
    r, _ = _extraer("APELLIDOS\nPEREZ\nIl l I4A lNAr\n1l.OCT 1990\nFECHA DE VENCIMIENTO\n03 OCT 2036")
    f = r["fecha_nacimiento"]
    assert not f.valido and f.valor_texto == "1l.OCT 1990" and f.valor == "1l.OCT 1990"
    assert r["fecha_vencimiento"].valor == "2036-10-03"


# ------------------------------------------------------------------ conflicto entre motores
def test_conflicto_de_cifras_entre_motores():
    assert _fechas_en_conflicto("1l.OCT 1320", "1920-10-10")  # día 1l (=11) frente a 10; año 3 frente a 9
    assert _fechas_en_conflicto("11 OCT 1320", "1920-10-11")  # año
    assert _fechas_en_conflicto("10 NOV 1920", "1920-10-10")  # mes
    assert not _fechas_en_conflicto("1l.OCT 1990", "1990-10-11")  # l = 1: la segunda opinión lo confirma
    assert not _fechas_en_conflicto("03 NOV d990", "1990-11-03")  # dígito ilegible: se completa
    assert not _fechas_en_conflicto("03 NOV d1990", "1990-11-03")
    assert not _fechas_en_conflicto("1990-1X-02", "1990-10-02")
    assert _fechas_en_conflicto("1990-11-02", "1990-10-02")
    assert not _fechas_en_conflicto("ilegible", "1990-10-02")  # sin forma de fecha: nada que contrastar
    assert not _fechas_en_conflicto(None, "1990-10-02")


# Forma del caso real (cédula inclinada, etiquetas ilegibles), con datos inventados. El motor principal lee el
# día y el año con caracteres confundidos; la segunda opinión lee "limpio" otro año. Ninguna es confiable.
PRINCIPAL = """CEDULA DE
REPUBLICA DEL ECUADOR
IDENTIDAD
APELLIDOS
CONDICION CIUDADANIA
PEREZ
SOTO
JUAN CARLOS
HA1HAt IrA)
LCUATORIANA
I1 t 11Alt IJ:T
1l.OCT 1320
GUAYAS GUAYAQUIL
ii c A LI V.HCIMILHTO
03 OCT 2036
NUI.123456789-01
"""
SEGUNDA = """CEDULA DE
IDENTIDAD
REPUBLICA DEL ECUADOR
APELLIDOS
PEREZ
SOTO
NOMBRES
JUAN CARLOS
NACIC ONAI IDAD
CCUATORIANA
IICHAL NA 11J 1
10. OCT 1920
GUAYAS GUAYAQUIL
I I CHA LI VENCRALAILNTO
03 OCT 2036
NUI.1234567890
"""


def test_caso_cedula_inclinada_no_inventa_la_fecha_y_rescata_la_nacionalidad():
    r, llamadas = _extraer(PRINCIPAL, SEGUNDA)
    assert llamadas == 1  # el número (obligatorio) no se leyó: entra la segunda opinión, como antes
    assert r["nacionalidad"].valor == "ECUATORIANA" and r["nacionalidad"].valor_texto == "LCUATORIANA"  # del principal
    f = r["fecha_nacimiento"]
    assert not f.valido and f.valor_texto == "1l.OCT 1320"  # no "1920-10-10"
    assert r["fecha_vencimiento"].valor == "2036-10-03"
    assert r["numero_documento"].valor == "1234567890" and r["nombres"].valor == "JUAN CARLOS"


def test_segunda_opinion_que_solo_completa_lo_ilegible_si_se_acepta():
    r, llamadas = _extraer(
        "APELLIDOS\nPEREZ\nIl l I4A lNAr\n1l.OCT 1990\nNUI.1234567890",
        "APELLIDOS\nPEREZ\nIl l I4A lNAr\n11 OCT 1990\nNUI.1234567890",
    )
    assert llamadas == 1 and r["fecha_nacimiento"].valor == "1990-10-11" and r["fecha_nacimiento"].valido
    r, _ = _extraer(
        "APELLIDOS\nPEREZ\nFECHA DE NACIMIENTO\n03 NOV d990\nNUI.1234567890",
        "APELLIDOS\nPEREZ\nFECHA DE NACIMIENTO\n03 NOV 1990\nNUI.1234567890",
    )
    assert r["fecha_nacimiento"].valor == "1990-11-03"
