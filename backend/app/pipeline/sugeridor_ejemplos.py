"""Sugerencia de palabras clave y etiquetas fijas con 1 a 3 ejemplos (docs/13 §5; entrega 5 de la cuadrícula).

Con UN ejemplo, TF-IDF premia lo único del documento, y lo más único son los datos del titular. Lo que identifica a
un tipo de documento es lo que se REPITE en todos sus ejemplares: con 2 o más ejemplos se toma lo común (los datos del
titular quedan fuera solos); con uno solo, se limita a vocabulario de etiquetas conocido o al encabezado, y cada
sugerencia sale marcada para revisar. Nada atado a un tipo de documento concreto: el léxico es amplio y solo filtra el
caso de un ejemplo.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from rapidfuzz import fuzz

from .sugeridor import STOPWORDS_ES

MAX_EJEMPLOS = 3
CONFIANZA_MINIMA = 0.85  # palabras leídas con menos confianza no se sugieren
FRANJA_ENCABEZADO = 0.2  # el 20 % superior de la página
SIMILITUD_ENTRE_EJEMPLOS = 85  # tolera errores de OCR al comparar ejemplos

STOPWORDS_EN = frozenset("a an and are as at be by for from in into is it of on or the th to with this that these those".split())
# palabras de etiquetas en inglés frecuentes en documentos bilingües: valen, pero por debajo de la mitad en español
PALABRAS_INGLES = frozenset(
    """surname surnames name names given nationality date birth sex gender place issue issued expiry expiration
    number license licence driver document identity card class category blood type address signature holder
    country republic personal""".split()
)
SIGLAS = frozenset({"nui", "ruc", "rut", "cc", "dni", "nit", "cui"})
# vocabulario típico de ETIQUETAS (no de valores) de documentos de identidad, facturas, planillas y licencias
LEXICO_ETIQUETAS = frozenset(
    """apellidos apellido nombres nombre nacionalidad fecha nacimiento sexo lugar emision expedicion vencimiento
    caducidad validez valida hasta numero documento cedula identidad identificacion registro civil republica licencia
    conducir categoria tipo sangre domicilio direccion firma titular estado profesion ciudadania ciudadano condicion
    autoidentificacion cliente cuenta contrato periodo consumo total pagar factura planilla servicio electrico agua
    medidor boleta comprobante valor saldo emisor receptor codigo restricciones observaciones donante clase serie
    folio unico""".split()
)
CONECTORES_INTERNOS = frozenset({"de", "del", "la", "las", "los", "el", "y", "e", "en", "a", "of", "the"})


def norm_palabra(s: str) -> str:
    s = "".join(c for c in unicodedata.normalize("NFD", (s or "").lower()) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z]", "", s)


@dataclass
class Ejemplo:
    """Un documento de ejemplo: su texto OCR y, si están guardadas, sus palabras con posición y confianza
    ({texto, x, y, ancho, alto, confianza}, relativas a la página; ver pipeline/posiciones.py)."""

    texto: str
    palabras: list[dict] = field(default_factory=list)

    def dudosas(self) -> set[str]:
        """Palabras leídas SOLO con poca confianza (si también aparecen bien leídas en otra parte, valen)."""
        bajas = {norm_palabra(p["texto"]) for p in self.palabras if p.get("confianza", 1) < CONFIANZA_MINIMA}
        altas = {norm_palabra(p["texto"]) for p in self.palabras if p.get("confianza", 1) >= CONFIANZA_MINIMA}
        return {w for w in bajas - altas if w}

    def encabezado(self) -> set[str]:
        return {norm_palabra(t) for p in self.palabras if p.get("y", 1) < FRANJA_ENCABEZADO for t in p["texto"].split()}


def segmentos(texto: str) -> list[list[str]]:
    """Líneas partidas en "/", "|" y ":" (las dos mitades de una etiqueta bilingüe son segmentos distintos), como
    listas de palabras normalizadas. Un segmento con cifras es un valor y se descarta entero."""
    salida = []
    for linea in (texto or "").split("\n"):
        for parte in re.split(r"[/|:]", linea):
            if re.search(r"\d", parte):
                continue
            palabras = [w for w in (norm_palabra(x) for x in parte.split()) if w]
            if palabras:
                salida.append(palabras)
    return salida


def util(w: str) -> bool:
    return (len(w) >= 3 or w in SIGLAS) and w not in STOPWORDS_ES and w not in STOPWORDS_EN


def palabras_utiles(frase: str) -> list[str]:
    return [w for w in frase.split() if util(w)]


def es_vocabulario_de_etiqueta(palabras: list[str]) -> bool:
    return bool(palabras) and all(w in LEXICO_ETIQUETAS or w in PALABRAS_INGLES or w in SIGLAS for w in palabras)


def _mezcla_idiomas(palabras: list[str]) -> bool:
    """"SEX FECHA DE NACIMIENTO" (fin en inglés de una etiqueta + la siguiente en español, en la misma línea)."""
    solo_ingles = any(w in PALABRAS_INGLES and w not in LEXICO_ETIQUETAS for w in palabras)
    solo_espanol = any(w in LEXICO_ETIQUETAS and w not in PALABRAS_INGLES for w in palabras)
    return solo_ingles and solo_espanol


def ngramas(ejemplo: Ejemplo, n_max: int = 3) -> set[str]:
    """Frases de 1 a n_max palabras útiles (pueden llevar conectores DENTRO: "fecha de nacimiento"), sin palabras
    leídas con poca confianza, sin cruzar de una mitad a otra de una etiqueta bilingüe ni mezclar sus idiomas."""
    dudosas = ejemplo.dudosas()
    salida: set[str] = set()
    for seg in segmentos(ejemplo.texto):
        for i in range(len(seg)):
            if not util(seg[i]) or seg[i] in dudosas:
                continue
            utiles = 0
            for j in range(i, len(seg)):
                w = seg[j]
                if w in dudosas:
                    break
                if util(w):
                    utiles += 1
                    if utiles > n_max:
                        break
                    if _mezcla_idiomas(seg[i : j + 1]):
                        break
                    salida.add(" ".join(seg[i : j + 1]))
                elif w not in CONECTORES_INTERNOS:
                    break
    return salida


def _en_todos(candidato: str, otros: list[set[str]]) -> bool:
    for conjunto in otros:
        if candidato in conjunto:
            continue
        if not any(abs(len(c) - len(candidato)) <= 3 and fuzz.ratio(candidato, c) >= SIMILITUD_ENTRE_EJEMPLOS for c in conjunto):
            return False
    return True


def sugerir_palabras_clave_ejemplos(ejemplos: list[Ejemplo], corpus: list[str], top_n: int = 10) -> list[dict]:
    """[{texto, peso 1-5, revisar}] a partir de 1 a 3 ejemplos del MISMO tipo de documento.
    `corpus`: textos de documentos de OTROS tipos (lo que aparece también ahí distingue menos)."""
    ejemplos = [e for e in ejemplos if e.texto.strip()][:MAX_EJEMPLOS]
    if not ejemplos:
        return []
    conjuntos = [ngramas(e) for e in ejemplos]
    un_solo_ejemplo = len(ejemplos) == 1
    candidatos = {c for c in conjuntos[0] if _en_todos(c, conjuntos[1:])}
    encabezado = set().union(*(e.encabezado() for e in ejemplos))
    if un_solo_ejemplo:
        # sin otro ejemplo con qué comparar: solo lo que tiene forma de etiqueta o está en el encabezado
        candidatos = {
            c for c in candidatos
            if es_vocabulario_de_etiqueta(palabras_utiles(c)) or (encabezado and all(w in encabezado for w in palabras_utiles(c)))
        }
    corpus_norm = [" ".join(" ".join(s) for s in segmentos(t)) for t in corpus if t]
    puntuados = []
    for c in candidatos:
        utiles = palabras_utiles(c)
        if not utiles:
            continue
        puntaje = float(len(utiles))
        if encabezado and all(w in encabezado for w in utiles):
            puntaje *= 1.5  # título/encabezado: lo más característico del tipo de documento
        if all(w in PALABRAS_INGLES for w in utiles):
            puntaje *= 0.5  # la mitad en inglés de una etiqueta bilingüe: alternativa, no la principal
        if corpus_norm:
            frecuencia = sum(1 for t in corpus_norm if c in t) / len(corpus_norm)
            puntaje *= 0.5 + (1 - frecuencia)
        puntuados.append((puntaje, c))
    puntuados.sort(key=lambda t: (-t[0], -len(t[1]), t[1]))
    elegidos: list[tuple[float, str]] = []
    for puntaje, c in puntuados:
        if any(c in e for _, e in elegidos):
            continue  # ya está dentro de una frase elegida ("nacimiento" en "fecha de nacimiento")
        elegidos.append((puntaje, c))
        if len(elegidos) >= top_n:
            break
    if not elegidos:
        return []
    maximo = elegidos[0][0]
    return [{"texto": c, "peso": max(1, min(5, round(5 * p / maximo))), "revisar": un_solo_ejemplo} for p, c in elegidos]


def sugerir_zonas_etiquetas(ejemplo: Ejemplo, palabras_clave: list[str], maximo: int = 15) -> list[dict]:
    """Etiquetas fijas para precargar la cuadrícula: líneas del ejemplo formadas solo por vocabulario de etiqueta, o que
    son una de las palabras clave sugeridas, con su caja relativa. Nunca una línea con cifras (es un valor)."""
    if not ejemplo.palabras:
        return []
    claves = set(palabras_clave)
    lineas: list[list[dict]] = []
    for p in sorted(ejemplo.palabras, key=lambda p: p["y"] + p["alto"] / 2):
        cy = p["y"] + p["alto"] / 2
        if lineas and abs(cy - (lineas[-1][-1]["y"] + lineas[-1][-1]["alto"] / 2)) <= 0.6 * max(p["alto"], 1e-3):
            lineas[-1].append(p)
        else:
            lineas.append([p])
    zonas = []
    for linea in lineas:
        linea.sort(key=lambda p: p["x"])
        texto = " ".join(p["texto"] for p in linea).strip()
        if not texto or re.search(r"\d", texto):
            continue
        normal = [w for w in (norm_palabra(x) for x in texto.split()) if w]
        if not es_vocabulario_de_etiqueta([w for w in normal if util(w)]) and " ".join(normal) not in claves:
            continue
        x0, y0 = min(p["x"] for p in linea), min(p["y"] for p in linea)
        x1, y1 = max(p["x"] + p["ancho"] for p in linea), max(p["y"] + p["alto"] for p in linea)
        zonas.append({"texto_esperado": texto[:200], "x": round(x0, 4), "y": round(y0, 4),
                      "ancho": round(min(1 - x0, x1 - x0), 4), "alto": round(min(1 - y0, y1 - y0), 4), "pagina": 1})
        if len(zonas) >= maximo:
            break
    return zonas
