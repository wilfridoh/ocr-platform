"""Validadores y normalizadores por tipo de dato (docs/02-backend.md §4.6)."""
from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime
from typing import Any

_MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}

_RE_FECHA_DMY_NUM = re.compile(r"\b(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})\b")
_RE_FECHA_TEXTO = re.compile(
    r"\b(\d{1,2})\s+de\s+([a-zA-Záéíóúñ]+)\s+(?:de\s+)?(\d{4})\b", re.IGNORECASE
)
_RE_FECHA_MES_ABREV = re.compile(r"\b(\d{1,2})\s+([A-Za-zÁÉÍÓÚáéíóúñÑ]{3,10})\s+[A-Za-z]?(\d{4})\b")
_ABREV_MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


def _mes_aproximado(texto: str) -> int | None:
    """Número de mes desde nombre completo, abreviatura o abreviatura con un error de OCR ('RAY'→may)."""
    from rapidfuzz import fuzz

    t = "".join(c for c in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(c) != "Mn")
    if t in _MESES:
        return _MESES[t]
    if t == "set":
        return 9
    mejor, puntaje = None, 0.0
    for i, ab in enumerate(_ABREV_MESES, 1):
        sc = 100.0 if t.startswith(ab) else fuzz.ratio(t[:3], ab)
        if sc > puntaje:
            mejor, puntaje = i, sc
    return mejor if puntaje >= 66 else None


_RE_EMAIL = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
_RE_TELEFONO = re.compile(r"(?:\+?56)?\s?[9]\s?\d{4}\s?\d{4}|\+?\d[\d\s\-()]{6,14}\d")
_RE_MONTO = re.compile(r"[\d.,]+")


def validar_fecha(valor: str) -> tuple[str | None, bool]:
    """Devuelve (ISO 8601 'YYYY-MM-DD' o None, válido)."""
    if not valor:
        return None, False
    valor = valor.strip()
    m = _RE_FECHA_DMY_NUM.search(valor)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if y < 100:
            y += 2000 if y < 70 else 1900
        try:
            return date(y, mo, d).isoformat(), True
        except ValueError:
            return None, False
    m = _RE_FECHA_TEXTO.search(valor)
    if m:
        d = int(m.group(1))
        mes_txt = m.group(2).lower()
        y = int(m.group(3))
        mo = _MESES.get(mes_txt)
        if mo:
            try:
                return date(y, mo, d).isoformat(), True
            except ValueError:
                return None, False
    # "03 NOV 1996" (cédulas): mes abreviado o con ruido de OCR ("RAY"), y letra espuria antes del año
    m = _RE_FECHA_MES_ABREV.search(valor)
    if m:
        mo = _mes_aproximado(m.group(2))
        if mo:
            try:
                return date(int(m.group(3)), mo, int(m.group(1))).isoformat(), True
            except ValueError:
                return None, False
    # ya en ISO
    try:
        return datetime.fromisoformat(valor).date().isoformat(), True
    except ValueError:
        return None, False


def validar_monto(valor: str) -> tuple[float | None, bool]:
    """Elimina separador de miles, detecta coma decimal, devuelve número."""
    if not valor:
        return None, False
    m = _RE_MONTO.search(valor)
    if not m:
        return None, False
    txt = m.group(0)
    if "," in txt and "." in txt:
        if txt.rfind(",") > txt.rfind("."):
            txt = txt.replace(".", "").replace(",", ".")
        else:
            txt = txt.replace(",", "")
    elif "," in txt:
        # coma como decimal solo si quedan <=2 dígitos tras ella
        partes = txt.split(",")
        if len(partes[-1]) <= 2:
            txt = txt.replace(".", "").replace(",", ".")
        else:
            txt = txt.replace(",", "")
    else:
        # punto: miles si hay más de un grupo de 3 dígitos tras él, o grupos repetidos
        if txt.count(".") > 1:
            txt = txt.replace(".", "")
        elif "." in txt:
            entero, dec = txt.split(".")
            if len(dec) == 3 and len(entero) <= 3:
                # ambiguo tipo "45.320": se interpreta como separador de miles (es-CL)
                txt = entero + dec
    try:
        return float(txt), True
    except ValueError:
        return None, False


def _modulo11_rut(cuerpo: str) -> str:
    suma = 0
    mult = 2
    for ch in reversed(cuerpo):
        suma += int(ch) * mult
        mult = 2 if mult == 7 else mult + 1
    resto = 11 - (suma % 11)
    if resto == 11:
        return "0"
    if resto == 10:
        return "K"
    return str(resto)


def validar_rut(valor: str) -> tuple[str | None, bool]:
    """RUT chileno con dígito verificador módulo 11. Normaliza a 'NNNNNNNN-D'."""
    if not valor:
        return None, False
    limpio = re.sub(r"[.\s]", "", valor).upper()
    m = re.match(r"^(\d{1,8})-?([\dK])$", limpio)
    if not m:
        return None, False
    cuerpo, dv = m.group(1), m.group(2)
    dv_calc = _modulo11_rut(cuerpo)
    normalizado = f"{cuerpo}-{dv}"
    return normalizado, dv_calc == dv


def validar_cedula(valor: str) -> tuple[str | None, bool]:
    """Validación genérica: 6 a 12 dígitos (con guiones/puntos opcionales)."""
    if not valor:
        return None, False
    limpio = re.sub(r"[.\-\s]", "", valor)
    if limpio.isdigit() and 6 <= len(limpio) <= 12:
        return limpio, True
    return None, False


def validar_email(valor: str) -> tuple[str | None, bool]:
    if not valor:
        return None, False
    m = _RE_EMAIL.search(valor)
    if m:
        return m.group(0).lower(), True
    return None, False


def validar_telefono(valor: str) -> tuple[str | None, bool]:
    if not valor:
        return None, False
    m = _RE_TELEFONO.search(valor)
    if not m:
        return None, False
    digitos = re.sub(r"\D", "", m.group(0))
    if 7 <= len(digitos) <= 15:
        return digitos, True
    return None, False


def validar_numero(valor: str) -> tuple[float | None, bool]:
    if not valor:
        return None, False
    try:
        limpio = valor.strip().replace(" ", "")
        if "," in limpio and "." not in limpio:
            limpio = limpio.replace(",", ".")
        else:
            limpio = limpio.replace(",", "")
        return float(limpio), True
    except ValueError:
        return None, False


def validar_texto(valor: str) -> tuple[str | None, bool]:
    v = (valor or "").strip()
    return (v or None), bool(v)


VALIDADORES = {
    "texto": validar_texto,
    "numero": validar_numero,
    "monto": validar_monto,
    "fecha": validar_fecha,
    "rut": validar_rut,
    "cedula": validar_cedula,
    "email": validar_email,
    "telefono": validar_telefono,
}


def validar_normalizar(tipo_dato: str, valor_texto: str | None) -> tuple[Any, bool]:
    fn = VALIDADORES.get(tipo_dato, validar_texto)
    return fn(valor_texto or "")
