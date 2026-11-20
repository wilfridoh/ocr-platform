from __future__ import annotations

import logging
from datetime import datetime
from io import BytesIO
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..almacen import AlmacenDisco
from ..commands.errores import DocumentoPurgado
from ..commands.procesar_documento import PlantillaForzadaNoExiste, procesar_documento
from ..commands.reprocesar_documento import DocumentoNoExiste, reprocesar_documento
from ..config import Settings, get_settings
from ..pipeline.ingesta import ErrorIngesta, rasterizar
from ..queries.buscar_documentos import buscar_documentos
from ..persistencia import repositorios as repo
from .dependencias import get_almacen, get_db
from .seguridad import Principal, autenticar, verificar_api_key

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documentos", tags=["documentos"], dependencies=[Depends(verificar_api_key)])


@router.post("", status_code=status.HTTP_201_CREATED)
async def subir_documento(
    archivo: UploadFile = File(...),
    plantilla_id: int | None = Form(default=None),
    sincrono: bool = Form(default=True),
    db: Session = Depends(get_db),
    almacen: AlmacenDisco = Depends(get_almacen),
    settings: Settings = Depends(get_settings),
    principal: Principal = Depends(autenticar),
) -> dict:
    datos = await archivo.read()
    try:
        # El pipeline OCR es CPU/IO bloqueante: fuera del event loop, para que /salud y el resto
        # del API sigan respondiendo mientras se procesa (o se cargan/descargan modelos).
        documento_id, resultado = await run_in_threadpool(
            procesar_documento, db, almacen, settings, archivo.filename or "documento", datos, plantilla_id,
            None, principal.usuario_id
        )
    except ErrorIngesta as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except PlantillaForzadaNoExiste as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except DocumentoPurgado as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"{e}. Vuelve a subirlo.") from e
    except Exception as e:  # noqa: BLE001
        # el detalle va al log, no al cliente: puede traer nombres de tablas/columnas o valores del documento
        logger.exception("Error inesperado procesando un documento")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="No se pudo procesar el documento") from e

    return resultado.a_contrato(documento_id, archivo.filename or "documento", estado="COMPLETADO")


@router.get("")
def listar_documentos(
    tipo: str | None = None,
    estado: str | None = None,
    desde: datetime | None = None,
    hasta: datetime | None = None,
    pagina: int = 1,
    tamano: int = 20,
    db: Session = Depends(get_db),
) -> dict:
    documentos, total = buscar_documentos(db, tipo, estado, desde, hasta, pagina, tamano)
    return {
        "items": [d.model_dump() for d in documentos],
        "total": total,
        "pagina": pagina,
        "tamano": tamano,
    }


@router.get("/{documento_id}")
def obtener_documento(documento_id: str, db: Session = Depends(get_db)) -> dict:
    documento = repo.obtener_documento(db, documento_id)
    if not documento:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento no encontrado")
    resultado = documento.resultado
    return {
        "id": documento.DocumentoId,
        "nombre_archivo": documento.NombreArchivo,
        "tipo_mime": documento.TipoMime,
        "tamano_bytes": documento.TamanoBytes,
        "hash_sha256": documento.HashSha256,
        "paginas": documento.Paginas,
        "estado": documento.Estado,
        "plantilla_forzada_id": documento.PlantillaForzadaId,
        "mensaje_error": documento.MensajeError,
        "recibido_en": documento.RecibidoEn,
        "procesado_en": documento.ProcesadoEn,
        "tipo_detectado": resultado.TipoDetectado if resultado else None,
        "confianza_global": float(resultado.ConfianzaGlobal) if resultado else None,
    }


@router.get("/{documento_id}/archivo")
def descargar_archivo(
    documento_id: str, db: Session = Depends(get_db), almacen: AlmacenDisco = Depends(get_almacen)
) -> StreamingResponse:
    documento = repo.obtener_documento(db, documento_id)
    if not documento:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento no encontrado")
    datos = almacen.leer(documento.RutaAlmacen)
    return StreamingResponse(
        BytesIO(datos),
        media_type=documento.TipoMime,
        headers={"Content-Disposition": f'attachment; filename="{documento.NombreArchivo}"'},
    )


@router.get("/{documento_id}/paginas/{n}")
def obtener_pagina_imagen(
    documento_id: str, n: int, db: Session = Depends(get_db), almacen: AlmacenDisco = Depends(get_almacen)
) -> StreamingResponse:
    documento = repo.obtener_documento(db, documento_id)
    if not documento:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento no encontrado")
    datos = almacen.leer(documento.RutaAlmacen)
    paginas = rasterizar(documento.NombreArchivo, datos)
    if n < 1 or n > len(paginas):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Página fuera de rango")
    buf = BytesIO()
    paginas[n - 1].save(buf, format="PNG")
    buf.seek(0)
    return StreamingResponse(buf, media_type="image/png")


# ------------------------------------------------------------- cuadrícula (docs/13 §7)
def _resultado_y_recorte(db: Session, documento_id: str, n: int):
    from ..pipeline.posiciones import leer_recorte

    documento = repo.obtener_documento(db, documento_id)
    if not documento:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento no encontrado")
    if n < 1 or n > (documento.Paginas or 1):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Página fuera de rango")
    resultado = documento.resultado
    recorte = leer_recorte(resultado.RecorteJson if resultado else None).get(n)
    return documento, resultado, recorte


def _relacion_esperada(db: Session, resultado, relacion: float | None) -> float | None:
    """Proporción con la que se juzga el recorte: la pedida en la consulta (editor de una plantilla nueva) o la del
    diseño de la versión de plantilla con que se procesó el documento. Ninguna atada a un formato concreto."""
    if relacion:
        return relacion
    if resultado is None or resultado.PlantillaVersionId is None:
        return None
    from ..dominio.modelos import DisenoPlantilla
    from ..persistencia import modelos as m

    version = db.get(m.PlantillaVersion, resultado.PlantillaVersionId)
    if version is None or not version.DisenoJson:
        return None
    return DisenoPlantilla.model_validate_json(version.DisenoJson).relacion


def _recorte_publico(recorte: dict | None, confiable: bool) -> dict:
    base = recorte or {"aplicado": False, "origen": "desconocido", "esquinas": None, "relacion": None, "orientacion": 0}
    return {
        "confiable": confiable,
        "aplicado": bool(base.get("aplicado")),
        "origen": base.get("origen"),
        "esquinas": base.get("esquinas"),
        "relacion": base.get("relacion"),
        "orientacion": base.get("orientacion") or 0,
    }


@router.get("/{documento_id}/paginas/{n}/enderezada")
def obtener_pagina_enderezada(
    documento_id: str,
    n: int,
    relacion: float | None = Query(default=None, ge=1.0, le=10.0),
    formato: Literal["png", "jpeg"] = "png",
    db: Session = Depends(get_db),
    almacen: AlmacenDisco = Depends(get_almacen),
    settings: Settings = Depends(get_settings),
) -> StreamingResponse:
    """La página recortada, girada y enderezada en color: el mismo marco que las coordenadas de /palabras. Sin datos
    de recorte (documento anterior a la migración 009) devuelve la página original con X-Recorte-Origen: desconocido.
    `?formato=jpeg` (calidad 90) para móvil: una foto en PNG pesa 1-2 MB."""
    import cv2
    import numpy as np

    from ..pipeline.ingesta import ingerir
    from ..pipeline.posiciones import recorte_confiable
    from ..pipeline.preprocesado import reconstruir_enderezada

    documento, resultado, recorte = _resultado_y_recorte(db, documento_id, n)
    datos = almacen.leer(documento.RutaAlmacen)
    doc = ingerir(
        documento.NombreArchivo, datos, max_mb=settings.MAX_TAMANO_MB, dpi=settings.OCR_DPI,
        max_megapixeles=settings.OCR_MAX_MEGAPIXELES, megapixeles_procesado=settings.OCR_MEGAPIXELES_PROCESADO,
        max_paginas=settings.OCR_MAX_PAGINAS,
    )
    if doc.es_pdf_nativo or not doc.imagenes:
        # PDF con texto nativo: no hubo recorte; las coordenadas son de la página tal cual
        img = cv2.cvtColor(np.array(rasterizar(documento.NombreArchivo, datos)[n - 1].convert("RGB")), cv2.COLOR_RGB2BGR)
    else:
        img = reconstruir_enderezada(doc.imagenes[n - 1], recorte)
    if formato == "jpeg":
        ok, codificada = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 90])
    else:
        ok, codificada = cv2.imencode(".png", img)
    if not ok:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="No se pudo generar la imagen")
    confiable = recorte_confiable(recorte, _relacion_esperada(db, resultado, relacion))
    return StreamingResponse(
        BytesIO(codificada.tobytes()),
        media_type="image/jpeg" if formato == "jpeg" else "image/png",
        headers={
            "X-Recorte-Confiable": "true" if confiable else "false",
            "X-Recorte-Origen": (recorte or {}).get("origen") or "desconocido",
            "X-Orientacion": str((recorte or {}).get("orientacion") or 0),
            "Cache-Control": "no-store",
        },
    )


@router.get("/{documento_id}/paginas/{n}/palabras")
def obtener_palabras(
    documento_id: str,
    n: int,
    relacion: float | None = Query(default=None, ge=1.0, le=10.0),
    db: Session = Depends(get_db),
) -> dict:
    """Palabras del OCR con su caja relativa (0-1) sobre la imagen de /enderezada, y los datos del recorte."""
    from ..pipeline.posiciones import leer_palabras, recorte_confiable

    _, resultado, recorte = _resultado_y_recorte(db, documento_id, n)
    palabras = leer_palabras(resultado.PalabrasJson if resultado else None)
    if not palabras:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Este documento no tiene posiciones guardadas. Reprocese el documento para ver posiciones.",
        )
    confiable = recorte_confiable(recorte, _relacion_esperada(db, resultado, relacion))
    return {"pagina": n, "recorte": _recorte_publico(recorte, confiable), "palabras": palabras.get(n, [])}


class RecorteManualEntrada(BaseModel):
    esquinas: list[list[float]] | None = None  # 4 puntos relativos a la imagen original; None = conservar/automático
    orientacion: Literal[0, 90, 180, 270] = 0  # giro horario a aplicar tras el recorte


@router.post("/{documento_id}/paginas/{n}/recorte")
def recortar_manual(
    documento_id: str,
    n: int,
    entrada: RecorteManualEntrada,
    db: Session = Depends(get_db),
    almacen: AlmacenDisco = Depends(get_almacen),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Recorte y/o giro marcados por una persona (docs/13 §4.2): valida las esquinas, reprocesa el documento con ellas y
    devuelve el resultado nuevo. La imagen se vuelve a pedir a /enderezada. Reprocesos posteriores conservan el recorte."""
    from ..commands.reprocesar_documento import PaginaFueraDeRango
    from ..pipeline.preprocesado import EsquinasInvalidas, validar_esquinas

    documento, _, anterior = _resultado_y_recorte(db, documento_id, n)
    if entrada.esquinas is not None:
        try:
            esquinas = validar_esquinas(entrada.esquinas)
        except EsquinasInvalidas as e:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)) from e
    else:  # solo giro: conserva las esquinas marcadas antes a mano, si las hay
        esquinas = (anterior or {}).get("esquinas") if (anterior or {}).get("origen") == "manual" else None
    try:
        doc_id, resultado = reprocesar_documento(
            db, almacen, settings, documento_id, None, (n, {"esquinas": esquinas, "orientacion": entrada.orientacion})
        )
    except DocumentoNoExiste as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except PaginaFueraDeRango as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except PlantillaForzadaNoExiste as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    documento = repo.obtener_documento(db, doc_id)
    return resultado.a_contrato(doc_id, documento.NombreArchivo, estado=documento.Estado)


@router.delete("/{documento_id}/paginas/{n}/recorte")
def quitar_recorte_manual(
    documento_id: str,
    n: int,
    db: Session = Depends(get_db),
    almacen: AlmacenDisco = Depends(get_almacen),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Quita el recorte y el giro manuales de la página y reprocesa con la detección automática. Devuelve el resultado
    nuevo (si la página no tenía recorte manual, equivale a reprocesar)."""
    from ..commands.reprocesar_documento import PaginaFueraDeRango

    _resultado_y_recorte(db, documento_id, n)
    try:
        doc_id, resultado = reprocesar_documento(db, almacen, settings, documento_id, None, (n, None))
    except (DocumentoNoExiste, PaginaFueraDeRango, PlantillaForzadaNoExiste) as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    documento = repo.obtener_documento(db, doc_id)
    return resultado.a_contrato(doc_id, documento.NombreArchivo, estado=documento.Estado)


@router.post("/{documento_id}/reprocesar")
def reprocesar(
    documento_id: str,
    plantilla_id: int | None = None,
    db: Session = Depends(get_db),
    almacen: AlmacenDisco = Depends(get_almacen),
    settings: Settings = Depends(get_settings),
) -> dict:
    try:
        doc_id, resultado = reprocesar_documento(db, almacen, settings, documento_id, plantilla_id)
    except DocumentoNoExiste as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except PlantillaForzadaNoExiste as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    documento = repo.obtener_documento(db, doc_id)
    return resultado.a_contrato(doc_id, documento.NombreArchivo, estado=documento.Estado)
