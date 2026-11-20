from app.dominio.modelos import PalabraClaveDTO
from app.pipeline.clasificador import PlantillaCandidata, clasificar


def _candidata(id_, codigo, palabras_clave, umbral=0.5):
    return PlantillaCandidata(
        plantilla_id=id_, version_id=id_, codigo=codigo, umbral_confianza=umbral, palabras_clave=palabras_clave
    )


def test_clasifica_gana_plantilla_con_mas_coincidencias():
    texto = "Planilla de consumo eléctrico. Lectura anterior 100 kWh. Total a pagar $ 45.320."
    plantillas = [
        _candidata(
            1,
            "planilla_servicio_electrico",
            [
                PalabraClaveDTO(texto="consumo kwh", peso=3),
                PalabraClaveDTO(texto="total a pagar", peso=2),
                PalabraClaveDTO(texto="lectura anterior", peso=2),
            ],
        ),
        _candidata(2, "cedula_identidad", [PalabraClaveDTO(texto="republica", peso=3)]),
    ]
    clasificacion, encontradas = clasificar(texto, plantillas)
    assert clasificacion.tipo == "planilla_servicio_electrico"
    assert clasificacion.confianza > 0.5
    assert "total a pagar" in encontradas


def test_clasifica_desconocido_bajo_umbral():
    texto = "Un documento sin relación con ninguna plantilla conocida."
    plantillas = [_candidata(1, "planilla_servicio_electrico", [PalabraClaveDTO(texto="consumo kwh", peso=3)])]
    clasificacion, _ = clasificar(texto, plantillas, umbral_desconocido=0.5)
    assert clasificacion.tipo == "desconocido"


def test_clasifica_tolerante_a_errores_ocr():
    # "kwh" mal leído como "kvvh" por el OCR
    texto = "Consumo kvvh del periodo. Total a pagar: 10000"
    plantillas = [
        _candidata(
            1,
            "planilla_servicio_electrico",
            [PalabraClaveDTO(texto="consumo kwh", peso=3), PalabraClaveDTO(texto="total a pagar", peso=2)],
        )
    ]
    clasificacion, _ = clasificar(texto, plantillas, umbral_desconocido=0.3)
    assert clasificacion.tipo == "planilla_servicio_electrico"


def test_devuelve_alternativas():
    texto = "Total a pagar $ 1000. consumo kwh 20"
    plantillas = [
        _candidata(1, "a", [PalabraClaveDTO(texto="consumo kwh", peso=3)], umbral=0.3),
        _candidata(2, "b", [PalabraClaveDTO(texto="total a pagar", peso=3)], umbral=0.9),
        _candidata(3, "c", [PalabraClaveDTO(texto="palabra inexistente", peso=1)], umbral=0.3),
    ]
    clasificacion, _ = clasificar(texto, plantillas, umbral_desconocido=0.3)
    assert len(clasificacion.alternativas) <= 2


# ---------------------------------------------------------------- huecos de cobertura


def test_sin_plantillas_devuelve_desconocido():
    # caso "ningún tipo supera el umbral" en su forma más extrema: no hay ninguna plantilla activa
    clasificacion, encontradas = clasificar("cualquier texto de un documento", [])
    assert clasificacion.tipo == "desconocido"
    assert clasificacion.confianza == 0.0
    assert clasificacion.alternativas == []
    assert encontradas == []


def test_plantilla_sin_palabras_clave_no_rompe_y_queda_desconocida():
    # plantilla activa pero mal configurada (sin palabras clave): no debe dividir por cero
    texto = "Un documento cualquiera"
    plantillas = [_candidata(1, "plantilla_vacia", [])]
    clasificacion, encontradas = clasificar(texto, plantillas, umbral_desconocido=0.3)
    assert clasificacion.tipo == "desconocido"
    assert encontradas == []


def test_texto_vacio_no_rompe_clasificador():
    plantillas = [_candidata(1, "a", [PalabraClaveDTO(texto="total a pagar", peso=3)])]
    clasificacion, encontradas = clasificar("", plantillas, umbral_desconocido=0.3)
    assert clasificacion.tipo == "desconocido"
    assert encontradas == []


def test_clasifica_tolerante_a_confusion_0_o_y_1_l():
    # ruido típico de OCR: "0" leído como "O" y "1" como "l"
    texto = "Cédula de ldentidad. Repúb1ica de Chile. Nacionalidad chilena."
    plantillas = [
        _candidata(1, "cedula_identidad", [PalabraClaveDTO(texto="republica de chile", peso=3)]),
    ]
    clasificacion, _ = clasificar(texto, plantillas, umbral_desconocido=0.3)
    assert clasificacion.tipo == "cedula_identidad"


def test_clasifica_con_puntuacion_y_numeros_intermedios():
    texto = "Planilla\nConsumo: 145 kWh\nTotal a pagar $ 45.320\nLectura anterior: 1200\nFecha de vencimiento 30/11/2026"
    plantillas = [
        _candidata(
            1,
            "planilla_servicio",
            [
                PalabraClaveDTO(texto="consumo kwh", peso=3),
                PalabraClaveDTO(texto="total a pagar", peso=3),
                PalabraClaveDTO(texto="lectura anterior", peso=2),
                PalabraClaveDTO(texto="fecha de vencimiento", peso=2),
            ],
        )
    ]
    clasificacion, encontradas = clasificar(texto, plantillas, umbral_desconocido=0.5)
    assert clasificacion.tipo == "planilla_servicio" and clasificacion.confianza > 0.9
    assert "consumo kwh" in encontradas


def test_no_falsos_positivos_con_palabras_sueltas():
    texto = "El consumo de agua del mes. Otro texto sin relación, kilos."
    plantillas = [_candidata(1, "x", [PalabraClaveDTO(texto="consumo kwh", peso=3)])]
    clasificacion, _ = clasificar(texto, plantillas, umbral_desconocido=0.3)
    assert clasificacion.tipo == "desconocido"


def test_variantes_con_barra_cuentan_una_sola_vez():
    texto = "Planilla\nN° Cliente: 1234567-8\nTotal pagar 45.320"
    pk = [
        PalabraClaveDTO(texto="numero de cliente|n cliente|nro cliente", peso=4),
        PalabraClaveDTO(texto="total a pagar|total pagar", peso=3),
    ]
    clasificacion, encontradas = clasificar(texto, [_candidata(1, "planilla_servicio", pk)], umbral_desconocido=0.5)
    assert clasificacion.tipo == "planilla_servicio" and clasificacion.confianza >= 0.9
    assert len(encontradas) == 2
