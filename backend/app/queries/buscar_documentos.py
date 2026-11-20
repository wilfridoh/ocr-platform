from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from ..dominio.modelos import DocumentoDTO
from ..persistencia import repositorios as repo
from ..persistencia import modelos as m


def buscar_documentos(
    db: Session,
    tipo: str | None = None,
    estado: str | None = None,
    desde: datetime | None = None,
    hasta: datetime | None = None,
    pagina: int = 1,
    tamano: int = 20,
) -> tuple[list[DocumentoDTO], int]:
    documentos, total = repo.buscar_documentos(db, tipo, estado, desde, hasta, pagina, tamano)
    out = []
    for d in documentos:
        resultado = d.resultado
        out.append(
            DocumentoDTO(
                id=d.DocumentoId,
                nombre_archivo=d.NombreArchivo,
                tipo_mime=d.TipoMime,
                tamano_bytes=d.TamanoBytes,
                hash_sha256=d.HashSha256,
                paginas=d.Paginas,
                estado=d.Estado,
                plantilla_forzada_id=d.PlantillaForzadaId,
                mensaje_error=d.MensajeError,
                recibido_en=d.RecibidoEn,
                procesado_en=d.ProcesadoEn,
                tipo_detectado=resultado.TipoDetectado if resultado else None,
                confianza_global=float(resultado.ConfianzaGlobal) if resultado else None,
            )
        )
    return out, total
