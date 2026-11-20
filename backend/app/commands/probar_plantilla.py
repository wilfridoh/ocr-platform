"""POST /plantillas/{id}/probar: aplica una plantilla a un documento sin guardar."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..dominio.modelos import ResultadoDTO
from ..persistencia import modelos as m
from ..persistencia import repositorios as repo
from ._convertir import campos_de_version, diseno_de_version
from ..pipeline.extractor import extraer_campos
from ..pipeline import ensamblador as ensamblador_mod
from ..dominio.modelos import Clasificacion


class PlantillaNoExiste(ValueError):
    pass


class DocumentoSinResultado(ValueError):
    pass


def probar_plantilla(db: Session, plantilla_id: int, documento_id: str) -> ResultadoDTO:
    plantilla = repo.obtener_plantilla(db, plantilla_id)
    if not plantilla or not plantilla.version_actual:
        raise PlantillaNoExiste(f"La plantilla {plantilla_id} no existe")
    resultado_guardado = db.execute(select(m.Resultado).where(m.Resultado.DocumentoId == documento_id)).scalars().first()
    if not resultado_guardado:
        raise DocumentoSinResultado(f"El documento {documento_id} no tiene un resultado de OCR disponible")

    from ..dominio.modelos import PaginaOCR

    # Reconstruye una página "sintética" a partir del texto guardado (sin coordenadas de palabra,
    # ya que el resultado persistido no conserva las cajas); suficiente para métodos regex/ancla.
    pagina = PaginaOCR(numero=1, texto=resultado_guardado.TextoCompleto or "", palabras=[], confianza_media=1.0)
    campos_plantilla = campos_de_version(plantilla.version_actual)
    campos_dto = extraer_campos(campos_plantilla, [pagina], diseno=diseno_de_version(plantilla.version_actual))
    obligatorios = {c.nombre for c in campos_plantilla if c.obligatorio}
    clasificacion = Clasificacion(
        tipo=plantilla.Codigo, plantilla_id=plantilla.PlantillaId, version_id=plantilla.version_actual.PlantillaVersionId, confianza=1.0
    )
    return ensamblador_mod.ensamblar(
        [pagina], clasificacion, campos_dto, [], obligatorios, {"total": 0}, resultado_guardado.MotorOcr or ""
    )
