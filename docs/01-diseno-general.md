# 01 — Diseño general

## 1. Objetivo

Construir una plataforma que, dado un documento escaneado o fotografiado, devuelva un **JSON** con:

- el **tipo de documento** detectado (por ejemplo: *cuenta de contrato*, *planilla de servicio*, *cédula*),
- el **texto completo** leído por OCR,
- los **campos extraídos** según la plantilla de ese tipo (número de contrato, dirección, cliente, monto, fecha, etc.),
- las **palabras clave** encontradas y un **nivel de confianza** por cada dato.

La plataforma debe ser **administrable** (crear y mantener plantillas sin programar), **integrable** (API REST y servidor MCP) y **portable** (Docker, local hoy, nube mañana).

## 2. Alcance

### Incluido en esta fase
| # | Capacidad |
|---|---|
| 1 | Carga de documentos: JPG, PNG, PDF (nativo o escaneado), varias páginas |
| 2 | OCR local con preprocesamiento de imagen |
| 3 | Clasificación del documento contra las plantillas registradas |
| 4 | Extracción de campos definidos en la plantilla y salida JSON |
| 5 | Detección de palabras clave configurables (por ejemplo: "dirección", "total a pagar") |
| 6 | Administrador de plantillas: listar, crear desde un documento de ejemplo, editar campos, activar/desactivar |
| 7 | Historial de documentos procesados y su resultado |
| 8 | Servidor MCP que expone todo lo anterior como herramientas para agentes de IA |
| 9 | Despliegue con Docker Compose: API, frontend, MCP y SQL Server |

### Fuera de alcance (fases siguientes)
- Reconocimiento facial y comparación biométrica cédula vs. selfie (**fase 2, próxima semana**).
- Firma digital, flujo de aprobación, multiusuario con roles.
- Entrenamiento de modelos OCR propios.

## 3. Supuestos de diseño

Estos puntos se asumieron porque el requerimiento no los fijó. Si alguno no aplica, se ajusta el diseño.

| Supuesto | Valor asumido | Impacto si cambia |
|---|---|---|
| Idioma de los documentos | Español | Agregar paquetes de idioma al OCR |
| Tipos iniciales | Cuenta de contrato, planilla de servicio, cédula de identidad | Solo cambian las plantillas semilla |
| Motor OCR | Local (PaddleOCR principal; docTR segunda opinión; Tesseract fallback — ver [docs/06](06-investigacion-ocr-engines.md)). Los documentos no salen de la infraestructura | Si se permite un modelo de visión vía API, la extracción mejora y se simplifica |
| Volumen | Decenas a cientos de documentos por día, procesamiento síncrono o en cola corta | Para miles por hora se agrega un worker con cola |
| Autenticación | API key simple | Si se requiere SSO/roles se agrega capa de identidad |

## 4. Arquitectura

```
┌──────────────────────────────────────────────────────────────────────┐
│                           CLIENTES                                   │
│   Navegador (Frontend React)        Agente IA (Claude, etc.)         │
└───────────────┬─────────────────────────────┬────────────────────────┘
                │ HTTP/JSON                   │ MCP (stdio / HTTP)
                ▼                             ▼
┌───────────────────────────┐   ┌─────────────────────────────┐
│   API REST  (FastAPI)     │◄──│   Servidor MCP (Python)     │
│   /documentos /plantillas │   │   tools: procesar_documento │
│   /resultados /salud      │   │   listar_plantillas, ...    │
└─────────────┬─────────────┘   └─────────────────────────────┘
              │
              ▼
┌──────────────────────────────────────────────────────────────┐
│                    NÚCLEO DE PROCESAMIENTO                    │
│                                                              │
│  1. Ingesta        → valida archivo, convierte PDF a imágenes │
│  2. Preprocesado   → gris, deskew, binarización, denoise      │
│  3. OCR            → texto + cajas + confianza por palabra    │
│  4. Clasificación  → puntúa cada plantilla, elige la mejor    │
│  5. Extracción     → aplica reglas de campos de la plantilla  │
│  6. Validación     → formatos (fecha, RUT/cédula, monto)      │
│  7. Ensamblado     → JSON final + confianza global            │
└─────────────────────────────┬────────────────────────────────┘
                              │
                              ▼
                 ┌─────────────────────────┐    ┌──────────────────┐
                 │  SQL Server             │    │  Almacén archivos│
                 │  plantillas, documentos │    │  (volumen Docker │
                 │  resultados, auditoría  │    │   o blob storage)│
                 └─────────────────────────┘    └──────────────────┘
```

### Componentes

| Componente | Tecnología | Responsabilidad |
|---|---|---|
| **Frontend** | React + Vite + TypeScript | Subir documentos, ver resultado JSON, administrar plantillas, historial |
| **API Backend** | Python 3.12 + FastAPI | Exponer endpoints, orquestar el pipeline, persistir |
| **Núcleo OCR** | OpenCV + PaddleOCR (principal) + docTR (segunda opinión) + Tesseract (fallback) | Leer el documento |
| **Clasificador** | Reglas: palabras clave ponderadas + similitud de texto (TF-IDF) | Elegir plantilla |
| **Extractor** | Reglas por campo: regex, anclas de texto, zonas (coordenadas relativas) | Obtener los valores |
| **Servidor MCP** | SDK oficial `mcp` para Python | Exponer herramientas a agentes |
| **Base de datos** | SQL Server 2022 (contenedor `mcr.microsoft.com/mssql/server`) | Persistencia |
| **Orquestación** | Docker Compose | Levantar todo con un comando |

### Patrón CQRS (ligero)

El backend separa **comandos** (acciones que cambian estado: procesar documento, crear plantilla) de **consultas** (lecturas: listar plantillas, obtener resultado). No se usan dos bases de datos ni event sourcing; es una separación de código que mantiene el pipeline de procesamiento aislado de las pantallas de consulta y facilita mover el procesamiento a un worker asíncrono más adelante.

## 5. Flujo principal: procesar un documento

```
Usuario sube "planilla_luz.pdf"
   │
   ▼
POST /api/documentos            → se guarda el archivo, estado = RECIBIDO
   │
   ▼
Pipeline                        → estado = PROCESANDO
   ├─ PDF → imágenes 300 DPI
   ├─ Preprocesado por página
   ├─ OCR → texto + palabras con coordenadas y confianza
   ├─ Clasificación:
   │     plantilla "Planilla servicio eléctrico"  score 0.91  ✔
   │     plantilla "Cuenta de contrato"           score 0.34
   │     plantilla "Cédula"                       score 0.02
   ├─ Extracción con la plantilla ganadora:
   │     numero_cliente  = "1234567-8"   (regex tras ancla "N° Cliente")
   │     direccion       = "Av. Siempre Viva 742" (zona superior derecha)
   │     total_pagar     = 45.320        (regex monto tras "Total a pagar")
   │     fecha_venc      = 2026-11-30    (regex fecha, validada)
   ├─ Palabras clave encontradas: ["dirección", "consumo", "total a pagar"]
   └─ Confianza global 0.87
   │
   ▼
Se guarda el resultado           → estado = COMPLETADO
   │
   ▼
Respuesta JSON
```

### Formato de salida (contrato JSON)

```json
{
  "documento_id": "9f3c2a1e-...",
  "archivo": "planilla_luz.pdf",
  "paginas": 1,
  "estado": "COMPLETADO",
  "clasificacion": {
    "tipo": "planilla_servicio_electrico",
    "plantilla_id": 3,
    "confianza": 0.91,
    "alternativas": [{ "tipo": "cuenta_contrato", "confianza": 0.34 }]
  },
  "campos": {
    "numero_cliente": { "valor": "1234567-8", "confianza": 0.95, "pagina": 1, "motor": "paddle" },
    "direccion":      { "valor": "Av. Siempre Viva 742", "confianza": 0.82, "pagina": 1, "motor": "paddle" },
    "total_pagar":    { "valor": 45320, "confianza": 0.93, "pagina": 1, "motor": "doctr" },
    "fecha_vencimiento": { "valor": "2026-11-30", "confianza": 0.90, "pagina": 1, "motor": "paddle" }
  },
  "palabras_clave": ["dirección", "consumo", "total a pagar"],
  "texto_completo": "....",
  "confianza_global": 0.87,
  "advertencias": [],
  "tiempos_ms": { "ocr": 1840, "clasificacion": 25, "extraccion": 40, "total": 1950 }
}
```

Si ningún tipo supera el umbral de confianza, `clasificacion.tipo` es `"desconocido"` y el JSON incluye igualmente el texto completo y las palabras clave, para que el usuario pueda **crear una plantilla nueva desde ese documento**.

## 6. Flujo secundario: crear una plantilla

1. El usuario entra al **Administrador de plantillas** y pulsa *Nueva plantilla*.
2. Sube un documento de ejemplo. El sistema lo lee con OCR y muestra el texto con sus zonas.
3. El usuario indica:
   - nombre y código del tipo (`planilla_servicio_electrico`),
   - palabras clave que identifican el tipo (con un peso cada una),
   - campos a extraer: nombre, tipo de dato, y regla (regex, ancla "texto que lo precede", o zona dibujada sobre la imagen).
4. El sistema prueba la plantilla sobre el documento de ejemplo y muestra el JSON resultante.
5. Se guarda. Desde ese momento todos los documentos nuevos se comparan también contra esta plantilla.

El sistema **sugiere** automáticamente palabras clave (términos frecuentes y distintivos del ejemplo) y campos candidatos (patrones de fecha, montos, números largos), para que la creación sea rápida.

## 7. Integración MCP

El servidor MCP expone la plataforma como herramientas, para que un agente de IA pueda decir "procesa este documento y dime la dirección":

| Herramienta | Descripción |
|---|---|
| `procesar_documento(ruta_o_base64)` | Ejecuta el pipeline y devuelve el JSON |
| `obtener_resultado(documento_id)` | Recupera un resultado anterior |
| `listar_plantillas()` | Devuelve plantillas activas con sus campos |
| `obtener_plantilla(id)` | Detalle de una plantilla |
| `crear_plantilla(definicion)` | Crea una plantilla a partir de una definición JSON |
| `probar_plantilla(plantilla_id, documento_id)` | Aplica una plantilla a un documento y devuelve el resultado sin guardarlo |
| `buscar_documentos(filtros)` | Historial filtrado por tipo, fecha, estado |

El servidor MCP no reimplementa lógica: llama a la misma API REST.

## 8. Decisiones de diseño y alternativas

| Decisión | Elegido | Alternativas consideradas | Razón |
|---|---|---|---|
| Lenguaje backend | Python | C#/.NET | Ecosistema OCR y MCP maduro; velocidad de construcción |
| Motor OCR | **PaddleOCR** principal, **docTR** segunda opinión, Tesseract fallback ligero. Ver [docs/06](06-investigacion-ocr-engines.md) | Tesseract como principal (descartado por evidencia); modelos de visión vía API | Privacidad y costo cero; PaddleOCR/docTR muestran menor CER que Tesseract en benchmarks externos (20.5%/19.7% vs 33.6%); se puede añadir un modelo de visión como "extractor premium" más adelante |
| Clasificación | Reglas ponderadas + similitud de texto | Modelo entrenado | Sin datos de entrenamiento al inicio; las reglas son explicables y editables desde la UI |
| Extracción | Regex + anclas + zonas | LLM | Determinista, auditable, sin costo por documento |
| Base de datos | SQL Server | Postgres | Requerimiento del cliente |
| Frontend | React + Vite | Plantillas servidas por FastAPI | Editor visual de zonas requiere interactividad |
| Procesamiento | Síncrono con límite de tiempo; cola opcional | Siempre asíncrono | Simplicidad para la entrega inicial |

## 9. Calidad y métricas

- Cada campo lleva **confianza**; campos bajo umbral se marcan en `advertencias` para revisión humana.
- Se guarda el **texto OCR completo** y las **coordenadas**, lo que permite auditar de dónde salió cada valor.
- Métrica de referencia: **CER** (tasa de error por carácter) medida sobre un conjunto de documentos con verdad conocida, y **exactitud por campo** (porcentaje de campos extraídos correctamente).

## 10. Seguridad y privacidad

- Los documentos se procesan **dentro de la infraestructura**; el OCR es local.
- Archivos originales se guardan en un volumen cifrable, con política de retención configurable.
- API protegida con clave (`X-API-Key`); el MCP hereda la misma clave.
- Logs sin contenido de documentos, solo identificadores y tiempos.

## 11. Roadmap

| Semana | Entregable |
|---|---|
| Actual | Núcleo OCR + clasificación + extracción, API, MCP, UI de carga y plantillas, Docker Compose con SQL Server |
| Siguiente | Módulo biométrico: comparación facial foto de cédula vs. selfie, con porcentaje de coincidencia y factores que afectan (lentes, iluminación, edad) |
| Posterior | Worker asíncrono con cola, modelo de visión opcional, despliegue en nube, roles de usuario |

## 12. Glosario

| Término | Significado |
|---|---|
| **OCR** | Reconocimiento óptico de caracteres: pasar imagen a texto |
| **Deskew** | Corregir la inclinación de una página escaneada torcida |
| **Binarización** | Convertir la imagen a blanco y negro puro para que el OCR lea mejor |
| **Plantilla** | Definición de un tipo de documento: cómo identificarlo y qué campos extraer |
| **Ancla** | Texto fijo que precede a un dato ("N° Cliente:") y sirve para ubicarlo |
| **Zona** | Rectángulo en coordenadas relativas (0-1) de la página donde está un dato |
| **Confianza** | Número 0-1 que indica qué tan seguro está el sistema de un valor |
| **CER / WER** | Tasa de error por carácter / por palabra, métrica estándar de OCR |
| **CQRS** | Separar el código que escribe (comandos) del que lee (consultas) |
| **MCP** | Model Context Protocol: estándar para que agentes de IA usen herramientas |
