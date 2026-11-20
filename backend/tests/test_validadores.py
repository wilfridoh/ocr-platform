from app.pipeline import validadores as v


def test_fecha_formato_dmy_barra():
    iso, ok = v.validar_fecha("30/11/2026")
    assert ok and iso == "2026-11-30"


def test_fecha_formato_dmy_guion_anio_corto():
    iso, ok = v.validar_fecha("05-03-26")
    assert ok and iso == "2026-03-05"


def test_fecha_en_texto():
    iso, ok = v.validar_fecha("12 de marzo de 2026")
    assert ok and iso == "2026-03-12"


def test_fecha_invalida():
    iso, ok = v.validar_fecha("no es una fecha")
    assert not ok and iso is None


def test_monto_separador_miles_punto():
    valor, ok = v.validar_monto("45.320")
    assert ok and valor == 45320.0


def test_monto_con_simbolo_pesos():
    valor, ok = v.validar_monto("$ 45.320")
    assert ok and valor == 45320.0


def test_monto_coma_decimal():
    valor, ok = v.validar_monto("1.234,56")
    assert ok and valor == 1234.56


def test_rut_valido():
    valor, ok = v.validar_rut("12345678-5")
    assert ok and valor == "12345678-5"


def test_rut_invalido_dv():
    _valor, ok = v.validar_rut("12345678-9")
    assert not ok


def test_rut_con_puntos():
    valor, ok = v.validar_rut("12.345.678-5")
    assert ok and valor == "12345678-5"


def test_cedula_generica():
    valor, ok = v.validar_cedula("1234567890")
    assert ok and valor == "1234567890"


def test_cedula_invalida_muy_corta():
    _valor, ok = v.validar_cedula("123")
    assert not ok


def test_email_valido():
    valor, ok = v.validar_email("contacto en Juan.Perez@Empresa.cl para dudas")
    assert ok and valor == "juan.perez@empresa.cl"


def test_telefono_valido():
    valor, ok = v.validar_telefono("+56 9 1234 5678")
    assert ok and valor == "56912345678"


def test_numero_simple():
    valor, ok = v.validar_numero("1234")
    assert ok and valor == 1234.0


# ---------------------------------------------------------------- huecos de cobertura


def test_fecha_iso_passthrough():
    # un documento con PDF nativo puede traer la fecha ya en ISO
    iso, ok = v.validar_fecha("2026-11-30")
    assert ok and iso == "2026-11-30"


def test_fecha_dia_invalido():
    # 31 de febrero no existe: el validador debe rechazar, no inventar una fecha
    iso, ok = v.validar_fecha("31/02/2026")
    assert not ok and iso is None


def test_fecha_mes_invalido():
    iso, ok = v.validar_fecha("15/13/2026")
    assert not ok and iso is None


def test_fecha_anio_corto_umbral_siglo():
    # regla documentada: <70 -> 2000+, >=70 -> 1900+
    iso_69, ok_69 = v.validar_fecha("01/01/69")
    iso_70, ok_70 = v.validar_fecha("01/01/70")
    assert ok_69 and iso_69 == "2069-01-01"
    assert ok_70 and iso_70 == "1970-01-01"


def test_fecha_vacia():
    iso, ok = v.validar_fecha("")
    assert not ok and iso is None


def test_monto_sin_decimales_ni_separador():
    valor, ok = v.validar_monto("320")
    assert ok and valor == 320.0


def test_monto_varios_puntos_miles():
    valor, ok = v.validar_monto("1.234.567")
    assert ok and valor == 1234567.0


def test_monto_ruido_sin_digitos():
    valor, ok = v.validar_monto("sin monto aquí")
    assert not ok and valor is None


def test_rut_con_letras_invalido():
    valor, ok = v.validar_rut("ABCDEFGH-5")
    assert not ok and valor is None


def test_rut_digito_verificador_k():
    # cuerpo "6" -> DV módulo 11 calculado es K (resto 10)
    valor, ok = v.validar_rut("6-K")
    assert ok and valor == "6-K"


def test_cedula_limite_inferior_valida():
    valor, ok = v.validar_cedula("123456")
    assert ok and valor == "123456"


def test_cedula_demasiado_larga_invalida():
    _valor, ok = v.validar_cedula("1234567890123")
    assert not ok


def test_email_invalido_sin_arroba():
    valor, ok = v.validar_email("esto no es un correo")
    assert not ok and valor is None


def test_telefono_invalido_muy_corto():
    valor, ok = v.validar_telefono("123")
    assert not ok and valor is None


def test_numero_ruido_no_numerico():
    valor, ok = v.validar_numero("abc")
    assert not ok and valor is None


def test_texto_vacio_no_valido():
    valor, ok = v.validar_texto("   ")
    assert not ok and valor is None


def test_texto_recorta_espacios():
    valor, ok = v.validar_texto("  Hola Mundo  ")
    assert ok and valor == "Hola Mundo"
