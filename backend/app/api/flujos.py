"""Flujos de captura (docs/07 §5): perfiles de captura dirigida y procesamiento restringido a sus plantillas.

ÚNICA excepción pública de toda la API (sin X-API-Key), y solo para flujos con AccesoPublico:
  - GET  /flujos-captura/{codigo}/publico     (datos mínimos para pintar la pantalla)
  - POST /flujos-captura/{codigo}/documentos  (subir un documento; sin clave solo si el flujo es público)
Todo lo demás exige clave. Y TODO el modo anónimo está apagado salvo que se active PUBLICO_HABILITADO=true
(por defecto false: sin clave, estas rutas también dan 401). Por eso este router NO tiene una dependencia global: cada ruta declara la suya
y tests/test_flujos_permisos.py::test_ninguna_ruta_queda_sin_proteger recorre TODAS las rutas de la app.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from ..almacen import AlmacenDisco
from ..commands import flujos_captura as cmd
from ..commands.errores import DocumentoPurgado
from ..commands.procesar_documento import procesar_documento
from ..config import Settings, get_settings
from ..dominio.flujos import (
    AccesoPublicoEntrada,
    EstadoEntrada,
    FlujoCapturaCrear,
    FlujoPublicoDTO,
    PermisosEntrada,
)
from ..persistencia import modelos as m
from ..persistencia import repositorios as repo
from ..persistencia import utilidades_flujos as uf
from ..pipeline.ingesta import ErrorIngesta, extension_de
from .dependencias import get_almacen, get_db
from .limitador import (
    CupoConcurrencia,
    huella_ip,
    ip_cliente,
    leer_con_tope,
    limitar_info_publica,
    limitar_subida_publica,
)
from .seguridad import Principal, autenticar, autenticar_opcional, exigir_edicion, requiere_rol

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/flujos-captura", tags=["flujos de captura"])


def _flujo_o_404(db: Session, flujo_id: int):
    try:
        return cmd.obtener(db, flujo_id)
    except cmd.FlujoNoExiste as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


# ------------------------------------------------------------------ rutas con clave
@router.get("")
def listar(
    todos: bool = False, db: Session = Depends(get_db), principal: Principal = Depends(autenticar)
) -> list[dict]:
    """Operador: solo flujos activos (lo que ve el selector de "Procesar"). `?todos=true` (Editor o superior)
    incluye los inactivos, para el administrador de flujos."""
    if todos and not principal.tiene_rol("Editor"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Se requiere el rol Editor o superior")
    return [uf.flujo_a_dto(f).model_dump(mode="json") for f in uf.listar_flujos(db, solo_activos=not todos)]


@router.get("/{codigo}")
def detalle(codigo: str, db: Session = Depends(get_db), principal: Principal = Depends(autenticar)) -> dict:
    flujo = uf.flujo_por_codigo(db, codigo)
    # un flujo inactivo no existe para un Operador
    if flujo is None or (not flujo.Activo and not principal.tiene_rol("Editor")):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flujo de captura no encontrado")
    return uf.flujo_a_dto(flujo).model_dump(mode="json")


@router.post("", status_code=status.HTTP_201_CREATED)
def crear(
    datos: FlujoCapturaCrear, db: Session = Depends(get_db), principal: Principal = Depends(requiere_rol("Editor"))
) -> dict:
    try:
        flujo = cmd.crear_flujo(db, datos, principal.usuario_id)
    except (cmd.CodigoFlujoDuplicado, cmd.PlantillasInvalidas) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    return uf.flujo_a_dto(flujo).model_dump(mode="json")


@router.put("/{flujo_id}")
def editar(
    flujo_id: int,
    datos: FlujoCapturaCrear,
    db: Session = Depends(get_db),
    principal: Principal = Depends(requiere_rol("Editor")),
) -> dict:
    flujo = _flujo_o_404(db, flujo_id)
    exigir_edicion(principal, flujo.RolMinimoEdicion)
    try:
        flujo = cmd.actualizar_flujo(db, flujo, datos)
    except (cmd.CodigoFlujoDuplicado, cmd.PlantillasInvalidas) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    return uf.flujo_a_dto(flujo).model_dump(mode="json")


@router.patch("/{flujo_id}/estado")
def cambiar_estado(
    flujo_id: int,
    datos: EstadoEntrada,
    db: Session = Depends(get_db),
    principal: Principal = Depends(requiere_rol("Editor")),
) -> dict:
    flujo = _flujo_o_404(db, flujo_id)
    exigir_edicion(principal, flujo.RolMinimoEdicion)
    return uf.flujo_a_dto(cmd.cambiar_estado(db, flujo, datos.activo)).model_dump(mode="json")


@router.patch("/{flujo_id}/permisos")
def permisos(
    flujo_id: int,
    datos: PermisosEntrada,
    db: Session = Depends(get_db),
    _: Principal = Depends(requiere_rol("Administrador")),
) -> dict:
    flujo = _flujo_o_404(db, flujo_id)
    return uf.flujo_a_dto(cmd.fijar_permisos(db, flujo, datos.rol_minimo_edicion)).model_dump(mode="json")


@router.patch("/{flujo_id}/acceso-publico")
def acceso_publico(
    flujo_id: int,
    datos: AccesoPublicoEntrada,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    principal: Principal = Depends(requiere_rol("Administrador")),
) -> dict:
    """Abre o cierra el acceso SIN clave a este flujo. Solo un Administrador (es una decisión de seguridad)."""
    if not settings.PUBLICO_HABILITADO:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El acceso público está deshabilitado en este servidor (PUBLICO_HABILITADO=false)",
        )
    flujo = _flujo_o_404(db, flujo_id)
    anterior = flujo.AccesoPublico
    flujo = cmd.fijar_acceso_publico(db, flujo, datos.acceso_publico)
    if anterior != flujo.AccesoPublico:
        logger.warning(
            "Acceso público del flujo '%s' %s por %s", flujo.Codigo,
            "ACTIVADO" if flujo.AccesoPublico else "desactivado", principal.nombre,
        )
    return uf.flujo_a_dto(flujo).model_dump(mode="json")


# ------------------------------------------------------------------ rutas con modo público
@router.get("/{codigo}/publico")
def detalle_publico(
    codigo: str,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    principal: Principal | None = Depends(autenticar_opcional),
) -> dict:
    """Datos mínimos de un flujo público, SIN clave: instrucción y formatos aceptados. No expone plantillas ni
    ids. Un flujo inexistente, inactivo o no público responde 404 igual (no se puede enumerar flujos)."""
    if principal is None:
        limitar_info_publica(ip_cliente(request, settings), settings)
    flujo = uf.flujo_por_codigo(db, codigo)
    if flujo is None or not flujo.Activo or (principal is None and not flujo.AccesoPublico):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flujo de captura no encontrado")
    return FlujoPublicoDTO(
        codigo=flujo.Codigo,
        nombre=flujo.Nombre,
        instruccion=flujo.Instruccion,
        acepta_camara=flujo.AceptaCamara,
        acepta_pdf=flujo.AceptaPdf,
        # lo necesario para mostrar el aviso de privacidad con los datos REALES de este servidor
        retencion_dias=settings.DOC_RETENCION_DIAS,
        aviso_version=settings.AVISO_PRIVACIDAD_VERSION,
    ).model_dump(mode="json")


def _contrato_publico(contrato: dict, etiquetas: dict[str, str]) -> dict:
    """Respuesta reducida para quien subió sin clave: su resultado, sin texto OCR completo ni datos internos.
    Cada campo lleva solo su valor, su confianza y el rótulo legible (p. ej. "Número de cliente")."""
    return {
        "documento_id": contrato["documento_id"],
        "archivo": contrato["archivo"],
        "estado": contrato["estado"],
        "clasificacion": {"tipo": contrato["clasificacion"]["tipo"], "confianza": contrato["clasificacion"]["confianza"]},
        "campos": {
            k: {"valor": v["valor"], "confianza": v["confianza"], "etiqueta": etiquetas.get(k, k.replace("_", " "))}
            for k, v in contrato["campos"].items()
        },
        "confianza_global": contrato["confianza_global"],
        "advertencias": contrato["advertencias"],
        "flujo_captura": contrato.get("flujo_captura"),
    }


@router.post("/{codigo}/documentos", status_code=status.HTTP_201_CREATED)
async def procesar_con_flujo(
    codigo: str,
    request: Request,
    archivo: UploadFile = File(...),
    consentimiento: bool = Form(default=False),
    aviso_version: str | None = Form(default=None),
    db: Session = Depends(get_db),
    almacen: AlmacenDisco = Depends(get_almacen),
    settings: Settings = Depends(get_settings),
    principal: Principal | None = Depends(autenticar_opcional),
) -> dict:
    """Como POST /documentos, pero la clasificación se limita a las plantillas del flujo. Si ninguna aplica,
    el documento queda con estado NO_COINCIDE (no 'desconocido': aquí sí sabemos qué se esperaba).

    Con X-API-Key: cualquier flujo activo (Operador o superior). Sin clave: solo flujos activos con
    AccesoPublico, con límite por IP y global, tope de concurrencia y respuesta reducida."""
    anonimo = principal is None
    ip = ip_cliente(request, settings)
    if anonimo:
        limitar_subida_publica(ip, settings)  # cuenta también los intentos contra flujos que no existen
    flujo = uf.flujo_por_codigo(db, codigo)
    if flujo is None or not flujo.Activo or (anonimo and not flujo.AccesoPublico):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flujo de captura no encontrado")
    if anonimo:
        # Sin consentimiento no se recibe ni un byte: la persona debe haber visto y aceptado el aviso VIGENTE.
        if not consentimiento:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Debes aceptar el aviso de privacidad para subir tu documento")
        if aviso_version != settings.AVISO_PRIVACIDAD_VERSION:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El aviso de privacidad cambió. Recarga la página y vuelve a aceptarlo")
    nombre = archivo.filename or "documento"
    if not flujo.AceptaPdf and extension_de(nombre) == "pdf":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Este flujo no acepta archivos PDF")
    max_mb = min(settings.MAX_TAMANO_MB, settings.PUBLICO_MAX_TAMANO_MB) if anonimo else settings.MAX_TAMANO_MB
    datos = await leer_con_tope(archivo, max_mb * 1024 * 1024)

    async def _procesar():
        return await run_in_threadpool(
            procesar_documento, db, almacen, settings, nombre, datos, None, flujo,
            principal.usuario_id if principal else None,
            settings.AVISO_PRIVACIDAD_VERSION if anonimo else None,  # consentimiento (solo el flujo público lo exige)
        )

    try:
        if anonimo:
            with CupoConcurrencia(settings):
                documento_id, resultado = await _procesar()
        else:
            documento_id, resultado = await _procesar()
    except ErrorIngesta as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except HTTPException:
        raise
    except DocumentoPurgado as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"{e}. Vuelve a subirlo.") from e
    except Exception as e:  # noqa: BLE001
        logger.exception("Error procesando documento del flujo %s", codigo)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="No se pudo procesar el documento") from e

    # Auditoría: de dónde llegó (distingue lo público de lo que sube el personal interno)
    if anonimo:
        origen = (
            f"Origen: PÚBLICO sin usuario identificado (flujo {flujo.Codigo}, huella IP {huella_ip(ip, settings.API_KEY)}); "
            f"consentimiento al aviso de privacidad v{settings.AVISO_PRIVACIDAD_VERSION}, retención {settings.DOC_RETENCION_DIAS} días"
        )
    elif principal.usuario_id is None:
        origen = f"Origen: clave del sistema (flujo {flujo.Codigo})"
    else:
        origen = f"Origen: usuario #{principal.usuario_id} {principal.rol} (flujo {flujo.Codigo})"
    repo.registrar_log(db, documento_id, "acceso", "INFO", origen)

    documento = repo.obtener_documento(db, documento_id)
    cuerpo = resultado.a_contrato(documento_id, nombre, estado=documento.Estado)
    cuerpo["flujo_captura"] = flujo.Codigo
    if not anonimo:
        return cuerpo
    version = db.get(m.PlantillaVersion, resultado.clasificacion.version_id) if resultado.clasificacion.version_id else None
    return _contrato_publico(cuerpo, {c.Nombre: c.Etiqueta for c in version.campos} if version else {})
