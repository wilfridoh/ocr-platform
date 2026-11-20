from types import SimpleNamespace

import numpy as np

from app.dominio.modelos import CampoPlantillaDTO, PaginaOCR, PalabraOCR, ReglaCampo
from app.pipeline.extractor import extraer_campos
from app.pipeline.ingesta import DocumentoIngresado
from app.pipeline.orquestador import proveedor_segunda_opinion


def _pagina(texto: str, conf: float) -> PaginaOCR:
    palabras = [PalabraOCR(texto=t, x=0, y=0, ancho=10, alto=10, confianza=conf, linea=0, bloque=0) for t in texto.split()]
    return PaginaOCR(numero=1, texto=texto, palabras=palabras, confianza_media=conf, ancho=100, alto=100)


def _campo() -> CampoPlantillaDTO:
    return CampoPlantillaDTO(
        nombre="total", etiqueta="Total", tipo_dato="monto", obligatorio=True,
        regla=ReglaCampo(metodo="regex", regex=r"Total\s+([\d.]+)"),
    )


def test_no_invoca_segunda_opinion_si_confianza_alta():
    llamadas = []
    res = extraer_campos([_campo()], [_pagina("Total 45.320", 0.95)], lambda: llamadas.append(1), 0.7)
    assert res[0].valor == 45320 and not llamadas


def test_segunda_opinion_corrige_lectura_baja():
    principal = _pagina("Total 4S.32O", 0.4)  # lectura mala, no valida como monto
    alterno = _pagina("Total 45.320", 0.9)
    res = extraer_campos([_campo()], [principal], lambda: [alterno], 0.7)
    assert res[0].valor == 45320 and res[0].valido


def test_segunda_opinion_no_disponible_conserva_principal():
    res = extraer_campos([_campo()], [_pagina("Total 45.320", 0.5)], lambda: None, 0.7)
    assert res[0].valor == 45320


def test_proveedor_none_si_ninguno_o_mismo_motor_o_pdf_nativo():
    doc = DocumentoIngresado()
    doc.imagenes_procesadas = [np.zeros((10, 10, 3), dtype=np.uint8)]
    s = SimpleNamespace(OCR_SEGUNDA_OPINION="ninguno")
    assert proveedor_segunda_opinion(doc, s, "paddle") is None
    s = SimpleNamespace(OCR_SEGUNDA_OPINION="doctr")
    assert proveedor_segunda_opinion(doc, s, "doctr") is None
    assert proveedor_segunda_opinion(DocumentoIngresado(), s, "pdf-nativo") is None
    assert callable(proveedor_segunda_opinion(doc, s, "paddle"))


def test_campo_registra_motor_que_dio_la_lectura():
    principal = _pagina("Total 4S.32O", 0.4)
    principal.motor = "paddle"
    alterno = _pagina("Total 45.320", 0.9)
    alterno.motor = "doctr"
    assert extraer_campos([_campo()], [principal], lambda: [alterno], 0.7)[0].motor == "doctr"
    assert extraer_campos([_campo()], [_pagina("Total 45.320", 0.95)], None, 0.7)[0].motor is None  # sin motor en la página
    p2 = _pagina("Total 45.320", 0.95)
    p2.motor = "paddle"
    c = extraer_campos([_campo()], [p2], None, 0.7)[0]
    assert c.motor == "paddle"
    ausente = extraer_campos([_campo()], [_pagina("nada", 0.9)], None, 0.7)[0]
    assert ausente.motor is None
