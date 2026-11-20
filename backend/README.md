# OCR Platform — Backend

API FastAPI + pipeline OCR + servidor MCP. Ver `docs/02-backend.md` (y el
cambio de motor OCR en `docs/06-investigacion-ocr-engines.md`) en la raíz del
repositorio para el diseño completo.

## Requisitos

- Python 3.12
- Tesseract 5 instalado (fallback ligero; en Windows: `winget install -e --id UB-Mannheim.TesseractOCR`)
  con el paquete de idioma español (`spa.traineddata`).
- Para el motor principal (PaddleOCR) y la segunda opinión (docTR/OnnxTR), instalar además
  `requirements-ocr-extra.txt` (pesado; opcional en desarrollo local, obligatorio en Docker).

## Instalación local (Windows / PowerShell)

```powershell
$env:Path = [Environment]::GetEnvironmentVariable('Path','User') + ';' + [Environment]::GetEnvironmentVariable('Path','Machine')
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
# Opcional (motor principal PaddleOCR + segunda opinión docTR, requiere más tiempo/espacio):
.venv\Scripts\python.exe -m pip install -r requirements-ocr-extra.txt --extra-index-url https://www.paddlepaddle.org.cn/packages/stable/cpu/
copy .env.example .env
```

Si Tesseract no está en el PATH del sistema, define `TESSERACT_CMD` en `.env`
(por defecto en Windows: `C:\Program Files\Tesseract-OCR\tesseract.exe`).
Si `spa.traineddata` no quedó en `C:\Program Files\Tesseract-OCR\tessdata`,
puedes dejarlo en `backend/tessdata/` y apuntar `TESSDATA_PREFIX=./tessdata`.

## Correr en local

```powershell
$env:API_KEY = "dev"
$env:DATABASE_URL = "sqlite:///./dev.db"
.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Con `DATABASE_URL` apuntando a SQLite, la app crea las tablas automáticamente
al iniciar (`CREAR_TABLAS` se activa solo para SQLite). Con SQL Server, el
esquema lo crea el agente de base de datos con scripts en `db/schema.sql`;
el backend **no** usa Alembic ni `create_all` contra SQL Server.

Swagger: http://localhost:8000/docs — todas las rutas requieren la cabecera
`X-API-Key` salvo `/api/salud`.

### Ejemplos curl

```bash
curl http://localhost:8000/api/salud

curl -X POST http://localhost:8000/api/plantillas \
  -H "X-API-Key: dev" -H "Content-Type: application/json" \
  -d '{
        "codigo": "planilla_servicio_electrico",
        "nombre": "Planilla servicio eléctrico",
        "umbral_confianza": 0.3,
        "palabras_clave": [{"texto": "total a pagar", "peso": 3}],
        "campos": [
          {"nombre": "total_pagar", "etiqueta": "Total a pagar", "tipo_dato": "monto",
           "obligatorio": true, "regla": {"metodo": "regex", "regex": "Total a pagar\\s*\\$?\\s*([\\d.,]+)"}}
        ]
      }'

curl -X POST http://localhost:8000/api/documentos \
  -H "X-API-Key: dev" \
  -F "archivo=@planilla_luz.pdf"

curl -H "X-API-Key: dev" http://localhost:8000/api/documentos/<documento_id>/resultado
```

## Tests

```powershell
.venv\Scripts\python.exe -m pytest -q
```

Los tests de pipeline/API usan SQLite en memoria y marcan `skip` automáticamente
si Tesseract no está disponible en el entorno (las pruebas end-to-end fuerzan
`OCR_MOTOR=tesseract` para no depender de PaddleOCR/docTR en CI ligero).

## Servidor MCP

```powershell
$env:OCR_API_URL = "http://localhost:8000/api"
$env:OCR_API_KEY = "dev"
.venv\Scripts\python.exe -m mcp_server.server          # stdio (Claude Desktop / Claude Code)
$env:MCP_TRANSPORT = "http"; .venv\Scripts\python.exe -m mcp_server.server   # streamable-http
```

Herramientas expuestas: `procesar_documento`, `obtener_resultado`,
`listar_plantillas`, `obtener_plantilla`, `crear_plantilla`, `probar_plantilla`,
`buscar_documentos`.

## Variables de entorno

Ver `.env.example`. Las más relevantes: `DATABASE_URL`, `API_KEY`, `OCR_MOTOR`
(`paddle`/`doctr`/`tesseract`), `OCR_SEGUNDA_OPINION`, `ALMACEN_RUTA`.

## Docker

```bash
docker build -t ocr-backend .
docker run -p 8000:8000 --env-file .env ocr-backend
```

El servidor MCP se construye desde la misma imagen con otro comando de
arranque: `python -m mcp_server.server`.

## Limitaciones conocidas / desviaciones

Ver el reporte final del agente en la conversación de la tarea para el
detalle de limitaciones y desviaciones respecto a `docs/02-backend.md`.
