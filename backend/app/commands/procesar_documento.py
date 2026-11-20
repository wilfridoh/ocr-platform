"""Comando: procesar un documento completo (ingesta -> OCR -> clasificación -> extracción -> persistencia)."""
from __future__ import annotations

import time

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import ObjectDeletedError, StaleDataError

from ..almacen import AlmacenDisco
from ..dominio.modelos import CampoExtraidoDTO, Clasificacion, PlantillaDTO, ResultadoDTO
from ..pipeline import clasificador as clasificador_mod
from ..pipeline import ensamblador as ensamblador_mod
from ..pipeline.extractor import extraer_campos
from ..pipeline.ingesta import ErrorIngesta, extension_de
from ..pipeline.orquestador import ErrorPipeline, procesar_bytes, proveedor_segunda_opinion
from ..persistencia import repositorios as repo
from ._convertir import campos_de_version, palabras_clave_de_version
from .errores import DocumentoPurgado  # noqa: F401  (reexportado)


MAX_NOMBRE_ARCHIVO = 260  # Documento.NombreArchivo es NVARCHAR(260)


class PlantillaForzadaNoExiste(ValueError):
    pass


def _plantillas_candidatas(
    db: Session, plantilla_ids_permitidas: set[int] | None = None
) -> list[clasificador_mod.PlantillaCandidata]:
    """Plantillas activas contra las que se clasifica. En un flujo de captura, solo las permitidas por el flujo."""
    plantillas = repo.listar_plantillas(db, solo_activas=True)
    candidatas = []
    for p in plantillas:
        if plantilla_ids_permitidas is not None and p.PlantillaId not in plantilla_ids_permitidas:
            continue
        v = p.version_actual
        if not v:
            continue
        candidatas.append(
            clasificador_mod.PlantillaCandidata(
                plantilla_id=p.PlantillaId,
                version_id=v.PlantillaVersionId,
                codigo=p.Codigo,
                umbral_confianza=float(v.UmbralConfianza),
                palabras_clave=palabras_clave_de_version(v),
            )
        )
    return candidatas


def _procesar_documento(
    db: Session,
    almacen: AlmacenDisco,
    settings,
    nombre_archivo: str,
    datos: bytes,
    plantilla_id: int | None = None,
    flujo=None,
    creado_por_id: int | None = None,
    aviso_version: str | None = None,
) -> tuple[str, ResultadoDTO]:
    """Ejecuta el pipeline completo, persiste y devuelve (documento_id, resultado).

    `flujo` (modelos.FlujoCaptura) restringe la clasificación a sus plantillas permitidas; si ninguna
    aplica, el documento queda en estado NO_COINCIDE (se esperaba algo concreto y no llegó)."""
    # NVARCHAR cuenta unidades UTF-16: un emoji fuera del plano básico ocupa 2 (len() de Python contaría 1)
    if len(nombre_archivo.encode("utf-16-le", "surrogatepass")) // 2 > MAX_NOMBRE_ARCHIVO:
        # antes de OCR y de guardar nada: si no, el INSERT falla y además queda el archivo sin registro
        raise ErrorIngesta(f"El nombre del archivo es demasiado largo (máximo {MAX_NOMBRE_ARCHIVO} caracteres)")
    plantilla_forzada = None
    if plantilla_id is not None:
        plantilla_forzada = repo.obtener_plantilla(db, plantilla_id)
        if not plantilla_forzada:
            raise PlantillaForzadaNoExiste(f"La plantilla {plantilla_id} no existe")

    tiempos: dict[str, int] = {}
    t_total = time.perf_counter()

    try:
        doc_ingresado, paginas, motor_usado, tiempos_pipeline = procesar_bytes(nombre_archivo, datos, settings)
    except ErrorIngesta:
        raise
    tiempos.update(tiempos_pipeline)

    extension = extension_de(nombre_archivo)
    ruta_relativa = AlmacenDisco(settings.ALMACEN_RUTA).guardar(doc_ingresado.hash_sha256, extension, datos)

    documento = repo.crear_documento(
        db,
        nombre_archivo=nombre_archivo,
        tipo_mime=doc_ingresado.tipo_mime,
        tamano_bytes=len(datos),
        hash_sha256=doc_ingresado.hash_sha256,
        ruta_almacen=ruta_relativa,
        paginas=len(paginas),
        plantilla_forzada_id=plantilla_id,
        flujo_captura_id=flujo.FlujoCapturaId if flujo else None,
        creado_por_id=creado_por_id,
        aviso_version=aviso_version,
    )
    repo.actualizar_estado_documento(db, documento, "PROCESANDO")

    try:
        t0 = time.perf_counter()
        if plantilla_forzada and plantilla_forzada.version_actual:
            v = plantilla_forzada.version_actual
            clasificacion = Clasificacion(
                tipo=plantilla_forzada.Codigo,
                plantilla_id=plantilla_forzada.PlantillaId,
                version_id=v.PlantillaVersionId,
                confianza=1.0,
            )
            palabras_clave_encontradas: list[str] = [pc.Texto for pc in v.palabras_clave]
            version_ganadora = v
        else:
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
                proveedor_segunda_opinion(doc_ingresado, settings, motor_usado),
                settings.OCR_UMBRAL_SEGUNDA_OPINION,
                settings.OCR_SEGUNDA_OPINION_SOLO_OBLIGATORIOS,
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
        )
        sin_coincidencia = flujo is not None and clasificacion.tipo == "desconocido"
        repo.actualizar_estado_documento(db, documento, "NO_COINCIDE" if sin_coincidencia else "COMPLETADO")
        repo.registrar_log(
            db, documento.DocumentoId, "ensamblado", "INFO",
            "Sin plantilla coincidente en el flujo" if sin_coincidencia else "Procesamiento completado", tiempos["total"],
        )
        return documento.DocumentoId, resultado
    except ErrorPipeline as e:
        db.rollback()
        repo.actualizar_estado_documento(db, documento, "ERROR", str(e))
        repo.registrar_log(db, documento.DocumentoId, "ocr", "ERROR", str(e))
        raise
    except Exception as e:  # noqa: BLE001
        db.rollback()  # si la purga borró el documento, aquí salta ObjectDeleted/StaleData y lo traduce el envoltorio
        repo.actualizar_estado_documento(db, documento, "ERROR", str(e))
        repo.registrar_log(db, documento.DocumentoId, "pipeline", "ERROR", str(e))
        raise


def procesar_documento(*args, **kwargs) -> tuple[str, ResultadoDTO]:
    """Procesa y persiste un documento (ver `_procesar_documento`). Si una purga lo elimina a mitad de camino
    (datos de la BD que cambian bajo los pies de esta sesión) se lanza DocumentoPurgado, no un error interno."""
    db: Session = args[0]
    try:
        return _procesar_documento(*args, **kwargs)
    except (StaleDataError, ObjectDeletedError) as e:
        db.rollback()
        raise DocumentoPurgado("El documento se eliminó mientras se procesaba (puede que se haya purgado)") from e
    except IntegrityError as e:
        db.rollback()
        # una FK rota al guardar el resultado de un documento que ya no existe es la misma carrera con la purga
        if "FOREIGN KEY" in str(getattr(e, "orig", e)).upper():
            raise DocumentoPurgado("El documento se eliminó mientras se procesaba (puede que se haya purgado)") from e
        raise
