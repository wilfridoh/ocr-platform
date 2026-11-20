from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..almacen import AlmacenDisco
from ..commands.reprocesar_plantilla import reprocesar_documentos_de_plantilla
from ..config import Settings, get_settings
from ..persistencia import repositorios as repo

from ..commands.actualizar_plantilla import PlantillaNoExiste as PlantillaNoExisteAct
from ..commands.actualizar_plantilla import actualizar_plantilla as cmd_actualizar
from ..commands.actualizar_plantilla import cambiar_estado as cmd_cambiar_estado
from ..commands.crear_plantilla import CodigoDuplicado
from ..commands.crear_plantilla import crear_plantilla as cmd_crear
from ..commands.probar_plantilla import DocumentoSinResultado as DocSinResultadoProbar
from ..commands.probar_plantilla import PlantillaNoExiste as PlantillaNoExisteProbar
from ..commands.probar_plantilla import probar_plantilla as cmd_probar
from ..commands.sugerir_plantilla import DemasiadosEjemplos, DocumentoSinResultado
from ..commands.sugerir_plantilla import sugerir_plantilla as cmd_sugerir
from ..dominio.modelos import CampoPlantillaDTO, DisenoPlantilla, PlantillaCrear, PlantillaEstado
from .._convertir_a_dto import plantilla_a_dto
from ..queries.listar_plantillas import listar_plantillas as q_listar
from ..queries.listar_plantillas import obtener_plantilla as q_obtener
from .dependencias import get_almacen, get_db
from ..dominio.flujos import PermisosEntrada
from .seguridad import Principal, exigir_edicion, requiere_rol, verificar_api_key

router = APIRouter(prefix="/plantillas", tags=["plantillas"], dependencies=[Depends(verificar_api_key)])


def _exigir_edicion_plantilla(db: Session, plantilla_id: int, principal: Principal) -> None:
    """404 si no existe; 403 si el rol del usuario no alcanza para esta plantilla (RolMinimoEdicion)."""
    plantilla = repo.obtener_plantilla(db, plantilla_id)
    if plantilla is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plantilla no encontrada")
    exigir_edicion(principal, plantilla.RolMinimoEdicion)


@router.get("")
def listar(activa: bool | None = None, db: Session = Depends(get_db)) -> list[dict]:
    plantillas = q_listar(db, solo_activas=bool(activa)) if activa else q_listar(db, solo_activas=False)
    return [p.model_dump(mode="json") for p in plantillas]


@router.get("/{plantilla_id}")
def obtener(plantilla_id: int, db: Session = Depends(get_db)) -> dict:
    p = q_obtener(db, plantilla_id)
    if not p:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plantilla no encontrada")
    return p.model_dump(mode="json")


@router.get("/{plantilla_id}/versiones")
def listar_versiones(plantilla_id: int, db: Session = Depends(get_db)) -> list[dict]:
    plantilla = repo.obtener_plantilla(db, plantilla_id)
    if not plantilla:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plantilla no encontrada")
    versiones = sorted(plantilla.versiones, key=lambda v: v.Numero)
    return [
        {
            "version": v.Numero,
            "fecha": v.CreadoEn.isoformat() if v.CreadoEn else None,
            "comentario": "Versión inicial" if v.Numero == 1 else None,
        }
        for v in versiones
    ]


@router.post("/{plantilla_id}/reprocesar")
def reprocesar(
    plantilla_id: int,
    db: Session = Depends(get_db),
    almacen: AlmacenDisco = Depends(get_almacen),
    settings: Settings = Depends(get_settings),
    _: Principal = Depends(requiere_rol("Editor")),
) -> dict:
    try:
        return reprocesar_documentos_de_plantilla(db, almacen, settings, plantilla_id)
    except PlantillaNoExisteAct as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.post("", status_code=status.HTTP_201_CREATED)
def crear(
    datos: PlantillaCrear, db: Session = Depends(get_db), _: Principal = Depends(requiere_rol("Editor"))
) -> dict:
    try:
        plantilla = cmd_crear(db, datos)
    except CodigoDuplicado as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    return plantilla_a_dto(plantilla).model_dump(mode="json")


@router.put("/{plantilla_id}")
def editar(
    plantilla_id: int,
    datos: PlantillaCrear,
    db: Session = Depends(get_db),
    principal: Principal = Depends(requiere_rol("Editor")),
) -> dict:
    _exigir_edicion_plantilla(db, plantilla_id, principal)
    try:
        plantilla = cmd_actualizar(db, plantilla_id, datos)
    except PlantillaNoExisteAct as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    return plantilla_a_dto(plantilla).model_dump(mode="json")


@router.patch("/{plantilla_id}/estado")
def cambiar_estado(
    plantilla_id: int,
    datos: PlantillaEstado,
    db: Session = Depends(get_db),
    principal: Principal = Depends(requiere_rol("Editor")),
) -> dict:
    _exigir_edicion_plantilla(db, plantilla_id, principal)
    try:
        plantilla = cmd_cambiar_estado(db, plantilla_id, datos.activa)
    except PlantillaNoExisteAct as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    return plantilla_a_dto(plantilla).model_dump(mode="json")


@router.post("/sugerir")
def sugerir(
    documento_id: list[str] = Query(..., description="De 1 a 3 documentos de ejemplo del mismo tipo (repetir el parámetro)"),
    db: Session = Depends(get_db),
    _: Principal = Depends(requiere_rol("Editor")),
) -> dict:
    try:
        sugerencia = cmd_sugerir(db, documento_id)
    except (DocumentoSinResultado, DemasiadosEjemplos) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    return sugerencia.model_dump(mode="json")


class ProbarEntrada(BaseModel):
    """Cambios aún no guardados para la vista previa del editor de cuadrícula (docs/13 §7). Todo opcional: sin cuerpo
    se prueba la versión actual. "diseno": null explícito prueba sin cuadrícula."""

    campos: Optional[list[CampoPlantillaDTO]] = None
    diseno: Optional[DisenoPlantilla] = None


@router.post("/{plantilla_id}/probar")
def probar(
    plantilla_id: int,
    documento_id: str,
    entrada: Optional[ProbarEntrada] = Body(default=None),
    db: Session = Depends(get_db),
    _: Principal = Depends(requiere_rol("Editor")),
) -> dict:
    try:
        extras = {}
        if entrada is not None:
            if entrada.campos is not None:
                extras["campos"] = entrada.campos
            if "diseno" in entrada.model_fields_set:
                extras["diseno"] = entrada.diseno
        resultado = cmd_probar(db, plantilla_id, documento_id, **extras)
    except PlantillaNoExisteProbar as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except DocSinResultadoProbar as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    return resultado.a_contrato(documento_id, documento_id, estado="COMPLETADO")


@router.patch("/{plantilla_id}/permisos")
def fijar_permisos(
    plantilla_id: int,
    datos: PermisosEntrada,
    db: Session = Depends(get_db),
    _: Principal = Depends(requiere_rol("Administrador")),
) -> dict:
    """Fija el rol mínimo necesario para editar la plantilla (solo Administrador)."""
    plantilla = repo.obtener_plantilla(db, plantilla_id)
    if plantilla is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plantilla no encontrada")
    plantilla.RolMinimoEdicion = datos.rol_minimo_edicion
    db.commit()
    db.refresh(plantilla)
    return plantilla_a_dto(plantilla).model_dump(mode="json")
