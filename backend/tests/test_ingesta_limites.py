"""Límites de la ingesta contra archivos pequeños en bytes pero enormes al decodificar (bomba de píxeles)."""
import io
import time

import numpy as np
import pytest
from PIL import Image

from app.pipeline.ingesta import ErrorIngesta, ingerir


def _png(ancho: int, alto: int) -> bytes:
    buf = io.BytesIO()
    Image.fromarray(np.full((alto, ancho), 255, dtype=np.uint8)).save(buf, format="PNG", compress_level=9)
    return buf.getvalue()


def test_bomba_de_pixeles_se_rechaza_sin_decodificar():
    """El caso de QA: un PNG de pocos KB que son 9000x9000 px (81 MP) tardaba ~49 s en procesarse."""
    datos = _png(9000, 9000)
    assert len(datos) < 500 * 1024  # pasa de sobra cualquier límite de tamaño en bytes
    t0 = time.perf_counter()
    with pytest.raises(ErrorIngesta, match="demasiado grande"):
        ingerir("bomba.png", datos)
    assert time.perf_counter() - t0 < 2  # se decide leyendo solo la cabecera


def test_imagen_grande_pero_legitima_se_reduce_no_se_rechaza():
    """Una foto de celular de 24 MP es válida: se acepta y se reduce al tamaño de procesado (<= 20 MP)."""
    doc = ingerir("foto.png", _png(6000, 4000))
    alto, ancho = doc.imagenes[0].shape[:2]
    assert ancho * alto <= 20_000_000 and abs(ancho / alto - 1.5) < 0.01  # misma proporción


def test_imagen_normal_no_se_toca():
    doc = ingerir("a4.png", _png(2480, 3508))  # A4 a 300 DPI
    assert doc.imagenes[0].shape[:2] == (3508, 2480)


def test_limites_configurables():
    with pytest.raises(ErrorIngesta, match="demasiado grande"):
        ingerir("a.png", _png(3000, 2000), max_megapixeles=5)
    doc = ingerir("a.png", _png(3000, 2000), megapixeles_procesado=2)
    alto, ancho = doc.imagenes[0].shape[:2]
    assert ancho * alto <= 2_000_000


def test_tiff_con_demasiados_fotogramas_se_rechaza():
    base = Image.fromarray(np.full((20, 20), 255, dtype=np.uint8))
    buf = io.BytesIO()
    base.save(buf, format="TIFF", save_all=True, append_images=[base] * 39)  # 40 páginas
    with pytest.raises(ErrorIngesta, match="40 páginas"):
        ingerir("multi.tiff", buf.getvalue())
    assert len(ingerir("multi.tiff", buf.getvalue(), max_paginas=40).imagenes) == 40


def _pdf(ancho_pt: int, alto_pt: int, paginas: int = 1) -> bytes:
    """PDF mínimo válido, sin texto, con páginas de `ancho_pt` x `alto_pt` puntos."""
    objs = ["<< /Type /Catalog /Pages 2 0 R >>"]
    kids = " ".join(f"{3 + i} 0 R" for i in range(paginas))
    objs.append(f"<< /Type /Pages /Kids [{kids}] /Count {paginas} >>")
    for _ in range(paginas):
        objs.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {ancho_pt} {alto_pt}] >>")
    out = b"%PDF-1.4\n"
    offsets = []
    for i, o in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n{o}\nendobj\n".encode()
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()
    return out


def test_pdf_con_pagina_gigante_se_renderiza_a_resolucion_acotada():
    """Una MediaBox enorme no debe reservar gigas: se baja la resolución para no pasar del tamaño de procesado."""
    t0 = time.perf_counter()
    doc = ingerir("gigante.pdf", _pdf(20000, 20000))  # 20000 pt = 278 pulgadas por lado; a 300 DPI serían 6 GP
    alto, ancho = doc.imagenes[0].shape[:2]
    assert ancho * alto <= 21_000_000
    assert time.perf_counter() - t0 < 10


def test_pdf_con_demasiadas_paginas_se_rechaza():
    with pytest.raises(ErrorIngesta, match="35 páginas"):
        ingerir("largo.pdf", _pdf(200, 200, paginas=35))


def test_archivos_corruptos_siguen_dando_error_de_ingesta():
    with pytest.raises(ErrorIngesta):
        ingerir("roto.png", b"\x89PNG\r\n\x1a\n" + b"0" * 50)
    with pytest.raises(ErrorIngesta):
        ingerir("vacio.png", b"")
