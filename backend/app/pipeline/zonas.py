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
