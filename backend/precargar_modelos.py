"""Descarga los modelos OCR durante el build de la imagen (no en runtime).

Deja PaddleOCR (PP-OCRv5 latino) y docTR/OnnxTR en sus carpetas de caché (/root/.paddleocr y
/root/.cache/onnxtr), de modo que la imagen funcione sin internet (docs/01 §3: procesamiento local).
Usa los mismos parámetros que app/pipeline/ocr.py; si cambian allá, cambiarlos aquí.
"""
import numpy as np

blanco = np.full((200, 600, 3), 255, dtype=np.uint8)

from paddleocr import PaddleOCR  # noqa: E402

PaddleOCR(use_angle_cls=True, lang="latin", show_log=False).ocr(blanco, cls=True)
print("PaddleOCR: modelos listos")

from onnxtr.models import ocr_predictor  # noqa: E402

ocr_predictor(det_arch="fast_base", reco_arch="vitstr_base")([blanco])
print("docTR/OnnxTR: modelos listos")
