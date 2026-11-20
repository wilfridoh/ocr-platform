"""Servidor MCP (docs/02-backend.md §6, docs/01-diseno-general.md §7).

No reimplementa lógica: cada herramienta llama a la API REST con httpx.
Transporte: stdio por defecto; streamable-http si MCP_TRANSPORT=http.
"""
from __future__ import annotations

import os
from pathlib import Path

import httpx
from mcp.server.fastmcp import FastMCP

API = os.environ.get("OCR_API_URL", "http://localhost:8000/api")
KEY = os.environ.get("OCR_API_KEY", "cambiar-en-produccion")

mcp = FastMCP(
    "ocr-platform",
    host=os.environ.get("MCP_HOST", "127.0.0.1"),
    port=int(os.environ.get("MCP_PORT", "8000")),
)


def _headers() -> dict:
    return {"X-API-Key": KEY}


@mcp.tool()
def procesar_documento(ruta: str, plantilla_id: int | None = None) -> dict:
    """Lee un documento (PDF/imagen) desde una ruta local, lo clasifica y extrae sus campos.
    Devuelve el JSON estructurado del contrato (tipo, campos, confianza, texto completo)."""
    archivo = Path(ruta)
    if not archivo.exists():
        raise FileNotFoundError(f"No existe el archivo: {ruta}")
    with open(archivo, "rb") as f:
        data = {"plantilla_id": str(plantilla_id)} if plantilla_id is not None else {}
        r = httpx.post(
            f"{API}/documentos",
            files={"archivo": (archivo.name, f)},
            data=data,
            headers=_headers(),
            timeout=120,
        )
    r.raise_for_status()
    return r.json()


@mcp.tool()
def obtener_resultado(documento_id: str) -> dict:
    """Recupera el resultado (JSON del contrato) de un documento ya procesado anteriormente."""
    r = httpx.get(f"{API}/documentos/{documento_id}/resultado", headers=_headers(), timeout=30)
    r.raise_for_status()
    return r.json()


@mcp.tool()
def listar_plantillas(solo_activas: bool = True) -> list[dict]:
    """Lista las plantillas de documentos registradas con sus palabras clave y campos."""
    r = httpx.get(f"{API}/plantillas", params={"activa": solo_activas}, headers=_headers(), timeout=30)
    r.raise_for_status()
    return r.json()


@mcp.tool()
def obtener_plantilla(plantilla_id: int) -> dict:
    """Devuelve el detalle de una plantilla: palabras clave, campos y reglas de extracción."""
    r = httpx.get(f"{API}/plantillas/{plantilla_id}", headers=_headers(), timeout=30)
    r.raise_for_status()
    return r.json()


@mcp.tool()
def crear_plantilla(definicion: dict) -> dict:
    """Crea una plantilla a partir de una definición JSON (codigo, nombre, palabras_clave, campos)."""
    r = httpx.post(f"{API}/plantillas", json=definicion, headers=_headers(), timeout=30)
    r.raise_for_status()
    return r.json()


@mcp.tool()
def probar_plantilla(plantilla_id: int, documento_id: str) -> dict:
    """Aplica una plantilla a un documento ya procesado y devuelve el resultado SIN guardarlo."""
    r = httpx.post(
        f"{API}/plantillas/{plantilla_id}/probar",
        params={"documento_id": documento_id},
        headers=_headers(),
        timeout=60,
    )
    r.raise_for_status()
    return r.json()


@mcp.tool()
def buscar_documentos(
    tipo: str | None = None,
    estado: str | None = None,
    desde: str | None = None,
    hasta: str | None = None,
    pagina: int = 1,
    tamano: int = 20,
) -> dict:
    """Busca en el historial de documentos procesados, filtrando por tipo, estado y fechas."""
    params = {k: v for k, v in {
        "tipo": tipo, "estado": estado, "desde": desde, "hasta": hasta, "pagina": pagina, "tamano": tamano,
    }.items() if v is not None}
    r = httpx.get(f"{API}/documentos", params=params, headers=_headers(), timeout=30)
    r.raise_for_status()
    return r.json()


def main() -> None:
    transporte = os.environ.get("MCP_TRANSPORT", "stdio")
    if transporte == "http":
        mcp.run(transport="streamable-http")
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
