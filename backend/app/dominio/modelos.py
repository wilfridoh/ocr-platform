"""Modelos Pydantic del dominio (independientes de HTTP y de la BD)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator

TIPOS_DATO = ("texto", "numero", "monto", "fecha", "rut", "cedula", "email", "telefono")
METODOS = ("regex", "ancla", "zona")

TipoDato = Literal["texto", "numero", "monto", "fecha", "rut", "cedula", "email", "telefono"]
Metodo = Literal["regex", "ancla", "zona"]


# ---------------------------------------------------------------- OCR
class PalabraOCR(BaseModel):
    texto: str
    x: int
    y: int
    ancho: int
    alto: int
    confianza: float  # 0-1
    linea: int
    bloque: int
    pagina: int = 1


class PaginaOCR(BaseModel):
    numero: int = 1
    texto: str = ""
    palabras: list[PalabraOCR] = Field(default_factory=list)
    confianza_media: float = 0.0
    ancho: int = 0
    alto: int = 0
    pasos_preprocesado: list[str] = Field(default_factory=list)
    motor: Optional[str] = None  # motor que leyó la página (paddle/doctr/tesseract/pdf-nativo)
    # cómo se recortó/enderezó la página antes del OCR (docs/13 §1.3): aplicado, origen, esquinas, relacion...
    recorte: Optional[dict[str, Any]] = None


# ---------------------------------------------------------------- Plantillas
class ZonaRelativa(BaseModel):
    """Rectángulo relativo (0-1) sobre la página ya recortada y enderezada (docs/13 §1)."""

    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    ancho: float = Field(gt=0, le=1)
    alto: float = Field(gt=0, le=1)
    pagina: Optional[int] = Field(default=None, ge=1)

    @field_validator("alto")
    @classmethod
    def _dentro_de_la_pagina(cls, v: float, info) -> float:
        d = info.data
        if "x" in d and "ancho" in d and d["x"] + d["ancho"] > 1.0001:
            raise ValueError("la zona se sale de la página por la derecha (x + ancho > 1)")
        if "y" in d and d["y"] + v > 1.0001:
            raise ValueError("la zona se sale de la página por abajo (y + alto > 1)")
        return v


class ZonaEtiqueta(ZonaRelativa):
    """Etiqueta fija impresa: texto que debe aparecer en esa zona (se usa para validar el diseño)."""

    texto_esperado: str = Field(min_length=1, max_length=200)


class DisenoPlantilla(BaseModel):
    """Diseño por posición de una versión de plantilla (docs/13 §1.2). Nada atado a un formato concreto: la proporción
    esperada es un dato de la plantilla."""

    formato: str = Field(default="libre", max_length=20)  # preajuste del editor: ID-1, A4, carta, libre...
    relacion: Optional[float] = Field(default=None, ge=1.0, le=10.0)  # lado mayor / lado menor esperado
    umbral_coincidencia: float = Field(default=0.8, ge=0, le=1)
    tolerancia: float = Field(default=0.03, ge=0, le=0.2)  # fracción del ancho/alto
    densidad_rejilla: Optional[str] = Field(default=None, pattern=r"^\d{1,2}x\d{1,2}$")  # solo UI, p. ej. "12x8"
    elementos_fijos: list[ZonaEtiqueta] = Field(default_factory=list, max_length=100)  # etiquetas sin campo


class ReglaCampo(BaseModel):
    metodo: Metodo
    regex: Optional[str] = None
    ancla: Optional[str] = None
    pagina: Optional[int] = None
    x: Optional[float] = None
    y: Optional[float] = None
    ancho: Optional[float] = None
    alto: Optional[float] = None
    # extras opcionales
    flags: Optional[str] = None  # p. ej. "i" para ignorar mayúsculas
    misma_linea: bool = True  # ancla: buscar en la misma línea; si no hay, la siguiente
    lineas: int = 1  # ancla con el valor en las líneas siguientes: cuántas líneas unir (p. ej. 2 apellidos en 2 líneas)
    # valores canónicos del campo (p. ej. gentilicios): una lectura a 1 carácter de distancia de uno de ellos se
    # guarda en su forma canónica, y si la regla no encuentra nada se busca en el texto una palabra así (docs/02 §4.5)
    catalogo: Optional[list[str]] = None
    # x/y/ancho/alto (arriba) son la zona del VALOR; esta es la etiqueta fija impresa del campo (docs/13 §1.1)
    zona_etiqueta: Optional[ZonaEtiqueta] = None

    @field_validator("regex")
    @classmethod
    def _regex_valido(cls, v: Optional[str]) -> Optional[str]:
        if v:
            import re

            re.compile(v)
        return v


class PalabraClaveDTO(BaseModel):
    texto: str = Field(min_length=1, max_length=200)
    peso: int = Field(default=1, ge=1, le=5)


class CampoPlantillaDTO(BaseModel):
    id: Optional[int] = None
    nombre: str = Field(min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_]+$")
    etiqueta: str = Field(min_length=1, max_length=200)
    tipo_dato: TipoDato = "texto"
    obligatorio: bool = False
    regla: ReglaCampo
    orden: int = 0


class PlantillaCrear(BaseModel):
    codigo: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9_]+$")
    nombre: str = Field(min_length=1, max_length=200)
    descripcion: Optional[str] = Field(default=None, max_length=1000)
    activa: bool = True
    umbral_confianza: float = Field(default=0.6, ge=0, le=1)
    palabras_clave: list[PalabraClaveDTO] = Field(default_factory=list)
    campos: list[CampoPlantillaDTO] = Field(default_factory=list)
    documento_ejemplo_id: Optional[str] = None
    creado_por: Optional[str] = None
    # diseño por posición de la versión (docs/13 §1.2); None = sin cuadrícula, se comporta como siempre
    diseno: Optional[DisenoPlantilla] = None


class PlantillaDTO(PlantillaCrear):
    id: int
    version_id: Optional[int] = None
    version: int = 1
    creado_en: Optional[datetime] = None
    actualizado_en: Optional[datetime] = None
    ejemplos_texto: list[str] = Field(default_factory=list, exclude=True)
    rol_minimo_edicion: str = "Editor"  # docs/07: rol mínimo para editar esta plantilla
    total_documentos: Optional[int] = None  # documentos procesados con alguna versión (solo en el listado)


class PlantillaEstado(BaseModel):
    activa: bool


# ---------------------------------------------------------------- Resultado
class AlternativaClasificacion(BaseModel):
    tipo: str
    confianza: float
    plantilla_id: Optional[int] = None


class Clasificacion(BaseModel):
    tipo: str = "desconocido"
    plantilla_id: Optional[int] = None
    version_id: Optional[int] = None
    confianza: float = 0.0
    alternativas: list[AlternativaClasificacion] = Field(default_factory=list)


class CampoExtraidoDTO(BaseModel):
    nombre: str
    campo_plantilla_id: Optional[int] = None
    valor: Any = None  # valor normalizado
    valor_texto: Optional[str] = None
    confianza: float = 0.0
    pagina: Optional[int] = None
    x: Optional[float] = None
    y: Optional[float] = None
    ancho: Optional[float] = None
    alto: Optional[float] = None
    valido: bool = False
    motor: Optional[str] = None  # motor OCR que dio la lectura final del campo
    # plantilla con diseño: la etiqueta leyó el valor fuera de la zona marcada (advertencia campo_fuera_de_zona)
    fuera_de_zona: bool = False


class ResultadoDTO(BaseModel):
    """Resultado interno del pipeline (antes de convertirlo al JSON del contrato)."""

    paginas: list[PaginaOCR]
    clasificacion: Clasificacion
    campos: list[CampoExtraidoDTO]
    palabras_clave: list[str]
    texto_completo: str
    confianza_global: float
    advertencias: list[str]
    tiempos_ms: dict[str, int]
    motor_ocr: str
    # coincidencia de DISEÑO con la plantilla (docs/13 §3.3); None si la plantilla no tiene cuadrícula
    coincidencia: Optional[dict[str, Any]] = None

    def a_contrato(self, documento_id: str, archivo: str, estado: str = "COMPLETADO") -> dict:
        """JSON del contrato (docs/01 sección 5)."""
        campos = {}
        for c in self.campos:
            item: dict[str, Any] = {"valor": c.valor, "confianza": round(c.confianza, 3), "pagina": c.pagina, "motor": c.motor}
            campos[c.nombre] = item
        return {
            "documento_id": documento_id,
            "archivo": archivo,
            "paginas": len(self.paginas),
            "estado": estado,
            "clasificacion": {
                "tipo": self.clasificacion.tipo,
                "plantilla_id": self.clasificacion.plantilla_id,
                "confianza": round(self.clasificacion.confianza, 3),
                "alternativas": [
                    {"tipo": a.tipo, "confianza": round(a.confianza, 3)} for a in self.clasificacion.alternativas
                ],
            },
            "campos": campos,
            "palabras_clave": self.palabras_clave,
            "texto_completo": self.texto_completo,
            "confianza_global": round(self.confianza_global, 3),
            "advertencias": self.advertencias,
            "tiempos_ms": self.tiempos_ms,
            "coincidencia": self.coincidencia,
        }


class DocumentoDTO(BaseModel):
    id: str
    nombre_archivo: str
    tipo_mime: str
    tamano_bytes: int
    hash_sha256: str
    paginas: int
    estado: str
    plantilla_forzada_id: Optional[int] = None
    mensaje_error: Optional[str] = None
    recibido_en: Optional[datetime] = None
    procesado_en: Optional[datetime] = None
    tipo_detectado: Optional[str] = None
    confianza_global: Optional[float] = None


class PalabraClaveSugerida(PalabraClaveDTO):
    # sugerida con un solo ejemplo: no hay con qué comparar para separar textos impresos de datos del titular
    revisar: bool = False


class SugerenciaPlantilla(BaseModel):
    documento_id: str  # el primero (compatibilidad)
    documento_ids: list[str] = Field(default_factory=list)
    palabras_clave: list[PalabraClaveSugerida]
    campos: list[CampoPlantillaDTO]
    texto: str
    # etiquetas fijas con su posición para precargar la cuadrícula (solo si el ejemplo tiene posiciones guardadas)
    zonas_sugeridas: list[ZonaEtiqueta] = Field(default_factory=list)
