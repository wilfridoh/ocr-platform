"""Posición sobre la página recortada (docs/13 §2): marco por página (¿recorte fiable?), etiquetas fijas encontradas,
desplazamiento global y texto dentro de una zona. Lo usan la extracción (entrega 3) y la coincidencia de diseño
(entrega 4). Todo en coordenadas relativas 0-1; nada atado a un formato de documento."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from statistics import median

from rapidfuzz import fuzz

from ..dominio.modelos import CampoPlantillaDTO, DisenoPlantilla, PaginaOCR, ZonaRelativa
from .posiciones import recorte_confiable

SIMILITUD_ETIQUETA = 0.8  # una etiqueta fija se da por encontrada desde aquí
SIMILITUD_MINIMA = 0.6  # por debajo, ni se considera candidata
DESPLAZAMIENTO_MAXIMO = 0.25  # un "hallazgo" más lejos que esto de su zona es otra cosa con texto parecido


def _norm(s: str) -> str:
    s = "".join(c for c in unicodedata.normalize("NFD", s or "") if unicodedata.category(c) != "Mn")
    return re.sub(r"[^0-9a-z]", "", s.lower())


@dataclass
class PalabraRel:
    texto: str
    x0: float
    y0: float
    x1: float
    y1: float
    confianza: float
    norm: str = ""  # texto normalizado (sin tildes ni signos, minúsculas), calculado una vez

    @property
    def cx(self) -> float:
        return (self.x0 + self.x1) / 2

    @property
    def cy(self) -> float:
        return (self.y0 + self.y1) / 2


def palabras_relativas(pagina: PaginaOCR) -> list[PalabraRel]:
    if not pagina.ancho or not pagina.alto:
        return []
    w, h = float(pagina.ancho), float(pagina.alto)
    return [
        PalabraRel(p.texto, p.x / w, p.y / h, (p.x + p.ancho) / w, (p.y + p.alto) / h, float(p.confianza), _norm(p.texto))
        for p in pagina.palabras
    ]


@dataclass
class EtiquetaFija:
    texto_esperado: str
    zona: ZonaRelativa
    campo: str | None = None  # None = elemento fijo sin campo (encabezado...)


@dataclass
class EtiquetaEncontrada:
    etiqueta: EtiquetaFija
    similitud: float  # 0-1; 0 si no aparece
    leido: str | None = None
    cx: float | None = None
    cy: float | None = None
    dentro: bool = False  # su centro cae en la zona esperada (con desplazamiento y tolerancia)
    indices: tuple[int, ...] = ()  # posiciones de sus palabras en la página


@dataclass
class MarcoPagina:
    numero: int
    confiable: bool
    tolerancia: float
    dx: float = 0.0
    dy: float = 0.0
    etiquetas: list[EtiquetaEncontrada] = field(default_factory=list)
    palabras: list[PalabraRel] = field(default_factory=list)
    excluidas: set[int] = field(default_factory=set)  # palabras que forman etiquetas fijas: nunca son un valor

    @property
    def verificado(self) -> bool:
        """Recorte fiable y al menos la mitad de las etiquetas fijas de la página en su sitio: el diseño se confirma y la
        zona puede ganarle a la etiqueta cuando discrepan (docs/13 §2.2)."""
        if not self.confiable or not self.etiquetas:
            return False
        return sum(e.dentro for e in self.etiquetas) * 2 >= len(self.etiquetas)

    def contiene(self, zona: ZonaRelativa, x: float, y: float) -> bool:
        t = self.tolerancia
        return (zona.x - t + self.dx <= x <= zona.x + zona.ancho + t + self.dx
                and zona.y - t + self.dy <= y <= zona.y + zona.alto + t + self.dy)


def etiquetas_fijas(campos: list[CampoPlantillaDTO], diseno: DisenoPlantilla) -> list[EtiquetaFija]:
    fijas = [EtiquetaFija(c.regla.zona_etiqueta.texto_esperado, c.regla.zona_etiqueta, c.nombre)
             for c in campos if c.regla.zona_etiqueta]
    fijas += [EtiquetaFija(e.texto_esperado, e, None) for e in diseno.elementos_fijos]
    return fijas


def buscar_etiqueta(palabras: list[PalabraRel], etiqueta: EtiquetaFija) -> EtiquetaEncontrada:
    """La secuencia de palabras consecutivas que mejor se parece al texto esperado (sin espacios: el OCR a veces pega o
    parte palabras). Entre candidatas casi igual de parecidas, la más cercana a su zona."""
    objetivo = _norm(etiqueta.texto_esperado)
    if not objetivo or not palabras:
        return EtiquetaEncontrada(etiqueta, 0.0)
    n = max(1, len(etiqueta.texto_esperado.split()))
    zx = etiqueta.zona.x + etiqueta.zona.ancho / 2
    zy = etiqueta.zona.y + etiqueta.zona.alto / 2
    candidatas = []
    normas = [p.norm or _norm(p.texto) for p in palabras]
    largo = len(objetivo)
    for tam in {max(1, n - 1), n, n + 1}:
        for i in range(len(palabras) - tam + 1):
            texto = "".join(normas[i : i + tam])
            if abs(len(texto) - largo) > largo * 0.6:  # imposible llegar a la similitud mínima: ni se compara
                continue
            sim = fuzz.ratio(objetivo, texto, score_cutoff=SIMILITUD_MINIMA * 100) / 100.0
            if sim >= SIMILITUD_MINIMA:
                ventana = palabras[i : i + tam]
                cx = (min(p.x0 for p in ventana) + max(p.x1 for p in ventana)) / 2
                cy = (min(p.y0 for p in ventana) + max(p.y1 for p in ventana)) / 2
                candidatas.append((sim, ((cx - zx) ** 2 + (cy - zy) ** 2) ** 0.5, cx, cy, " ".join(p.texto for p in ventana),
                                   tuple(range(i, i + tam))))
    if not candidatas:
        return EtiquetaEncontrada(etiqueta, 0.0)
    mejor_sim = max(c[0] for c in candidatas)
    sim, _, cx, cy, leido, indices = min((c for c in candidatas if c[0] >= mejor_sim - 0.05), key=lambda c: c[1])
    return EtiquetaEncontrada(etiqueta, round(sim, 3), leido, cx, cy, indices=indices)


def _fuera(v: float, desde: float, hasta: float) -> float:
    """Cuánto queda `v` fuera del intervalo (con signo); 0 si está dentro."""
    return v - hasta if v > hasta else (v - desde if v < desde else 0.0)


def calcular_marcos(
    paginas: list[PaginaOCR], campos: list[CampoPlantillaDTO], diseno: DisenoPlantilla | None
) -> dict[int, MarcoPagina]:
    """Un marco por página. Sin diseño, vacío: la extracción se comporta como siempre."""
    if diseno is None:
        return {}
    fijas = etiquetas_fijas(campos, diseno)
    marcos = {}
    for pagina in paginas:
        palabras = palabras_relativas(pagina)
        marco = MarcoPagina(
            numero=pagina.numero,
            confiable=bool(palabras) and recorte_confiable(pagina.recorte, diseno.relacion),
            tolerancia=diseno.tolerancia,
            palabras=palabras,
        )
        encontradas = [buscar_etiqueta(palabras, f) for f in fijas if (f.zona.pagina or 1) == pagina.numero]
        # desplazamiento global (docs/13 §2.3): por cada etiqueta encontrada con seguridad, lo MÍNIMO que hay que mover su
        # zona para que la contenga (0 si ya está dentro: una zona dibujada holgada no sesga el cálculo); la mediana
        difs = []
        for e in encontradas:
            if e.similitud >= SIMILITUD_ETIQUETA and e.cx is not None:
                z = e.etiqueta.zona
                ddx = _fuera(e.cx, z.x, z.x + z.ancho)
                ddy = _fuera(e.cy, z.y, z.y + z.alto)
                if abs(ddx) <= DESPLAZAMIENTO_MAXIMO and abs(ddy) <= DESPLAZAMIENTO_MAXIMO:
                    difs.append((ddx, ddy))
        if len(difs) >= 2:
            marco.dx = median(d[0] for d in difs)
            marco.dy = median(d[1] for d in difs)
        for e in encontradas:
            e.dentro = e.similitud >= SIMILITUD_ETIQUETA and e.cx is not None and marco.contiene(e.etiqueta.zona, e.cx, e.cy)
        marco.etiquetas = encontradas
        # una etiqueta impresa suele estar a pocos milímetros de su valor: con la tolerancia podría colarse en la zona
        marco.excluidas = {i for e in encontradas if e.similitud >= SIMILITUD_ETIQUETA for i in e.indices}
        marcos[pagina.numero] = marco
    return marcos


def texto_en_zona(marco: MarcoPagina, zona: ZonaRelativa) -> tuple[str | None, float, tuple[float, float, float, float] | None]:
    """(texto, confianza media, caja que lo envuelve) de las palabras cuyo centro cae en la zona (con desplazamiento y
    tolerancia), en orden de lectura: líneas de arriba abajo y, en cada una, de izquierda a derecha."""
    dentro = [p for i, p in enumerate(marco.palabras) if i not in marco.excluidas and marco.contiene(zona, p.cx, p.cy)]
    if not dentro:
        return None, 0.0, None
    alto_medio = median(p.y1 - p.y0 for p in dentro) or 0.01
    lineas: list[list[PalabraRel]] = []
    for p in sorted(dentro, key=lambda p: p.cy):
        if lineas and abs(p.cy - lineas[-1][-1].cy) <= 0.6 * alto_medio:
            lineas[-1].append(p)
        else:
            lineas.append([p])
    texto = " ".join(" ".join(p.texto for p in sorted(linea, key=lambda p: p.x0)) for linea in lineas)
    caja = (min(p.x0 for p in dentro), min(p.y0 for p in dentro), max(p.x1 for p in dentro), max(p.y1 for p in dentro))
    return texto, sum(p.confianza for p in dentro) / len(dentro), caja


def zona_valor(campo: CampoPlantillaDTO) -> ZonaRelativa | None:
    r = campo.regla
    if r.x is None or r.y is None or not r.ancho or not r.alto:
        return None
    try:
        return ZonaRelativa(x=r.x, y=r.y, ancho=min(r.ancho, 1 - r.x), alto=min(r.alto, 1 - r.y), pagina=r.pagina)
    except ValueError:  # regla antigua con coordenadas fuera de 0-1: sin zona
        return None


# ------------------------------------------------------------------ orientación 0° / 180° (docs/13 §4.3)
def _girar_180(pagina: PaginaOCR) -> PaginaOCR:
    """La misma página con las cajas de las palabras giradas 180° (el texto ya lo leyó bien el clasificador de ángulo
    del motor; lo que queda invertido son las posiciones)."""
    w, h = pagina.ancho, pagina.alto
    palabras = [p.model_copy(update={"x": w - p.x - p.ancho, "y": h - p.y - p.alto}) for p in pagina.palabras]
    recorte = dict(pagina.recorte or {})
    recorte["orientacion"] = (int(recorte.get("orientacion") or 0) + 180) % 360
    recorte["orientacion_auto"] = True  # decidido por el sistema: un reproceso lo vuelve a decidir, no lo fija
    return pagina.model_copy(update={"palabras": palabras, "recorte": recorte})


MIN_ETIQUETAS_GIRO = 2


def _en_sitio(marco: MarcoPagina) -> int:
    return sum(e.dentro for e in marco.etiquetas)


def orientar_paginas(paginas: list[PaginaOCR], campos: list[CampoPlantillaDTO], diseno: DisenoPlantilla | None) -> set[int]:
    """Con diseño: si una página encaja claramente mejor girada 180° (más etiquetas fijas en su sitio), se gira EN EL
    LUGAR (cajas de las palabras y orientación de su recorte), así lo que se guarda queda coherente con la imagen
    enderezada. Coste: un cálculo de marcos más por página, sin releer nada. Devuelve los números de página girados."""
    giradas: set[int] = set()
    if diseno is None:
        return giradas
    for pagina in paginas:
        if not pagina.palabras or not recorte_confiable(pagina.recorte, diseno.relacion):
            continue
        girada = _girar_180(pagina)
        normal = calcular_marcos([pagina], campos, diseno).get(pagina.numero)
        invertida = calcular_marcos([girada], campos, diseno).get(pagina.numero)
        # exige evidencia: al menos 2 etiquetas, y la mitad, en su sitio girada (con una sola es fácil acertar por azar)
        if (
            normal is not None and invertida is not None
            and _en_sitio(invertida) > _en_sitio(normal)
            and _en_sitio(invertida) >= MIN_ETIQUETAS_GIRO
            and _en_sitio(invertida) * 2 >= len(invertida.etiquetas)
        ):
            pagina.palabras, pagina.recorte = girada.palabras, girada.recorte
            giradas.add(pagina.numero)
    return giradas


def girar_paginas_180(paginas: list[PaginaOCR], numeros: set[int]) -> None:
    """Aplica el mismo giro (en el lugar) a otra lectura de las mismas imágenes: la segunda opinión."""
    for p in paginas:
        if p.numero in numeros:
            g = _girar_180(p)
            p.palabras, p.recorte = g.palabras, g.recorte


# ------------------------------------------------------------------ coincidencia de diseño (docs/13 §3)
PESO_ETIQUETAS = 0.7
PESO_ALINEACION = 0.3
MARGEN_PARCIAL = 0.15  # "parcial" entre umbral - 0,15 y umbral (pedido de UX)
FACTOR_FUERA_DE_ZONA = 0.5  # una etiqueta leída fuera de su zona aporta la mitad de su similitud al término de etiquetas


def _distancia_a_zona(marco: MarcoPagina, e: EtiquetaEncontrada) -> float:
    z = e.etiqueta.zona
    t = marco.tolerancia
    dx = _fuera(e.cx, z.x - t + marco.dx, z.x + z.ancho + t + marco.dx)
    dy = _fuera(e.cy, z.y - t + marco.dy, z.y + z.alto + t + marco.dy)
    return (dx * dx + dy * dy) ** 0.5


def calcular_coincidencia(
    paginas: list[PaginaOCR],
    campos: list[CampoPlantillaDTO],
    diseno: DisenoPlantilla | None,
    extraidos: list | None = None,
    orientacion: int | None = None,
) -> dict | None:
    """Puntaje de coincidencia de DISEÑO (no de autenticidad): 70 % etiquetas fijas (similitud del texto leído en su
    zona) + 30 % alineación (desplazamiento residual medio, en fracción de la página). None sin diseño.

    `extraidos` (CampoExtraidoDTO) informa el estado de las zonas de valor sin repetir el dato: leido_ok."""
    if diseno is None:
        return None
    marcos = calcular_marcos(paginas, campos, diseno)
    confiable = any(m.confiable for m in marcos.values())
    etiquetas = [(m, e) for m in marcos.values() for e in m.etiquetas]
    zonas: list[dict] = []
    similitudes, distancias, ok = [], [], 0
    for marco, e in etiquetas:
        encontrada = e.similitud >= SIMILITUD_MINIMA and e.cx is not None
        if e.similitud >= SIMILITUD_ETIQUETA and e.dentro:
            estado = "coincide"
            ok += 1
        elif encontrada:
            estado = "parcial"
        else:
            estado = "no_coincide"
        # fuera de su zona solo aporta la mitad: si no, un documento con OTRA disposición de las mismas etiquetas
        # sumaría 0,7 solo por contenerlas
        similitudes.append(0.0 if not encontrada else (e.similitud if e.dentro else e.similitud * FACTOR_FUERA_DE_ZONA))
        if encontrada:
            distancias.append(_distancia_a_zona(marco, e))
        z = e.etiqueta.zona
        zonas.append({
            "campo": e.etiqueta.campo, "tipo": "etiqueta", "estado": estado, "esperado": e.etiqueta.texto_esperado,
            "leido": e.leido if encontrada else None, "similitud": round(e.similitud, 3),
            "x": z.x, "y": z.y, "ancho": z.ancho, "alto": z.alto, "pagina": z.pagina or 1,
        })
    por_nombre = {c.nombre: c for c in (extraidos or [])}
    valores_total = valores_ok = 0
    for campo in campos:
        z = zona_valor(campo)
        if z is None:
            continue
        valores_total += 1
        r = por_nombre.get(campo.nombre)
        leido_ok = bool(r is not None and r.valido and r.valor_texto)
        valores_ok += leido_ok
        estado = "no_coincide" if not leido_ok else ("parcial" if getattr(r, "fuera_de_zona", False) else "coincide")
        zonas.append({"campo": campo.nombre, "tipo": "valor", "estado": estado, "leido_ok": leido_ok,
                      "x": z.x, "y": z.y, "ancho": z.ancho, "alto": z.alto, "pagina": z.pagina or 1})

    legibles = sum(1 for _, e in etiquetas if e.similitud >= SIMILITUD_MINIMA and e.cx is not None)
    verificable = confiable and bool(etiquetas) and legibles * 2 >= len(etiquetas)
    termino_etiquetas = sum(similitudes) / len(similitudes) if similitudes else 0.0
    desplazamiento = sum(distancias) / len(distancias) if distancias else None
    alineacion = 0.0 if desplazamiento is None else 1 - min(1.0, desplazamiento / max(1e-6, 2 * diseno.tolerancia))
    puntaje = PESO_ETIQUETAS * termino_etiquetas + PESO_ALINEACION * alineacion
    umbral = diseno.umbral_coincidencia
    veredicto = None
    if verificable:
        veredicto = "coincide" if puntaje >= umbral else ("parcial" if puntaje >= umbral - MARGEN_PARCIAL else "no_coincide")
    primera = paginas[0] if paginas else None
    recorte = (primera.recorte or {}) if primera else {}
    return {
        "verificable": verificable,
        "puntaje": round(puntaje, 3) if verificable else None,
        "umbral": umbral,
        "veredicto": veredicto,
        "etiquetas_ok": ok,
        "etiquetas_total": len(etiquetas),
        "desplazamiento_medio": round(desplazamiento, 4) if desplazamiento is not None else None,
        "valores_legibles": valores_ok,
        "valores_total": valores_total,
        "recorte_confiable": confiable,
        "recorte_origen": recorte.get("origen") or "desconocido",
        "orientacion": orientacion if orientacion is not None else int(recorte.get("orientacion") or 0),
        "zonas": zonas,
    }


def advertencias_coincidencia(coincidencia: dict | None) -> list[str]:
    if not coincidencia:
        return []
    if not coincidencia["verificable"]:
        return ["diseno_no_verificable"]
    if coincidencia["veredicto"] == "no_coincide":
        return ["diseno_no_coincide"]
    return []
