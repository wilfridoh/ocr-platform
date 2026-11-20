"""GET /documentos/{id}/resultado -- separado de documentos.py por estructura (docs/02-backend.md §2)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..queries.obtener_resultado import DocumentoNoExiste, obtener_resultado
from .dependencias import get_db
from .seguridad import verificar_api_key

router = APIRouter(prefix="/documentos", tags=["resultados"], dependencies=[Depends(verificar_api_key)])


@router.get("/{documento_id}/resultado")
def resultado_de_documento(documento_id: str, db: Session = Depends(get_db)) -> dict:
    try:
        return obtener_resultado(db, documento_id)
    except DocumentoNoExiste as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
