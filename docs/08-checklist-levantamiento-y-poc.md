# 08 — Checklist: levantar el ambiente y arrancar la prueba de concepto

> Qué necesita cada parte como mínimo para quedar en pie, y qué falta además de "que arranque" para poder correr una prueba de concepto (PoC) real. Refleja el estado del proyecto al 2026-11-13.

## 0. Estado actual (antes de la checklist)

| Parte | Estado real | Falta |
|---|---|---|
| **Documentación / diseño** | Completa (`docs/01` a `docs/08`, `qa/`) | — |
| **Backend** | Completo, con los 4 gaps de la siguiente iteración ya cerrados por Desarrollo OCR: autodetección de `TESSDATA_PREFIX`, docTR como segunda opinión real, rutas `/plantillas/{id}/versiones` y `/plantillas/{id}/reprocesar`, `scripts/evaluar.py`. 80/80 tests. Pendiente de aprobación: exponer el motor que resolvió cada campo en el JSON (aprobado, en curso) | Rebuild del contenedor con estos cambios |
| **Base de datos** | ✅ Construida y verificada contra SQL Server real (8 tablas, 3 plantillas, scripts idempotentes) | — |
| **Frontend** | ✅ Las 7 pantallas de `docs/03` completas, build verificado | Ajustar si el contrato JSON cambia (campo `motor`) |
| **Infraestructura (Docker Compose)** | ✅ Stack completo levantado y sano: `docker compose ps` muestra mssql/backend/mcp/frontend healthy, `/api/salud` y el frontend responden desde fuera | Rebuild con los cambios de backend pendientes |
| **Maqueta visual (referencia, no código)** | `C:\OCR\diseno\maqueta.html` — navegable, incluye ya los flujos de `docs/07` | — (es solo referencia de UX) |
| **QA** | 40 tests nuevos de Dev QA OCR (`qa/informe-qa-backend-ocr.md`), 3 hallazgos reales documentados | Siguiente pasada: endpoints de plantillas, filtros, MCP, PDF multi-página |

**La PoC end-to-end quedó validada** por Dev QA OCR sobre el stack real (informe completo en [qa/informe-qa-poc-e2e.md](../qa/informe-qa-poc-e2e.md)):
- UI real: "Sistema disponible", subida de documentos, historial, detalle.
- MCP real: handshake JSON-RPC completo (`initialize`, `tools/list` con las 7 herramientas, `listar_plantillas`, `procesar_documento`) — clasificó con confianza 1.0 de punta a punta.
- 2 documentos reales (no sintéticos) clasificaron correctamente como "desconocido", sin forzarlos a ninguna plantilla.
- SQL Server real: 9 documentos persistidos y verificados con sqlcmd.
- Tras el fix de palabras clave, `consumo` y `fecha_vencimiento` ya se extraen bien; `direccion` sigue con un caso dudoso a confirmar con datos reales (cédula pendiente).

### ✅ Validación con cédula real (2026-11-16)

El usuario aportó una cédula real (`doc_md/DocumentosPruebas/Cedula_Papeleta_261116_074511.pdf` — carpeta excluida del repositorio por contener datos personales reales). Resultado final tras 2 ciclos de corrección:

| Campo | Resultado |
|---|---|
| Clasificación | `cedula_identidad`, confianza 0.963 |
| `numero_documento` | ✅ 0.94 |
| `nombres` | ✅ 0.87 |
| `apellidos` | ✅ 0.81 (motor docTR) — **verificado estructuralmente por Dev QA OCR** que toma la sección del titular, no padre/madre |
| `fecha_vencimiento` | ✅ 0.91 |
| `nacionalidad` | ✅ 0.96 |
| `sexo` | ✅ 0.96 |
| `fecha_nacimiento` | ⚠️ 0.35, encontrado pero con confianza baja intencional (OCR perdió un dígito del año; el sistema no lo adivina) |
| **Confianza global** | **0.882** |

Bugs reales encontrados y corregidos en el camino: formato de fecha/sexo no genérico, ancla ambigua que tomaba datos del padre/madre en vez del titular (el más grave — valor incorrecto con confianza alta y sin aviso), mojibake de codificación en una migración SQL. Observación menor pendiente, no bloqueante: `apellidos` podría estar capturando solo el primer apellido del compuesto.

Con esto, la PoC queda validada con los 3 tipos de documento (desconocido, planilla sintética, cédula real). Pendiente de usuario: definir el criterio formal de éxito (§6.2) si se quiere una medición más allá de este caso puntual.

**Límites conocidos, anotados por Desarrollo OCR (ninguno bloqueante):**
- `apellidos` en cédula puede salir incompleto si el apellido compuesto queda en líneas separadas por el OCR — el método ancla toma una sola línea; arreglarlo bien requiere una regla por zona o un parámetro `lineas_valor`, a validar con más de una cédula antes de generalizar. El usuario ve/edita el valor en la UI mientras tanto.
- `fecha_nacimiento` con dígito del año perdido queda marcada con baja confianza a propósito (no se adivina).
- `nacionalidad` solo reconoce gentilicios de una lista fija.
- El sugeridor de plantillas no detecta el patrón "Etiqueta Nombre" sin ":" ni dígitos.
- Tesseract (fallback) rinde muy por debajo de PaddleOCR/docTR en la prueba sintética — revisar PSM/binarización si alguna vez se usa como motor activo, no solo de respaldo.

Próximo paso natural cuando haya más documentos reales: correr `scripts/evaluar.py` (ya con métrica de acierto de clasificación) para cerrar formalmente la §6.2.

### ⚠️ Riesgo grave encontrado en la PoC: modelos OCR se descargan en caliente (no pre-cacheados)

Detectado por Dev QA OCR: `PaddleOCR`/`OnnxTR` descargan sus pesos de internet en el **primer** request que los necesita (no en el build de la imagen), dentro del propio request HTTP. Consecuencias observadas:
1. **El backend queda totalmente inalcanzable 2-3 minutos** (ni siquiera `/api/salud` responde) la primera vez que un documento dispara la segunda opinión de docTR con un campo de baja confianza — algo muy común (cualquier campo opcional ausente). Agota el threadpool de uvicorn y tumba todo el API, no solo ese request.
2. **Contradice el diseño** (`docs/01` §3/§10: "los documentos no salen de la infraestructura", procesamiento 100% local): si el entorno real no tiene salida a internet, esto no es lento, **falla por completo**.
3. Los modelos quedan en la capa del contenedor (`/root/.paddleocr`, `/root/.cache/onnxtr`), así que cada `docker compose up --build` repite la descarga y el riesgo de colgar el API.

**✅ Resuelto y verificado.** Desarrollo OCR encontró la causa de fondo real (el pipeline bloqueante corría directo en el event loop de uvicorn; la descarga de modelos solo lo disparaba) y aplicó 3 defensas: `run_in_threadpool` en `/documentos`, modelos horneados en el build del Dockerfile (imagen autocontenida/offline) + volúmenes persistentes, y lock/semáforo/timeout en la segunda opinión. Verificado tras rebuild: `/api/salud` en 51ms, documento completo en 4.2s (antes 130s+ o caída total). Los bugs de extracción (`direccion`, `consumo`, `fecha_vencimiento`) también quedaron corregidos y confirmados con el mismo request: los 6 campos salen bien, confianza global 0.909, cero advertencias.

## 1. Mínimo para levantar el AMBIENTE

Prerrequisitos de la máquina (ya resueltos en esta sesión):

| Herramienta | Estado |
|---|---|
| Python 3.12 | ✅ instalado |
| Node 24 / npm | ✅ instalado |
| Docker Desktop | ✅ instalado, iniciado |
| Tesseract 5 + `spa.traineddata` | ✅ instalado |
| Git | ✅ instalado |
| `sqlcmd` / ODBC Driver 18 | ✅ instalado |

Acción para levantar todo junto una vez los tres pendientes entreguen:
```bash
cd C:\OCR
copy .env.example .env   # si no existe ya
powershell -File scripts\levantar.ps1
```
Esto debe: construir las imágenes, levantar `mssql` y esperar su healthcheck, aplicar `db/schema.sql` + `seed.sql` (vía el servicio `db-init`), levantar `backend`, `mcp` y `frontend`.

## 2. Mínimo para BASE DE DATOS

- [ ] `db/schema.sql` ejecuta sin error contra un SQL Server 2022 limpio (local o en contenedor).
- [ ] `db/seed.sql` deja las 3 plantillas semilla (`cuenta_contrato`, `planilla_servicio`, `cedula_identidad`) con sus campos y palabras clave.
- [ ] Columnas y nombres de tabla coinciden **exactamente** con `docs/04-base-de-datos.md` (el backend ya tiene sus modelos SQLAlchemy escritos contra ese contrato).
- [ ] `docker compose up -d mssql` llega a `healthy` en menos de 90s.
- **Criterio de "levantado":** `sqlcmd` puede conectarse y `SELECT COUNT(*) FROM Plantilla` devuelve 3.

## 3. Mínimo para BACKEND

Ya cumplido, pero para re-verificar en cualquier momento:
```powershell
cd C:\OCR\backend
.venv\Scripts\python.exe -m pytest -q
$env:API_KEY="dev"; $env:DATABASE_URL="sqlite:///./dev.db"; $env:TESSDATA_PREFIX="C:\OCR\backend\tessdata"
.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```
- [ ] `GET /api/salud` responde `{"api":"ok",...}`.
- [ ] `POST /api/documentos` con una imagen de prueba devuelve JSON con campos extraídos.
- **Pendiente antes de producción (no bloquea la PoC):** conectar docTR como segunda opinión real en `extractor.py`; correr contra SQL Server real, no solo SQLite.

## 4. Mínimo para FRONTEND

- [ ] `npm run build` compila sin errores de TypeScript.
- [ ] `npm run dev` levanta y la pantalla "Procesar" se ve con el mock de datos (`VITE_USAR_MOCK=true`), sin necesitar el backend corriendo.
- [ ] Con el backend real levantado, cambiar a `VITE_USAR_MOCK=false` y subir un documento real desde la UI debe mostrar el resultado tal como lo devuelve la API.
- **Criterio de "levantado":** `http://localhost:3000` (vía Docker) o `http://localhost:5173` (dev) muestra la pantalla Procesar y permite subir un archivo.

## 5. Mínimo para INFRAESTRUCTURA (Docker Compose)

- [ ] `docker compose config` valida sin errores.
- [ ] `docker compose up -d --build` levanta los 5 servicios (mssql, db-init, backend, mcp, frontend) sin que ninguno quede en `restarting`.
- [ ] `docker compose logs backend` no muestra errores de conexión a BD.
- **Criterio de "levantado":** `http://localhost:3000` (frontend) y `http://localhost:8000/api/salud` (backend) responden desde fuera de los contenedores.

## 6. Una vez todo levantado: qué más se necesita para la PRUEBA DE CONCEPTO

Levantar el ambiente **no es** lo mismo que tener una PoC demostrable. Para la PoC falta:

### 6.1 Datos de prueba reales
- [ ] Al menos **2-3 documentos reales o realistas por tipo** (cuenta de contrato, planilla de servicio, cédula) — escaneados o fotografiados, no solo sintéticos generados con PIL. Sin esto no se puede medir si el OCR realmente funciona en condiciones reales.
- [ ] Guardarlos en `C:\OCR\muestras\` (no están en el repo todavía).

### 6.2 Criterio de éxito definido
- [ ] Definir el umbral mínimo aceptable: ¿qué % de campos correctos por documento se considera "funciona"? (sugerido: ≥85% para continuar, <70% requiere ajustar plantillas o motor antes de seguir).
- [ ] Correr `scripts/evaluar.py` (implementado, ver `docs/02` §9) sobre esas muestras, comparando PaddleOCR vs docTR vs Tesseract en CER y exactitud por campo — esto es lo que valida o refuta la elección de motor de `docs/06` con evidencia propia, no solo con benchmarks externos.

### 6.3 Flujo de extremo a extremo demostrable
- [ ] Subir un documento desde la UI real (no solo `curl`), ver el resultado clasificado y los campos extraídos en pantalla.
- [ ] Crear una plantilla nueva desde la UI usando el asistente (no solo por API) y confirmar que sugiere palabras clave/campos razonables.
- [ ] Conectar un cliente MCP (Claude Desktop o Claude Code) al servidor MCP y pedirle "procesa este documento y dime la dirección" para confirmar que la capa de agente funciona de punta a punta.

### 6.4 QA mínimo antes de mostrarla
- [ ] **Pruebas unitarias** cubriendo backend (ya hecho: 32 tests) y, cuando exista, base de datos (schema aplica sin error, constraints funcionan) y frontend (al menos los componentes críticos: carga de archivo, editor de reglas).
- [ ] Un pase de QA dedicado que corra el flujo completo con las muestras reales de §6.1 y reporte discrepancias.

→ Para este punto se asigna una sesión dedicada **Dev QA OCR**, especializada en pruebas unitarias y de flujo, independiente de los agentes de construcción.

## 7. Orden recomendado a partir de ahora

1. Esperar a que terminen los 3 agentes retomados (BD, frontend, infraestructura).
2. Levantar todo con `docker compose up -d --build` y verificar los criterios de las secciones 2-5.
3. Reunir las muestras reales (§6.1) — esto requiere acción del usuario/equipo, no es automatizable.
4. Pasar las muestras a **Dev QA OCR** para pruebas unitarias y medición de exactitud real.
5. Con eso, decidir si la PoC está lista para mostrarse o si el motor/plantillas necesitan ajuste.
