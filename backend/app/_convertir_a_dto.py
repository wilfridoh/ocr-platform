"""Convierte modelos ORM (persistencia) en DTOs de dominio para las respuestas de la API."""
from __future__ import annotations

import json

from .dominio.modelos import CampoPlantillaDTO, DisenoPlantilla, PalabraClaveDTO, PlantillaDTO, ReglaCampo
from .persistencia import modelos as m


def plantilla_a_dto(p: m.Plantilla) -> PlantillaDTO:
    v = p.version_actual
    palabras_clave = [PalabraClaveDTO(texto=pc.Texto, peso=pc.Peso) for pc in (v.palabras_clave if v else [])]
    campos = []
    if v:
        for c in sorted(v.campos, key=lambda x: x.Orden):
            campos.append(
                CampoPlantillaDTO(
                    id=c.CampoPlantillaId,
                    nombre=c.Nombre,
                    etiqueta=c.Etiqueta,
                    tipo_dato=c.TipoDato,
                    obligatorio=c.Obligatorio,
                    regla=ReglaCampo(**json.loads(c.ReglaJson)),
                    orden=c.Orden,
                )
            )
    return PlantillaDTO(
        id=p.PlantillaId,
        codigo=p.Codigo,
        nombre=p.Nombre,
        descripcion=p.Descripcion,
        activa=p.Activa,
        umbral_confianza=float(v.UmbralConfianza) if v else 0.6,
        palabras_clave=palabras_clave,
        campos=campos,
        version_id=v.PlantillaVersionId if v else None,
        version=v.Numero if v else 1,
        rol_minimo_edicion=p.RolMinimoEdicion or "Editor",
        diseno=DisenoPlantilla.model_validate_json(v.DisenoJson) if v and v.DisenoJson else None,
        creado_en=p.CreadoEn,
        actualizado_en=p.ActualizadoEn,
    )
