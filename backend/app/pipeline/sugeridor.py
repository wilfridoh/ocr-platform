"""Sugerencia automática de plantillas (docs/02-backend.md §5)."""
from __future__ import annotations

import re
import unicodedata

from ..dominio.modelos import CampoPlantillaDTO, PalabraClaveDTO, ReglaCampo

_RE_FECHA = re.compile(r"\b\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}\b")
_RE_MONTO = re.compile(r"\$\s?[\d.,]+|\b[\d]{1,3}(?:[.,]\d{3})+\b")
_RE_RUT = re.compile(r"\b\d{1,2}[.,]?\d{3}[.,]?\d{3}-[\dkK]\b")
_RE_EMAIL = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
_RE_TELEFONO = re.compile(r"\+?\d[\d\s\-()]{6,14}\d")
_RE_NUM_LARGO = re.compile(r"\b\d{5,}\b")

# Orden = prioridad: cada línea produce a lo sumo un campo (el primer patrón que calce).
_RE_FECHA_TEXTO = re.compile(r"\b\d{1,2}\s+de\s+[a-záéíóúñ]+\s+(?:de|del)\s+\d{4}\b", re.IGNORECASE)
_RE_DURACION = re.compile(
    r"\b\d+(?:[.,]\d+)?\s*(?:total\s+)?(?:mins?|minutos?|horas?|hrs?|h|dias?|kwh|kw)\b", re.IGNORECASE
)
# "Etiqueta: valor" genérico (último recurso): el valor debe llevar algún dígito, para no tomar prosa.
_RE_ETIQUETA_VALOR = re.compile(r"^(?P<etiqueta>[^:]{2,60}):\s*(?P<valor>.*\d.*)$")

_PATRONES = [
    ("fecha", _RE_FECHA),
    ("fecha", _RE_FECHA_TEXTO),
    ("rut", _RE_RUT),
    ("email", _RE_EMAIL),
    ("monto", _RE_MONTO),
    ("numero", _RE_NUM_LARGO),
    ("texto", _RE_DURACION),  # duraciones/cantidades con unidad: el valor incluye la unidad
    ("telefono", _RE_TELEFONO),
]

# Palabras vacías del español: no sirven como palabra clave ni como ancla.
STOPWORDS_ES = frozenset(
    """a al algo ante con contra cual cuando de del desde donde durante e el ella ellas ello ellos en entre era
    es esa esas ese eso esos esta estas este esto estos fue ha han hasta hay la las le les lo los mas me mi mis
    muy ni no nos nosotros o os otra otro para pero por porque que quien se sea segun ser si sin sobre su sus
    tambien te ti tu tus un una uno unas unos y ya""".split()
)
_MAX_PALABRAS_ANCLA = 4  # una ancla es una etiqueta corta ("Total a pagar"), no una frase
_MAX_PALABRAS_PREFIJO = 6  # más palabras antes del valor y sin ':' => prosa, no un campo
_RE_PALABRAS = re.compile(r"[^\W\d_]+")


def _tokens_utiles(frase: str) -> list[str]:
    return [t for t in _RE_PALABRAS.findall(frase.lower()) if t not in STOPWORDS_ES and len(t) > 1]


def _ancla_candidata(prefijo: str) -> str | None:
    """Etiqueta corta que precede a un valor, o None si es prosa o no tiene contenido."""
    prefijo = prefijo.strip(" \t")
    termina_en_dos_puntos = prefijo.endswith(":")
    palabras = prefijo.strip(" :.-\t").split()
    if len(palabras) > _MAX_PALABRAS_PREFIJO and not termina_en_dos_puntos:
        return None
    if len(palabras) > _MAX_PALABRAS_ANCLA:
        palabras = palabras[-_MAX_PALABRAS_ANCLA:]
    ancla = " ".join(palabras).strip(" :.-\t")
    if not _tokens_utiles(ancla):  # solo stopwords o símbolos
        return None
    return ancla


def sugerir_palabras_clave(texto: str, corpus: list[str], top_n: int = 10) -> list[PalabraClaveDTO]:
    """N-gramas (1-3 palabras) frecuentes en `texto` y poco frecuentes en `corpus` (TF-IDF),
    sin palabras vacías del español ni números."""
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
    except Exception:  # noqa: BLE001
        # Sin scikit-learn: solo frecuencia simple de palabras largas
        palabras = [w for w in re.findall(r"[a-zA-Záéíóúñ]{4,}", texto.lower()) if w not in STOPWORDS_ES]
        vistos: dict[str, int] = {}
        for w in palabras:
            vistos[w] = vistos.get(w, 0) + 1
        top = sorted(vistos.items(), key=lambda kv: kv[1], reverse=True)[:top_n]
        return [PalabraClaveDTO(texto=w, peso=min(5, max(1, c))) for w, c in top]

    documentos = corpus + [texto] if corpus else [texto]
    vect = TfidfVectorizer(
        ngram_range=(1, 3),
        max_features=300,
        stop_words=sorted(STOPWORDS_ES),
        strip_accents="unicode",
        token_pattern=r"(?u)\b[^\W\d_]{2,}\b",  # solo palabras: sin números ni símbolos
    )
    try:
        matriz = vect.fit_transform(documentos)
    except ValueError:
        return []
    vector_objetivo = matriz[-1].toarray()[0]
    vocab = vect.get_feature_names_out()
    orden = vector_objetivo.argsort()[::-1][:top_n]
    sugeridas = []
    for idx in orden:
        score = float(vector_objetivo[idx])
        if score <= 0:
            continue
        peso = max(1, min(5, round(score * 5) + 1))
        sugeridas.append(PalabraClaveDTO(texto=vocab[idx], peso=peso))
    return sugeridas


def sugerir_campos(texto: str) -> list[CampoPlantillaDTO]:
    """Patrones genéricos (fecha, RUT, email, monto, número largo, teléfono) con su ancla corta.
    A lo sumo un campo por línea; las líneas de prosa larga se descartan."""
    campos = []
    vistos_nombres: set[str] = set()
    for i, linea in enumerate(texto.split("\n")):
        # (tipo de dato, texto que precede al valor), en orden de prioridad
        candidatos = [(t, linea[: m.start()]) for t, p in _PATRONES if (m := p.search(linea))]
        m_ev = _RE_ETIQUETA_VALOR.match(linea.strip())
        if m_ev:
            candidatos.append(("texto", m_ev.group("etiqueta") + ":"))
        for tipo_dato, prefijo in candidatos:
            ancla = _ancla_candidata(prefijo)
            if not ancla:
                continue
            sin_tildes = "".join(c for c in unicodedata.normalize("NFD", ancla.lower()) if unicodedata.category(c) != "Mn")
            nombre_base = re.sub(r"[^a-z0-9]+", "_", sin_tildes).strip("_") or tipo_dato
            nombre = nombre_base
            contador = 1
            while nombre in vistos_nombres:
                contador += 1
                nombre = f"{nombre_base}_{contador}"
            vistos_nombres.add(nombre)
            campos.append(
                CampoPlantillaDTO(
                    nombre=nombre[:100],
                    etiqueta=ancla[:200] or tipo_dato,
                    tipo_dato=tipo_dato,
                    obligatorio=False,
                    regla=ReglaCampo(metodo="ancla", ancla=ancla),
                    orden=i,
                )
            )
            break  # un campo por línea
    return campos
