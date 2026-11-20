# OCR Platform - backend API / MCP server
# Motor OCR principal: PaddleOCR (PP-OCRv5). Segunda opinión: docTR vía OnnxTR.
# Tesseract se mantiene como fallback ligero (docs/06-investigacion-ocr-engines.md).
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    TESSDATA_PREFIX=/usr/share/tesseract-ocr/5/tessdata

# --- Dependencias de sistema: Tesseract (fallback), unixodbc, ODBC Driver 18 de Microsoft
# (guía oficial: https://learn.microsoft.com/sql/connect/odbc/linux-mac/installing-the-microsoft-odbc-driver-for-sql-server)
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl gnupg2 ca-certificates apt-transport-https \
        tesseract-ocr tesseract-ocr-spa \
        unixodbc unixodbc-dev gcc g++ \
        libgl1 libglib2.0-0 \
    && curl -sSL -O https://packages.microsoft.com/keys/microsoft.asc \
    && gpg --dearmor microsoft.asc \
    && mkdir -p /usr/share/keyrings \
    && mv microsoft.asc.gpg /usr/share/keyrings/microsoft-prod.gpg \
    && curl -sSL -O https://packages.microsoft.com/config/debian/12/prod.list \
    && mv prod.list /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* microsoft.asc

WORKDIR /app

COPY requirements.txt requirements-ocr-extra.txt ./
# paddlepaddle: wheel CPU explícito (sin CUDA); paddleocr (PP-OCRv5); onnxtr (backend ONNX de docTR,
# evita cargar PyTorch/TensorFlow completos). poppler-utils ya no es necesario: pypdfium2 rasteriza PDFs.
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir -r requirements-ocr-extra.txt \
        --extra-index-url https://www.paddlepaddle.org.cn/packages/stable/cpu/

# Modelos OCR horneados en la imagen (build), no descargados en el primer request: imagen
# autocontenida/offline. Va antes de COPY app para que el layer se cachee al cambiar el código.
COPY precargar_modelos.py ./
RUN python precargar_modelos.py && rm precargar_modelos.py

COPY app ./app
COPY mcp_server ./mcp_server

ENV ALMACEN_RUTA=/data/archivos
RUN mkdir -p /data/archivos

EXPOSE 8000

# Arranque por defecto: API. El servidor MCP se construye desde la misma imagen
# con otro comando: `python -m mcp_server.server` (MCP_TRANSPORT=http para remoto).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
