"""Ingesta: validar archivo, calcular hash, PDF -> imágenes o texto nativo."""
from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass, field

import numpy as np
from PIL import Image

from ..dominio.modelos import PaginaOCR, PalabraOCR

EXTENSIONES = {"pdf", "jpg", "jpeg", "png", "tif", "tiff"}
MIME_POR_EXT = {
    "pdf": "application/pdf",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "tif": "image/tiff",
    "tiff": "image/tiff",
}


# Valores por defecto (la configuración los sobrescribe: OCR_MAX_MEGAPIXELES, OCR_MEGAPIXELES_PROCESADO, OCR_MAX_PAGINAS)
MAX_MEGAPIXELES = 50
MEGAPIXELES_PROCESADO = 20
MAX_PAGINAS = 30


class ErrorIngesta(ValueError):
    """Formato no soportado, archivo corrupto o demasiado grande (HTTP 400)."""


@dataclass
class DocumentoIngresado:
    imagenes: list[np.ndarray] = field(default_factory=list)  # BGR por página (vacío si PDF nativo)
    paginas_nativas: list[PaginaOCR] = field(default_factory=list)  # texto nativo de PDF
    imagenes_procesadas: list[np.ndarray] = field(default_factory=list)  # tras preprocesado (para segunda opinión)
    es_pdf_nativo: bool = False
    hash_sha256: str = ""
    tipo_mime: str = ""
    extension: str = ""

    @property
    def paginas(self) -> int:
        return len(self.paginas_nativas) if self.es_pdf_nativo else len(self.imagenes)


def extension_de(nombre: str) -> str:
    return nombre.rsplit(".", 1)[-1].lower() if "." in nombre else ""


def sha256(datos: bytes) -> str:
    return hashlib.sha256(datos).hexdigest()


def validar(nombre: str, datos: bytes, max_mb: int = 20) -> str:
    ext = extension_de(nombre)
    if ext not in EXTENSIONES:
        raise ErrorIngesta(f"Formato no soportado: .{ext or '?'} (permitidos: {', '.join(sorted(EXTENSIONES))})")
    if not datos:
        raise ErrorIngesta("Archivo vacío")
    if len(datos) > max_mb * 1024 * 1024:
        raise ErrorIngesta(f"El archivo supera el límite de {max_mb} MB")
    return ext


def _pil_a_bgr(img: Image.Image) -> np.ndarray:
    rgb = np.array(img.convert("RGB"))
    return rgb[:, :, ::-1].copy()


def _reducir_si_excede(img: Image.Image, max_px: int) -> Image.Image:
    """Reduce (manteniendo proporción) una imagen con más de `max_px` píxeles."""
    ancho, alto = img.size
    if ancho * alto <= max_px:
        return img
    factor = (max_px / (ancho * alto)) ** 0.5
    return img.resize((max(1, int(ancho * factor)), max(1, int(alto * factor))), Image.Resampling.LANCZOS)


def _cargar_imagen(
    datos: bytes,
    max_megapixeles: int = MAX_MEGAPIXELES,
    megapixeles_procesado: int = MEGAPIXELES_PROCESADO,
    max_paginas: int = MAX_PAGINAS,
) -> list[np.ndarray]:
    max_px = max_megapixeles * 1_000_000
    try:
        img = Image.open(io.BytesIO(datos))  # solo lee la cabecera: el tamaño se conoce SIN decodificar los píxeles
        n = getattr(img, "n_frames", 1)
        if n > max_paginas:
            raise ErrorIngesta(f"El archivo tiene {n} páginas; el máximo es {max_paginas}")
        paginas = []
        for i in range(n):
            img.seek(i)
            ancho, alto = img.size
            if ancho * alto > max_px:
                raise ErrorIngesta(
                    f"Imagen demasiado grande ({ancho}x{alto} px = {ancho * alto / 1e6:.0f} MP); el máximo es {max_megapixeles} MP"
                )
            rgb = _reducir_si_excede(img.convert("RGB"), megapixeles_procesado * 1_000_000)
            paginas.append(_pil_a_bgr(rgb))
        return paginas
    except ErrorIngesta:
        raise
    except Exception as e:  # noqa: BLE001
        raise ErrorIngesta(f"Imagen corrupta o ilegible: {e}") from e


def _texto_nativo_pdf(pdf) -> list[PaginaOCR] | None:
    """Devuelve páginas con texto nativo si el PDF lo contiene (suficiente texto), si no None."""
    paginas: list[PaginaOCR] = []
    total_chars = 0
    for i in range(len(pdf)):
        pagina = pdf[i]
        ancho, alto = pagina.get_size()
        tp = pagina.get_textpage()
        texto = tp.get_text_range() or ""
        palabras: list[PalabraOCR] = []
        # Cajas por palabra aproximadas: recorrer rectángulos de texto
        try:
            n_rects = tp.count_rects()
            for r in range(n_rects):
                l, b, rr, t = tp.get_rect(r)
                frag = tp.get_text_bounded(l, b, rr, t) or ""
                for w in frag.split():
                    palabras.append(
                        PalabraOCR(
                            texto=w,
                            x=int(l),
                            y=int(alto - t),
                            ancho=int(rr - l),
                            alto=int(t - b),
                            confianza=0.99,
                            linea=r,
                            bloque=0,
                            pagina=i + 1,
                        )
                    )
        except Exception:  # noqa: BLE001
            pass
        total_chars += len(texto.strip())
        paginas.append(
            PaginaOCR(
                numero=i + 1,
                texto=texto,
                palabras=palabras,
                confianza_media=0.99 if texto.strip() else 0.0,
                ancho=int(ancho),
                alto=int(alto),
                pasos_preprocesado=["pdf_nativo"],
            )
        )
    # Umbral: al menos 20 caracteres por página en promedio
    if total_chars >= 20 * max(1, len(pdf)):
        return paginas
    return None


def _cargar_pdf(
    datos: bytes, dpi: int, megapixeles_procesado: int = MEGAPIXELES_PROCESADO, max_paginas: int = MAX_PAGINAS
) -> tuple[list[np.ndarray], list[PaginaOCR] | None]:
    import pypdfium2 as pdfium

    try:
        pdf = pdfium.PdfDocument(datos)
    except Exception as e:  # noqa: BLE001
        raise ErrorIngesta(f"PDF corrupto o ilegible: {e}") from e
    if len(pdf) == 0:
        raise ErrorIngesta("PDF sin páginas")
    if len(pdf) > max_paginas:
        raise ErrorIngesta(f"El PDF tiene {len(pdf)} páginas; el máximo es {max_paginas}")
    nativas = _texto_nativo_pdf(pdf)
    if nativas:
        return [], nativas
    escala = dpi / 72.0
    imagenes = []
    max_px = megapixeles_procesado * 1_000_000
    for i in range(len(pdf)):
        ancho_pt, alto_pt = pdf[i].get_size()
        esc = escala
        if ancho_pt * esc * alto_pt * esc > max_px:  # página enorme (p. ej. MediaBox gigante): bajar la resolución, no la memoria
            esc = (max_px / max(1.0, ancho_pt * alto_pt)) ** 0.5
        bitmap = pdf[i].render(scale=esc)
        imagenes.append(_pil_a_bgr(bitmap.to_pil()))
    return imagenes, None


def ingerir(
    nombre: str,
    datos: bytes,
    max_mb: int = 20,
    dpi: int = 300,
    max_megapixeles: int = MAX_MEGAPIXELES,
    megapixeles_procesado: int = MEGAPIXELES_PROCESADO,
    max_paginas: int = MAX_PAGINAS,
) -> DocumentoIngresado:
    ext = validar(nombre, datos, max_mb)
    doc = DocumentoIngresado(hash_sha256=sha256(datos), tipo_mime=MIME_POR_EXT[ext], extension=ext)
    if ext == "pdf":
        imagenes, nativas = _cargar_pdf(datos, dpi, megapixeles_procesado, max_paginas)
        if nativas:
            doc.es_pdf_nativo = True
            doc.paginas_nativas = nativas
        else:
            doc.imagenes = imagenes
    else:
        doc.imagenes = _cargar_imagen(datos, max_megapixeles, megapixeles_procesado, max_paginas)
    return doc


def rasterizar(nombre: str, datos: bytes, dpi: int = 150) -> list[Image.Image]:
    """Rasteriza siempre (para /documentos/{id}/paginas/{n}), incluso PDFs nativos."""
    ext = extension_de(nombre)
    if ext == "pdf":
        import pypdfium2 as pdfium

        pdf = pdfium.PdfDocument(datos)
        return [pdf[i].render(scale=dpi / 72.0).to_pil() for i in range(len(pdf))]
    img = Image.open(io.BytesIO(datos))
    out = []
    for i in range(getattr(img, "n_frames", 1)):
        img.seek(i)
        out.append(img.convert("RGB").copy())
    return out
