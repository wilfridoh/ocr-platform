"""Repositorios: encapsulan el acceso a las tablas ORM para commands/ y queries/."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..dominio.modelos import PlantillaCrear
from . import modelos as m


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------- Plantilla
def listar_plantillas(db: Session, solo_activas: bool = False) -> list[m.Plantilla]:
    q = select(m.Plantilla).options(
        selectinload(m.Plantilla.version_actual).selectinload(m.PlantillaVersion.palabras_clave),
        selectinload(m.Plantilla.version_actual).selectinload(m.PlantillaVersion.campos),
    )
    if solo_activas:
        q = q.where(m.Plantilla.Activa == True)  # noqa: E712 - .is_(True) compila a "IS 1" invalido en T-SQL/mssql
    return list(db.execute(q).scalars().all())


def obtener_plantilla(db: Session, plantilla_id: int) -> m.Plantilla | None:
    q = (
        select(m.Plantilla)
        .where(m.Plantilla.PlantillaId == plantilla_id)
        .options(
            selectinload(m.Plantilla.version_actual).selectinload(m.PlantillaVersion.palabras_clave),
            selectinload(m.Plantilla.version_actual).selectinload(m.PlantillaVersion.campos),
        )
    )
    return db.execute(q).scalars().first()


def obtener_plantilla_por_codigo(db: Session, codigo: str) -> m.Plantilla | None:
    q = select(m.Plantilla).where(m.Plantilla.Codigo == codigo)
    return db.execute(q).scalars().first()


def crear_plantilla(db: Session, datos: PlantillaCrear) -> m.Plantilla:
    plantilla = m.Plantilla(
        Codigo=datos.codigo,
        Nombre=datos.nombre,
        Descripcion=datos.descripcion,
        Activa=datos.activa,
    )
    db.add(plantilla)
    db.flush()

    version = m.PlantillaVersion(
        PlantillaId=plantilla.PlantillaId,
        Numero=1,
        UmbralConfianza=datos.umbral_confianza,
        DocumentoEjemploId=datos.documento_ejemplo_id,
        CreadoPor=datos.creado_por,
    )
    db.add(version)
    db.flush()

    for pc in datos.palabras_clave:
        db.add(m.PalabraClave(PlantillaVersionId=version.PlantillaVersionId, Texto=pc.texto, Peso=pc.peso))
    for i, c in enumerate(datos.campos):
        db.add(
            m.CampoPlantilla(
                PlantillaVersionId=version.PlantillaVersionId,
                Nombre=c.nombre,
                Etiqueta=c.etiqueta,
                TipoDato=c.tipo_dato,
                Obligatorio=c.obligatorio,
                Metodo=c.regla.metodo,
                ReglaJson=c.regla.model_dump_json(),
                Orden=c.orden or i,
            )
        )
    plantilla.VersionActualId = version.PlantillaVersionId
    db.flush()
    db.commit()
    db.refresh(plantilla)
    return plantilla


def nueva_version_plantilla(db: Session, plantilla: m.Plantilla, datos: PlantillaCrear) -> m.Plantilla:
    """PUT /plantillas/{id}: crea una nueva versión sin perder el historial."""
    ultimo_numero = max((v.Numero for v in plantilla.versiones), default=0)
    version = m.PlantillaVersion(
        PlantillaId=plantilla.PlantillaId,
        Numero=ultimo_numero + 1,
        UmbralConfianza=datos.umbral_confianza,
        DocumentoEjemploId=datos.documento_ejemplo_id,
        CreadoPor=datos.creado_por,
    )
    db.add(version)
    db.flush()
    for pc in datos.palabras_clave:
        db.add(m.PalabraClave(PlantillaVersionId=version.PlantillaVersionId, Texto=pc.texto, Peso=pc.peso))
    for i, c in enumerate(datos.campos):
        db.add(
            m.CampoPlantilla(
                PlantillaVersionId=version.PlantillaVersionId,
                Nombre=c.nombre,
                Etiqueta=c.etiqueta,
                TipoDato=c.tipo_dato,
                Obligatorio=c.obligatorio,
                Metodo=c.regla.metodo,
                ReglaJson=c.regla.model_dump_json(),
                Orden=c.orden or i,
            )
        )
    plantilla.Nombre = datos.nombre
    plantilla.Descripcion = datos.descripcion
    plantilla.Activa = datos.activa
    plantilla.VersionActualId = version.PlantillaVersionId
    plantilla.ActualizadoEn = _utcnow()
    db.flush()
    db.commit()
    db.refresh(plantilla)
    return plantilla


def cambiar_estado_plantilla(db: Session, plantilla: m.Plantilla, activa: bool) -> m.Plantilla:
    plantilla.Activa = activa
    plantilla.ActualizadoEn = _utcnow()
    db.commit()
    db.refresh(plantilla)
    return plantilla


# --------------------------------------------------------------------- Documento
def crear_documento(
    db: Session,
    nombre_archivo: str,
    tipo_mime: str,
    tamano_bytes: int,
    hash_sha256: str,
    ruta_almacen: str,
    paginas: int,
    plantilla_forzada_id: int | None = None,
    flujo_captura_id: int | None = None,
    creado_por_id: int | None = None,
    aviso_version: str | None = None,
) -> m.Documento:
    doc = m.Documento(
        NombreArchivo=nombre_archivo,
        TipoMime=tipo_mime,
        TamanoBytes=tamano_bytes,
        HashSha256=hash_sha256,
        RutaAlmacen=ruta_almacen,
        Paginas=paginas,
        Estado="RECIBIDO",
        PlantillaForzadaId=plantilla_forzada_id,
        FlujoCapturaId=flujo_captura_id,
        CreadoPorId=creado_por_id,
        # consentimiento de privacidad: se registra la fecha y la versión del aviso que la persona aceptó
        ConsentimientoEn=_utcnow() if aviso_version else None,
        AvisoVersion=aviso_version,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def obtener_documento(db: Session, documento_id: str) -> m.Documento | None:
    return db.get(m.Documento, documento_id)


def actualizar_estado_documento(
    db: Session, documento: m.Documento, estado: str, mensaje_error: str | None = None
) -> m.Documento:
    documento.Estado = estado
    documento.MensajeError = mensaje_error
    if estado in ("COMPLETADO", "ERROR", "NO_COINCIDE"):
        documento.ProcesadoEn = _utcnow()
    db.commit()
    db.refresh(documento)
    return documento


def buscar_documentos(
    db: Session,
    tipo: str | None = None,
    estado: str | None = None,
    desde: datetime | None = None,
    hasta: datetime | None = None,
    pagina: int = 1,
    tamano: int = 20,
) -> tuple[list[m.Documento], int]:
    q = select(m.Documento).outerjoin(m.Resultado, m.Resultado.DocumentoId == m.Documento.DocumentoId)
    if estado:
        q = q.where(m.Documento.Estado == estado)
    if tipo:
        q = q.where(m.Resultado.TipoDetectado == tipo)
    if desde:
        q = q.where(m.Documento.RecibidoEn >= desde)
    if hasta:
        q = q.where(m.Documento.RecibidoEn <= hasta)
    total = len(list(db.execute(q).scalars().all()))
    q = q.order_by(m.Documento.RecibidoEn.desc()).offset((pagina - 1) * tamano).limit(tamano)
    return list(db.execute(q).scalars().all()), total


# --------------------------------------------------------------------- Resultado
def guardar_resultado(
    db: Session,
    documento: m.Documento,
    plantilla_version_id: int | None,
    tipo_detectado: str,
    confianza_clasificacion: float,
    confianza_global: float,
    texto_completo: str,
    palabras_clave: list[str],
    alternativas: list[dict],
    advertencias: list[str],
    tiempos_ms: dict,
    motor_ocr: str,
    campos: list[dict],
) -> m.Resultado:
    existente = db.execute(select(m.Resultado).where(m.Resultado.DocumentoId == documento.DocumentoId)).scalars().first()
    if existente:
        db.delete(existente)
        db.flush()

    resultado = m.Resultado(
        DocumentoId=documento.DocumentoId,
        PlantillaVersionId=plantilla_version_id,
        TipoDetectado=tipo_detectado,
        ConfianzaClasificacion=confianza_clasificacion,
        ConfianzaGlobal=confianza_global,
        TextoCompleto=texto_completo,
        PalabrasClaveJson=json.dumps(palabras_clave, ensure_ascii=False),
        AlternativasJson=json.dumps(alternativas, ensure_ascii=False),
        AdvertenciasJson=json.dumps(advertencias, ensure_ascii=False),
        TiemposJson=json.dumps(tiempos_ms, ensure_ascii=False),
        MotorOcr=motor_ocr,
    )
    db.add(resultado)
    db.flush()

    for c in campos:
        db.add(
            m.CampoExtraido(
                ResultadoId=resultado.ResultadoId,
                CampoPlantillaId=c.get("campo_plantilla_id"),
                Nombre=c["nombre"],
                ValorTexto=c.get("valor_texto"),
                ValorNormalizadoJson=json.dumps(c.get("valor"), ensure_ascii=False) if c.get("valor") is not None else None,
                Confianza=c.get("confianza", 0.0),
                Pagina=c.get("pagina"),
                Valido=c.get("valido", False),
                Motor=c.get("motor"),
            )
        )
    db.commit()
    db.refresh(resultado)
    return resultado


def obtener_resultado(db: Session, documento_id: str) -> m.Resultado | None:
    q = (
        select(m.Resultado)
        .where(m.Resultado.DocumentoId == documento_id)
        .options(selectinload(m.Resultado.campos))
    )
    return db.execute(q).scalars().first()


# --------------------------------------------------------------------- Log
def registrar_log(
    db: Session, documento_id: str, paso: str, nivel: str, mensaje: str, duracion_ms: int | None = None
) -> None:
    db.add(
        m.LogProcesamiento(
            DocumentoId=documento_id, Paso=paso, Nivel=nivel, Mensaje=mensaje[:2000], DuracionMs=duracion_ms
        )
    )
    db.commit()
