from app.dominio.modelos import CampoPlantillaDTO, PaginaOCR, PalabraOCR, ReglaCampo
from app.pipeline.extractor import extraer_campo


def _palabra(texto, x, y, ancho=40, alto=20, linea=0, confianza=0.9):
    return PalabraOCR(texto=texto, x=x, y=y, ancho=ancho, alto=alto, confianza=confianza, linea=linea, bloque=0)


def _pagina(texto: str, palabras: list[PalabraOCR], ancho=1000, alto=1000) -> PaginaOCR:
    return PaginaOCR(numero=1, texto=texto, palabras=palabras, confianza_media=0.9, ancho=ancho, alto=alto)


def test_extraccion_regex():
    texto = "Total a pagar $ 45.320\nOtros datos"
    campo = CampoPlantillaDTO(
        nombre="total_pagar",
        etiqueta="Total a pagar",
        tipo_dato="monto",
        regla=ReglaCampo(metodo="regex", regex=r"Total a pagar\s*\$?\s*([\d.,]+)"),
    )
    resultado = extraer_campo(campo, [_pagina(texto, [])])
    assert resultado.valido
    assert resultado.valor == 45320.0


def test_extraccion_ancla_misma_linea():
    texto = "N Cliente: 1234567-8\nFecha: 01/01/2026"
    campo = CampoPlantillaDTO(
        nombre="numero_cliente",
        etiqueta="N Cliente",
        tipo_dato="texto",
        regla=ReglaCampo(metodo="ancla", ancla="N Cliente", regex=r"[\d.-]+"),
    )
    resultado = extraer_campo(campo, [_pagina(texto, [])])
    assert resultado.valido
    assert resultado.valor == "1234567-8"


def test_extraccion_ancla_tolerante_a_errores_ocr():
    # simula un error típico de OCR: "N' Cliente" en vez de "N° Cliente"
    texto = "N' Cliente: 1234567-8"
    campo = CampoPlantillaDTO(
        nombre="numero_cliente",
        etiqueta="N Cliente",
        tipo_dato="texto",
        regla=ReglaCampo(metodo="ancla", ancla="N Cliente", regex=r"[\d.-]+"),
    )
    resultado = extraer_campo(campo, [_pagina(texto, [])])
    assert resultado.valor == "1234567-8"


def test_extraccion_zona():
    palabras = [
        _palabra("Av.", x=50, y=180, linea=0),
        _palabra("Siempre", x=100, y=180, linea=0),
        _palabra("Viva", x=170, y=180, linea=0),
        _palabra("742", x=220, y=180, linea=0),
        _palabra("OtroTexto", x=50, y=800, linea=5),
    ]
    campo = CampoPlantillaDTO(
        nombre="direccion",
        etiqueta="Dirección",
        tipo_dato="texto",
        regla=ReglaCampo(metodo="zona", pagina=1, x=0.0, y=0.1, ancho=0.5, alto=0.1),
    )
    resultado = extraer_campo(campo, [_pagina("", palabras, ancho=1000, alto=1000)])
    assert resultado.valido
    assert "Siempre" in resultado.valor


def test_campo_no_encontrado_no_valido():
    campo = CampoPlantillaDTO(
        nombre="inexistente",
        etiqueta="Inexistente",
        tipo_dato="texto",
        regla=ReglaCampo(metodo="regex", regex=r"NoExiste(\d+)"),
    )
    resultado = extraer_campo(campo, [_pagina("texto sin relación", [])])
    assert not resultado.valido
    assert resultado.valor is None


# ---------------------------------------------------------------- huecos de cobertura


def test_campo_obligatorio_ausente_tiene_confianza_cero():
    # un campo que no se encuentra en absoluto debe quedar con confianza 0, no "0.5 por defecto"
    campo = CampoPlantillaDTO(
        nombre="total_pagar",
        etiqueta="Total a pagar",
        tipo_dato="monto",
        obligatorio=True,
        regla=ReglaCampo(metodo="regex", regex=r"Total a pagar\s*\$?\s*([\d.,]+)"),
    )
    resultado = extraer_campo(campo, [_pagina("documento sin ese campo", [])])
    assert not resultado.valido
    assert resultado.valor is None
    assert resultado.confianza == 0.0


def test_extraccion_ancla_en_pagina_posterior_documento_multipagina():
    # el ancla no está en la página 1 sino en la página 2
    pagina1 = _pagina("Encabezado genérico\nSin datos relevantes aquí", [])
    pagina2 = _pagina("N Cliente: 9876543-2\nOtros datos", [])
    campo = CampoPlantillaDTO(
        nombre="numero_cliente",
        etiqueta="N Cliente",
        tipo_dato="texto",
        regla=ReglaCampo(metodo="ancla", ancla="N Cliente", regex=r"[\d.-]+"),
    )
    resultado = extraer_campo(campo, [pagina1, pagina2])
    assert resultado.valido
    assert resultado.valor == "9876543-2"


def test_extraccion_ancla_valor_en_linea_siguiente():
    # el ancla está sola en su línea y el valor viene en la línea de abajo
    texto = "Vencimiento:\n30/11/2026"
    campo = CampoPlantillaDTO(
        nombre="fecha_vencimiento",
        etiqueta="Vencimiento",
        tipo_dato="fecha",
        regla=ReglaCampo(metodo="ancla", ancla="Vencimiento"),
    )
    resultado = extraer_campo(campo, [_pagina(texto, [])])
    assert resultado.valido
    assert resultado.valor == "2026-11-30"


def test_extraccion_zona_sin_palabras_en_el_recorte():
    # zona definida pero sin ninguna palabra OCR dentro del rectángulo (ej. campo ilegible/en blanco)
    palabras = [_palabra("OtroTexto", x=50, y=800, linea=5)]
    campo = CampoPlantillaDTO(
        nombre="direccion",
        etiqueta="Dirección",
        tipo_dato="texto",
        regla=ReglaCampo(metodo="zona", pagina=1, x=0.0, y=0.1, ancho=0.3, alto=0.1),
    )
    resultado = extraer_campo(campo, [_pagina("", palabras, ancho=1000, alto=1000)])
    assert not resultado.valido
    assert resultado.valor is None


def test_extraccion_zona_pagina_inexistente_en_documento_multipagina():
    # la regla pide la página 2 pero el documento solo tiene 1 página
    campo = CampoPlantillaDTO(
        nombre="direccion",
        etiqueta="Dirección",
        tipo_dato="texto",
        regla=ReglaCampo(metodo="zona", pagina=2, x=0.0, y=0.0, ancho=1.0, alto=1.0),
    )
    resultado = extraer_campo(campo, [_pagina("", [], ancho=1000, alto=1000)])
    assert not resultado.valido
    assert resultado.valor is None


def test_extraccion_regex_monto_sin_decimales_formato_distinto():
    # formato de monto sin separador de miles ni símbolo de moneda
    texto = "Total a pagar 9500\nFin del documento"
    campo = CampoPlantillaDTO(
        nombre="total_pagar",
        etiqueta="Total a pagar",
        tipo_dato="monto",
        regla=ReglaCampo(metodo="regex", regex=r"Total a pagar\s*\$?\s*([\d.,]+)"),
    )
    resultado = extraer_campo(campo, [_pagina(texto, [])])
    assert resultado.valido
    assert resultado.valor == 9500.0


def test_ancla_no_toma_etiquetas_compuestas_de_otro_campo():
    """'Nombres' aparece en 'APELLIDOS Y NOMBRES DEL PADRE': debe usar la etiqueta propia del titular."""
    texto = (
        "APELLIDOS Y NOMBRES DEL PADRE\nPEREZ PEREZ ANGEL\nAPELLIDOS Y NOMBRES DE LA MADRE\nGOMEZ GOMEZ MARIA\n"
        "NOMBRES\nJUAN CARLOS"
    )
    pagina = PaginaOCR(numero=1, texto=texto, confianza_media=0.9, ancho=100, alto=100)

    def campo(ancla):
        return CampoPlantillaDTO(
            nombre="x", etiqueta="x", tipo_dato="texto", obligatorio=True, regla=ReglaCampo(metodo="ancla", ancla=ancla)
        )

    assert extraer_campo(campo("Nombres"), [pagina]).valor == "JUAN CARLOS"
    # sin etiqueta propia de "Apellidos": mejor vacío (con advertencia) que el valor del padre
    r = extraer_campo(campo("Apellidos"), [pagina])
    assert r.valor is None and r.confianza == 0.0


def _campo_ancla(nombre, ancla):
    return CampoPlantillaDTO(
        nombre=nombre, etiqueta=nombre, tipo_dato="texto", obligatorio=True, regla=ReglaCampo(metodo="ancla", ancla=ancla)
    )


def test_conector_pegado_por_el_motor_ocr_no_rompe_el_filtro_de_etiqueta_compuesta():
    """docTR tokeniza distinto: 'YNOMBRES' sin espacio. Debe seguir descartándose como etiqueta del padre."""
    from app.pipeline.extractor import extraer_campos

    texto = "APELLIDOS YNOMBRES DEL PADRE\nPEREZ PEREZ ANGEL\nAPELLIDOSY NOMBRES DE LA MADRE\nGOMEZ MARIA\nNOMBRES\nJUAN CARLOS"
    pagina = PaginaOCR(numero=1, texto=texto, confianza_media=0.9, ancho=100, alto=100)
    campos = [_campo_ancla("nombres", "Nombres"), _campo_ancla("apellidos", "Apellidos")]
    r = {c.nombre: c for c in extraer_campos(campos, [pagina])}
    assert r["nombres"].valor == "JUAN CARLOS"
    assert r["apellidos"].valor is None  # nunca el del padre/madre


def test_etiqueta_con_otra_ancla_de_la_plantilla_en_la_misma_linea():
    from app.pipeline.extractor import extraer_campos

    pagina = PaginaOCR(numero=1, texto="APELLIDOS Y/O NOMBRES COMPLETOS\nFULANO\nNOMBRES\nJUAN", confianza_media=0.9, ancho=1, alto=1)
    campos = [_campo_ancla("nombres", "Nombres"), _campo_ancla("apellidos", "Apellidos")]
    r = {c.nombre: c for c in extraer_campos(campos, [pagina])}
    assert r["nombres"].valor == "JUAN"


def test_valor_legitimo_con_palabra_padre_no_se_descarta():
    pagina = PaginaOCR(numero=1, texto="Direccion Av. Padre Hurtado 123", confianza_media=0.9, ancho=1, alto=1)
    assert extraer_campo(_campo_ancla("direccion", "Direccion"), [pagina]).valor == "Av. Padre Hurtado 123"
