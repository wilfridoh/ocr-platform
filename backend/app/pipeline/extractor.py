"""Extractor: aplica la regla de cada campo (regex/ancla/zona) sobre el OCR."""
from __future__ import annotations

import logging
import re
import unicodedata
from collections.abc import Callable
from datetime import date
from functools import lru_cache

from rapidfuzz import fuzz
from rapidfuzz.distance import Levenshtein

from ..dominio.modelos import CampoExtraidoDTO, CampoPlantillaDTO, DisenoPlantilla, PaginaOCR, PalabraOCR
from .validadores import validar_normalizar
from .zonas import MarcoPagina, calcular_marcos, girar_paginas_180, orientar_paginas, texto_en_zona, zona_valor

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
    if not coincidentes and len(objetivo) >= 4:
        # El valor va PEGADO a su etiqueta en una sola palabra del OCR ("NUI.1234567890"): ninguna palabra cabe
        # dentro del valor, pero el valor sí está dentro de una palabra. Sin esto la confianza caía a 0,5 y un campo
        # bien leído pedía segunda opinión (lenta) sin necesidad.
        coincidentes = [p.confianza for p in palabras if objetivo in _normaliza(p.texto)]
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


def _posicion_ancla_en_linea(linea_norm: str, ancla_norm: str) -> int:
    """Posición del ancla en la línea, tolerando errores de OCR en la palabra ("nom8res" por "nombres"); -1 si no está."""
    pos = linea_norm.find(ancla_norm)
    if pos >= 0 or " " in ancla_norm:
        return pos
    for m in re.finditer(r"\S+", linea_norm):
        if len(m.group()) >= 4 and fuzz.ratio(ancla_norm, m.group()) >= 80:
            return m.start()
    return -1


def _valor_etiqueta_combinada(
    lineas: list[str], idx: int, ancla_norm: str, otras_anclas: tuple[str, ...]
) -> str | None:
    """Etiqueta combinada ("APELLIDOS Y NOMBRES"): el k-ésimo valor es la k-ésima línea de texto que sigue,
    donde k es la posición de esta ancla dentro de la etiqueta. None si la línea no es una etiqueta combinada."""
    linea_norm = _normaliza(lineas[idx])
    if _RE_PARENTESCO.search(linea_norm):
        return None  # "Apellidos y nombres del padre": es de otra persona
    propia = _posicion_ancla_en_linea(linea_norm, ancla_norm)
    if propia < 0:
        return None
    otras = [p for a in otras_anclas if (p := _posicion_ancla_en_linea(linea_norm, a)) >= 0]
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


# Palabras que solo aparecen en etiquetas de un documento de identidad (no en valores): una línea formada solo por
# ellas, o por ruido, es una etiqueta ("CONDICIÓN CIUDADANÍA"), no el valor de la etiqueta anterior.
_PALABRAS_ETIQUETA = frozenset(
    "lugar fecha nacimiento nacionalidad sexo estado civil firma domicilio profesion instruccion conyuge padre madre "
    "emision expedicion vencimiento numero cedula identidad identificacion registro condicion ciudadania ciudadano "
    "autoidentificacion apellidos nombres titular cedulado".split()
)


def _sin_ruido(linea: str) -> str:
    """Recorta los extremos de la línea que no tienen ni dos letras seguidas (restos de OCR: "#)", "[1]", "-")."""
    palabras = linea.split()
    sin_letras = lambda p: not re.search(r"[A-Za-z0-9ÁÉÍÓÚÑáéíóúñ]{2}", p)  # noqa: E731
    while palabras and sin_letras(palabras[0]):
        palabras.pop(0)
    while palabras and sin_letras(palabras[-1]):
        palabras.pop()
    return " ".join(palabras)


def _es_linea_de_etiqueta_o_ruido(linea: str) -> bool:
    util = _sin_ruido(linea)
    tokens = _PUNTUACION_TOKEN.sub(" ", _normaliza(util)).split()
    if not any(len(t) >= 3 for t in tokens):
        return True  # nada legible ("#)", "Ma", "..")
    return all(t in _PALABRAS_ETIQUETA or (len(t) < 3 and not t.isdigit()) for t in tokens)


_PUNTUACION_TOKEN = re.compile(r"[^\w\s]")


def _valor_en_lineas_siguientes(
    lineas: list[str], idx: int, ancla_norm: str, otras_anclas: tuple[str, ...], unir: int
) -> str | None:
    """Valor de una etiqueta cuyo texto está en las líneas de abajo: salta líneas que son otra etiqueta o ruido
    ("CONDICIÓN CIUDADANÍA"), toma la primera con texto y, si `unir` > 1, las siguientes consecutivas (apellidos en
    dos líneas) mientras sean texto de nombre (solo letras) y no una etiqueta/ancla."""
    valores: list[str] = []
    for linea in lineas[idx + 1 : idx + 1 + 5]:
        norm = _normaliza(linea)
        es_ancla = ancla_norm in norm or any(a in norm for a in otras_anclas)
        if es_ancla or _es_linea_de_etiqueta_o_ruido(linea):
            if valores:
                break  # ya hay valor: lo siguiente es otra etiqueta
            if es_ancla or _RE_OTRA_ETIQUETA.search(norm):
                return None  # empieza OTRO campo ("FECHA DE NACIMIENTO"): este no tiene valor; no tomar el ajeno
            continue  # etiqueta sin valor propio al lado ("CONDICIÓN CIUDADANÍA") o ruido: seguir buscando
        util = _sin_ruido(linea)
        if unir > 1:  # valores tipo nombre: restos cortos al final de la línea ("SOTO - Dn") son ruido del OCR
            palabras = util.split()
            while len(palabras) > 1 and (len(palabras[-1]) < 3 or not palabras[-1].isalpha()):
                palabras.pop()
            util = " ".join(palabras)
        if valores and not re.fullmatch(r"[A-Za-zÁÉÍÓÚÑáéíóúñ ]+", util):
            break  # solo se unen líneas que parecen nombre
        valores.append(util)
        if len(valores) >= max(1, unir):
            break
    return " ".join(valores) if valores else None


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
            if resto and _es_linea_de_etiqueta_o_ruido(resto):
                resto = ""  # tras la ancla solo hay otra etiqueta o ruido: el valor está en las líneas siguientes
            if not resto and campo.regla.misma_linea and idx + 1 < len(lineas):
                resto = _valor_en_lineas_siguientes(lineas, idx, ancla_norm, otras_anclas, campo.regla.lineas) or ""
            if campo.regla.regex and resto:
                flags = re.IGNORECASE if campo.regla.flags and "i" in campo.regla.flags else 0
                m = re.search(campo.regla.regex, resto, flags)
                resto = (m.group(1) if m and m.groups() else m.group(0)) if m else None
            if resto:
                conf = _confianza_region(pagina.palabras, resto) * (score / 100.0)
                return resto, pagina.numero, conf
    return None, None, 0.0


# --------------------------------------------------------------------- zona
def _aplicar_regex_zona(campo: CampoPlantillaDTO, texto: str) -> str | None:
    r = campo.regla
    if not r.regex or not texto:
        return texto or None
    flags = re.IGNORECASE if r.flags and "i" in r.flags else 0
    m = re.search(r.regex, texto, flags)
    return ((next((g for g in m.groups() if g), None) or m.group(0)) if m.groups() else m.group(0)) if m else None


def _extraer_zona(
    campo: CampoPlantillaDTO, paginas: list[PaginaOCR], marcos: dict | None = None
) -> tuple[str | None, int | None, float]:
    r = campo.regla
    num_pagina = r.pagina or 1
    marco = (marcos or {}).get(num_pagina)
    zona = zona_valor(campo)
    if marco is not None and zona is not None:
        # plantilla con diseño (docs/13 §2.3): con desplazamiento global y tolerancia; sin recorte fiable no hay zona
        if not marco.confiable:
            return None, None, 0.0
        texto, conf, _ = texto_en_zona(marco, zona)
        texto = _aplicar_regex_zona(campo, texto) if texto else None
        return (texto, num_pagina, conf) if texto else (None, None, 0.0)
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


_RE_FECHA_SUELTA = re.compile(
    r"(?<![\w/-])(?:([0-9lIO|]{1,2})[ .]{1,2}([A-Za-z]{3,10})[ .]{1,2}(\d{4})|(\d{1,2}[/-]\d{1,2}[/-]\d{4})|(\d{4}-\d{2}-\d{2}))(?!\d)"
)
_RE_CONTEXTO_OTRA_FECHA = re.compile(r"venc|emis|expedic|caduc")
_DIGITO_CONFUNDIDO = str.maketrans({"l": "1", "I": "1", "|": "1", "O": "0"})


def _fecha_nacimiento_sin_etiqueta(paginas: list[PaginaOCR]) -> tuple[str | None, int | None, float, bool]:
    """Respaldo cuando la etiqueta "FECHA DE NACIMIENTO" salió ilegible: la primera fecha del documento que no esté
    junto a "vencimiento/emisión" y que no sea futura (esa es de vencimiento). Confianza reducida: es una inferencia.

    Devuelve además si la lectura es DUDOSA: el día solo se entiende como número cambiando letras por dígitos
    ("1l" -> "11"). Una lectura dudosa se devuelve tal como se leyó para que quede como "no legible" (y para
    contrastarla con la segunda opinión), nunca como una fecha adivinada."""
    from .validadores import validar_fecha

    hoy = date.today().isoformat()
    for pagina in paginas:
        for m in _RE_FECHA_SUELTA.finditer(pagina.texto):
            if _RE_CONTEXTO_OTRA_FECHA.search(_normaliza(pagina.texto[max(0, m.start() - 60) : m.start()])):
                continue
            dudosa = False
            if m.group(1):
                dia = m.group(1).translate(_DIGITO_CONFUNDIDO)
                dudosa = dia != m.group(1)
                texto = f"{dia} {m.group(2)} {m.group(3)}"
            else:
                texto = m.group(0)
            iso, valido = validar_fecha(texto)
            if not valido or not iso:
                continue
            if iso > hoy:
                continue  # una fecha futura es de vencimiento, no de nacimiento
            conf = _confianza_region(pagina.palabras, m.group(0)) * 0.6
            return (m.group(0) if dudosa else texto), pagina.numero, conf, dudosa
    return None, None, 0.0, False


# ------------------------------------------------------------ fechas plausibles
def _desplazar_anios(d: date, anios: int) -> date:
    try:
        return d.replace(year=d.year + anios)
    except ValueError:  # 29 de febrero
        return d.replace(year=d.year + anios, day=28)


EDAD_MAXIMA = 120
VIGENCIA_MAXIMA_ANIOS = 30


def _rango_fecha(campo: CampoPlantillaDTO) -> tuple[date, date]:
    """Rango en que una fecha leída es plausible para el campo (docs/02-backend.md §4.6). Fuera de él la lectura se
    marca no válida en vez de guardar una fecha inventada (p. ej. "1320" por un año mal leído)."""
    hoy = date.today()
    nombre = _normaliza(f"{campo.nombre} {campo.etiqueta}")
    if "nacimiento" in nombre:
        return _desplazar_anios(hoy, -EDAD_MAXIMA), hoy
    if "venc" in nombre or "caduc" in nombre:
        return date(1900, 1, 1), _desplazar_anios(hoy, VIGENCIA_MAXIMA_ANIOS)
    return date(1900, 1, 1), _desplazar_anios(hoy, 100)


def _fecha_plausible(iso: str, campo: CampoPlantillaDTO) -> bool:
    try:
        d = date.fromisoformat(iso)
    except (TypeError, ValueError):
        return False
    desde, hasta = _rango_fecha(campo)
    return desde <= d <= hasta


# Letras que el OCR confunde con un dígito concreto. Otra letra en la posición de un dígito es ilegible (comodín).
_LETRA_DIGITO = {
    "l": "1", "I": "1", "i": "1", "|": "1", "!": "1", "O": "0", "o": "0", "D": "0", "Q": "0", "S": "5", "s": "5",
    "B": "8", "Z": "2", "z": "2", "G": "6", "b": "6", "g": "9", "q": "9", "T": "7",
}
_C = r"[0-9A-Za-z|!]"
_RE_PARTES_DMY = re.compile(rf"(?<![0-9A-Za-z])({_C}{{1,2}})[\s.,/-]{{1,3}}([A-Za-z]{{3,10}}|{_C}{{1,2}})[\s.,/-]{{1,3}}[A-Za-z]?({_C}{{3,4}})(?![0-9A-Za-z])")
_RE_PARTES_ISO = re.compile(rf"(?<![0-9A-Za-z])({_C}{{4}})-({_C}{{1,2}})-({_C}{{1,2}})(?![0-9A-Za-z])")


def _cifras_compatibles(leido: str, real: str) -> bool:
    """¿Lo leído (con posibles letras por dígitos) puede ser `real`? Se compara alineado a la derecha."""
    for c, r in zip(reversed(leido), reversed(real)):
        if c.isdigit():
            if c != r:
                return False
        elif c in _LETRA_DIGITO and _LETRA_DIGITO[c] != r:
            return False
    return True


def _fechas_en_conflicto(leido: str | None, iso: str) -> bool:
    """¿La lectura no válida del motor principal contradice la fecha (ISO) que leyó la segunda opinión? Hay conflicto
    si algún dígito legible (o letra que solo puede ser un dígito concreto) es distinto, o el mes es otro. Si la
    lectura principal no tiene forma de fecha, no hay con qué contrastar: no hay conflicto."""
    from .validadores import _mes_aproximado

    if not leido:
        return False
    try:
        real = date.fromisoformat(iso)
    except (TypeError, ValueError):
        return False
    m = _RE_PARTES_DMY.search(leido)
    if m:
        dia, mes, anio = m.group(1), m.group(2), m.group(3)
    else:
        m = _RE_PARTES_ISO.search(leido)
        if not m:
            return False
        anio, mes, dia = m.group(1), m.group(2), m.group(3)
    mes_num = int(mes) if mes.isdigit() else (_mes_aproximado(mes) if mes.isalpha() and len(mes) >= 3 else None)
    if mes_num is not None and mes_num != real.month:
        return True
    return not (_cifras_compatibles(dia, f"{real.day:02d}") and _cifras_compatibles(anio, f"{real.year:04d}"))


# ------------------------------------------------------------ catálogo de valores
_MIN_LARGO_DIFUSO = 7
_RE_TOKEN = re.compile(r"[0-9A-Za-zÁÉÍÓÚÜÑáéíóúüñ|!]+")


def _clave_catalogo(s: str) -> str:
    return _sin_acentos(s).upper()


def _en_catalogo(valor: str, catalogo: list[str]) -> str | None:
    """Forma canónica de `valor` si coincide con un elemento del catálogo o está a UN carácter de distancia de uno
    solo de ellos ("LCUATORIANA" -> "ECUATORIANA"). Lo difuso solo vale para elementos de 7+ letras: en palabras
    cortas un carácter cambia la palabra. Si queda a un carácter de dos elementos ("ECUATORIANX"), no se adivina."""
    v = _clave_catalogo(valor.strip())
    if not v:
        return None
    claves = _claves_catalogo(tuple(catalogo))
    for c, k in claves:
        if k == v:
            return c
    if len(v) < _MIN_LARGO_DIFUSO - 1:
        return None
    cercanos = [
        c for c, k in claves
        if len(k) >= _MIN_LARGO_DIFUSO and abs(len(k) - len(v)) <= 1 and Levenshtein.distance(v, k, score_cutoff=1) <= 1
    ]
    return cercanos[0] if len(cercanos) == 1 else None


@lru_cache(maxsize=64)
def _claves_catalogo(catalogo: tuple[str, ...]) -> tuple[tuple[str, str], ...]:
    return tuple((c, _clave_catalogo(c)) for c in catalogo)


def _canonico_seguro(campo: CampoPlantillaDTO, r: CampoExtraidoDTO) -> bool:
    """¿El valor es una forma canónica del catálogo del campo? Es un conjunto cerrado: la segunda opinión no lo
    mejora, así que un opcional así no la dispara aunque la palabra se haya leído con poca confianza."""
    return bool(campo.regla.catalogo) and r.valido and r.valor in campo.regla.catalogo


def _buscar_en_catalogo(
    catalogo: list[str], paginas: list[PaginaOCR]
) -> tuple[str | None, str | None, int | None, float]:
    """Primera palabra del documento que corresponde a un elemento del catálogo: (leída, canónica, página, conf)."""
    for pagina in paginas:
        for m in _RE_TOKEN.finditer(pagina.texto):
            canonico = _en_catalogo(m.group(), catalogo)
            if canonico:
                return m.group(), canonico, pagina.numero, _confianza_region(pagina.palabras, m.group())
    return None, None, None, 0.0


def extraer_campo(
    campo: CampoPlantillaDTO,
    paginas: list[PaginaOCR],
    otras_anclas: tuple[str, ...] = (),
    marcos: dict[int, MarcoPagina] | None = None,
) -> CampoExtraidoDTO:
    """`marcos` (calcular_marcos): solo con plantilla con diseño. Entonces la zona de valor del campo confirma, desempata
    o rescata la lectura de la etiqueta (docs/13 §2.2). Sin marcos, comportamiento de siempre."""
    metodo = campo.regla.metodo
    if metodo == "regex":
        valor_texto, pagina, conf_ocr = _extraer_regex(campo, paginas)
    elif metodo == "ancla":
        valor_texto, pagina, conf_ocr = _extraer_ancla(campo, paginas, otras_anclas)
    elif metodo == "zona":
        valor_texto, pagina, conf_ocr = _extraer_zona(campo, paginas, marcos)
    else:
        valor_texto, pagina, conf_ocr = None, None, 0.0

    dudosa = False
    if valor_texto is None and campo.tipo_dato == "fecha" and "nacimiento" in _normaliza(f"{campo.nombre} {campo.etiqueta}"):
        valor_texto, pagina, conf_ocr, dudosa = _fecha_nacimiento_sin_etiqueta(paginas)

    canonico = None
    if campo.regla.catalogo and valor_texto is None:
        valor_texto, canonico, pagina, conf_ocr = _buscar_en_catalogo(campo.regla.catalogo, paginas)

    base = _resultado_campo(campo, paginas, valor_texto, pagina, conf_ocr, dudosa, canonico)
    if marcos and metodo != "zona" and zona_valor(campo) is not None:
        base = _combinar_con_zona(campo, paginas, base, marcos)
    return base


def _resultado_campo(
    campo: CampoPlantillaDTO,
    paginas: list[PaginaOCR],
    valor_texto: str | None,
    pagina: int | None,
    conf_ocr: float,
    dudosa: bool = False,
    canonico: str | None = None,
) -> CampoExtraidoDTO:
    """Catálogo, validación y plausibilidad de una lectura ya ubicada: el mismo tratamiento venga de la etiqueta, de la
    regex o de la zona."""
    if campo.regla.catalogo and valor_texto is not None and canonico is None:
        canonico = _en_catalogo(valor_texto, campo.regla.catalogo)

    # se valida la forma canónica si la hay; valor_texto conserva lo que leyó el OCR
    valor_norm, valido = validar_normalizar(campo.tipo_dato, canonico or valor_texto)
    if campo.tipo_dato == "fecha" and valido and (dudosa or not _fecha_plausible(valor_norm, campo)):
        valido = False  # fecha imposible para el campo o leída a medias: "no legible", no una fecha inventada
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


FACTOR_ZONA = 0.8  # valor tomado solo de la zona (rescate o desempate): algo menos seguro que con etiqueta y zona
BONO_COINCIDENCIA = 0.05  # etiqueta y zona dicen lo mismo


def _coinciden(a: CampoExtraidoDTO, b: CampoExtraidoDTO) -> bool:
    if a.valido and b.valido and a.valor == b.valor:
        return True
    ta, tb = _normaliza(a.valor_texto or ""), _normaliza(b.valor_texto or "")
    if not ta or not tb:
        return False
    return ta in tb or tb in ta or fuzz.ratio(ta, tb) >= 90


def _combinar_con_zona(
    campo: CampoPlantillaDTO, paginas: list[PaginaOCR], base: CampoExtraidoDTO, marcos: dict[int, MarcoPagina]
) -> CampoExtraidoDTO:
    """Campo con etiqueta/regex Y zona de valor (docs/13 §2.2):
    - coinciden: se conserva la lectura de la etiqueta con +0,05 de confianza;
    - la etiqueta no encontró nada: se usa lo que hay en la zona (confianza x0,8);
    - discrepan: con el diseño verificado (recorte fiable y la mitad de las etiquetas fijas en su sitio) gana la zona si
      su valor es válido; si no, la etiqueta. En ambos casos queda la advertencia campo_fuera_de_zona.
    Sin recorte fiable la zona no se usa: comportamiento de siempre."""
    num = campo.regla.pagina or 1
    marco = marcos.get(num)
    zona = zona_valor(campo)
    if marco is None or not marco.confiable or zona is None:
        return base
    texto, conf, caja = texto_en_zona(marco, zona)
    texto = _aplicar_regex_zona(campo, texto) if texto else None
    z = _resultado_campo(campo, paginas, texto, num, conf) if texto else None
    if z is not None and caja:
        z.x, z.y, z.ancho, z.alto = round(caja[0], 4), round(caja[1], 4), round(caja[2] - caja[0], 4), round(caja[3] - caja[1], 4)

    if base.valor_texto is None:
        if z is not None and z.valido:
            z.confianza = round(z.confianza * FACTOR_ZONA, 3)
            return z
        return base
    if z is not None and _coinciden(base, z):
        base.confianza = round(min(1.0, base.confianza + BONO_COINCIDENCIA), 3)
        base.x, base.y, base.ancho, base.alto = z.x, z.y, z.ancho, z.alto
        return base
    if marco.verificado and z is not None and z.valido:
        logger.info("Campo '%s': la etiqueta leyó fuera de su zona; se usa el valor de la zona", campo.nombre)
        z.confianza = round(z.confianza * FACTOR_ZONA, 3)
        z.fuera_de_zona = True
        return z
    base.fuera_de_zona = True
    return base


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


def _mejor(a: CampoExtraidoDTO, b: CampoExtraidoDTO, tipo_dato: str = "texto") -> CampoExtraidoDTO:
    """Elige entre la lectura del motor principal (a) y la de segunda opinión (b)."""
    if a.valor_texto is None:
        return b if b.valor_texto is not None else a
    if b.valor_texto is None:
        return a
    if a.valido != b.valido:
        if b.valido and tipo_dato == "fecha" and _fechas_en_conflicto(a.valor_texto, b.valor):
            # los dos motores leyeron cifras distintas en la misma fecha ("1l.OCT 1320" frente a "10 OCT 1920"):
            # ninguna lectura es confiable; queda la del principal, marcada no válida, para revisión
            logger.info("Fecha en conflicto entre motores (%r / %r): queda no legible", a.valor_texto, b.valor_texto)
            return a
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
    solo_obligatorios: bool = False,
    diseno: DisenoPlantilla | None = None,
) -> list[CampoExtraidoDTO]:
    """Extrae todos los campos. Si se entrega `segunda_opinion` (callable perezoso que relee el
    documento con otro motor), los campos con confianza < umbral se reextraen con él y se
    conserva la mejor lectura. El callable solo se invoca si hay al menos un campo bajo umbral.

    Con `solo_obligatorios`, un campo NO obligatorio y vacío no dispara la relectura por sí solo: muchas variantes
    de un documento no traen impresos todos los opcionales (p. ej. una cédula sin fecha de vencimiento) y pagarían
    siempre la segunda opinión, que es lenta. Si la relectura entra por otro campo, los opcionales vacíos también
    se reintentan.

    Con `diseno` (plantilla con cuadrícula, docs/13) cada campo con zona de valor combina etiqueta y zona, y una página
    que encaja mejor girada 180° se gira en el lugar (cajas y orientación del recorte)."""
    giradas = orientar_paginas(paginas, campos, diseno)
    marcos = calcular_marcos(paginas, campos, diseno)
    resultados = [extraer_campo(c, paginas, _otras_anclas(c, campos), marcos) for c in campos]
    if segunda_opinion is None:
        return resultados
    pendientes = [i for i, r in enumerate(resultados) if r.confianza < umbral_segunda_opinion]
    if solo_obligatorios:
        disparan = [
            i for i in pendientes
            if campos[i].obligatorio
            or ((resultados[i].valor is not None or resultados[i].valor_texto) and not _canonico_seguro(campos[i], resultados[i]))
        ]
    else:
        disparan = pendientes
    if not disparan:
        return resultados
    alt = segunda_opinion()
    if not alt:
        return resultados
    if diseno is not None:
        # el segundo motor lee la MISMA imagen procesada: mismas cajas relativas, mismo giro y mismo recorte
        girar_paginas_180(alt, giradas)
        recortes = {p.numero: p.recorte for p in paginas}
        for p in alt:
            p.recorte = recortes.get(p.numero) or p.recorte
    marcos_alt = calcular_marcos(alt, campos, diseno)
    for i in pendientes:
        alternativo = extraer_campo(campos[i], alt, _otras_anclas(campos[i], campos), marcos_alt)
        elegido = _mejor(resultados[i], alternativo, campos[i].tipo_dato)
        if elegido is alternativo:
            logger.info(
                "Campo '%s': segunda opinión mejora la lectura (%r -> %r)",
                campos[i].nombre, resultados[i].valor_texto, alternativo.valor_texto,
            )
        resultados[i] = elegido
    return resultados
