"""Clasificador: puntúa cada plantilla activa contra el texto OCR (docs/02-backend.md §4.4)."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from rapidfuzz import fuzz

from ..dominio.modelos import AlternativaClasificacion, Clasificacion, PalabraClaveDTO


def _sin_acentos(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def _normaliza(s: str) -> str:
    return _sin_acentos(s or "").lower()


_PUNTUACION = re.compile(r"[^\w\s]|_", re.UNICODE)
_VACIAS = {"de", "del", "la", "el", "los", "las", "a", "en", "y", "por", "para"}
_VENTANA_EXTRA = 3  # tokens ajenos tolerados entre las palabras de una clave ("consumo: 145 kWh")


def _tokens(s: str) -> list[str]:
    """Texto normalizado sin puntuación, en tokens: 'Consumo: 145 kWh' -> ['consumo','145','kwh']."""
    return _PUNTUACION.sub(" ", _normaliza(s)).split()


def _token_coincide(clave: str, texto: str) -> bool:
    if clave == texto:
        return True
    if len(clave) < 3:  # claves muy cortas: solo exactas (evita falsos positivos)
        return False
    return fuzz.ratio(clave, texto) >= 80


@dataclass
class PlantillaCandidata:
    plantilla_id: int
    version_id: int
    codigo: str
    umbral_confianza: float
    palabras_clave: list[PalabraClaveDTO]
    ejemplos_texto: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.ejemplos_texto is None:
            self.ejemplos_texto = []


def _presencia_palabra_clave(texto_norm: str, palabra_norm: str) -> float:
    """Presencia 0-1 de una palabra clave en el texto.

    1.0 si aparece literal; 0.9 si todas sus palabras significativas aparecen en orden dentro de
    una ventana corta tolerando puntuación, números intermedios y errores de OCR leves
    (p. ej. 'consumo kwh' en 'Consumo: 145 kvvh')."""
    if not palabra_norm:
        return 0.0
    if palabra_norm in texto_norm:
        return 1.0
    claves = [t for t in _tokens(palabra_norm) if t not in _VACIAS] or _tokens(palabra_norm)
    texto = _tokens(texto_norm)
    if not claves or not texto:
        return 0.0
    # 1) frase completa aproximada (errores de OCR dentro de la clave: 'kvvh' por 'kwh')
    n = len(_tokens(palabra_norm))
    frase = " ".join(_tokens(palabra_norm))
    for i in range(max(1, len(texto) - n + 1)):
        if fuzz.ratio(frase, " ".join(texto[i : i + n])) >= 80:
            return 0.95
    # 2) palabras significativas en orden, tolerando puntuación y tokens intermedios
    for i, t in enumerate(texto):
        if not _token_coincide(claves[0], t):
            continue
        pos = i
        for clave in claves[1:]:
            limite = min(len(texto), pos + 2 + _VENTANA_EXTRA)
            sig = next((j for j in range(pos + 1, limite) if _token_coincide(clave, texto[j])), None)
            if sig is None:
                break
            pos = sig
        else:
            return 0.9
    return 0.0


def _score_palabras_clave(texto_norm: str, palabras_clave: list[PalabraClaveDTO]) -> tuple[float, list[str]]:
    if not palabras_clave:
        return 0.0, []
    suma_pesos = sum(pc.peso for pc in palabras_clave)
    if suma_pesos == 0:
        return 0.0, []
    acumulado = 0.0
    encontradas = []
    for pc in palabras_clave:
        # "a|b|c": variantes/abreviaturas de la misma clave; cuenta una sola vez (la mejor presencia)
        variantes = [v.strip() for v in pc.texto.split("|") if v.strip()]
        presencia = max((_presencia_palabra_clave(texto_norm, _normaliza(v)) for v in variantes), default=0.0)
        acumulado += pc.peso * presencia
        if presencia > 0:
            encontradas.append(pc.texto)
    return acumulado / suma_pesos, encontradas


def _similitud_tfidf(texto: str, ejemplos: list[str]) -> float:
    if not ejemplos:
        return 0.0
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
    except Exception:  # noqa: BLE001
        return 0.0
    try:
        corpus = ejemplos + [texto]
        vect = TfidfVectorizer()
        matriz = vect.fit_transform(corpus)
        sim = cosine_similarity(matriz[-1], matriz[:-1])
        return float(sim.max()) if sim.size else 0.0
    except ValueError:
        return 0.0


def clasificar(
    texto: str, plantillas: list[PlantillaCandidata], umbral_desconocido: float = 0.5
) -> tuple[Clasificacion, list[str]]:
    texto_norm = _normaliza(texto)
    puntajes: list[tuple[PlantillaCandidata, float, list[str]]] = []
    todas_encontradas: list[str] = []
    for plantilla in plantillas:
        score_kw, encontradas = _score_palabras_clave(texto_norm, plantilla.palabras_clave)
        score_tfidf = _similitud_tfidf(texto, plantilla.ejemplos_texto) if plantilla.ejemplos_texto else 0.0
        score = score_kw * 0.7 + score_tfidf * 0.3 if plantilla.ejemplos_texto else score_kw
        puntajes.append((plantilla, score, encontradas))

    puntajes.sort(key=lambda t: t[1], reverse=True)

    if not puntajes or puntajes[0][1] < max(puntajes[0][0].umbral_confianza, umbral_desconocido):
        alternativas = [
            AlternativaClasificacion(tipo=p.codigo, confianza=round(s, 3), plantilla_id=p.plantilla_id)
            for p, s, _ in puntajes[:3]
        ]
        return Clasificacion(tipo="desconocido", confianza=puntajes[0][1] if puntajes else 0.0, alternativas=alternativas), []

    ganadora, score, encontradas = puntajes[0]
    alternativas = [
        AlternativaClasificacion(tipo=p.codigo, confianza=round(s, 3), plantilla_id=p.plantilla_id)
        for p, s, _ in puntajes[1:3]
    ]
    clasificacion = Clasificacion(
        tipo=ganadora.codigo,
        plantilla_id=ganadora.plantilla_id,
        version_id=ganadora.version_id,
        confianza=round(score, 3),
        alternativas=alternativas,
    )
    return clasificacion, encontradas
