"""Comando: reprocesar un documento ya existente (releer su archivo del almacén)."""
from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import ObjectDeletedError, StaleDataError

from ..almacen import AlmacenDisco
from ..dominio.modelos import ResultadoDTO
from ..persistencia import modelos as m
from ..persistencia import repositorios as repo
from .procesar_documento import PlantillaForzadaNoExiste, _plantillas_candidatas  # noqa: F401
from . import procesar_documento as _pd


class DocumentoNoExiste(ValueError):
    pass


class PaginaFueraDeRango(ValueError):
    pass


def recortes_manuales_guardados(documento: m.Documento) -> dict[int, dict]:
    """Recortes que marcó una persona en un procesamiento anterior: reprocesar los conserva (no vuelve al automático)."""
    from ..pipeline.posiciones import leer_recorte

    resultado = documento.resultado
    guardados = leer_recorte(resultado.RecorteJson if resultado else None)
    return {
        n: {"esquinas": r.get("esquinas"), "orientacion": r.get("orientacion") or 0}
        for n, r in guardados.items()
        if r.get("origen") == "manual" or r.get("orientacion")
    }


def reprocesar_documento(
    db: Session,
    almacen: AlmacenDisco,
    settings,
    documento_id: str,
    plantilla_id: int | None = None,
    recorte_manual: tuple[int, dict] | None = None,
) -> tuple[str, ResultadoDTO]:
    """`recorte_manual` = (numero_pagina, {"esquinas": [[x,y]x4] | None, "orientacion": 0|90|180|270}): recorte y/o
    giro marcados por una persona para esa página (docs/13 §4.2). Los de otras páginas guardados antes se conservan.
    (numero_pagina, None) quita el recorte manual de esa página y la devuelve a la detección automática."""
    documento = repo.obtener_documento(db, documento_id)
    if not documento:
        raise DocumentoNoExiste(f"El documento {documento_id} no existe")
    try:
        datos = almacen.leer(documento.RutaAlmacen)
    except FileNotFoundError as e:
        raise DocumentoNoExiste(f"El archivo original del documento {documento_id} ya no existe (puede que se haya purgado)") from e
    plantilla_id = plantilla_id if plantilla_id is not None else documento.PlantillaForzadaId
    recortes = recortes_manuales_guardados(documento)
    if recorte_manual is not None:
        pagina, recorte = recorte_manual
        if not 1 <= pagina <= (documento.Paginas or 1):
            raise PaginaFueraDeRango(f"El documento tiene {documento.Paginas or 1} página(s)")
        if recorte is None:
            recortes.pop(pagina, None)  # quitar el recorte manual: esa página vuelve a la detección automática
        else:
            recortes[pagina] = recorte
    # Reutiliza el mismo DocumentoId: se actualiza en lugar de crear uno nuevo.
    try:
        return _reprocesar_sobre_documento(db, almacen, settings, documento, datos, plantilla_id, recortes)
    except (StaleDataError, ObjectDeletedError, IntegrityError) as e:
        # Carrera con la purga: el documento se borró entre que se cargó y que se guardó el resultado.
        db.rollback()
        if repo.obtener_documento(db, documento_id) is None:
            raise DocumentoNoExiste(f"El documento {documento_id} ya no existe (puede que se haya purgado)") from e
        raise


def _reprocesar_sobre_documento(db, almacen, settings, documento, datos, plantilla_id, recortes_manuales=None):
    import time

    from ..dominio.modelos import CampoExtraidoDTO, Clasificacion
    from ..pipeline import clasificador as clasificador_mod
    from ..pipeline import ensamblador as ensamblador_mod
    from ..pipeline import posiciones
    from ..pipeline.extractor import extraer_campos
    from ..pipeline.orquestador import ErrorPipeline, procesar_bytes, proveedor_segunda_opinion
    from ._convertir import campos_de_version, diseno_de_version

    plantilla_forzada = None
    if plantilla_id is not None:
        plantilla_forzada = repo.obtener_plantilla(db, plantilla_id)
        if not plantilla_forzada:
            raise PlantillaForzadaNoExiste(f"La plantilla {plantilla_id} no existe")

    repo.actualizar_estado_documento(db, documento, "PROCESANDO")
    tiempos: dict[str, int] = {}
    t_total = time.perf_counter()
    try:
        doc_ing, paginas, motor_usado, tiempos_pipeline = procesar_bytes(
            documento.NombreArchivo, datos, settings, recortes_manuales=recortes_manuales
        )
        tiempos.update(tiempos_pipeline)

        t0 = time.perf_counter()
        if plantilla_forzada and plantilla_forzada.version_actual:
            v = plantilla_forzada.version_actual
            clasificacion = Clasificacion(
                tipo=plantilla_forzada.Codigo,
                plantilla_id=plantilla_forzada.PlantillaId,
                version_id=v.PlantillaVersionId,
                confianza=1.0,
            )
            palabras_clave_encontradas = [pc.Texto for pc in v.palabras_clave]
            version_ganadora = v
        else:
            flujo = db.get(m.FlujoCaptura, documento.FlujoCapturaId) if documento.FlujoCapturaId else None
            permitidas = {p.PlantillaId for p in flujo.plantillas} if flujo else None
            candidatas = _plantillas_candidatas(db, permitidas)
            texto_completo = "\n".join(p.texto for p in paginas)
            clasificacion, palabras_clave_encontradas = clasificador_mod.clasificar(
                texto_completo, candidatas, settings.UMBRAL_DESCONOCIDO
            )
            version_ganadora = None
            if clasificacion.plantilla_id:
                pl = repo.obtener_plantilla(db, clasificacion.plantilla_id)
                version_ganadora = pl.version_actual if pl else None
        tiempos["clasificacion"] = int((time.perf_counter() - t0) * 1000)

        t0 = time.perf_counter()
        campos_dto: list[CampoExtraidoDTO] = []
        obligatorios: set[str] = set()
        if version_ganadora:
            campos_plantilla = campos_de_version(version_ganadora)
            obligatorios = {c.nombre for c in campos_plantilla if c.obligatorio}
            campos_dto = extraer_campos(
                campos_plantilla,
                paginas,
                proveedor_segunda_opinion(doc_ing, settings, motor_usado),
                settings.OCR_UMBRAL_SEGUNDA_OPINION,
                settings.OCR_SEGUNDA_OPINION_SOLO_OBLIGATORIOS,
                diseno_de_version(version_ganadora),
            )
        tiempos["extraccion"] = int((time.perf_counter() - t0) * 1000)
        tiempos["total"] = int((time.perf_counter() - t_total) * 1000)

        resultado = ensamblador_mod.ensamblar(
            paginas, clasificacion, campos_dto, palabras_clave_encontradas, obligatorios, tiempos, motor_usado
        )
        repo.guardar_resultado(
            db,
            documento,
            plantilla_version_id=version_ganadora.PlantillaVersionId if version_ganadora else None,
            tipo_detectado=clasificacion.tipo,
            confianza_clasificacion=clasificacion.confianza,
            confianza_global=resultado.confianza_global,
            texto_completo=resultado.texto_completo,
            palabras_clave=resultado.palabras_clave,
            alternativas=[a.model_dump() for a in clasificacion.alternativas],
            advertencias=resultado.advertencias,
            tiempos_ms=resultado.tiempos_ms,
            motor_ocr=motor_usado,
            campos=[c.model_dump() for c in campos_dto],
            palabras_json=posiciones.palabras_json(paginas),
            recorte_json=posiciones.recorte_json(paginas),
        )
        # documento de un flujo de captura sin plantilla aplicable: NO_COINCIDE (igual que al procesarlo)
        sin_coincidencia = documento.FlujoCapturaId is not None and plantilla_forzada is None and clasificacion.tipo == "desconocido"
        repo.actualizar_estado_documento(db, documento, "NO_COINCIDE" if sin_coincidencia else "COMPLETADO")
        return documento.DocumentoId, resultado
    except ErrorPipeline as e:
        repo.actualizar_estado_documento(db, documento, "ERROR", str(e))
        raise
