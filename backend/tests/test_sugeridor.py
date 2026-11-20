from app.pipeline.sugeridor import STOPWORDS_ES, sugerir_campos, sugerir_palabras_clave

TEXTO = (
    "Planilla de servicio electrico\nN Cliente: 1234567-8\nTotal a pagar $ 45.320\nVencimiento 30/11/2026\n"
    "El presente documento se emite en la ciudad de Quito a favor del titular de la cuenta por el valor de 12.500\n"
    "La empresa informa que el consumo de la planilla del mes de octubre fue de 145 kWh en el sector."
)


def test_palabras_clave_sin_stopwords_ni_numeros():
    kws = [k.texto for k in sugerir_palabras_clave(TEXTO, ["otro documento cualquiera sobre contratos"], 15)]
    assert kws
    for k in kws:
        tokens = k.split()
        assert not all(t in STOPWORDS_ES for t in tokens), k
        assert tokens[0] not in STOPWORDS_ES and tokens[-1] not in STOPWORDS_ES, k
        assert not any(ch.isdigit() for ch in k), k


def test_campos_con_anclas_cortas_y_tipadas():
    campos = {c.regla.ancla: c for c in sugerir_campos(TEXTO)}
    assert campos["N Cliente"].tipo_dato == "rut" or campos["N Cliente"].tipo_dato == "numero"
    assert campos["Total a pagar"].tipo_dato == "monto"
    assert campos["Vencimiento"].tipo_dato == "fecha"
    for c in campos.values():
        assert len(c.regla.ancla.split()) <= 4 and len(c.regla.ancla) <= 40


def test_prosa_larga_no_genera_campo():
    anclas = [c.regla.ancla for c in sugerir_campos(TEXTO)]
    assert not any("presente documento" in a or "ciudad de Quito" in a for a in anclas)


CERTIFICADO = (
    "Número de certificado: UC-18779f74-b052-4c3e-b5af-6fd53cde5065\n"
    "Url del certificado ude.my/UC-18779f74-b052-4c3e-b5af-6fd53cde5065\n"
    "Número de referencia: 0004\nCERTIFICADO DE FINALIZACIÓN\nHabilidades blandas para\n"
    "desarrolladores en la era de\nla IA\nInstructores Michael Rodriguez\n"
    "Fecha 5 de noviembre de 2026\nDuración 38 total mins"
)
ARTICULO = (
    "Sincronización de catálogos: proceso paso a\npaso\nOct 28, 2026 · @Claudio Hidalgo\n"
    "El paquete SSIS copia los catálogos de Resuelve, DWH y SIAC a la base del Gestor de Precios: extrae a tablas\n"
    "staging en paralelo, aplica los cambios a las tablas finales y registra cada ejecución.\nPage 1 of 19"
)


def test_certificado_real_da_campos_razonables():
    campos = {c.nombre: c for c in sugerir_campos(CERTIFICADO)}
    assert set(campos) == {"numero_de_certificado", "numero_de_referencia", "fecha", "duracion"}
    assert campos["fecha"].tipo_dato == "fecha" and campos["fecha"].regla.ancla == "Fecha"
    assert campos["numero_de_certificado"].regla.ancla == "Número de certificado"


def test_articulo_en_prosa_no_genera_ruido():
    assert sugerir_campos(ARTICULO) == []


def test_palabras_clave_certificado_incluyen_certificado():
    kws = [k.texto for k in sugerir_palabras_clave(CERTIFICADO, ["total a pagar consumo kwh"], 10)]
    assert "certificado" in kws
