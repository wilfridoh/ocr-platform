from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..dominio.modelos import SugerenciaPlantilla
from ..persistencia import modelos as m
from ..pipeline.posiciones import leer_palabras
from ..pipeline.sugeridor import sugerir_campos
from ..pipeline.sugeridor_ejemplos import MAX_EJEMPLOS, Ejemplo, sugerir_palabras_clave_ejemplos, sugerir_zonas_etiquetas

MAX_CORPUS = 300  # documentos de otros tipos con que se compara (los más recientes)


class DocumentoSinResultado(ValueError):
    pass


class DemasiadosEjemplos(ValueError):
    pass


def sugerir_plantilla(db: Session, documento_ids: str | list[str]) -> SugerenciaPlantilla:
    """Sugiere palabras clave, campos y etiquetas fijas a partir de 1 a 3 documentos de ejemplo del MISMO tipo
    (docs/13 §5). Con 2 o más, lo que se repite en todos es palabra clave y los datos de cada titular quedan fuera;
    con uno, las sugerencias llegan con `revisar`."""
    ids = [documento_ids] if isinstance(documento_ids, str) else list(dict.fromkeys(documento_ids))
    if not ids:
        raise DocumentoSinResultado("Indica al menos un documento de ejemplo")
    if len(ids) > MAX_EJEMPLOS:
        raise DemasiadosEjemplos(f"Como máximo {MAX_EJEMPLOS} documentos de ejemplo")
    resultados = []
    for doc_id in ids:
        r = db.execute(select(m.Resultado).where(m.Resultado.DocumentoId == doc_id)).scalars().first()
        if not r or not r.TextoCompleto:
            raise DocumentoSinResultado(f"El documento {doc_id} no tiene texto OCR disponible todavía")
        resultados.append(r)
    ejemplos = [Ejemplo(r.TextoCompleto, leer_palabras(r.PalabrasJson).get(1, [])) for r in resultados]

    # corpus: documentos de OTROS tipos (si un ejemplo ya se clasificó como algo, sus hermanos no cuentan como "otros")
    tipos = {r.TipoDetectado for r in resultados if r.TipoDetectado and r.TipoDetectado != "desconocido"}
    q = select(m.Resultado.TextoCompleto).where(m.Resultado.DocumentoId.not_in(ids))
    if tipos:
        q = q.where(m.Resultado.TipoDetectado.not_in(tipos))
    corpus = [t for t in db.execute(q.order_by(m.Resultado.CreadoEn.desc()).limit(MAX_CORPUS)).scalars().all() if t]

    palabras_clave = sugerir_palabras_clave_ejemplos(ejemplos, corpus)
    zonas = sugerir_zonas_etiquetas(ejemplos[0], [p["texto"] for p in palabras_clave])
    return SugerenciaPlantilla(
        documento_id=ids[0],
        documento_ids=ids,
        palabras_clave=palabras_clave,
        campos=sugerir_campos(ejemplos[0].texto),
        texto=ejemplos[0].texto,
        zonas_sugeridas=zonas,
    )
