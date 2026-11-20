"""Protecciones de la ruta pública (sin API key): límite de peticiones en memoria y tope de concurrencia.

Pensado para un solo proceso (Docker Compose con un uvicorn). Con varios workers/réplicas cada proceso
llevaría su propia cuenta; en ese caso habría que mover el contador a un almacén compartido (p. ej. Redis).
"""
from __future__ import annotations

import hashlib
import threading
import time
from collections import deque

from fastapi import HTTPException, Request, status

from ..config import Settings


class LimitadorVentana:
    """Ventana deslizante: a lo sumo `limite` eventos por clave en los últimos `ventana_s` segundos."""

    def __init__(self, ventana_s: float = 60.0, max_claves: int = 10_000) -> None:
        self._ventana = ventana_s
        self._max_claves = max_claves
        self._eventos: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def intentar(self, clave: str, limite: int, ahora: float | None = None) -> float | None:
        """Registra el evento si cabe y devuelve None; si no cabe devuelve los segundos hasta poder reintentar."""
        ahora = time.monotonic() if ahora is None else ahora
        with self._lock:
            q = self._eventos.setdefault(clave, deque())
            while q and ahora - q[0] >= self._ventana:
                q.popleft()
            if len(q) >= limite:
                return max(1.0, self._ventana - (ahora - q[0]))
            q.append(ahora)
            if len(self._eventos) > self._max_claves:
                self._podar(ahora)
            return None

    def _podar(self, ahora: float) -> None:
        for k in [k for k, q in self._eventos.items() if not q or ahora - q[-1] >= self._ventana]:
            del self._eventos[k]

    def reiniciar(self) -> None:
        with self._lock:
            self._eventos.clear()


limitador = LimitadorVentana()
_ocupacion = threading.Lock()
_ocupados = 0


def ip_cliente(request: Request, settings: Settings) -> str:
    """IP del cliente. Con PUBLICO_CONFIAR_PROXY se usa la ÚLTIMA entrada de X-Forwarded-For (la que agregó
    nuestro nginx; las anteriores las puede falsear el cliente). Si no, la IP directa de la conexión."""
    if settings.PUBLICO_CONFIAR_PROXY:
        xff = request.headers.get("x-forwarded-for")
        if xff:
            ultima = xff.split(",")[-1].strip()
            if ultima:
                return ultima
    return request.client.host if request.client else "desconocida"


def huella_ip(ip: str, sal: str) -> str:
    """Identificador no reversible de la IP para la auditoría (permite correlacionar abusos sin guardar la IP)."""
    return hashlib.sha256(f"{ip}|{sal}".encode("utf-8")).hexdigest()[:12]


def _rechazar(segundos: float, detalle: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=detalle,
        headers={"Retry-After": str(int(segundos) + 1)},
    )


def limitar_subida_publica(ip: str, settings: Settings) -> None:
    """Límite por IP y global para subir documentos sin clave. Lanza 429 con Retry-After."""
    espera = limitador.intentar(f"subida:{ip}", settings.PUBLICO_LIMITE_IP_POR_MINUTO)
    if espera is not None:
        raise _rechazar(espera, "Demasiadas solicitudes desde tu dirección. Intenta de nuevo en un momento.")
    espera = limitador.intentar("subida:*", settings.PUBLICO_LIMITE_GLOBAL_POR_MINUTO)
    if espera is not None:
        raise _rechazar(espera, "El servicio está recibiendo muchas solicitudes. Intenta de nuevo en un momento.")


def limitar_info_publica(ip: str, settings: Settings) -> None:
    espera = limitador.intentar(f"info:{ip}", settings.PUBLICO_LIMITE_INFO_POR_MINUTO)
    if espera is not None:
        raise _rechazar(espera, "Demasiadas solicitudes desde tu dirección. Intenta de nuevo en un momento.")


class CupoConcurrencia:
    """Tope de procesamientos públicos simultáneos: evita que una avalancha anónima acapare el OCR (y los hilos)."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._tomado = False

    def __enter__(self) -> "CupoConcurrencia":
        global _ocupados
        with _ocupacion:
            if _ocupados >= self._settings.PUBLICO_MAX_CONCURRENTES:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="El servicio está ocupado procesando otros documentos. Intenta de nuevo en unos segundos.",
                    headers={"Retry-After": "5"},
                )
            _ocupados += 1
            self._tomado = True
        return self

    def __exit__(self, *exc) -> None:
        global _ocupados
        if self._tomado:
            with _ocupacion:
                _ocupados -= 1


def ocupados_ahora() -> int:
    return _ocupados


async def leer_con_tope(archivo, max_bytes: int) -> bytes:
    """Lee la subida por bloques y corta (413) al pasar el tope, sin cargar un archivo gigante en memoria."""
    partes: list[bytes] = []
    total = 0
    while True:
        bloque = await archivo.read(1024 * 1024)
        if not bloque:
            break
        total += len(bloque)
        if total > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"El archivo supera el límite de {max_bytes // (1024 * 1024)} MB",
            )
        partes.append(bloque)
    return b"".join(partes)
