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


def paginas_guardadas(texto_completo: str, palabras_json: str | None, recorte_json: str | None) -> list[PaginaOCR]:
    """Rehace las páginas del OCR a partir de lo guardado en el resultado (para /probar sin releer el documento).
    Sin posiciones guardadas (resultado anterior a la migración 009): una página solo con el texto, como antes."""
    from ..dominio.modelos import PalabraOCR

    if not palabras_json:
        return [PaginaOCR(numero=1, texto=texto_completo or "", palabras=[], confianza_media=1.0)]
    datos = json.loads(palabras_json)
    recortes = leer_recorte(recorte_json)
    paginas = []
    guardadas = datos.get("paginas", [])
    for pag in guardadas:
        w, h = pag.get("ancho") or 1, pag.get("alto") or 1
        palabras = [
            PalabraOCR(texto=t, x=int(round(x * w)), y=int(round(y * h)), ancho=max(1, int(round(an * w))),
                       alto=max(1, int(round(al * h))), confianza=c, linea=i, bloque=0, pagina=pag["numero"])
            for i, (t, x, y, an, al, c) in enumerate(pag["palabras"])
        ]
        # una sola página: el texto guardado tal cual (conserva los saltos de línea que leen las reglas); varias:
        # se rehace por líneas a partir de las cajas
        texto = texto_completo if len(guardadas) == 1 else _texto_por_lineas(palabras)
        conf = sum(p.confianza for p in palabras) / len(palabras) if palabras else 0.0
        paginas.append(PaginaOCR(numero=pag["numero"], texto=texto or "", palabras=palabras, confianza_media=conf,
                                 ancho=w, alto=h, motor=pag.get("motor"), recorte=recortes.get(pag["numero"])))
    return paginas or [PaginaOCR(numero=1, texto=texto_completo or "", palabras=[], confianza_media=1.0)]


def _texto_por_lineas(palabras) -> str:
    lineas: list[list] = []
    for p in sorted(palabras, key=lambda p: p.y + p.alto / 2):
        if lineas and abs((p.y + p.alto / 2) - (lineas[-1][-1].y + lineas[-1][-1].alto / 2)) <= 0.6 * max(p.alto, 1):
            lineas[-1].append(p)
        else:
            lineas.append([p])
    return "\n".join(" ".join(w.texto for w in sorted(linea, key=lambda w: w.x)) for linea in lineas)


TOLERANCIA_RELACION = 0.08


def recorte_confiable(recorte: dict[str, Any] | None, relacion_esperada: float | None = None) -> bool:
    """¿La página quedó recortada de forma fiable para dibujar/usar zonas encima? (docs/13 §4.1)
    - recorte marcado por una persona: sí;
    - con proporción esperada (de la plantilla, sin atarse a un formato): la página recortada, o la imagen que ya es el
      documento (un escaneo), está a ±8 % de esa proporción;
    - sin proporción esperada: se recortó automáticamente."""
    if not recorte:
        return False
    if recorte.get("origen") == "manual" and recorte.get("esquinas"):
        return True
    if relacion_esperada:
        relacion = recorte.get("relacion") or 0
        return abs(relacion - relacion_esperada) <= TOLERANCIA_RELACION * relacion_esperada
    return bool(recorte.get("aplicado"))


def leer_recorte(texto_json: str | None) -> dict[int, dict[str, Any]]:
    if not texto_json:
        return {}
    return {pag["numero"]: {k: v for k, v in pag.items() if k != "numero"} for pag in json.loads(texto_json).get("paginas", [])}
