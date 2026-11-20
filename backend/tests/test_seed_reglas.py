"""Valida las reglas de campo de db/seed.sql contra el texto real que lee el OCR."""
import json
import re
from pathlib import Path

from app.dominio.modelos import CampoPlantillaDTO, PaginaOCR, ReglaCampo
from app.pipeline.extractor import extraer_campos

SEED = (Path(__file__).resolve().parents[2] / "db" / "seed.sql").read_text(encoding="utf-8")

TEXTO_PLANILLA = (
    "Planilla de servicio electrico\nN Cliente: 1234567-8\nDireccion: Av. Siempre Viva 742\n"
    "Periodo: Octubre 2026\nConsumo: 145 kWh\nTotal a pagar $ 45.320\nVencimiento 30/11/2026"
)


def _campos(codigo: str) -> list[CampoPlantillaDTO]:
    ini = SEED.index(f"WHERE Codigo = '{codigo}'")
    ini = SEED.index("INSERT INTO dbo.CampoPlantilla", ini)
    fin = SEED.index("UPDATE dbo.Plantilla SET VersionActualId", ini)
    campos = []
    patron = re.compile(r"\(@VersionId, '(\w+)', '[^']*', '(\w+)', \d, '\w+',\s*N'(\{.*?\})', \d+\)", re.S)
    for nombre, tipo, regla in patron.findall(SEED[ini:fin]):
        campos.append(
            CampoPlantillaDTO(nombre=nombre, etiqueta=nombre, tipo_dato=tipo, regla=ReglaCampo(**json.loads(regla)))
        )
    return campos


def test_reglas_seed_planilla_sobre_texto_real():
    pagina = PaginaOCR(numero=1, texto=TEXTO_PLANILLA, confianza_media=0.95, ancho=1000, alto=700)
    r = {c.nombre: c for c in extraer_campos(_campos("planilla_servicio"), [pagina])}
    assert r["numero_cliente"].valor == "1234567-8"
    assert r["direccion"].valor == "Av. Siempre Viva 742"
    assert r["periodo"].valor == "Octubre 2026"
    assert r["consumo"].valor == 145
    assert r["total_pagar"].valor == 45320
    assert r["fecha_vencimiento"].valor == "2026-11-30"


# Disposición real de una cédula ecuatoriana leída por OCR (etiquetas y valores desordenados, con
# ruido), pero con datos inventados.
TEXTO_CEDULA_EC = """REPUBLICA DEL ECUADOR
CEDULA D
IDENTIDAD E
APELLIDOS
PEREZ
NOMBRES
JUAN.CARLO5
NACIONALIOAD
UGAR Y FECHA DE EMISION
 ECUATORiANA
SEXO 1I
. QUITO 12 RAY 2024
FECHA DE NACIMIENTO
HOMBRE,
03 NOV d1990
 Na. DOCUMEnTO
LUGAR DE NACIMIENTO
#<ecu#########<<<<<.##########
 123456789*
chInsoraZo.gUANo
FECHA DE VENCINIENTO -
xxxxxxxmxxxxxxxe cu<sI<<<<<<<<x
LA MATRIZ. j
12 MAY 2034
CERTIFICADO DE VOTACION
cc N: 0912345678
JUNTA No.1234 MASCULINO"""


def test_reglas_seed_cedula_ecuatoriana_desordenada():
    pagina = PaginaOCR(numero=1, texto=TEXTO_CEDULA_EC, confianza_media=0.9, ancho=1000, alto=700)
    r = {c.nombre: c for c in extraer_campos(_campos("cedula_identidad"), [pagina])}
    assert r["numero_documento"].valor == "0912345678"
    assert r["fecha_nacimiento"].valor == "1990-11-03"
    assert r["fecha_vencimiento"].valor == "2034-05-12"
    assert r["sexo"].valor == "HOMBRE"


def test_validar_fecha_mes_abreviado_con_ruido():
    from app.pipeline.validadores import validar_fecha

    assert validar_fecha("03 NOV d1990") == ("1990-11-03", True)
    assert validar_fecha("12 RAY 2024") == ("2024-05-12", True)
    assert validar_fecha("5 de noviembre de 2026") == ("2026-11-05", True)
    assert validar_fecha("30/11/2026") == ("2026-11-30", True)
    assert validar_fecha("12 XYZ 2024")[1] is False


def test_nombres_y_apellidos_no_toman_encabezados_del_padre_o_madre():
    texto = (
        " APELLIDOS Y NOMBRES DEL PADR\nTIPO SANGRE\n PEREZ PEREZ ANGEL\n"
        " APELLIDOS Y NOMBRES DE LA MADrE\n GOMEZ GOMEZ MARIA\nPEREZ\nNOMBRES\nJUAN CARLOS\n"
        "NACIONALIOAD\nUGAR Y FECHA DE EMISION\n ECUATORiANA"
    )
    pagina = PaginaOCR(numero=1, texto=texto, confianza_media=0.9, ancho=1000, alto=700)
    r = {c.nombre: c for c in extraer_campos(_campos("cedula_identidad"), [pagina])}
    assert r["nombres"].valor == "JUAN CARLOS"
    assert r["apellidos"].valor is None  # sin etiqueta propia: vacío (con advertencia), no el valor del padre
    assert r["nacionalidad"].valor == "ECUATORiANA"


def test_fecha_con_anio_de_tres_digitos_se_marca_invalida_sin_adivinar():
    texto = "FECHA DE NACIMIENTO\nHOMBRE,\n03 NOV d990"
    pagina = PaginaOCR(numero=1, texto=texto, confianza_media=0.9, ancho=1000, alto=700)
    r = {c.nombre: c for c in extraer_campos(_campos("cedula_identidad"), [pagina])}
    assert r["fecha_nacimiento"].valor_texto == "03 NOV d990" and not r["fecha_nacimiento"].valido


def test_migraciones_coinciden_con_el_seed_y_son_ascii():
    """El estado final tras aplicar 002 y 003 debe ser lo que trae seed.sql, y los literales JSON de
    las reglas deben ser ASCII puro (no depender de la codificación con que sqlcmd lea el archivo)."""
    base = Path(__file__).resolve().parents[2] / "db"
    finales: dict[tuple[str, str], str] = {}
    patrones = {
        "migracion_002_reglas_campos.sql": r"\('([a-z_]+)', '([a-z_]+)', '\w+', '\w+', N'\{.*?\}', N'(\{.*?\})'\)",
        "migracion_003_reglas_cedula_ecuador.sql": r"\('([a-z_]+)', '([a-z_]+)', '\w+', N'(\{.*?\})'\)",
    }
    for nombre, patron in patrones.items():
        sql = (base / nombre).read_text(encoding="utf-8")
        filas = re.findall(patron, sql)
        assert filas, nombre
        for literal in re.findall(r"N'\{.*?\}'", sql):
            assert literal.isascii(), f"{nombre}: literal con caracteres no ASCII: {literal[:60]}"
        for codigo, campo, nuevo in filas:
            finales[(codigo, campo)] = nuevo  # la migración posterior reemplaza a la anterior
    for (codigo, campo), nuevo in finales.items():
        assert nuevo in SEED, f"{codigo}.{campo}: la regla final de las migraciones no está en seed.sql: {nuevo[:80]}"
