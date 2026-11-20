"""GET /documentos/{id}/resultado: devuelve el JSON del contrato (docs/01 §5)."""
from __future__ import annotations

import json

from sqlalchemy.orm import Session

from ..persistencia import modelos as m
from ..persistencia import repositorios as repo


class DocumentoNoExiste(ValueError):
    pass


def obtener_resultado(db: Session, documento_id: str) -> dict:
    documento = repo.obtener_documento(db, documento_id)
    if not documento:
        raise DocumentoNoExiste(f"El documento {documento_id} no existe")

    resultado = repo.obtener_resultado(db, documento_id)
    if not resultado:
        return {
            "documento_id": documento.DocumentoId,
            "archivo": documento.NombreArchivo,
            "paginas": documento.Paginas,
            "estado": documento.Estado,
            "clasificacion": {"tipo": "desconocido", "plantilla_id": None, "confianza": 0.0, "alternativas": []},
            "campos": {},
            "palabras_clave": [],
            "texto_completo": "",
            "confianza_global": 0.0,
            "advertencias": [],
            "tiempos_ms": {},
        }

    # plantilla y versión con que se leyó el documento (el frontend carga sus campos/etiquetas con esto)
    version = db.get(m.PlantillaVersion, resultado.PlantillaVersionId) if resultado.PlantillaVersionId else None

    campos = {}
    for c in resultado.campos:
        valor = json.loads(c.ValorNormalizadoJson) if c.ValorNormalizadoJson else c.ValorTexto
        campos[c.Nombre] = {"valor": valor, "confianza": float(c.Confianza), "pagina": c.Pagina, "motor": c.Motor}

    return {
        "documento_id": documento.DocumentoId,
        "archivo": documento.NombreArchivo,
        "paginas": documento.Paginas,
        "estado": documento.Estado,
        "clasificacion": {
            "tipo": resultado.TipoDetectado,
            "plantilla_id": version.PlantillaId if version else None,
            "plantilla_version": version.Numero if version else None,
            "confianza": float(resultado.ConfianzaClasificacion),
            "alternativas": json.loads(resultado.AlternativasJson) if resultado.AlternativasJson else [],
        },
        "campos": campos,
        "palabras_clave": json.loads(resultado.PalabrasClaveJson) if resultado.PalabrasClaveJson else [],
        "texto_completo": resultado.TextoCompleto or "",
        "confianza_global": float(resultado.ConfianzaGlobal),
        "advertencias": json.loads(resultado.AdvertenciasJson) if resultado.AdvertenciasJson else [],
        "tiempos_ms": json.loads(resultado.TiemposJson) if resultado.TiemposJson else {},
    }
