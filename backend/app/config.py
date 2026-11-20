"""Configuración de la aplicación leída desde variables de entorno."""
from __future__ import annotations

import os
import platform
from pathlib import Path
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


def _tesseract_default() -> str:
    if platform.system() == "Windows":
        return r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    return "tesseract"


_TESSDATA_LOCAL = Path(__file__).resolve().parents[1] / "tessdata"


def resolver_tessdata(prefix: str, idioma: str = "spa") -> str | None:
    """Carpeta tessdata a usar. Si `prefix` está vacío, autodetecta backend/tessdata
    cuando contiene `<idioma>.traineddata`; si no, devuelve None (Tesseract usa su default)."""
    if prefix:
        return prefix
    primer_idioma = idioma.split("+")[0]
    if (_TESSDATA_LOCAL / f"{primer_idioma}.traineddata").is_file():
        return str(_TESSDATA_LOCAL)
    return None


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    DATABASE_URL: str = "sqlite:///./dev.db"
    API_KEY: str = "cambiar-en-produccion"
    # Motor principal: "paddle" (default) / "doctr" / "tesseract" (fallback ligero)
    OCR_MOTOR: str = "paddle"
    # Segunda opinión (validación cruzada) para campos de baja confianza: "doctr" / "ninguno"
    OCR_SEGUNDA_OPINION: str = "doctr"
    OCR_UMBRAL_SEGUNDA_OPINION: float = 0.7
    # Tope de lecturas OCR simultáneas (cada una es CPU-intensiva; el resto espera en cola)
    OCR_MAX_CONCURRENTES: int = 2
    # Tiempo máximo (s) de una lectura de segunda opinión; al vencer se conserva el motor principal
    OCR_SEGUNDA_OPINION_TIMEOUT_S: int = 60
    # Cargar los motores en segundo plano al arrancar (sin bloquear el API)
    OCR_PRECARGAR: bool = False
    OCR_IDIOMA: str = "spa"
    # --- Retención de documentos (datos personales): una sola política para TODO documento ---
    # Un documento más viejo que DOC_RETENCION_DIAS se elimina (archivo + registros). 0 = sin caducidad automática.
    DOC_RETENCION_DIAS: int = 30
    # Tarea en segundo plano que purga a diario. Apagada por defecto (no borrar bases de desarrollo por sorpresa);
    # docker-compose la enciende. También se puede purgar a mano (Administrador) con POST /api/purga.
    DOC_PURGA_AUTOMATICA: bool = False
    DOC_PURGA_INTERVALO_HORAS: int = 24
    # Versión del aviso de privacidad de la pantalla pública: súbela cuando cambie el texto; queda registrada
    # en cada documento junto con la fecha en que la persona lo aceptó.
    AVISO_PRIVACIDAD_VERSION: str = "1"
    # INTERRUPTOR GLOBAL del acceso público (fase 4): apagado por defecto. Con False, las rutas con modo público
    # se comportan como el resto de la API (sin X-API-Key = 401) y no se puede abrir ningún flujo al público.
    PUBLICO_HABILITADO: bool = False
    # --- Acceso PÚBLICO (sin API key) a POST /flujos-captura/{codigo}/documentos, solo en flujos con AccesoPublico ---
    # Límite por IP (ventana de 60 s), límite global y tope de procesamientos públicos simultáneos.
    PUBLICO_LIMITE_IP_POR_MINUTO: int = 10
    PUBLICO_LIMITE_GLOBAL_POR_MINUTO: int = 60
    PUBLICO_LIMITE_INFO_POR_MINUTO: int = 60  # GET /flujos-captura/{codigo}/publico (por IP)
    PUBLICO_MAX_CONCURRENTES: int = 2
    # Tamaño máximo (MB) de una subida SIN clave (se aplica el menor entre este y MAX_TAMANO_MB): cada subida se guarda en disco
    PUBLICO_MAX_TAMANO_MB: int = 10
    # Tomar la IP real de X-Forwarded-For (la agrega nginx). Solo activar si el backend NO es alcanzable
    # directamente desde fuera: de lo contrario un cliente podría falsear su IP y esquivar el límite por IP.
    PUBLICO_CONFIAR_PROXY: bool = False
    OCR_DPI: int = 300
    # Límites de la ingesta contra archivos pequeños en bytes pero enormes al decodificar ("bombas de píxeles"):
    # por encima del máximo se rechaza (400) sin decodificar; entre el tamaño de procesado y el máximo se reduce.
    OCR_MAX_MEGAPIXELES: int = 50  # una página/imagen mayor se rechaza (A4 a 600 DPI = 35 MP; un celular de 48 MP cabe)
    OCR_MEGAPIXELES_PROCESADO: int = 20  # tamaño al que se reduce una imagen grande (A4 a 300 DPI = 8,7 MP)
    OCR_MAX_PAGINAS: int = 30  # páginas de un PDF o fotogramas de un TIFF
    ALMACEN_RUTA: str = "./data/archivos"
    MAX_TAMANO_MB: int = 20
    UMBRAL_DESCONOCIDO: float = 0.5
    TESSERACT_CMD: str = _tesseract_default()
    # Carpeta con *.traineddata. Vacío = autodetectar (backend/tessdata si contiene el idioma)
    TESSDATA_PREFIX: str = ""
    # Pasos de preprocesado activables
    PRE_PERSPECTIVA: bool = True  # aplanar fotos de tarjetas/documentos tomadas en ángulo
    PRE_DESKEW: bool = True
    PRE_DENOISE: bool = True
    PRE_BINARIZAR: bool = True
    PRE_REESCALAR: bool = True
    # Crear tablas al arrancar (solo útil en desarrollo con SQLite)
    CREAR_TABLAS: bool = False
    LOG_LEVEL: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    if s.DATABASE_URL.startswith("sqlite") and os.environ.get("CREAR_TABLAS") is None:
        # Con SQLite no hay scripts SQL de otro agente: crear el esquema automáticamente.
        s.CREAR_TABLAS = True
    return s
