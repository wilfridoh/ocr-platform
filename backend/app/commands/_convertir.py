"""Helpers para convertir modelos ORM (persistencia) en DTOs de dominio (pipeline)."""
from __future__ import annotations

import json

from ..dominio.modelos import CampoPlantillaDTO, PalabraClaveDTO, ReglaCampo
from ..persistencia import modelos as m


def campos_de_version(version: m.PlantillaVersion) -> list[CampoPlantillaDTO]:
    campos = []
    for c in sorted(version.campos, key=lambda x: x.Orden):
        regla_dict = json.loads(c.ReglaJson)
        campos.append(
            CampoPlantillaDTO(
                id=c.CampoPlantillaId,
                nombre=c.Nombre,
                etiqueta=c.Etiqueta,
                tipo_dato=c.TipoDato,
                obligatorio=c.Obligatorio,
                regla=ReglaCampo(**regla_dict),
                orden=c.Orden,
            )
        )
    return campos


def palabras_clave_de_version(version: m.PlantillaVersion) -> list[PalabraClaveDTO]:
    return [PalabraClaveDTO(texto=p.Texto, peso=p.Peso) for p in version.palabras_clave]
