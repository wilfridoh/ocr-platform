"""Test end-to-end del pipeline SIN base de datos: genera una planilla sintética
con PIL, la pasa por ingesta->preprocesado->OCR->extracción y comprueba los
valores exigidos en el encargo: N° Cliente, Total a pagar, Vencimiento."""
from __future__ import annotations

import pytest

from app.config import get_settings
from app.dominio.modelos import CampoPlantillaDTO, ReglaCampo
from app.pipeline.extractor import extraer_campos
from app.pipeline.ingesta import sha256
from app.pipeline.orquestador import procesar_bytes
from tests.conftest import imagen_a_bytes


def _tesseract_disponible() -> bool:
    try:
        import pytesseract

        settings = get_settings()
        pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD
        pytesseract.get_tesseract_version()
        return True
    except Exception:  # noqa: BLE001
        return False


CAMPOS_PLANILLA = [
    CampoPlantillaDTO(
        nombre="numero_cliente",
        etiqueta="Número de cliente",
        tipo_dato="texto",
        obligatorio=True,
        regla=ReglaCampo(metodo="ancla", ancla="N Cliente", regex=r"[\d.-]+"),
    ),
    CampoPlantillaDTO(
        nombre="total_pagar",
        etiqueta="Total a pagar",
        tipo_dato="monto",
        obligatorio=True,
        regla=ReglaCampo(metodo="regex", regex=r"Total a pagar\s*\$?\s*([\d.,]+)"),
    ),
    CampoPlantillaDTO(
        nombre="fecha_vencimiento",
        etiqueta="Vencimiento",
        tipo_dato="fecha",
        obligatorio=True,
        regla=ReglaCampo(metodo="ancla", ancla="Vencimiento"),
    ),
]


@pytest.mark.skipif(not _tesseract_disponible(), reason="Tesseract no disponible en este entorno")
def test_pipeline_end_to_end_planilla_sintetica(planilla_sintetica):
    settings = get_settings()
    # Forzar tesseract: motor principal (paddle/doctr) puede no estar instalado en CI ligero.
    settings.OCR_MOTOR = "tesseract"

    datos = imagen_a_bytes(planilla_sintetica, "PNG")
    assert sha256(datos)  # hash calculable

    _doc, paginas, motor_usado, tiempos = procesar_bytes("planilla_luz.png", datos, settings)
    assert len(paginas) == 1
    assert motor_usado == "tesseract"
    assert "ocr" in tiempos

    texto_completo = paginas[0].texto
    assert "1234567" in texto_completo.replace(" ", "") or "1234567" in texto_completo

    campos = extraer_campos(CAMPOS_PLANILLA, paginas)
    por_nombre = {c.nombre: c for c in campos}

    assert por_nombre["numero_cliente"].valido
    assert por_nombre["numero_cliente"].valor.replace(" ", "") in ("1234567-8", "12345678")

    assert por_nombre["total_pagar"].valido
    assert por_nombre["total_pagar"].valor == 45320.0

    assert por_nombre["fecha_vencimiento"].valido
    assert por_nombre["fecha_vencimiento"].valor == "2026-11-30"
