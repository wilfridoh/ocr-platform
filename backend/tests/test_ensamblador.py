from app.dominio.modelos import CampoExtraidoDTO, Clasificacion, PaginaOCR
from app.pipeline.ensamblador import confianza_global, construir_advertencias, ensamblar


def _campo(nombre, valor, valido, confianza=0.9, valor_texto=None):
    return CampoExtraidoDTO(
        nombre=nombre,
        valor=valor,
        valor_texto=valor_texto if valor_texto is not None else (str(valor) if valor is not None else None),
        confianza=confianza,
        valido=valido,
    )


def test_advertencia_campo_obligatorio_faltante():
    campos = [_campo("total_pagar", None, False, confianza=0.0, valor_texto=None)]
    advertencias = construir_advertencias(campos, obligatorios={"total_pagar"})
    assert advertencias == ["campo_obligatorio_faltante:total_pagar"]


def test_advertencia_campo_obligatorio_invalido_pero_con_texto():
    # el OCR encontró algo, pero el validador lo rechazó (p.ej. una fecha imposible):
    # sigue siendo "obligatorio_faltante" porque no es válido, no "no_valido"
    campos = [_campo("fecha_vencimiento", None, False, confianza=0.2, valor_texto="31/02/2026")]
    advertencias = construir_advertencias(campos, obligatorios={"fecha_vencimiento"})
    assert advertencias == ["campo_obligatorio_faltante:fecha_vencimiento"]


def test_advertencia_campo_opcional_no_valido_pero_no_obligatorio():
    campos = [_campo("telefono", None, False, confianza=0.1, valor_texto="abc")]
    advertencias = construir_advertencias(campos, obligatorios=set())
    assert advertencias == ["campo_no_valido:telefono"]


def test_sin_advertencias_cuando_todo_es_valido():
    campos = [_campo("numero_cliente", "1234567-8", True)]
    advertencias = construir_advertencias(campos, obligatorios={"numero_cliente"})
    assert advertencias == []


def test_confianza_global_sin_campos_solo_usa_clasificacion():
    clasificacion = Clasificacion(tipo="desconocido", confianza=0.0)
    conf = confianza_global(clasificacion, [], obligatorios=set())
    assert conf == 0.0


def test_confianza_global_combina_clasificacion_y_campos():
    clasificacion = Clasificacion(tipo="planilla_servicio_electrico", confianza=1.0)
    campos = [_campo("total_pagar", 45320.0, True, confianza=1.0)]
    conf = confianza_global(clasificacion, campos, obligatorios={"total_pagar"})
    # 0.4*1.0 + 0.6*1.0 == 1.0 (pesos documentados en docs/02 §4.7)
    assert conf == 1.0


def test_confianza_global_penaliza_campos_con_baja_confianza():
    clasificacion = Clasificacion(tipo="planilla_servicio_electrico", confianza=1.0)
    campos = [_campo("total_pagar", None, False, confianza=0.0, valor_texto=None)]
    conf = confianza_global(clasificacion, campos, obligatorios={"total_pagar"})
    assert conf < 1.0
    assert abs(conf - 0.4) < 1e-9


def test_ensamblar_tipo_desconocido_sin_campos_extraidos():
    # caso "ningún tipo supera el umbral": no hay plantilla ganadora, por lo tanto no hay campos que extraer
    pagina = PaginaOCR(numero=1, texto="documento irreconocible", palabras=[], confianza_media=0.5)
    clasificacion = Clasificacion(tipo="desconocido", confianza=0.1)
    resultado = ensamblar(
        paginas=[pagina],
        clasificacion=clasificacion,
        campos=[],
        palabras_clave_encontradas=[],
        obligatorios=set(),
        tiempos_ms={"ocr": 10},
        motor_ocr="tesseract",
    )
    assert resultado.clasificacion.tipo == "desconocido"
    assert resultado.campos == []
    assert resultado.advertencias == []
    contrato = resultado.a_contrato(documento_id="abc123", archivo="doc.png")
    assert contrato["clasificacion"]["tipo"] == "desconocido"
    assert contrato["campos"] == {}
