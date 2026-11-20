from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..config import Settings, get_settings
from .dependencias import get_db

router = APIRouter(tags=["sistema"])


@router.get("/salud")
def salud(request: Request, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)) -> dict:
    estado_bd = "ok"
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:  # noqa: BLE001
        estado_bd = f"error: {e}"

    estado_tesseract = "ok"
    try:
        import pytesseract

        pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD
        pytesseract.get_tesseract_version()
    except Exception as e:  # noqa: BLE001
        estado_tesseract = f"error: {e}"

    estado_paddle = "no_verificado"
    # find_spec no importa el paquete: importar paddleocr tarda segundos y bloquearía el healthcheck.
    from importlib.util import find_spec

    estado_paddle = "instalado" if find_spec("paddleocr") else "no_instalado"

    return {
        "api": "ok",
        "version": request.app.version,
        "base_datos": estado_bd,
        "tesseract": estado_tesseract,
        "paddleocr": estado_paddle,
        "motor_ocr_configurado": settings.OCR_MOTOR,
    }
