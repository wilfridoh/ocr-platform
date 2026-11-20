from __future__ import annotations

from datetime import datetime
from io import BytesIO

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..almacen import AlmacenDisco
from ..commands.procesar_documento import PlantillaForzadaNoExiste, procesar_documento
from ..commands.reprocesar_documento import DocumentoNoExiste, reprocesar_documento
from ..config import Settings, get_settings
from ..pipeline.ingesta import ErrorIngesta, rasterizar
from ..queries.buscar_documentos import buscar_documentos
from ..persistencia import repositorios as repo
from .dependencias import get_almacen, get_db
from .seguridad import Principal, autenticar, verificar_api_key

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
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e

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
    return resultado.a_contrato(doc_id, documento.NombreArchivo, estado="COMPLETADO")
