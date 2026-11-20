# Informe QA — Validación E2E de la PoC sobre el stack real (Docker + SQL Server)

Autor: sesión **Dev QA OCR**. Alcance: docs/08 §6.3 (flujo de extremo a extremo demostrable) sobre el stack real levantado en Docker (frontend :3000, backend :8000, MCP :8001, SQL Server real). No se modificó código de producción; los bugs de código los corrigieron Desarrollo OCR / Líder OCR durante la sesión, a partir de mis reportes.

**Nota de método:** el Browser pane integrado de esta sesión no puede manejar el selector nativo de archivos de un `<input type="file">`, y la extensión Claude in Chrome no estaba conectada en esta sesión. Por eso la "subida desde la UI" se hizo llamando al mismo endpoint (`POST /api/documentos`, multipart/form-data) que usa el formulario real, y verifiqué el resultado visualmente navegando las pantallas de Historial y Detalle en el navegador. No se ejecutó literalmente el clic + arrastre humano sobre el selector de archivos.

## 1. Bugs críticos encontrados y corregidos durante la sesión

Los tres siguientes bloqueaban por completo el flujo de la PoC. Los reporté a Líder OCR apenas los encontré; Desarrollo OCR los corrigió en caliente y los reverifiqué después del fix.

### 1.1 Subir cualquier documento al stack real devolvía 500
`app/persistencia/repositorios.py:25` usaba `m.Plantilla.Activa.is_(True)`, que SQLAlchemy compila a `WHERE [Plantilla].[Activa] IS 1` — sintaxis inválida en T-SQL (solo soporta `IS NULL`/`IS NOT NULL`). Funcionaba en SQLite (por eso nunca apareció en mis tests unitarios) pero rompía contra SQL Server real. `app/commands/procesar_documento.py:24` llama a esa misma función en cada `POST /documentos`, así que **cualquier** subida de documento fallaba, no solo el filtro `GET /plantillas?activa=true`.
**Estado:** corregido por Desarrollo OCR (`== True` en vez de `.is_(True)`). Reverificado con `curl` directo: `201 Created`.

### 1.2 Servidor MCP inalcanzable en :8001
`mcp_server/server.py` leía `MCP_TRANSPORT` del entorno pero nunca `MCP_HOST`/`MCP_PORT`, así que `mcp.run(transport="streamable-http")` arrancaba con el puerto por defecto de FastMCP (8000) dentro del contenedor, mientras Docker Compose mapeaba host:8001→contenedor:8001. Confirmé con `docker exec` + Python que dentro del contenedor el 8000 respondía (404 normal de FastMCP) y el 8001 daba *connection refused*.
**Estado:** corregido (host/port ahora se pasan a la construcción de `FastMCP`). Reverificado end-to-end: handshake MCP, `tools/list` (7 herramientas), `listar_plantillas` y `procesar_documento` funcionando sobre un archivo ya almacenado — ver §4.

### 1.3 Indicador "Sistema sin conexión" permanente en la UI
El frontend comparaba `salud.estado === "ok"`, pero el backend nunca devuelve un campo `estado` en `/api/salud` (devuelve `{"api":"ok","base_datos":"ok","tesseract":"ok",...}`). El indicador del sidebar mostraba "Sistema sin conexión" en rojo permanentemente, sin importar que todo estuviera sano.
**Estado:** corregido. Reverificado: "Sistema disponible" en verde con el backend sano.

## 2. Hallazgo crítico de infraestructura — NO corregido, documentado

**El backend completo quedó inalcanzable ~2–3 minutos** (ni `/api/salud`, ni desde dentro del propio contenedor, ni a través de nginx — "upstream timed out") al procesar el primer documento real tras el rebuild.

Causa confirmada en `docker logs ocr-backend`: un campo opcional con confianza 0.0 (más baja que `OCR_UMBRAL_SEGUNDA_OPINION`=0.7) disparó `segunda_opinion()` → docTR/OnnxTR, y como el contenedor nunca había usado ni PaddleOCR ni docTR, se puso a **descargar los modelos desde internet dentro del propio request** (`en_PP-OCRv3_det_infer.tar`, `latin_PP-OCRv3_rec_infer.tar`, `ch_ppocr_mobile_v2.0_cls_infer.tar` desde bcebos.com, y los `.onnx` de OnnxTR desde GitHub). Mientras tanto, **todo el resto de la API dejó de responder** — consistente con agotamiento del thread pool de Uvicorn (`run_in_threadpool`), no solo el request que disparó la descarga.

Por qué es grave más allá de la lentitud puntual:
1. Bloquea cualquier demo en vivo: el primer documento con un campo opcional ausente (muy común) puede colgar el sistema entero 2-3 min sin aviso al usuario.
2. Los modelos se descargan a `/root/.paddleocr` y `/root/.cache/onnxtr` **dentro de la capa del contenedor**, no en un volumen — así que cada `docker compose up --build` los vuelve a descargar.
3. Contradice docs/01 §3/§10 ("los documentos no salen de la infraestructura", procesamiento 100% local): en un entorno real sin salida a internet, esto no sería solo lento — **fallaría por completo**.

**No lo corregí** (no es trabajo mío tocar Dockerfile/infra). Sugerencia que dejé para Infraestructura/Desarrollo: pre-descargar los modelos en el build de la imagen, o montar un volumen persistente para esas carpetas de caché, y considerar que la segunda opinión no debería poder tumbar el resto del API (timeout o pool separado).

## 3. Flujo de subida y resultado en pantalla (punto 1 de docs/08 §6.3)

Subí 5 documentos reales/realistas contra el stack con SQL Server real y verifiqué el resultado en las pantallas de Historial (`/documentos`) y Detalle (`/documentos/:id`):

| Archivo | Tipo esperado | Resultado real | Confianza |
|---|---|---|---|
| `poc_planilla.png` (sintético, alineado a la plantilla semilla) | planilla_servicio | **planilla_servicio** (tras el fix de keywords de Desarrollo; antes del fix: "desconocido" 0.571) | 0.857 |
| `poc_cuenta_contrato.png` (sintético) | cuenta_contrato | **cuenta_contrato** | 0.985–1.0 |
| `poc_cedula.png` (sintético) | cedula_identidad | **cedula_identidad** | 0.799 |
| `Sincronización de catálogos proceso paso a paso.pdf` (**real**, 19 páginas, provisto por el usuario) | desconocido | **desconocido** ✔ | 0.136 |
| `UC-18779f74-....pdf` (**real**, certificado de curso, provisto por el usuario) | desconocido | **desconocido** ✔ | 0.0 |

Los 2 documentos reales de `C:\OCR\DocumentosPruebas\` se clasificaron correctamente como `desconocido`, sin forzarlos a encajar en ninguna plantilla — confirma el criterio que pidió Líder OCR.

Confirmé con `sqlcmd` contra `ocr-mssql` que los 9 documentos subidos durante la sesión quedaron persistidos en `dbo.Documento`, `dbo.Resultado` y `dbo.CampoExtraido` con `TipoDetectado`/`ConfianzaGlobal`/valores de campo coherentes con la respuesta JSON — la persistencia en SQL Server real funciona (punto 5 de la tarea).

La pantalla de Detalle muestra correctamente tipo, confianza global, tabla de campos con valor y confianza por campo. **Hallazgo menor de UI:** el encabezado de esa pantalla muestra literalmente `— · Plantilla v—` en vez del nombre y versión real de la plantilla usada (placeholders sin completar).

## 4. Servidor MCP (punto 4 de docs/08 §6.3)

Tras el fix del puerto, probé el protocolo completo a mano (handshake JSON-RPC + `notifications/initialized` + `tools/call`) contra `http://localhost:8001/mcp/`:

- `tools/list` → devuelve las 7 herramientas documentadas en docs/01 §7 (`procesar_documento`, `obtener_resultado`, `listar_plantillas`, `obtener_plantilla`, `crear_plantilla`, `probar_plantilla`, `buscar_documentos`).
- `listar_plantillas` → devuelve las 3 plantillas semilla completas (palabras clave, campos, reglas).
- `procesar_documento` con `ruta` apuntando al archivo ya almacenado en el volumen compartido (`/data/archivos/...`) → procesó de punta a punta: clasificó `cuenta_contrato` con confianza 1.0 y devolvió los 5 campos extraídos con su `motor` (equivalente a "procesa este documento y dime la dirección" de docs/08).

**Confirma que la capa de agente funciona de punta a punta**, no solo la API REST — con la salvedad de que no usé un cliente MCP real (Claude Desktop/Code) sino las llamadas HTTP crudas del protocolo, porque conectar un cliente MCP gráfico no estaba disponible en esta sesión.

## 5. Asistente de nueva plantilla y sugerencias (punto 2 de docs/08 §6.3)

**No pude completar el punto 2 exactamente como está escrito** (crear una plantilla real desde el asistente de 3 pasos) por la misma limitación de subida de archivos del Browser pane. Sí pude:

- Confirmar que el asistente (`/plantillas/nueva`) renderiza sus 3 pasos correctamente.
- Probar el endpoint que alimenta el paso 2 (`POST /plantillas/sugerir`) con los 2 documentos reales "desconocido", que es la llamada que la UI haría automáticamente al llegar a ese paso.

**Hallazgo real — las sugerencias no son usables en documentos reales de texto libre:**
- **Palabras clave**: en ambos documentos reales, las "palabras clave sugeridas" son casi puro stopwords en español sin filtrar — `"el","en","se","la","de","que","con","si","no","del"` para el documento de 19 páginas, y `"de","la","para","en","del","de la","en la"` para el certificado corto. docs/02 §5 dice que debería usar TF-IDF (alta frecuencia en el documento, baja en el resto del corpus) para evitar justo esto.
- **Campos**: en el documento de 19 páginas, el sistema sugirió campos como `todo_se_escribe_en_la_base_de_la_conexion_ole_destino` (ancla = una frase completa de 60+ caracteres) con `tipo_dato: "monto"`, o `dwh_dwh` también tipado como `"monto"` — ninguno es un monto real. En el certificado corto, sugirió `"campos": []` (ninguno), pese a que el texto sí contiene una fecha clara ("5 de noviembre de 2026").

Esto no bloquea la PoC (la plantilla se puede crear manualmente sin usar las sugerencias), pero si el objetivo es que el asistente "sugiera palabras clave/campos razonables" como pide el punto 2, **hoy no lo hace** en documentos de texto libre reales. Lo dejo documentado para Desarrollo OCR, no lo corrijo.

## 6. Otros hallazgos de UI (menores, no bloqueantes)

- **Columna "Docs" en `/plantillas` siempre muestra 0.** El frontend renderiza `a.total_documentos ?? 0`, pero `PlantillaDTO` nunca incluye ese campo — confirmado en el bundle (`a.total_documentos` nunca llega del backend). Con `cuenta_contrato` y `cedula_identidad` ya con documentos reales clasificados, la tabla sigue mostrando 0 para las tres.
- **Falta el aviso + botón "Crear plantilla desde este documento" para tipo "desconocido".** docs/03 §4.1/§4.3 lo especifica explícitamente; en la pantalla de Detalle de mis 2 documentos reales "desconocido" no aparece ningún aviso ni botón, solo "No hay campos para mostrar." — el usuario tendría que ir manualmente a `/plantillas/nueva` y volver a subir el mismo archivo.
- **El asistente no permite "elegir un documento del historial"** en el paso 1, solo subir un archivo nuevo — docs/03 §4.5 especifica ambas opciones.

## 7. Resumen para el usuario

| # | Hallazgo | Severidad | Estado |
|---|---|---|---|
| 1 | 500 en cualquier subida de documento (`Activa.is_`) | Crítico | ✅ Corregido y reverificado |
| 2 | Servidor MCP inalcanzable (puerto no pasado a FastMCP) | Crítico | ✅ Corregido y reverificado |
| 3 | Indicador "Sistema sin conexión" siempre rojo | Cosmético | ✅ Corregido y reverificado |
| 4 | Backend completo caído ~2-3 min por descarga de modelos en caliente | **Crítico, sin corregir** | Documentado — Infraestructura/Desarrollo |
| 5 | Sugerencias de palabras clave/campos inservibles en texto libre real | Funcional, no bloqueante | Documentado — Desarrollo OCR |
| 6 | Columna "Docs" siempre en 0 | UI menor | Documentado |
| 7 | Falta aviso/botón "Crear plantilla" para tipo desconocido | UI menor (gap vs. diseño) | Documentado |
| 8 | Asistente no permite elegir documento del historial | UI menor (gap vs. diseño) | Documentado |
| 9 | Encabezado de detalle muestra "— · Plantilla v—" | UI cosmético | Documentado |

Pendiente real para una siguiente vuelta: completar el punto 2 (crear plantilla desde el asistente) con una subida real de archivo — necesita Claude in Chrome conectado, o que el usuario lo haga él mismo mientras reviso en paralelo; y repetir la medición de clasificación con las muestras reales que vayan llegando, usando `scripts/evaluar.py` si existe o diseñándolo.

## 8. Primer documento real: cédula ecuatoriana (`documento_id` `142AD777-EB9B-4BAF-B84C-88B46E899CD9`)

**Nota de privacidad:** este documento contiene datos personales reales (nombre, número de cédula, fecha de nacimiento). Consulté el resultado directamente contra el backend local para hacer este análisis, pero **no reproduzco aquí el texto OCR completo ni ningún valor real** — solo la estructura del fallo. Borré la copia local que había guardado para el análisis en cuanto terminé.

Clasificación: **perfecta** (`cedula_identidad`, confianza 0.963). Extracción: **3 de 7 campos con valor, y de esos 3 al menos 2 son incorrectos** (no solo "4 campos vacíos" como se ve a primera vista) — este matiz importa porque cambia la severidad real del hallazgo. Analicé el `texto_completo` devuelto (sin copiarlo) para entender la causa de cada campo:

### 8.1 Dos causas raíz distintas, no una sola

**A) Campos con valor nulo (numero_documento, fecha_nacimiento, fecha_vencimiento, sexo) — mismatch real de formato, no solo ruido OCR:**
- `fecha_nacimiento` y `fecha_vencimiento` usan `regex: "Fecha de ... \d{2}/\d{2}/\d{4}"` (plantilla semilla) — pero la cédula ecuatoriana real escribe la fecha como **día + mes abreviado en texto + año** (p. ej. "26 NOV 1990"), nunca como `dd/mm/yyyy`. No es un problema de que el OCR lea mal los dígitos: aunque el OCR leyera perfecto, el regex nunca podría matchear ese formato porque busca separadores `/` entre tres grupos numéricos.
- `sexo` usa `regex: "Sexo\s*:?\s*([MF])"` — pero el documento real escribe **"HOMBRE"/"MUJER" en texto completo**, no la letra M/F. De nuevo: mismatch estructural de formato, no ruido de OCR.
- `numero_documento` sí parece más un problema de OCR real: el ancla "N° Documento" cae sobre una zona del documento con bastante ruido (símbolo "°" perdido, y el documento tiene superpuestas una cédula y un certificado de votación con zonas MRZ/código de barras que confunden el layout). Este sí podría mejorar con mejor preprocesado o con un `regex` más flexible, pero no lo até a una causa única con certeza.

**B) Campos con valor NO nulo pero incorrecto (nombres, apellidos, nacionalidad) — más grave que los nulos porque no generan advertencia:**
- El documento real tiene el ancla "Nombres" repetido **tres veces** en el layout (como parte de "Apellidos y Nombres del Padre", "Apellidos y Nombres de la Madre", y el campo real "Nombres" del titular). `_mejor_posicion_ancla()` en `app/pipeline/extractor.py` recorre todas las líneas y se queda con el **primer** score más alto (`score > mejor_score`, estrictamente mayor), sin ninguna heurística de posición o de evitar anclas que son substring de una frase más larga. Como resultado, "nombres" y "apellidos" terminaron devolviendo fragmentos de la línea de encabezado ("...Nombres del Padre") en vez del valor real, que está varias líneas más abajo.
- "nacionalidad" tiene un fallo relacionado pero distinto: el ancla si encontró la línea correcta, pero el valor real está **dos líneas después** de la etiqueta (el layout real intercala la etiqueta de otro campo justo debajo de "Nacionalidad" antes de llegar al valor). `_extraer_ancla()` solo mira **una** línea hacia adelante cuando no hay resto en la misma línea (`lineas[idx + 1]`), así que agarró la línea equivocada.
- **Por qué es más grave que un campo vacío:** `nombres` y `apellidos` son `obligatorio: true` en la plantilla semilla, pero como `extraer_campo()` obtuvo *algún* texto no vacío y `validar_texto()` acepta cualquier string no vacío como válido, `construir_advertencias()` nunca marca `campo_obligatorio_faltante` para ellos — aparecen con confianza 0.91-0.92 (alta, porque el OCR sí leyó bien *esa* región, solo que no es la región correcta) y **sin ninguna advertencia**. En un documento de identidad, devolver el nombre equivocado con confianza alta y sin aviso es el peor escenario posible para un humano que confíe en el campo sin revisar el texto completo.

### 8.2 Conclusión y para qué sirve esto

No es "hay que ajustar 4 reglas de regex", son al menos tres problemas de naturaleza distinta:
1. Formato de fecha y de sexo de la plantilla semilla no cubre el formato real ecuatoriano (texto, no sólo dígitos/letra).
2. El algoritmo de `ancla` no tiene forma de preferir la ocurrencia correcta cuando el texto ancla aparece repetido o como parte de un encabezado más largo.
3. El fallback "línea siguiente" de `ancla` asume que el valor está exactamente en la línea siguiente, lo cual no se sostiene en layouts reales con columnas intercaladas.
4. (Consecuencia de 2 y 3) El sistema de advertencias no tiene forma de detectar "extraje algo, pero probablemente no es lo correcto" — solo detecta "no extraje nada".

Se lo pasé a Desarrollo OCR (vía Líder OCR) con este nivel de detalle para que puedan decidir si ajustan la plantilla semilla, el algoritmo de `ancla`, o ambos — no lo corrijo yo. Cuando reprocesen, vale la pena revisar específicamente si `nombres`/`apellidos` quedan con el valor correcto, no solo si `numero_documento`/`fecha_nacimiento`/`fecha_vencimiento`/`sexo` dejan de estar en `null`.

### 8.3 Reproceso tras el fix de Desarrollo OCR — verificado, resultado mixto

Desarrollo OCR corrigió `_extraer_ancla` (ver §8.1-B) agregando `_es_etiqueta_compuesta()`: si la etiqueta encontrada está precedida por "y"/"e" o seguida de "y"/"e"/"de"/"del"/"la"/"las"/"los"/"el" (y no termina en ":"), se descarta como etiqueta de otro campo y se prueba la siguiente candidata. Verifiqué el reproceso del mismo documento (`confianza_global` subió de 0.613 a 0.814):

- **`nombres`: correcto.** Ahora sí toma la línea propia del titular ("NOMBRES" seguida de su valor), ya no el encabezado "...Nombres del Padre". El fix funciona para este caso.
- **`apellidos`: sigue incorrecto.** El Líder OCR reportó inicialmente "0.95, motor doctr, funcionando como se diseñó" basándose solo en metadatos (confianza alta); les pedí no tomar eso como prueba y verifiqué yo mismo contra el `texto_completo` sin exponer el valor: **sigue tomando la sección del padre, no la del titular** (el titular ni siquiera tiene una etiqueta "Apellidos" propia y legible en este documento real — solo existen los encabezados compuestos "Apellidos y Nombres del Padre/de la Madre"). Causa específica: el valor extraído por la segunda opinión (`motor: doctr`) viene de una lectura OCR donde el conector "Y" quedó pegado sin espacio a "NOMBRES" como un solo token; el nuevo filtro busca el conector como palabra separada, así que no lo detecta y deja pasar la etiqueta compuesta.
- **Confianza alta ≠ valor correcto, otra vez** — exactamente el riesgo que señalé en §8.1-B, y la razón por la que insistí en verificar el valor en vez de aceptar el 0.95 como evidencia de que estaba resuelto. Si este caso se queda así, lo correcto sería que `apellidos` quedara en `null` con advertencia `campo_obligatorio_faltante` (que es justamente lo que Desarrollo OCR esperaba que pasara), no con un valor incorrecto y alta confianza.
- `fecha_vencimiento` y `sexo`: correctos tras el fix de formato. `fecha_nacimiento`: se encuentra pero con confianza baja a propósito (el OCR perdió un dígito del año; el sistema no lo está adivinando, lo cual es el comportamiento correcto). `numero_documento`: sigue sin resolver, ruido OCR real sobre una zona con MRZ/código de barras superpuesto.

**Para Desarrollo OCR:** el filtro de etiqueta compuesta necesita tolerar conectores pegados sin espacio al token siguiente (normalizar/tokenizar separando conectores comunes antes de comparar), no solo buscarlos como palabra exacta separada por espacios.

### 8.4 Segundo reproceso (fix no dependiente de tokenización) — verificado, correcto

Desarrollo OCR ajustó el filtro para que no dependa de que el conector sea un token separado por espacios, y además corrigió la migración de reglas. Reprocesé y verifiqué de nuevo contra el `texto_completo` (sin exponer el valor):

- **`apellidos`: correcto esta vez.** El valor viene de la sección propia del titular (cerca de la firma/zona MRZ), no de los encabezados "...del Padre"/"...de la Madre".
- **Observación menor (no es el mismo bug):** el valor parece capturar solo el primer apellido del titular, no los dos — el ancla se detiene en la primera palabra de esa línea. Puede ser intencional según cómo se definió el campo en la plantilla; lo dejo anotado para Desarrollo OCR, no lo marco como hallazgo cerrado.
- `numero_documento` ya se extrae (0.938) — el ajuste de reglas resolvió también el ruido OCR que antes lo bloqueaba.
- `confianza_global` subió a 0.882; única advertencia restante: `fecha_nacimiento` por baja confianza intencional (el OCR perdió un dígito del año y el sistema no lo adivina, correcto).

**Conclusión de todo el caso §8:** el proceso de ida y vuelta (yo verificando el valor estructural contra el texto, no solo la confianza reportada) fue necesario dos veces — la primera iteración del fix parecía exitosa por metadatos (0.95 de confianza) pero seguía mal; solo la segunda iteración, verificada de la misma forma, resultó realmente correcta. Vale la pena que quede como precedente: en este proyecto, una confianza alta en un campo de tipo `texto` no es evidencia suficiente de que el valor sea correcto cuando hay ambigüedad de anclas en el documento.
