from __future__ import annotations

import io
import os
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

FUENTES_CANDIDATAS = [
    r"C:\Windows\Fonts\arial.ttf",
    r"C:\Windows\Fonts\calibri.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def _fuente(tamano: int = 32) -> ImageFont.FreeTypeFont:
    for ruta in FUENTES_CANDIDATAS:
        if os.path.exists(ruta):
            return ImageFont.truetype(ruta, tamano)
    return ImageFont.load_default()


def renderizar_texto(
    lineas: list[str], ancho: int = 1200, alto: int = 900, tamano_fuente: int = 32, margen: int = 60
) -> Image.Image:
    """Genera una imagen sintética con texto renderizado (para pruebas sin documentos reales)."""
    img = Image.new("RGB", (ancho, alto), color="white")
    draw = ImageDraw.Draw(img)
    fuente = _fuente(tamano_fuente)
    y = margen
    for linea in lineas:
        draw.text((margen, y), linea, fill="black", font=fuente)
        y += int(tamano_fuente * 1.6)
    return img


def imagen_a_bgr(img: Image.Image) -> np.ndarray:
    rgb = np.array(img.convert("RGB"))
    return rgb[:, :, ::-1].copy()


def imagen_a_bytes(img: Image.Image, formato: str = "PNG") -> bytes:
    buf = io.BytesIO()
    img.save(buf, format=formato)
    return buf.getvalue()


@pytest.fixture
def planilla_sintetica() -> Image.Image:
    """La 'planilla' de referencia del encargo: N° Cliente, Total a pagar, Vencimiento."""
    return renderizar_texto(
        [
            "Planilla de servicio eléctrico",
            "N° Cliente: 1234567-8",
            "Total a pagar $ 45.320",
            "Vencimiento 30/11/2026",
        ],
        ancho=1400,
        alto=500,
        tamano_fuente=36,
    )


@pytest.fixture(autouse=True, scope="session")
def _entorno_test():
    os.environ.setdefault("API_KEY", "dev")
    os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
    os.environ.setdefault("CREAR_TABLAS", "true")
    yield
