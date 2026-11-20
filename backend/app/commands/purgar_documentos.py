"""Retención y purga de documentos (datos personales): una sola política para TODO documento.

- `vencidos`: documentos recibidos hace más de `retencion_dias` (DOC_RETENCION_DIAS).
- `todos`: todo, sin esperar al plazo (limpieza manual de documentos de prueba; solo Administrador).

Qué se elimina de cada documento: su registro, su resultado (campos extraídos) y su log, y el archivo original.
Dos detalles que importan:
  * El almacén guarda por HASH: dos subidas idénticas comparten UN archivo. Solo se borra el archivo cuando ya
    ningún documento que se conserve lo usa.
  * Una plantilla puede tener un documento de ejemplo (PlantillaVersion.DocumentoEjemploId): al purgarlo, la
    referencia pasa a NULL (la plantilla y sus reglas se conservan).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal

from sqlalchemy import and_, delete, not_, select, update
from sqlalchemy.orm import Session

from ..almacen import AlmacenDisco
from ..persistencia import modelos as m

logger = logging.getLogger(__name__)

Alcance = Literal["vencidos", "todos"]
_LOTE = 500  # SQL Server admite ~2100 parámetros por consulta


class PurgaNoDisponible(ValueError):
    """Alcance 'vencidos' con la retención desactivada (DOC_RETENCION_DIAS = 0)."""


@dataclass
class ResumenPurga:
    documentos: int = 0
    archivos: int = 0  # archivos que se liberan (los compartidos con documentos que se conservan no cuentan)
    bytes: int = 0

    def a_dict(self) -> dict[str, int]:
        return {"documentos": self.documentos, "archivos": self.archivos, "bytes": self.bytes}


def _limite(retencion_dias: int, ahora: datetime | None = None) -> datetime:
    # RecibidoEn se guarda como UTC sin zona
    return ((ahora or datetime.now(timezone.utc)) - timedelta(days=retencion_dias)).replace(tzinfo=None)


def _limite_horas(horas: int, ahora: datetime | None = None) -> datetime:
    return ((ahora or datetime.now(timezone.utc)) - timedelta(hours=horas)).replace(tzinfo=None)


def _condicion(alcance: Alcance, retencion_dias: int, ahora: datetime | None):
    if alcance == "todos":
        # Todo, EXCEPTO lo que se está recibiendo o procesando ahora mismo (última hora): purgarlo a mitad de camino
        # rompería esa subida. Lo que quedó «atascado» más de una hora sí entra.
        en_curso = and_(m.Documento.Estado.in_(("RECIBIDO", "PROCESANDO")), m.Documento.RecibidoEn >= _limite_horas(1, ahora))
        return not_(en_curso)
    if retencion_dias <= 0:
        raise PurgaNoDisponible("La retención automática está desactivada (DOC_RETENCION_DIAS = 0)")
    return m.Documento.RecibidoEn < _limite(retencion_dias, ahora)


def _seleccion(db: Session, alcance: Alcance, retencion_dias: int, ahora: datetime | None) -> list[tuple[str, str]]:
    cond = _condicion(alcance, retencion_dias, ahora)
    q = select(m.Documento.DocumentoId, m.Documento.RutaAlmacen)
    if cond is not None:
        q = q.where(cond)
    return [(i, r) for i, r in db.execute(q).all()]


def _rutas_que_se_conservan(db: Session, rutas: set[str], ids_purga: set[str]) -> set[str]:
    """De `rutas`, las que algún documento que NO se purga sigue usando."""
    conservadas: set[str] = set()
    lista = sorted(rutas)
    for i in range(0, len(lista), _LOTE):
        trozo = lista[i : i + _LOTE]
        q = select(m.Documento.RutaAlmacen, m.Documento.DocumentoId).where(m.Documento.RutaAlmacen.in_(trozo))
        for ruta, doc_id in db.execute(q).all():
            if doc_id not in ids_purga:
                conservadas.add(ruta)
    return conservadas


def vista_previa(
    db: Session, almacen: AlmacenDisco, alcance: Alcance, retencion_dias: int, ahora: datetime | None = None
) -> ResumenPurga:
    """Cuánto se eliminaría, sin borrar nada."""
    sel = _seleccion(db, alcance, retencion_dias, ahora)
    ids = {i for i, _ in sel}
    rutas = {r for _, r in sel}
    liberadas = rutas - _rutas_que_se_conservan(db, rutas, ids)
    return ResumenPurga(documentos=len(ids), archivos=len(liberadas), bytes=sum(almacen.tamano(r) for r in liberadas))


def purgar(
    db: Session, almacen: AlmacenDisco, alcance: Alcance, retencion_dias: int, ahora: datetime | None = None
) -> ResumenPurga:
    sel = _seleccion(db, alcance, retencion_dias, ahora)
    ids = [i for i, _ in sel]
    rutas = {r for _, r in sel}
    id_set = set(ids)

    # 1) registros de BD, por lotes (primero lo que depende del documento)
    for k in range(0, len(ids), _LOTE):
        lote = ids[k : k + _LOTE]
        resultados = select(m.Resultado.ResultadoId).where(m.Resultado.DocumentoId.in_(lote))
        db.execute(delete(m.CampoExtraido).where(m.CampoExtraido.ResultadoId.in_(resultados)), execution_options={"synchronize_session": False})
        db.execute(delete(m.Resultado).where(m.Resultado.DocumentoId.in_(lote)), execution_options={"synchronize_session": False})
        db.execute(delete(m.LogProcesamiento).where(m.LogProcesamiento.DocumentoId.in_(lote)), execution_options={"synchronize_session": False})
        db.execute(
            update(m.PlantillaVersion).where(m.PlantillaVersion.DocumentoEjemploId.in_(lote)).values(DocumentoEjemploId=None),
            execution_options={"synchronize_session": False},
        )
        db.execute(delete(m.Documento).where(m.Documento.DocumentoId.in_(lote)), execution_options={"synchronize_session": False})
        db.commit()

    # 2) archivos: solo los que ya ningún documento usa (se consulta DESPUÉS de confirmar la BD)
    liberadas = rutas - _rutas_que_se_conservan(db, rutas, set())
    resumen = ResumenPurga(documentos=len(id_set))
    for ruta in sorted(liberadas):
        tamano = almacen.tamano(ruta)
        try:
            if almacen.eliminar(ruta):
                resumen.archivos += 1
                resumen.bytes += tamano
        except OSError:
            logger.exception("No se pudo borrar el archivo %s (queda huérfano; no afecta a la BD)", ruta)
    logger.warning(
        "Purga de documentos (%s, retención %s días): %d documentos, %d archivos, %d bytes",
        alcance, retencion_dias, resumen.documentos, resumen.archivos, resumen.bytes,
    )
    return resumen
