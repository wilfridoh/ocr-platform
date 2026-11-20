"""Coincidencia de diseño de un documento con su plantilla (docs/13 §3) y sugerencia de otra plantilla con diseño
cuando no coincide. Valida el DISEÑO (textos impresos en su sitio), no la autenticidad."""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..dominio.modelos import CampoExtraidoDTO, CampoPlantillaDTO, Clasificacion, DisenoPlantilla, PaginaOCR
from ..persistencia import modelos as m
from ..persistencia import repositorios as repo
from ..pipeline.zonas import calcular_coincidencia
from ._convertir import campos_de_version, diseno_de_version


def evaluar_coincidencia(
    db: Session,
    paginas: list[PaginaOCR],
    campos_plantilla: list[CampoPlantillaDTO],
    diseno: DisenoPlantilla | None,
    campos_extraidos: list[CampoExtraidoDTO],
    clasificacion: Clasificacion | None = None,
) -> dict | None:
    """Bloque `coincidencia` del resultado; None si la plantilla no tiene cuadrícula. Si el diseño se puede verificar y
    no coincide, mira las otras candidatas de la clasificación que tengan diseño (sin releer: mismas cajas, < 10 ms) y
    sugiere la mejor que supere su umbral."""
    coincidencia = calcular_coincidencia(paginas, campos_plantilla, diseno, campos_extraidos)
    if coincidencia is None:
        return None
    coincidencia["sugerencia"] = None
    if coincidencia["verificable"] and coincidencia["veredicto"] != "coincide" and clasificacion is not None:
        mejor = None
        for alt in clasificacion.alternativas:
            if not alt.plantilla_id or alt.plantilla_id == clasificacion.plantilla_id:
                continue
            plantilla = repo.obtener_plantilla(db, alt.plantilla_id)
            version: m.PlantillaVersion | None = plantilla.version_actual if plantilla else None
            diseno_alt = diseno_de_version(version)
            if diseno_alt is None:
                continue
            otra = calcular_coincidencia(paginas, campos_de_version(version), diseno_alt)
            if otra and otra["verificable"] and otra["puntaje"] >= diseno_alt.umbral_coincidencia:
                if mejor is None or otra["puntaje"] > mejor["puntaje"]:
                    mejor = {"plantilla_id": plantilla.PlantillaId, "codigo": plantilla.Codigo, "puntaje": otra["puntaje"]}
        coincidencia["sugerencia"] = mejor
    return coincidencia
