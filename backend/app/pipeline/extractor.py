"""Extractor: aplica la regla de cada campo (regex/ancla/zona) sobre el OCR."""
from __future__ import annotations

import logging
import re
import unicodedata
from collections.abc import Callable

from rapidfuzz import fuzz

from ..dominio.modelos import CampoExtraidoDTO, CampoPlantillaDTO, PaginaOCR, PalabraOCR
from .validadores import validar_normalizar

logger = logging.getLogger(__name__)


def _sin_acentos(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def _normaliza(s: str) -> str:
    return _sin_acentos(s or "").lower().strip()


def _texto_completo(paginas: list[PaginaOCR]) -> str:
    return "\n".join(p.texto for p in paginas)


def _pagina_de_offset(paginas: list[PaginaOCR], offset: int) -> int:
    acumulado = 0
    for p in paginas:
        fin = acumulado + len(p.texto) + 1  # +1 por el '\n' de unión
        if offset < fin:
            return p.numero
        acumulado = fin
    return paginas[-1].numero if paginas else 1


def _confianza_region(palabras: list[PalabraOCR], texto_buscado: str) -> float:
    """Confianza media de las palabras del OCR cuyo texto participa de texto_buscado."""
    if not palabras or not texto_buscado:
        return 0.5
    objetivo = _normaliza(texto_buscado)
    coincidentes = [p.confianza for p in palabras if _normaliza(p.texto) and _normaliza(p.texto) in objetivo]
    if not coincidentes:
        return 0.5
    return sum(coincidentes) / len(coincidentes)


# --------------------------------------------------------------------- regex
def _extraer_regex(campo: CampoPlantillaDTO, paginas: list[PaginaOCR]) -> tuple[str | None, int | None, float]:
    if not campo.regla.regex:
        return None, None, 0.0
    flags = re.IGNORECASE if campo.regla.flags and "i" in campo.regla.flags else 0
    texto = _texto_completo(paginas)
    m = re.search(campo.regla.regex, texto, flags)
    if not m:
        return None, None, 0.0
    # con alternativas (a|b) el valor está en el primer grupo que participó del calce
    valor = next((g for g in m.groups() if g), None) if m.groups() else m.group(0)
    if valor is None:
        valor = m.group(0)
    pagina = _pagina_de_offset(paginas, m.start())
    p = next((p for p in paginas if p.numero == pagina), paginas[0] if paginas else None)
    conf = _confianza_region(p.palabras if p else [], valor)
    return valor, pagina, conf


# --------------------------------------------------------------------- ancla
# "APELLIDOS Y NOMBRES DEL PADRE": el ancla "Nombres" forma parte de una etiqueta más larga (otro campo),
# no es la etiqueta buscada. Tomarla devolvería el valor equivocado sin ninguna advertencia.
_CONECTORES_ANTES = {"y", "e"}
_CONECTORES_DESPUES = {"y", "e", "de", "del", "la", "las", "los", "el"}


def _ventana_ancla(palabras_norm: list[str], ancla_norm: str) -> tuple[int, int]:
    """(inicio, fin) de las palabras de la línea que mejor calzan con el ancla."""
    n = max(1, len(ancla_norm.split()))
    mejor, mejor_score = 0, 0.0
    for start in range(len(palabras_norm)):
        sc = fuzz.ratio(ancla_norm, " ".join(palabras_norm[start : start + n]))
        if sc > mejor_score:
            mejor_score, mejor = sc, start
    return mejor, min(len(palabras_norm), mejor + n)


# "... DEL PADRE / DE LA MADRE": etiqueta de otra persona. Exige el conector: "Av. Padre Hurtado" es un valor.
_RE_PARENTESCO = re.compile(r"\b(?:del?|de la)\s+(?:padr|madr|conyug)")


def _es_etiqueta_compuesta(
    palabras: list[str],
    palabras_norm: list[str],
    inicio: int,
    fin: int,
    ancla_norm: str = "",
    otras_anclas: tuple[str, ...] = (),
) -> bool:
    """¿La línea es una etiqueta más larga (de otro campo) que solo contiene a esta ancla?

    No depende de la tokenización del motor OCR: algunos motores pegan el conector a la palabra
    ("YNOMBRES"), así que además de comparar tokens se mira el texto restante de la línea."""
    if palabras[fin - 1].rstrip().endswith(":"):
        return False  # "Nombres: ..." es una etiqueta explícita
    if inicio > 0 and palabras_norm[inicio - 1] in _CONECTORES_ANTES:
        return True
    if fin < len(palabras) and palabras_norm[fin] in _CONECTORES_DESPUES:
        return True
    # conector pegado a la palabra del ancla: "ynombres" (antes) o "apellidosy" (después)
    primera = ancla_norm.split()[0] if ancla_norm.split() else ""
    ultima = ancla_norm.split()[-1] if ancla_norm.split() else ""
    pal_ini, pal_fin = palabras_norm[inicio], palabras_norm[fin - 1]
    if primera and pal_ini != primera and pal_ini.endswith(primera) and pal_ini[: -len(primera)] in _CONECTORES_ANTES:
        return True
    if ultima and pal_fin != ultima and pal_fin.startswith(ultima) and pal_fin[len(ultima) :] in _CONECTORES_ANTES:
        return True
    # solo las palabras contiguas al ancla: una etiqueta compuesta es corta ("... DEL PADRE"); mirar toda la
    # línea descartaría valores legítimos ("Dirección Av. Padre Hurtado 123" si el OCR pierde los ':')
    fuera = " ".join(palabras_norm[max(0, inicio - 3) : inicio] + palabras_norm[fin : fin + 4])
    if _RE_PARENTESCO.search(fuera):
        return True
    # el resto de la línea contiene la etiqueta de OTRO campo de la plantilla ("APELLIDOS ... NOMBRES")
    return any(a and a in fuera for a in otras_anclas)


def _posiciones_ancla(lineas: list[str], ancla_norm: str) -> list[tuple[int, float]]:
    """Líneas candidatas (índice, score), de mejor a peor; a igual score, la primera del documento."""
    cands = []
    for i, linea in enumerate(lineas):
        score = fuzz.partial_ratio(ancla_norm, _normaliza(linea))
        if score >= 70:
            cands.append((i, score))
    cands.sort(key=lambda t: (-t[1], t[0]))
    return cands


# Etiquetas que delimitan el bloque de valores de una etiqueta combinada (otra etiqueta del documento, no un valor)
_RE_OTRA_ETIQUETA = re.compile(
    r"\b(?:lugar|fecha|nacimiento|nacionalidad|sexo|estado|civil|firma|domicilio|profesion|instruccion|"
    r"conyuge|padres?|madres?|emision|expedicion|vencimiento|numero|cedula|identificacion|registro)\b"
)
_LINEAS_BUSQUEDA_COMBINADA = 6


def _limpiar_valor_combinado(linea: str) -> str:
    """Quita el ruido del OCR en los extremos de la línea ("#) [1] - FELIX FRANCISCO" -> "FELIX FRANCISCO").
    Se conservan las palabras cortas del medio ("DE", "LA"): solo se recortan extremos sin ≥2 letras seguidas."""
    palabras = linea.split()

    def ruido(p: str) -> bool:
        return not (p.isalpha() and len(p) >= 2)

    while palabras and ruido(palabras[0]):
        palabras.pop(0)
    while palabras and ruido(palabras[-1]):
        palabras.pop()
    return " ".join(palabras)


def _valor_etiqueta_combinada(
    lineas: list[str], idx: int, ancla_norm: str, otras_anclas: tuple[str, ...]
) -> str | None:
    """Etiqueta combinada ("APELLIDOS Y NOMBRES"): el k-ésimo valor es la k-ésima línea de texto que sigue,
    donde k es la posición de esta ancla dentro de la etiqueta. None si la línea no es una etiqueta combinada."""
    linea_norm = _normaliza(lineas[idx])
    if _RE_PARENTESCO.search(linea_norm):
        return None  # "Apellidos y nombres del padre": es de otra persona
    propia = linea_norm.find(ancla_norm)
    if propia < 0:
        return None
    otras = [p for a in otras_anclas if (p := linea_norm.find(a)) >= 0]
    if not otras:
        return None
    k = sum(1 for p in otras if p < propia)
    valores: list[str] = []
    for linea in lineas[idx + 1 : idx + 1 + _LINEAS_BUSQUEDA_COMBINADA]:
        norm = _normaliza(linea)
        if _RE_OTRA_ETIQUETA.search(norm) or ancla_norm in norm or any(a in norm for a in otras_anclas):
            break  # otra etiqueta (con su propio valor): ya no son valores de la etiqueta combinada
        valor = _limpiar_valor_combinado(linea)
        if sum(c.isalpha() for c in valor) >= 3:
            valores.append(valor)
        if len(valores) > k:
            return valores[k]
    return None


def _extraer_ancla(
    campo: CampoPlantillaDTO, paginas: list[PaginaOCR], otras_anclas: tuple[str, ...] = ()
) -> tuple[str | None, int | None, float]:
    ancla = campo.regla.ancla or ""
    if not ancla:
        return None, None, 0.0
    ancla_norm = _normaliza(ancla)
    for pagina in paginas:
        lineas = [l for l in pagina.texto.split("\n") if l.strip()]
        for idx, score in _posiciones_ancla(lineas, ancla_norm):
            linea = lineas[idx]
            palabras_linea = linea.split()
            palabras_norm = [_normaliza(w) for w in palabras_linea]
            inicio, fin_ancla = _ventana_ancla(palabras_norm, ancla_norm)
            if _es_etiqueta_compuesta(palabras_linea, palabras_norm, inicio, fin_ancla, ancla_norm, otras_anclas):
                # etiqueta combinada ("APELLIDOS Y NOMBRES"): los valores van en las líneas siguientes, en el mismo orden
                combinado = _valor_etiqueta_combinada(lineas, idx, ancla_norm, otras_anclas)
                if combinado:
                    return combinado, pagina.numero, _confianza_region(pagina.palabras, combinado) * (score / 100.0)
                continue  # etiqueta de otro campo (p. ej. "... del Padre"): probar la siguiente candidata
            resto = " ".join(palabras_linea[fin_ancla:]).strip(" :.-\t")
            if not resto and campo.regla.misma_linea and idx + 1 < len(lineas):
                resto = lineas[idx + 1].strip()
            if campo.regla.regex and resto:
                flags = re.IGNORECASE if campo.regla.flags and "i" in campo.regla.flags else 0
                m = re.search(campo.regla.regex, resto, flags)
                resto = (m.group(1) if m and m.groups() else m.group(0)) if m else None
            if resto:
                conf = _confianza_region(pagina.palabras, resto) * (score / 100.0)
                return resto, pagina.numero, conf
    return None, None, 0.0


# --------------------------------------------------------------------- zona
def _extraer_zona(campo: CampoPlantillaDTO, paginas: list[PaginaOCR]) -> tuple[str | None, int | None, float]:
    r = campo.regla
    num_pagina = r.pagina or 1
    pagina = next((p for p in paginas if p.numero == num_pagina), None)
    if not pagina or not pagina.ancho or not pagina.alto:
        return None, None, 0.0
    x0 = (r.x or 0.0) * pagina.ancho
    y0 = (r.y or 0.0) * pagina.alto
    x1 = x0 + (r.ancho or 1.0) * pagina.ancho
    y1 = y0 + (r.alto or 1.0) * pagina.alto
    seleccion = [
        p
        for p in pagina.palabras
        if x0 <= p.x + p.ancho / 2 <= x1 and y0 <= p.y + p.alto / 2 <= y1
    ]
    if not seleccion:
        return None, None, 0.0
    seleccion.sort(key=lambda p: (p.linea, p.x))
    texto = " ".join(p.texto for p in seleccion)
    if r.regex and texto:
        flags = re.IGNORECASE if r.flags and "i" in r.flags else 0
        m = re.search(r.regex, texto, flags)
        texto = (m.group(1) if m and m.groups() else m.group(0)) if m else None
    if not texto:
        return None, None, 0.0
    conf = sum(p.confianza for p in seleccion) / len(seleccion)
    return texto, num_pagina, conf


def extraer_campo(
    campo: CampoPlantillaDTO, paginas: list[PaginaOCR], otras_anclas: tuple[str, ...] = ()
) -> CampoExtraidoDTO:
    metodo = campo.regla.metodo
    if metodo == "regex":
        valor_texto, pagina, conf_ocr = _extraer_regex(campo, paginas)
    elif metodo == "ancla":
        valor_texto, pagina, conf_ocr = _extraer_ancla(campo, paginas, otras_anclas)
    elif metodo == "zona":
        valor_texto, pagina, conf_ocr = _extraer_zona(campo, paginas)
    else:
        valor_texto, pagina, conf_ocr = None, None, 0.0

    valor_norm, valido = validar_normalizar(campo.tipo_dato, valor_texto)
    # confianza combinada: OCR de la región * (1.0 si el validador aceptó, penaliza si no)
    confianza = conf_ocr if valido else conf_ocr * 0.4
    if valor_texto is None:
        confianza = 0.0
    pag_motor = next((p for p in paginas if p.numero == pagina), paginas[0] if paginas else None)
    return CampoExtraidoDTO(
        nombre=campo.nombre,
        campo_plantilla_id=campo.id,
        valor=valor_norm if valido else valor_texto,
        valor_texto=valor_texto,
        confianza=round(confianza, 3),
        pagina=pagina,
        valido=valido,
        motor=pag_motor.motor if (pag_motor and valor_texto is not None) else None,
    )


def _otras_anclas(campo: CampoPlantillaDTO, campos: list[CampoPlantillaDTO]) -> tuple[str, ...]:
    """Anclas (normalizadas, >= 4 letras) de los demás campos de la plantilla, que no sean
    ni contengan ni estén contenidas en la del campo actual."""
    propia = _normaliza(campo.regla.ancla or "")
    otras = []
    for c in campos:
        a = _normaliza(c.regla.ancla or "") if c.regla.metodo == "ancla" else ""
        if len(a) >= 4 and a != propia and a not in propia and propia not in a:
            otras.append(a)
    return tuple(otras)


def _mejor(a: CampoExtraidoDTO, b: CampoExtraidoDTO) -> CampoExtraidoDTO:
    """Elige entre la lectura del motor principal (a) y la de segunda opinión (b)."""
    if a.valor_texto is None:
        return b if b.valor_texto is not None else a
    if b.valor_texto is None:
        return a
    if a.valido != b.valido:
        return a if a.valido else b
    if a.valor == b.valor:
        # Ambos motores coinciden: validación cruzada, se conserva la mayor confianza.
        return a if a.confianza >= b.confianza else b
    return b if b.confianza > a.confianza else a


def extraer_campos(
    campos: list[CampoPlantillaDTO],
    paginas: list[PaginaOCR],
    segunda_opinion: Callable[[], list[PaginaOCR] | None] | None = None,
    umbral_segunda_opinion: float = 0.7,
) -> list[CampoExtraidoDTO]:
    """Extrae todos los campos. Si se entrega `segunda_opinion` (callable perezoso que relee el
    documento con otro motor), los campos con confianza < umbral se reextraen con él y se
    conserva la mejor lectura. El callable solo se invoca si hay al menos un campo bajo umbral."""
    resultados = [extraer_campo(c, paginas, _otras_anclas(c, campos)) for c in campos]
    if segunda_opinion is None:
        return resultados
    pendientes = [i for i, r in enumerate(resultados) if r.confianza < umbral_segunda_opinion]
    if not pendientes:
        return resultados
    alt = segunda_opinion()
    if not alt:
        return resultados
    for i in pendientes:
        alternativo = extraer_campo(campos[i], alt, _otras_anclas(campos[i], campos))
        elegido = _mejor(resultados[i], alternativo)
        if elegido is alternativo:
            logger.info(
                "Campo '%s': segunda opinión mejora la lectura (%r -> %r)",
                campos[i].nombre, resultados[i].valor_texto, alternativo.valor_texto,
            )
        resultados[i] = elegido
    return resultados
