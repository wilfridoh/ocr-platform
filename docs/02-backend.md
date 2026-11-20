# 02 — Backend: API, pipeline OCR y servidor MCP

## 1. Stack

| Pieza | Elección | Versión |
|---|---|---|
| Lenguaje | Python | 3.12 |
| Framework web | FastAPI + Uvicorn | última estable |
| OCR | **PaddleOCR (PP-OCRv5)** motor principal; **docTR** como segunda opinión; Tesseract 5 (`pytesseract`) como fallback ligero. Ver [docs/06-investigacion-ocr-engines.md](06-investigacion-ocr-engines.md) | |
| Imagen | OpenCV (`opencv-python-headless`), Pillow, `pdf2image` (Poppler) | |
| PDF nativo | `pypdfium2` para extraer texto sin OCR cuando el PDF ya lo tiene | |
| Base de datos | SQL Server vía SQLAlchemy 2 + `pyodbc` (ODBC Driver 18) | |
| Migraciones | Alembic | |
| Validación | Pydantic v2 | |
| MCP | SDK oficial `mcp` (Python) | |
| Tests | pytest | |

## 2. Estructura del código

```
backend/
├── app/
│   ├── main.py                  # crea la app FastAPI, registra routers
│   ├── config.py                # settings desde variables de entorno
│   ├── api/                     # capa HTTP
│   │   ├── documentos.py
│   │   ├── plantillas.py
│   │   ├── resultados.py
│   │   └── salud.py
│   ├── commands/                # CQRS: acciones que cambian estado
│   │   ├── procesar_documento.py
│   │   ├── crear_plantilla.py
│   │   └── actualizar_plantilla.py
│   ├── queries/                 # CQRS: lecturas
│   │   ├── listar_plantillas.py
│   │   ├── obtener_resultado.py
│   │   └── buscar_documentos.py
│   ├── pipeline/                # núcleo OCR, independiente de HTTP y BD
│   │   ├── ingesta.py           # validar, PDF→imágenes, detectar PDF nativo
│   │   ├── preprocesado.py      # gris, deskew, binarización, denoise
│   │   ├── ocr.py               # interfaz MotorOCR + PaddleOCRMotor + DocTRMotor + TesseractOCR (fallback)
│   │   ├── clasificador.py      # puntuar plantillas
│   │   ├── extractor.py         # aplicar reglas de campos
│   │   ├── validadores.py       # fecha, monto, RUT/cédula
│   │   └── ensamblador.py       # construir el JSON final
│   ├── dominio/                 # modelos Pydantic (Plantilla, Campo, Resultado...)
│   ├── persistencia/            # SQLAlchemy: modelos ORM y repositorios
│   └── almacen/                 # guardar/leer archivos (disco o blob)
├── mcp_server/
│   └── server.py                # herramientas MCP que llaman a la API
├── alembic/                     # migraciones
├── tests/
├── Dockerfile
└── requirements.txt
```

Regla: **`pipeline/` no importa nada de `api/` ni de `persistencia/`**. Recibe bytes y plantillas, devuelve un resultado. Así se puede probar sin servidor ni base de datos y mover a un worker después.

## 3. API REST

Base: `http://localhost:8000/api`. Todas las rutas requieren cabecera `X-API-Key` salvo `/salud`.

### Documentos

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/documentos` | Sube un archivo (`multipart/form-data`) y lo procesa. Parámetros opcionales: `plantilla_id` (forzar tipo), `sincrono=true/false` |
| `GET` | `/documentos` | Lista con filtros: `tipo`, `estado`, `desde`, `hasta`, `pagina`, `tamano` |
| `GET` | `/documentos/{id}` | Metadatos y estado |
| `GET` | `/documentos/{id}/resultado` | JSON de resultado (contrato del diseño general) |
| `GET` | `/documentos/{id}/archivo` | Descarga el original |
| `GET` | `/documentos/{id}/paginas/{n}` | Imagen de la página (para la UI de plantillas) |
| `GET` | `/documentos/{id}/paginas/{n}/enderezada` | Página recortada, girada y enderezada, en color: el marco de las coordenadas de `/palabras`. Cabeceras `X-Recorte-Confiable`, `X-Recorte-Origen` (`automatico`/`manual`/`ninguno`/`pdf`/`desconocido`) y `X-Orientacion`. `?relacion=` opcional para juzgar el recorte con la proporción de una plantilla nueva (docs/13 §7); `?formato=jpeg` (calidad 90) para móvil, PNG por defecto. |
| `GET` | `/documentos/{id}/paginas/{n}/palabras` | `{pagina, recorte: {confiable, aplicado, origen, esquinas, relacion, orientacion}, palabras: [{texto, x, y, ancho, alto, confianza}]}` con coordenadas relativas 0–1. 404 «Reprocese el documento…» si es anterior a la migración 009. |
| `POST` | `/documentos/{id}/paginas/{n}/recorte` | Recorte y/o giro manual: `{esquinas?: [[x,y]×4], orientacion?: 0\|90\|180\|270}`. Las esquinas son relativas a la imagen original (arriba-izq, arriba-der, abajo-der, abajo-izq). Valida (422 si no es un cuadrilátero convexo razonable), reprocesa y devuelve el resultado. Los reprocesos posteriores conservan el recorte manual. |
| `POST` | `/documentos/{id}/reprocesar` | Vuelve a ejecutar el pipeline (por ejemplo, tras editar una plantilla) |

### Plantillas

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/plantillas` | Lista (filtro `activa`) |
| `GET` | `/plantillas/{id}` | Detalle con palabras clave y campos |
| `POST` | `/plantillas` | Crea plantilla |
| `PUT` | `/plantillas/{id}` | Edita (crea nueva versión) |
| `PATCH` | `/plantillas/{id}/estado` | Activa / desactiva |
| `POST` | `/plantillas/sugerir` | Recibe un `documento_id` y devuelve palabras clave y campos sugeridos |
| `POST` | `/plantillas/{id}/probar` | Aplica la plantilla a un `documento_id` sin guardar |
| `GET` | `/plantillas/{id}/versiones` | Historial de versiones: `[{version, fecha, comentario}]` (404 si la plantilla no existe) |
| `POST` | `/plantillas/{id}/reprocesar` | Reprocesa todos los documentos clasificados con cualquier versión de esta plantilla; devuelve `{total, errores}` |

### Sistema

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/salud` | Estado de API, BD, Tesseract |
| `GET` | `/docs` | Swagger generado por FastAPI |

### Modelo de plantilla (entrada/salida de la API)

```json
{
  "id": 3,
  "codigo": "planilla_servicio_electrico",
  "nombre": "Planilla servicio eléctrico",
  "descripcion": "Boleta mensual de electricidad",
  "activa": true,
  "umbral_confianza": 0.6,
  "palabras_clave": [
    { "texto": "consumo kwh", "peso": 3 },
    { "texto": "total a pagar", "peso": 2 },
    { "texto": "lectura anterior", "peso": 2 }
  ],
  "campos": [
    {
      "nombre": "numero_cliente",
      "etiqueta": "Número de cliente",
      "tipo_dato": "texto",
      "obligatorio": true,
      "regla": { "metodo": "ancla", "ancla": "N° Cliente", "regex": "[\\d.-]+" }
    },
    {
      "nombre": "total_pagar",
      "etiqueta": "Total a pagar",
      "tipo_dato": "monto",
      "obligatorio": true,
      "regla": { "metodo": "regex", "regex": "Total a pagar\\s*\\$?\\s*([\\d.,]+)" }
    },
    {
      "nombre": "direccion",
      "etiqueta": "Dirección",
      "tipo_dato": "texto",
      "obligatorio": false,
      "regla": { "metodo": "zona", "pagina": 1, "x": 0.05, "y": 0.18, "ancho": 0.5, "alto": 0.06 }
    }
  ]
}
```

Tipos de dato soportados: `texto`, `numero`, `monto`, `fecha`, `rut`, `cedula`, `email`, `telefono`. Cada tipo tiene un validador y un normalizador (por ejemplo, `monto` convierte `"45.320"` en `45320`).

Métodos de regla:
- **`regex`**: expresión sobre el texto completo; el grupo 1 es el valor.
- **`ancla`**: busca el texto ancla (tolerante a errores OCR) y toma lo que sigue en la misma línea o la siguiente, filtrado por `regex` opcional.
- **`zona`**: recorta un rectángulo relativo de la página y lee ahí; útil cuando no hay texto ancla.

## 4. Pipeline en detalle

### 4.1 Ingesta
- Acepta `pdf`, `jpg`, `jpeg`, `png`, `tiff`. Límite de tamaño configurable (20 MB por defecto).
- Si es PDF, detecta si tiene **texto nativo** (`pypdfium2`). Si lo tiene, se usa directamente y se omite el OCR (más rápido y exacto). Si no, se rasteriza a 300 DPI.
- Calcula hash SHA-256 para detectar duplicados.

### 4.2 Preprocesado (OpenCV)
1. Escala de grises.
2. Corrección de inclinación (deskew) por transformada de Hough o minAreaRect.
3. Reducción de ruido (`fastNlMeansDenoising` suave).
4. Binarización adaptativa (Sauvola/Otsu según histograma).
5. Si la imagen es pequeña, reescalado para alcanzar ~30 px de altura de línea.

Cada paso se puede desactivar por configuración; se guarda qué pasos se aplicaron para auditoría.

### 4.3 OCR
Interfaz única:

```python
class MotorOCR(Protocol):
    def leer(self, imagen: np.ndarray, idioma: str) -> PaginaOCR: ...

class PaginaOCR:
    texto: str
    palabras: list[PalabraOCR]   # texto, x, y, ancho, alto, confianza, linea, bloque
    confianza_media: float
```

Implementaciones: `PaddleOCRMotor` (**por defecto**, modelo `latin_PP-OCRv5_mobile_rec`, CPU-only), `DocTRMotor` (segunda opinión vía `OnnxTR`, se invoca cuando la confianza de un campo cae bajo umbral, para validación cruzada) y `TesseractOCR` (`--oem 1 --psm 6`, idioma `spa`, fallback si los motores deep learning fallan o el entorno tiene recursos muy restringidos). Se elige por variable de entorno `OCR_MOTOR`.

> **Cambio respecto a la v1 de este documento:** el motor por defecto era Tesseract, con PaddleOCR como alternativa. La investigación de mercado en [docs/06-investigacion-ocr-engines.md](06-investigacion-ocr-engines.md) encontró evidencia (CER en benchmarks externos: PaddleOCR ≈ 20.5%, docTR ≈ 19.7%, Tesseract ≈ 33.6%) de que Tesseract es el menos preciso de los tres, así que se invirtió la jerarquía. Antes de fijarlo en producción, correr `scripts/evaluar.py` (§9) sobre una muestra real en español es la validación que pesa más que el benchmark externo.

### 4.4 Clasificación
Para cada plantilla activa:

```
score = suma(peso_i × presencia_i) / suma(peso_i)        # palabras clave, con tolerancia OCR
      × 0.7
      + similitud_coseno(TF-IDF texto, TF-IDF ejemplos_plantilla) × 0.3
```

- La presencia se calcula con coincidencia aproximada (distancia de Levenshtein ≤ 1 o 2 según longitud) para tolerar errores típicos del OCR (`0/O`, `1/l`).
- Gana la plantilla con mayor score si supera su `umbral_confianza`; si no, `desconocido`.
- Se devuelven las 3 mejores alternativas.

### 4.5 Extracción
Aplica cada campo de la plantilla ganadora con su método. La confianza del campo combina la confianza OCR media de las palabras usadas y si el validador del tipo de dato aceptó el valor.

**Catálogo de valores** (`"catalogo": [...]` en la regla, opcional): lista de formas canónicas del campo (p. ej. los gentilicios de `nacionalidad` en la cédula, migración 008).
- Si la regla encuentra un valor que coincide con un elemento, o está a **un** carácter de distancia (Levenshtein ≤ 1, sin distinguir mayúsculas ni tildes), el valor guardado es la forma canónica. Ejemplo: `LCUATORIANA` se guarda como `ECUATORIANA`. `ValorTexto` conserva lo que leyó el OCR.
- Si la regla no encuentra nada, se busca en el texto la primera palabra que cumpla lo mismo.
- La tolerancia de un carácter solo aplica a elementos de 7 letras o más; en palabras cortas, un carácter cambia la palabra.
- Si la lectura queda a un carácter de dos elementos (`ECUATORIANX`), no se elige ninguno.

### 4.6 Validación y normalización
- `fecha`: reconoce `dd/mm/yyyy`, `dd-mm-yy`, `12 de marzo de 2026`, `03 NOV 1990`; devuelve ISO 8601. Una fecha inexistente (31/02) no es válida. Además, la lectura se marca **no válida** (advertencia `campo_no_valido`, o `campo_obligatorio_faltante` si el campo es obligatorio; nunca se guarda como fecha) cuando:
  - **Está fuera del rango plausible del campo**, que se elige por el nombre o la etiqueta del campo:
    - *nacimiento*: entre hoy − 120 años y hoy.
    - *vencimiento/caducidad*: entre 1900 y hoy + 30 años.
    - otras fechas: entre 1900 y hoy + 100 años.
  - **Se infirió sin etiqueta y el día solo se entiende cambiando letras por dígitos.** Es el respaldo de la fecha de nacimiento cuando la etiqueta salió ilegible; por ejemplo, `1l.OCT 1990`. Se guarda tal como se leyó, sin adivinar el día.
  - **Los dos motores la leen distinto.** El motor principal dejó una lectura no válida y la segunda opinión trae una fecha válida que la contradice: otro mes, o un dígito legible distinto. Las letras que solo pueden ser un dígito concreto (`l`/`I`→1, `O`→0, `S`→5…) cuentan como ese dígito; otra letra en esa posición no contradice nada. Por ejemplo, `1l.OCT 1320` frente a `10 OCT 1920`. Queda la lectura del principal, no válida, para revisión. Si en cambio la segunda opinión solo completa lo ilegible (`03 NOV d990` → `03 NOV 1990`), se acepta.
- `monto`: elimina separadores de miles, detecta coma decimal; devuelve número.
- `rut` / `cedula`: dígito verificador (RUT chileno módulo 11; otros formatos configurables).
- Campos obligatorios ausentes → advertencia `campo_obligatorio_faltante`.

### 4.7 Ensamblado
Construye el JSON del contrato (ver diseño general), calcula `confianza_global` como media ponderada de clasificación y campos obligatorios, y persiste.

## 5. Sugerencia automática de plantillas

Endpoint `POST /plantillas/sugerir`. Sobre el texto OCR de un documento de ejemplo:
- **Palabras clave sugeridas**: n-gramas (1 a 3 palabras) con alta frecuencia en el documento y baja frecuencia en el resto del corpus procesado (TF-IDF). Se proponen las 10 mejores.
- **Campos sugeridos**: patrones detectados con regex genéricos (fechas, montos, RUT/cédulas, correos, teléfonos, números largos) junto al texto ancla que los precede en la misma línea. El usuario los renombra y confirma.

## 6. Servidor MCP

Archivo `mcp_server/server.py`. Usa `FastMCP` del SDK oficial. Cada herramienta llama a la API REST con `httpx`, reutilizando `X-API-Key`.

```python
from mcp.server.fastmcp import FastMCP
import httpx, os

API = os.environ["OCR_API_URL"]
KEY = os.environ["OCR_API_KEY"]
mcp = FastMCP("ocr-platform")

@mcp.tool()
def procesar_documento(ruta: str, plantilla_id: int | None = None) -> dict:
    """Lee un documento (PDF/imagen), lo clasifica y extrae sus campos. Devuelve JSON estructurado."""
    with open(ruta, "rb") as f:
        r = httpx.post(f"{API}/documentos", files={"archivo": f},
                       data={"plantilla_id": plantilla_id} if plantilla_id else None,
                       headers={"X-API-Key": KEY}, timeout=120)
    r.raise_for_status()
    return r.json()

@mcp.tool()
def listar_plantillas(solo_activas: bool = True) -> list[dict]:
    """Lista las plantillas de documentos registradas con sus campos."""
    ...

# obtener_resultado, obtener_plantilla, crear_plantilla, probar_plantilla, buscar_documentos
```

Transporte: `stdio` para uso local desde Claude Desktop / Claude Code, y `streamable-http` en el contenedor para acceso remoto. Configuración de ejemplo para un cliente MCP:

```json
{
  "mcpServers": {
    "ocr-platform": {
      "command": "python",
      "args": ["-m", "mcp_server.server"],
      "env": { "OCR_API_URL": "http://localhost:8000/api", "OCR_API_KEY": "..." }
    }
  }
}
```

## 7. Configuración (variables de entorno)

| Variable | Ejemplo | Descripción |
|---|---|---|
| `DATABASE_URL` | `mssql+pyodbc://sa:Pass@mssql:1433/ocr?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes` | Conexión SQL Server |
| `API_KEY` | `cambiar-en-produccion` | Clave de la API |
| `OCR_MOTOR` | `paddle` (default) / `doctr` / `tesseract` | Motor principal |
| `OCR_SEGUNDA_OPINION` | `doctr` / `ninguno` | Motor usado para validación cruzada en campos de baja confianza |
| `OCR_UMBRAL_SEGUNDA_OPINION` | `0.7` | Confianza mínima de un campo antes de pedir segunda opinión |
| `OCR_SEGUNDA_OPINION_SOLO_OBLIGATORIOS` | `true` | La segunda opinión es lenta (~13 s por página). Con `true`, un campo **no obligatorio y vacío** no la dispara por sí solo (muchas variantes de un documento no traen todos los opcionales, p. ej. una cédula sin fecha de vencimiento); la disparan los obligatorios vacíos o bajo el umbral y cualquier campo con valor bajo el umbral, y entonces también se reintentan los opcionales vacíos. Con `false`, cualquier campo bajo el umbral la dispara (comportamiento anterior) |
| `OCR_IDIOMA` | `spa` | Idioma (Tesseract; PaddleOCR/docTR usan su modelo latino) |
| `OCR_DPI` | `300` | Resolución al rasterizar PDF |
| `ALMACEN_RUTA` | `/data/archivos` | Carpeta de archivos |
| `MAX_TAMANO_MB` | `20` | Límite de carga |
| `UMBRAL_DESCONOCIDO` | `0.5` | Umbral global mínimo de clasificación |
| `OCR_MAX_MEGAPIXELES` | `50` | Imagen/página de más megapíxeles se rechaza (400) sin decodificarla (anti «bomba de píxeles») |
| `OCR_MEGAPIXELES_PROCESADO` | `20` | Tamaño al que se reduce una imagen grande antes del OCR (A4 a 300 DPI = 8,7 MP) |
| `PRE_PERSPECTIVA` | `true` | Aplanar fotos de documentos/tarjetas tomadas en ángulo antes del OCR (si no detecta un contorno confiable, no hace nada) |
| `OCR_MAX_PAGINAS` | `30` | Máximo de páginas de un PDF o fotogramas de un TIFF |
| `DOC_RETENCION_DIAS` | `30` | Días que se conserva un documento; pasado el plazo se elimina (archivo + registros). `0` = sin caducidad automática. Una sola política para todo documento (docs/07 §5.3) |
| `DOC_PURGA_AUTOMATICA` / `DOC_PURGA_INTERVALO_HORAS` | `false` / `24` | Hilo que purga los vencidos a diario. Apagado por defecto en el código; `docker-compose.yml` lo enciende |
| `AVISO_PRIVACIDAD_VERSION` | `1` | Versión del aviso de privacidad de la pantalla pública; se registra con cada consentimiento. Súbela si cambia el texto |
| `PUBLICO_HABILITADO` | `false` | Interruptor global del acceso público sin API key (docs/07 §5.2). Apagado: toda la API exige clave |
| `PUBLICO_LIMITE_IP_POR_MINUTO` / `PUBLICO_LIMITE_GLOBAL_POR_MINUTO` / `PUBLICO_LIMITE_INFO_POR_MINUTO` | `10` / `60` / `60` | Límites del modo público (por IP, global y para la consulta del flujo) |
| `PUBLICO_MAX_CONCURRENTES` / `PUBLICO_MAX_TAMANO_MB` | `2` / `10` | Procesamientos públicos simultáneos y tamaño máximo de una subida sin clave |
| `PUBLICO_CONFIAR_PROXY` | `false` | Usar la IP de `X-Forwarded-For` (solo si el backend no es alcanzable directo; ver docs/05 §5.1) |

## 8. Manejo de errores

| Situación | Código HTTP | `estado` del documento |
|---|---|---|
| Formato no soportado / archivo corrupto | 400 | — (no se guarda) |
| Falla de OCR (el motor configurado no responde) | 500 | `ERROR` con `mensaje_error` |
| Ningún tipo supera umbral | 200 | `COMPLETADO` con tipo `desconocido` |
| Plantilla forzada no existe | 404 | — |

Todo error del pipeline se registra en `LogProcesamiento` con paso, mensaje y duración.

## 9. Pruebas

- **Unitarias** del pipeline con imágenes sintéticas (texto renderizado con PIL) para cada validador, método de regla y el clasificador.
- **De integración**: levantar API con SQL Server en contenedor, subir documentos de `tests/muestras/` y comparar contra `tests/esperados/*.json`.
- **Métrica**: script `scripts/evaluar.py` (implementado) que calcula CER y exactitud por campo sobre un conjunto etiquetado, comparando motores. Uso:
  `backend\.venv\Scripts\python.exe scripts\evaluar.py CARPETA --esperado esperado.json --plantilla plantilla.json --motores paddle,doctr,tesseract [-v] [--salida out.json]`.
  `esperado.json`: `{"archivo.png": {"texto": "<referencia, opcional → CER>", "campos": {"nombre_campo": valor}}}`; `plantilla.json`: mismo JSON de `POST /plantillas`. Ver la cabecera del script.

## 10. Docker

`backend/Dockerfile` basado en `python:3.12-slim` instalando `paddlepaddle` (wheel CPU, fijado explícitamente para evitar que intente usar CUDA) + `paddleocr`, `onnxtr` (backend ONNX de docTR, evita cargar PyTorch/TensorFlow completos), y como fallback `tesseract-ocr` + `tesseract-ocr-spa`, además de `unixodbc` y el ODBC Driver 18 de Microsoft. `poppler-utils` ya no es necesario: la rasterización de PDF usa `pypdfium2` (ver §4.1). Expone 8000. El servidor MCP se construye desde la misma imagen con otro comando de arranque.
