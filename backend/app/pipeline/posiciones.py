"""Posición de las palabras del OCR y datos del recorte, para guardarlos con el resultado (docs/13 §1.3).

Formato guardado en Resultado.PalabrasJson (compacto: una cédula ronda 5-15 KB):

    {"v": 1, "paginas": [{"numero": 1, "motor": "paddle", "ancho": 1500, "alto": 946,
                          "palabras": [[texto, x, y, ancho, alto, confianza], ...]}]}

x, y, ancho y alto son relativos (0-1) a la imagen sobre la que leyó el OCR (ya recortada y enderezada), con 4
decimales; confianza con 3. Resultado.RecorteJson: {"v": 1, "paginas": [{"numero": 1, ...datos del recorte}]}.
Contienen los mismos datos que TextoCompleto, con su posición: misma retención, purga y permisos.
"""
from __future__ import annotations

import json
from typing import Any

from ..dominio.modelos import PaginaOCR

VERSION_FORMATO = 1


def palabras_json(paginas: list[PaginaOCR]) -> str | None:
    """Serializa las palabras con posición relativa; None si ninguna página trae dimensiones o palabras."""
    salida = []
    for p in paginas:
        if not p.ancho or not p.alto or not p.palabras:
            continue
        salida.append(
            {
                "numero": p.numero,
                "motor": p.motor,
                "ancho": p.ancho,
                "alto": p.alto,
                "palabras": [
                    [
                        w.texto,
                        round(w.x / p.ancho, 4),
                        round(w.y / p.alto, 4),
                        round(w.ancho / p.ancho, 4),
                        round(w.alto / p.alto, 4),
                        round(float(w.confianza), 3),
                    ]
                    for w in p.palabras
                ],
            }
        )
    if not salida:
        return None
    return json.dumps({"v": VERSION_FORMATO, "paginas": salida}, ensure_ascii=False, separators=(",", ":"))


def recorte_json(paginas: list[PaginaOCR]) -> str | None:
    salida = [{"numero": p.numero, **p.recorte} for p in paginas if p.recorte]
    if not salida:
        return None
    return json.dumps({"v": VERSION_FORMATO, "paginas": salida}, ensure_ascii=False, separators=(",", ":"))


def leer_palabras(texto_json: str | None) -> dict[int, list[dict[str, Any]]]:
    """Inverso de palabras_json: {numero_pagina: [{texto, x, y, ancho, alto, confianza}]} (vacío si no hay)."""
    if not texto_json:
        return {}
    datos = json.loads(texto_json)
    return {
        pag["numero"]: [
            {"texto": t, "x": x, "y": y, "ancho": an, "alto": al, "confianza": c} for t, x, y, an, al, c in pag["palabras"]
        ]
        for pag in datos.get("paginas", [])
    }


def leer_recorte(texto_json: str | None) -> dict[int, dict[str, Any]]:
    if not texto_json:
        return {}
    return {pag["numero"]: {k: v for k, v in pag.items() if k != "numero"} for pag in json.loads(texto_json).get("paginas", [])}
