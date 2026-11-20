"""Ensamblador: construye el ResultadoDTO final (confianza global, advertencias)."""
from __future__ import annotations

from ..dominio.modelos import CampoExtraidoDTO, Clasificacion, PaginaOCR, ResultadoDTO


def confianza_global(clasificacion: Clasificacion, campos: list[CampoExtraidoDTO], obligatorios: set[str]) -> float:
    componentes = [clasificacion.confianza]
    pesos = [0.4]
    if campos:
        conf_campos = sum(c.confianza for c in campos) / len(campos)
        componentes.append(conf_campos)
        pesos.append(0.6)
    total_peso = sum(pesos)
    return sum(c * p for c, p in zip(componentes, pesos)) / total_peso if total_peso else 0.0


def construir_advertencias(campos: list[CampoExtraidoDTO], obligatorios: set[str]) -> list[str]:
    advertencias = []
    for c in campos:
        if c.nombre in obligatorios and (c.valor is None or not c.valido):
            advertencias.append(f"campo_obligatorio_faltante:{c.nombre}")
        elif not c.valido and c.valor_texto:
            advertencias.append(f"campo_no_valido:{c.nombre}")
        if c.fuera_de_zona:
            advertencias.append(f"campo_fuera_de_zona:{c.nombre}")
    return advertencias


def ensamblar(
    paginas: list[PaginaOCR],
    clasificacion: Clasificacion,
    campos: list[CampoExtraidoDTO],
    palabras_clave_encontradas: list[str],
    obligatorios: set[str],
    tiempos_ms: dict[str, int],
    motor_ocr: str,
) -> ResultadoDTO:
    texto_completo = "\n".join(p.texto for p in paginas)
    advertencias = construir_advertencias(campos, obligatorios)
    conf_global = confianza_global(clasificacion, campos, obligatorios)
    return ResultadoDTO(
        paginas=paginas,
        clasificacion=clasificacion,
        campos=campos,
        palabras_clave=palabras_clave_encontradas,
        texto_completo=texto_completo,
        confianza_global=conf_global,
        advertencias=advertencias,
        tiempos_ms=tiempos_ms,
        motor_ocr=motor_ocr,
    )
