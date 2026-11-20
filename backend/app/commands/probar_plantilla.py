"""POST /plantillas/{id}/probar: aplica una plantilla a un documento sin guardar."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..dominio.modelos import CampoPlantillaDTO, Clasificacion, DisenoPlantilla, ResultadoDTO
from ..persistencia import modelos as m
from ..persistencia import repositorios as repo
from ..pipeline import ensamblador as ensamblador_mod
from ..pipeline.extractor import extraer_campos
from ..pipeline.posiciones import paginas_guardadas
from ..pipeline.zonas import calcular_coincidencia
from ._convertir import campos_de_version, diseno_de_version

_SIN_CAMBIO = object()


class PlantillaNoExiste(ValueError):
    pass


class DocumentoSinResultado(ValueError):
    pass


def probar_plantilla(
    db: Session,
    plantilla_id: int,
    documento_id: str,
    campos: list[CampoPlantillaDTO] | None = None,
    diseno: DisenoPlantilla | None | object = _SIN_CAMBIO,
) -> ResultadoDTO:
    """Sin releer el documento: usa el texto y las posiciones guardadas en su resultado (entrega 1 de la cuadrícula).
    `campos` y `diseno` permiten probar cambios aún no guardados (vista previa del editor de cuadrícula); sin ellos,
    la versión actual de la plantilla. `diseno=None` explícito prueba sin cuadrícula."""
    plantilla = repo.obtener_plantilla(db, plantilla_id)
    if not plantilla or not plantilla.version_actual:
        raise PlantillaNoExiste(f"La plantilla {plantilla_id} no existe")
    resultado_guardado = db.execute(select(m.Resultado).where(m.Resultado.DocumentoId == documento_id)).scalars().first()
    if not resultado_guardado:
        raise DocumentoSinResultado(f"El documento {documento_id} no tiene un resultado de OCR disponible")

    # posiciones guardadas (o, en resultados anteriores a la migración 009, una página solo con texto)
    paginas = paginas_guardadas(resultado_guardado.TextoCompleto or "", resultado_guardado.PalabrasJson, resultado_guardado.RecorteJson)
    campos_plantilla = campos if campos is not None else campos_de_version(plantilla.version_actual)
    diseno_usado = diseno_de_version(plantilla.version_actual) if diseno is _SIN_CAMBIO else diseno
    campos_dto = extraer_campos(campos_plantilla, paginas, diseno=diseno_usado)
    obligatorios = {c.nombre for c in campos_plantilla if c.obligatorio}
    clasificacion = Clasificacion(
        tipo=plantilla.Codigo, plantilla_id=plantilla.PlantillaId, version_id=plantilla.version_actual.PlantillaVersionId, confianza=1.0
    )
    coincidencia = calcular_coincidencia(paginas, campos_plantilla, diseno_usado, campos_dto)
    return ensamblador_mod.ensamblar(
        paginas, clasificacion, campos_dto, [], obligatorios, {"total": 0}, resultado_guardado.MotorOcr or "", coincidencia
    )
