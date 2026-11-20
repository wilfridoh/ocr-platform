from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..dominio.modelos import SugerenciaPlantilla
from ..pipeline.sugeridor import sugerir_campos, sugerir_palabras_clave
from ..persistencia import modelos as m


class DocumentoSinResultado(ValueError):
    pass


def sugerir_plantilla(db: Session, documento_id: str) -> SugerenciaPlantilla:
    resultado = db.execute(select(m.Resultado).where(m.Resultado.DocumentoId == documento_id)).scalars().first()
    if not resultado or not resultado.TextoCompleto:
        raise DocumentoSinResultado(f"El documento {documento_id} no tiene texto OCR disponible todavía")
    texto = resultado.TextoCompleto
    corpus = [
        r.TextoCompleto
        for r in db.execute(select(m.Resultado).where(m.Resultado.DocumentoId != documento_id)).scalars().all()
        if r.TextoCompleto
    ]
    palabras_clave = sugerir_palabras_clave(texto, corpus)
    campos = sugerir_campos(texto)
    return SugerenciaPlantilla(documento_id=documento_id, palabras_clave=palabras_clave, campos=campos, texto=texto)
