"""Punto de entrada FastAPI."""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .api import documentos, flujos, plantillas, purga, resultados, salud, usuarios
from .config import get_settings
from .persistencia.db import inicializar_esquema

app = FastAPI(
    title="OCR Platform API",
    description="Lectura, clasificación y extracción de documentos vía OCR.",
    version="1.0.0",
    docs_url="/docs",
)


_RUTAS_SUBIDA = ("/api/documentos", "/api/flujos-captura/")


@app.middleware("http")
async def _tope_de_subida(request: Request, call_next):
    """Rechaza (413) las subidas cuyo Content-Length supera el límite ANTES de leer el cuerpo: así un cliente
    anónimo no puede obligar al servidor a recibir un archivo gigante. (Sin Content-Length —chunked— lo corta
    nginx con client_max_body_size y, además, leer_con_tope() en la ruta.)"""
    ruta = request.url.path
    if request.method == "POST" and ruta.startswith(_RUTAS_SUBIDA) and (ruta == "/api/documentos" or ruta.endswith("/documentos")):
        cl = request.headers.get("content-length")
        limite = (get_settings().MAX_TAMANO_MB + 1) * 1024 * 1024  # +1 MB de margen para el multipart
        if cl and cl.isdigit() and int(cl) > limite:
            return JSONResponse(
                status_code=413, content={"detail": f"El archivo supera el límite de {get_settings().MAX_TAMANO_MB} MB"}
            )
    return await call_next(request)


@app.on_event("startup")
def _startup() -> None:
    settings = get_settings()
    inicializar_esquema()
    import os

    os.makedirs(settings.ALMACEN_RUTA, exist_ok=True)
    from . import purga_automatica

    purga_automatica.iniciar(settings)  # solo si DOC_PURGA_AUTOMATICA=true y hay retención
    if settings.OCR_PRECARGAR:
        import threading

        from .pipeline.ocr import precargar_motores

        threading.Thread(target=precargar_motores, args=(settings,), daemon=True, name="ocr-precarga").start()


app.include_router(salud.router, prefix="/api")
app.include_router(documentos.router, prefix="/api")
app.include_router(resultados.router, prefix="/api")
app.include_router(plantillas.router, prefix="/api")
app.include_router(flujos.router, prefix="/api")
app.include_router(usuarios.router, prefix="/api")
app.include_router(usuarios.router_yo, prefix="/api")
app.include_router(purga.router, prefix="/api")
