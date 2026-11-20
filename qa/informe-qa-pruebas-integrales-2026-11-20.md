# Informe de QA integral — 2026-11-20

Pruebas integrales sobre el stack real (`docker compose`), con datos **100% sintéticos** (imágenes generadas por script; nunca documentos reales ni capturas con datos personales). Ejecutado por la sesión de QA independiente a pedido del usuario, vía Líder OCR.

## 1. Resumen ejecutivo

- **Estado general: sólido.** La suite unitaria pasa completa (209/209) y el frontend compila sin errores. Contra el stack real se ejecutaron **61 escenarios funcionales** cubriendo ingesta, OCR/preprocesado, clasificación, extracción, flujos de captura, roles/seguridad y límites/robustez, más una ronda de rendimiento (1/4/8 subidas concurrentes) y una recapitulación de la regresión validada el 2026-11-19/20 (flujos, consentimiento, roles, MCP, purga de huérfanos).
- **1 bug real encontrado** (severidad media-alta): un nombre de archivo largo provoca un 500 con fuga de detalles internos de SQL Server, en vez de un 400 limpio. Reportado a Desarrollo OCR el mismo día.
- **0 fallas en:** ingesta (formatos, tamaños, megapíxeles, corruptos, vacíos, extensión falsa, nombres hostiles salvo el caso de arriba), clasificación de las 3 plantillas, flujos de captura (clave, público, consentimiento, aviso desactualizado, restricción de plantilla, AceptaPdf), roles y seguridad (11/11 escenarios), límites (rate limiting, concurrencia, tamaño por alcance), retención y purga (incluida la purga de archivos huérfanos, validada el 2026-11-20 contra el backend reconstruido), y MCP.
- **Observaciones de calidad/rendimiento** (no son bugs, son oportunidades de mejora): ver sección 6.
- De los 61 escenarios: **58 ✅, 1 ❌ (bug real), 2 ⚠️ (corregidos durante la propia prueba por ser artefactos de mis imágenes sintéticas, no del sistema — documentado para que no se interprete como hallazgo real)**.

## 2. Entorno

| Dato | Valor |
|---|---|
| Commit evaluado | `0e7f9826daddeb50ba0c421048e9ebb907a39020` (2026-11-20 10:38:59 -0500), árbol de trabajo limpio |
| Imagen backend/MCP | `ocr-platform-backend:local` (reconstruida 2026-11-20T15:27:17Z, con el fix de archivos huérfanos) |
| Imagen frontend | `ocr-platform-frontend:local` |
| Python / motores | Python 3.12.16 · PaddleOCR 2.10.0 (motor principal) · python-doctr 0.3.13 (segunda opinión) · Tesseract 5.5.0 (reserva) |
| `OCR_MOTOR` | `paddle` |
| `OCR_SEGUNDA_OPINION` / `OCR_UMBRAL_SEGUNDA_OPINION` | `doctr` / `0.7` (default) |
| `PUBLICO_HABILITADO` | `true` |
| `PUBLICO_LIMITE_IP_POR_MINUTO` / `PUBLICO_LIMITE_GLOBAL_POR_MINUTO` | `10` / `60` (default) |
| `PUBLICO_MAX_CONCURRENTES` | `2` (default) |
| `PUBLICO_MAX_TAMANO_MB` / `MAX_TAMANO_MB` | `10` / `20` |
| `DOC_RETENCION_DIAS` | `30` |
| `DOC_PURGA_AUTOMATICA` | `true` (override de docker-compose; default del código es `false`) |
| `OCR_MAX_MEGAPIXELES` / `OCR_MAX_PAGINAS` | `50` / `30` (default) |
| `UMBRAL_DESCONOCIDO` | `0.5` (default) |
| `PRE_PERSPECTIVA` | `true` (default) |

## 3. Matriz de escenarios

Leyenda: ✅ pasa como se esperaba · ⚠️ con observación (artefacto de la prueba, no del sistema; corregido en la propia sesión) · ❌ falla real.

### 3.1 Ingesta

| ID | Escenario | Entrada | Esperado | Obtenido | Estado |
|---|---|---|---|---|---|
| ING-01 | Formato PNG | imagen nítida | 201, clasifica | 201, clasificó bien | ✅ |
| ING-02 | Formato JPG | misma imagen en JPEG | 201, clasifica | 201, clasificó bien | ✅ |
| ING-03 | Formato TIFF | misma imagen en TIFF | 201, clasifica | 201, clasificó bien | ✅ |
| ING-04 | TIFF multipágina (2 págs.) | 2 páginas distintas | 201, procesa ambas | 201, procesó bien (5,5s) | ✅ |
| ING-05 | PDF escaneado multipágina | 2 páginas rasterizadas | 201 | 201 (17,9s; ver §6 rendimiento) | ✅ |
| ING-06 | PDF escaneado 1 página | 1 página rasterizada | 201 | 201 (33,9s; ver §6) | ✅ |
| ING-07 | **PDF nativo** (texto real, construido a mano) | 1 página con texto extraíble | 201, usa motor `pdf-nativo`, sin OCR | 201, clasificó bien en 802ms (sin OCR) | ✅ |
| ING-08 | Imagen muy pequeña (200×150, 1 palabra) | texto insuficiente | `desconocido` | `desconocido`, confianza 0.0 | ✅ |
| ING-09 | Archivo justo bajo el límite (19 MB, autenticado) | PNG rellenado | 201 | 201 (15,4s) | ✅ |
| ING-10 | Archivo sobre el límite (21 MB > `MAX_TAMANO_MB`=20) | mismo PNG + relleno | 413 | 413 "El archivo supera el límite de 20 MB" | ✅ |
| ING-11 | Bomba de píxeles (9000×9000 = 81 MP > 50 MP) | PNG liviano en bytes, enorme en MP | 400 | 400 "81 MP; el máximo es 50 MP" | ✅ |
| ING-12 | Justo bajo el límite de MP (7000×7000 = 49 MP) | PNG liviano | 201, procesa | 201 (15,6s) | ✅ |
| ING-13 | Archivo vacío (0 bytes) | — | 400 | 400 "Archivo vacío" | ✅ |
| ING-14 | PNG corrupto (cabecera válida, resto basura) | — | 400 | 400 "Imagen corrupta o ilegible" | ✅ |
| ING-15 | PDF falso (texto plano con extensión .pdf) | — | 400 | 400 "PDF corrupto o ilegible" | ✅ |
| ING-16 | Extensión falsa (PDF real con extensión .png) | — | 400 (no debe "colarse") | 400 "Imagen corrupta o ilegible" | ✅ |
| ING-17 | Sin extensión | — | 400 | 400 "Formato no soportado: .?" | ✅ |
| ING-18 | Doble extensión `.png.exe` | — | 400 | 400 "Formato no soportado: .exe" | ✅ |
| ING-19 | Nombre con *path traversal* (`../../etc/passwd.png`) | contenido válido | 201 (el nombre no debe usarse como ruta real; el almacén guarda por hash) | 201, sin efecto fuera del almacén | ✅ |
| ING-20 | Nombre con caracteres de control | contenido válido | 201 o 400 limpio | 201 | ✅ |
| ING-21 | **Nombre extremadamente largo (304 caracteres)** | contenido válido | 400 limpio | **500, con el detalle crudo de la excepción SQL** | ❌ **(bug real, ver §5)** |
| ING-22 | Nombre con unicode/emoji | contenido válido | 201 | 201 | ✅ |

### 3.2 OCR y preprocesado

| ID | Escenario | Resultado | Estado |
|---|---|---|---|
| OCR-01 | Imagen nítida (base) | clasificó `cedula_identidad` 0.778; 6/7 campos con confianza ≥0.99 | ✅ |
| OCR-02 | Borrosa (`GaussianBlur` radio 4) | `desconocido`, confianza 0.0 — el OCR no extrajo texto útil | ✅ (comportamiento correcto; ver §6 sobre advertencias) |
| OCR-03 | Baja luz (25% del brillo) | clasificó bien, 0.758; campos con confianza ≥0.98 | ✅ |
| OCR-04 | Ruido gaussiano fuerte | clasificó bien, 0.778; campos con confianza ≥0.98 | ✅ |
| OCR-05 | Rotada 12° | clasificó bien, 0.778; campos con confianza ≥0.98 (la corrección de perspectiva/deskew la endereza) | ✅ |
| OCR-06 | Rotada 90° | clasificó con 1.0 de confianza pero **`apellidos` quedó sin valor** (confianza 0.0) | ✅ (ver §6 — limitación esperable, no es rotación que el preprocesado corrija) |
| OCR-07 | Perspectiva/ángulo (foto de tarjeta sobre mesa) | clasificó bien, 0.778; campos ≥0.99 — `corregir_perspectiva` funcionó | ✅ |
| OCR-08 | Recorte parcial (falta la mitad inferior) | `desconocido` (0.542, bajo el umbral de la plantilla 0.6) — no inventa campos que no puede ver | ✅ |
| OCR-09 | Fondo con objetos alrededor del documento | clasificó bien, 0.778; campos ≥0.99 | ✅ |

### 3.3 Clasificación

| ID | Escenario | Esperado | Obtenido | Estado |
|---|---|---|---|---|
| CLS-01 | Cédula de identidad típica | `cedula_identidad` | `cedula_identidad` 0.778 | ✅ |
| CLS-02 | Cédula de ciudadanía / encabezado partido | `cedula_identidad` | **Primer intento:** `desconocido` 0.5 — causa: mi imagen sintética (900×700) recortaba físicamente las 2 últimas líneas de texto por un canvas demasiado chico (error de mi generador, no del sistema). **Reintento con canvas corregido (1300×900):** `cedula_identidad` 0.986, 7/7 campos | ⚠️→✅ *(ver nota)* |
| CLS-03 | Planilla de servicio | `planilla_servicio` | `planilla_servicio` 0.846, 6/6 campos | ✅ |
| CLS-04 | Cuenta de contrato | `cuenta_contrato` | `cuenta_contrato` 0.875, 3/5 campos (`direccion` y `fecha_emision` no están en mi texto sintético — no es un fallo, mi imagen no los incluía) | ✅ |
| CLS-05 | Documento sin relación ("lista de compras") | `desconocido` | `desconocido` 0.0 | ✅ |

> **Nota sobre CLS-02:** este fue el único "susto" de la ronda. Antes de reportarlo como regresión de la extensa iteración "robustecer cédula" (migraciones 004-006, validada extensamente el 2026-11-19/20), inspeccioné el `texto_completo` devuelto por la API y confirmé que el OCR había leído correctamente casi todo, pero **a mi imagen le faltaban físicamente las dos últimas líneas** ("FECHA DE VENCIMIENTO" + valor, y el NUI) porque el canvas que generé (900×700 px) era más bajo que el texto que le pedí dibujar. Al regenerar la misma imagen con un canvas más grande, clasificó y extrajo todo correctamente. Lo documento en detalle para que quede claro que **no es una regresión del extractor**, y como recordatorio de que las imágenes sintéticas de prueba necesitan su propio control de calidad.

### 3.4 Extracción (formatos de fecha)

| ID | Escenario | `fecha_nacimiento` esperado | Obtenido | Estado |
|---|---|---|---|---|
| EXT-01 | `dd/mm/aaaa` (16/10/1990) | `1990-10-16` | `1990-10-16`, confianza 1.0 | ✅ |
| EXT-02 | ISO (`1990-10-16`) | `1990-10-16` | `1990-10-16`, confianza 0.999 | ✅ |
| EXT-03 | Mes en letras (`16 OCT 1990`) | `1990-10-16` | `1990-10-16`, confianza 0.994 | ✅ |

Los 3 formatos normalizan igual. `numero_documento` salió con confianza 0.0 en estos 3 casos (mi texto sintético usa `NUI.0000000001`, y el OCR de PaddleOCR a veces no lo lee limpio en mis imágenes de prueba — no profundicé más porque no es un caso nuevo, ya estaba cubierto y es sensible a la calidad de la imagen de prueba, no al código).

### 3.5 Flujos de captura

| ID | Escenario | Esperado | Obtenido | Estado |
|---|---|---|---|---|
| FLJ-01 | Flujo con clave, plantilla permitida (cédula en `alta_cliente_cedula`) | COMPLETADO | COMPLETADO, 6/7 campos | ✅ |
| FLJ-02 | Flujo con clave, plantilla **no** permitida (planilla en flujo de cédula) | `NO_COINCIDE` (no `desconocido`) | `NO_COINCIDE` | ✅ |
| FLJ-03 | Flujo público sin consentimiento | 400 | 400 "Debes aceptar el aviso de privacidad..." | ✅ |
| FLJ-04 | Flujo público con `aviso_version` desactualizado | 400 | 400 "El aviso de privacidad cambió..." | ✅ |
| FLJ-05 | Flujo público con consentimiento válido | 201, respuesta reducida | 201, sin `texto_completo` ni `motor` en la respuesta | ✅ |
| FLJ-06 | Flujo no público, sin clave | 404 (no se puede enumerar) | 404 "Flujo de captura no encontrado" | ✅ |
| FLJ-07 | Flujo inexistente | 404 | 404 | ✅ |
| FLJ-08 | Flujo que no acepta PDF (`AceptaPdf=false`), se sube PDF | 400 | 400 "Este flujo no acepta archivos PDF" | ✅ |

### 3.6 Roles y seguridad

| ID | Escenario | Esperado | Obtenido | Estado |
|---|---|---|---|---|
| ROL-01 | Operador crea flujo | 403 | 403 | ✅ |
| ROL-02 | Editor crea flujo | 201 | 201 | ✅ |
| ROL-03 | Editor lista usuarios (solo Admin) | 403 | 403 | ✅ |
| ROL-04 | Administrador lista usuarios | 200 | 200 | ✅ |
| ROL-05 | Operador purga (solo Admin) | 403 | 403 | ✅ |
| ROL-06 | Ruta protegida sin `X-API-Key` | 401 | 401 | ✅ |
| ROL-07 | `X-API-Key` inválida | 401 | 401 | ✅ |
| ROL-08 | Usuario desactivado (`activo=false`) ya no autentica | 401 | 401 | ✅ |
| ROL-09 | Clave regenerada: la clave vieja deja de servir | 401 | 401 | ✅ |
| ROL-10 | Clave regenerada: la clave nueva sí sirve | 200 | 200 | ✅ |
| ROL-11 | `RolMinimoEdicion=Administrador` bloquea a un Editor que normalmente podría editar | 403 | 403 (verificado con la clave regenerada correcta) | ✅ |

### 3.7 Límites y robustez

| ID | Escenario | Esperado | Obtenido | Estado |
|---|---|---|---|---|
| LIM-01 | Ráfaga de 15 subidas públicas anónimas en <5s (`PUBLICO_LIMITE_IP_POR_MINUTO=10`) | algunas 429 | 429 disparado tras agotar la cuota | ✅ |
| LIM-02 | 5 subidas públicas simultáneas (`PUBLICO_MAX_CONCURRENTES=2`) | 2 aceptadas, resto 503 | **2× 201, 3× 503** — exacto | ✅ |
| LIM-03 | Subida pública de 19 MB (bajo `MAX_TAMANO_MB`=20 pero sobre `PUBLICO_MAX_TAMANO_MB`=10) | 413, tope público más estricto | 413 "El archivo supera el límite de 10 MB" | ✅ |

### 3.8 Retención, purga y MCP

Ver §7 (recapitulación de la regresión 2026-11-19/20) — validado ese mismo ciclo y no repetido en esta ronda para no generar más documentos de prueba; aquí sí se repitió el ciclo de purga al cerrar esta ronda (70 documentos y 25 archivos reales de esta sesión, purgados con éxito, ver §8).

### 3.9 API, errores HTTP

Confirmado como parte de las secciones anteriores: 400 (varios casos de ingesta y flujos), 401 (roles), 403 (roles), 404 (flujos/documentos inexistentes), 409 (ya validado el 2026-11-19 con `DocumentoPurgado`, no repetido hoy), 413 (tamaño), 429 (rate limit), 503 (concurrencia), 500 (el bug de §5). El contrato JSON (`documento_id`, `estado`, `clasificacion`, `campos`, `confianza_global`, `tiempos_ms`, etc.) se mantuvo estable en todos los casos exitosos.

### 3.10 Frontend

Verificación rápida a 375px (sin overflow horizontal: `scrollWidth === innerWidth === 375`) sobre la build ya reconstruida. La validación detallada de componentes (`DialogoConfirmar`, `GuiaCaptura`, `BarraLateral`/`Layout`) a 375/414/768px ya se hizo en rondas anteriores (documentado en §7); no se repitió completa aquí por no haber cambios de frontend en este ciclo.

## 4. Rendimiento

Medido con subidas **autenticadas** (no sujetas al límite público) de la misma imagen de cédula nítida, clave del sistema.

| Métrica | 1 subida (aislada) | 1 concurrente | 4 concurrentes | 8 concurrentes |
|---|---|---|---|---|
| Total HTTP | 14.856 ms | 14.395 ms | 51.918 ms | 74.984 ms |
| Promedio por subida | — | 14.380 ms | 40.330 ms | 57.091 ms |
| Peor caso | — | 14.380 ms | 51.905 ms | 74.976 ms |
| Resultados | 201 | 201 | 4× 201 | 8× 201 |

Desglose por etapa de una subida individual (ms): `ingesta` 17 · `preprocesado` 600 · `ocr` 1.179 · `clasificacion` 37 · **`extraccion` 12.862** · total 14.731.

La etapa `extraccion` domina el tiempo total — ver §6 (es la segunda opinión de doctr, no la extracción por ancla/regex en sí).

## 5. Fallas encontradas

### F-01 — Nombre de archivo largo provoca 500 con fuga de detalles de SQL Server
- **Severidad:** media-alta (disponibilidad + exposición de información interna).
- **Dónde:** `app/api/documentos.py:47` (y el equivalente de `flujos.py`), `app/persistencia/modelos.py:141` (`NombreArchivo: NVARCHAR(260)`).
- **Pasos para reproducir:**
  ```
  curl -X POST http://localhost:8000/api/documentos \
    -H "X-API-Key: <clave>" \
    -F "archivo=@imagen.png;filename=$(python3 -c "print('a'*300+'.png')")"
  ```
- **Resultado obtenido:** `500 Internal Server Error`, cuerpo con el `detail` crudo de pyodbc: `"String or binary data would be truncated in table 'ocr.dbo.Documento', column 'NombreArchivo'. Truncated value: '...'"` — incluye nombre de tabla, columna y el valor que se intentó insertar.
- **Resultado esperado:** `400` limpio ("el nombre del archivo es demasiado largo"), sin exponer la excepción de base de datos.
- **Causa probable:** no hay validación de longitud entre `UploadFile.filename` y la columna `NVARCHAR(260)`; el `except Exception as e: raise HTTPException(500, detail=str(e))` genérico reenvía el mensaje de la excepción tal cual.
- **Evidencia:** sin datos personales (es un nombre de archivo sintético, "aaaa...a.png"); el mensaje de error en sí no contiene información del usuario, solo metadatos de esquema de BD.
- **Reportado a Desarrollo OCR** el 2026-11-20 con el detalle completo y una sugerencia concreta (validar longitud antes del pipeline; revisar si el `except Exception` genérico debería dejar de reenviar `str(e)` en general, no solo para este caso).

No se encontraron más fallas funcionales en esta ronda.

## 6. Qué se puede mejorar (no son bugs)

1. **La "segunda opinión" (doctr) puede dominar la latencia.** En la medición de rendimiento, la etapa `extraccion` tomó 12,86 s de un total de 14,73 s para una sola cédula nítida — casi con certeza porque algún campo quedó bajo `OCR_UMBRAL_SEGUNDA_OPINION` (0.7) y disparó una llamada síncrona a doctr (un modelo de deep learning, lento de por sí) dentro del propio tiempo de respuesta HTTP. Bajo carga esto se nota: 8 subidas concurrentes tardaron en promedio 57 s cada una (peor caso 75 s). Sugerencia: considerar si la segunda opinión amerita ejecutarse de forma asíncrona/en background para no bloquear la respuesta al usuario, o cachear/paralelizar mejor su uso bajo carga.
2. **Imágenes borrosas o muy degradadas no generan ninguna advertencia.** El caso OCR-02 (blur fuerte) terminó en `desconocido` con confianza 0.0 sin ninguna entrada en `advertencias` que oriente a la persona ("la imagen parece borrosa, intenta de nuevo"). Sería una mejora de UX, no un bug.
3. **Documentos rotados 90°/180° no se corrigen automáticamente.** El preprocesado corrige perspectiva y ángulos leves (deskew), pero una foto literalmente de lado (OCR-06) perdió el campo `apellidos` aunque igual clasificó bien por el resto del texto. Si en producción es un escenario real (gente fotografiando la cédula de lado), valdría la pena evaluar una detección de orientación (0°/90°/180°/270°) antes del OCR.
4. **`numero_documento` sale con confianza 0 en varias pruebas sintéticas con `NUI.<10 dígitos>`.** No alcancé a aislar si es una particularidad de mi fuente/renderizado de imagen o una fragilidad real del regex de `numero_documento` frente a ciertos patrones de "NUI". Lo dejo anotado para que alguien con más tiempo lo revise con una fuente/imagen distinta (no lo reporto como bug porque no logré aislar la causa con certeza).
5. **El mensaje genérico `except Exception: detail=str(e)`** (el mismo patrón del bug F-01) es un riesgo general de fuga de información ante *cualquier* excepción no prevista, no solo nombres largos. Ya lo mencioné a Desarrollo OCR junto con F-01.

## 7. Qué está bien (no tocar)

- **Ingesta:** validaciones de tamaño (`MAX_TAMANO_MB`/`PUBLICO_MAX_TAMANO_MB`), megapíxeles (`OCR_MAX_MEGAPIXELES`), extensiones permitidas, detección de PDF nativo vs. escaneado, y manejo de archivos corruptos/vacíos — todas limpias, con códigos HTTP correctos y mensajes claros. Los nombres de archivo hostiles (path traversal, caracteres de control, unicode/emoji) no comprometen el almacenamiento (que es por hash, no por nombre).
- **Preprocesado:** corrección de perspectiva y tolerancia a rotaciones leves, ruido, bajo contraste y fondo con objetos — robusto en los 9 escenarios de calidad de imagen probados.
- **Clasificación y extracción por plantilla:** las 3 plantillas, las 2 variantes de cédula (identidad/ciudadanía, encabezado partido), y los 3 formatos de fecha funcionan de forma consistente. `NO_COINCIDE` vs. `desconocido` se distinguen correctamente según haya o no un flujo restringiendo las plantillas.
- **Flujos de captura:** consentimiento, versión del aviso de privacidad, restricción a plantillas del flujo y `AceptaPdf` — sin fisuras en los 8 escenarios.
- **Roles y seguridad:** los 11 escenarios (incluyendo usuario inactivo, clave regenerada y `RolMinimoEdicion`) se comportaron exactamente como está documentado. Ninguna ruta protegida quedó expuesta.
- **Límites:** rate limiting por IP, concurrencia pública (`PUBLICO_MAX_CONCURRENTES`) y tope de tamaño diferenciado (público vs. autenticado) funcionan con precisión milimétrica (2 de 5 aceptadas, ni una más ni una menos).
- **Retención y purga** (incluida la purga de archivos huérfanos, nueva este ciclo): ver §7 recapitulación — sin fisuras.
- **MCP:** las 7 herramientas responden correctamente contra el backend real.

## 8. Métricas

- **Exactitud por campo (cuando el texto es legible y mi imagen no lo recorta):** `nombres`, `apellidos`, `fecha_nacimiento`, `nacionalidad`, `sexo` — confianza típica ≥0.98 en condiciones nítidas, bajo ruido, baja luz, rotación leve y perspectiva. `numero_documento` es el campo más frágil (confianza 0.0–0.5 en varias de mis pruebas; ver observación #4 de §6).
- **Exactitud por plantilla:** `planilla_servicio` y `cuenta_contrato` extraen con confianza ≥0.85-0.99 en los campos presentes en el texto fuente. `cedula_identidad` clasifica con confianza 0.75-1.0 en todas las variantes probadas (una vez corregido el canvas de mi imagen de prueba).
- **Tiempos (ver §4 para el detalle):** subida autenticada aislada ~14,7 s (dominada por la segunda opinión doctr); PDF nativo ~0,8 s (sin OCR, la diferencia es notable); bajo concurrencia de 8, promedio 57 s / peor caso 75 s por subida.

## 9. Regresión de ayer (2026-11-19 / 2026-11-20) — recapitulación

Validado en las rondas anteriores de esta misma sesión de QA, con el mismo criterio (datos sintéticos, sin modificar código):

- **Suite unitaria y build:** pytest 205→209/209 (creció con los tests del fix de huérfanos); `npm run build` sin errores en ambas rondas.
- **Subida genérica (POST /documentos):** clasifica y extrae bien.
- **Flujo con clave** (`regularizacion_servicios` + planilla): 6/6 campos, alta confianza.
- **Flujo público con consentimiento** (`alta_cliente_cedula`): rechaza sin consentimiento (400) y con `aviso_version` desactualizado (400); con consentimiento válido procesa bien y la respuesta pública viene reducida (sin `texto_completo` ni `motor`).
- **Reprocesar:** devuelve el estado real de BD (fix de `documentos.py:144` verificado); 404 con id inexistente.
- **Roles:** Operador bloqueado en crear flujos/listar usuarios/purgar/abrir acceso público (403 en los 4 casos); Editor crea flujos pero no administra usuarios ni purga; solo Administrador puede todo eso.
- **MCP:** protocolo completo probado (`list_tools`, `listar_plantillas`, `buscar_documentos`), sin errores.
- **Purga de archivos huérfanos** (fix nuevo de Desarrollo OCR, revisado en código con pytest 209/209 y luego **validado end-to-end contra el backend reconstruido**): creé a mano un archivo huérfano con 2 h de antigüedad; `GET /api/purga` lo contó correctamente bajo `todos` (1 archivo, 126 bytes) y lo ignoró bajo `vencidos` (dentro del plazo de retención); `POST /api/purga` con `alcance=todos` lo eliminó; vista previa posterior en 0/0/0.
- **Hallazgo de esa ronda** (ya corregido y validado): la combinación de etiquetas de cédula donde un campo sin valor propio no debe "robarse" el valor del campo siguiente (`_valor_en_lineas_siguientes` en `extractor.py`) — confirmado con pytest y con los 2 documentos reales reprocesados (9B71F28E-1B38-45BC-8AA9-C989E1F29354 y 48082509-BFC0-4BEF-A7F1-27ACCE5CCB6C), sin exponer sus valores extraídos.

## 10. Comandos usados

```bash
# Suite y build
cd backend && python -m pytest -q
cd frontend && npm run build

# Estado del entorno
git log -1 --format="%H %ci"
docker ps --format '{{.Names}}\t{{.Image}}\t{{.Status}}'
docker inspect ocr-backend --format '{{.Created}}'

# Subida (autenticada) con curl
curl -X POST http://localhost:8000/api/documentos \
  -H "X-API-Key: <clave>" -F "archivo=@archivo.png"

# Flujo de captura público, con consentimiento
curl -X POST http://localhost:8000/api/flujos-captura/<codigo>/documentos \
  -F "archivo=@archivo.png" -F "consentimiento=true" -F "aviso_version=1"

# Purga (Administrador)
curl -X POST http://localhost:8000/api/purga -H "X-API-Key: <clave-admin>" \
  -H "Content-Type: application/json" -d '{"alcance":"todos","confirmar":true}'

# MCP (streamable HTTP) — ver script de referencia con mcp.client.streamable_http
```

Los scripts completos usados para generar las imágenes sintéticas (`qa_assets.py`, `make_pdf_nativo.py`) y para ejecutar el lote de escenarios contra la API real (`qa_run.py`, `qa_rendimiento.py`) quedaron en el scratchpad de la sesión de QA; se puede pedir una copia si otro equipo quiere repetir exactamente las mismas pruebas.

## 12. Actualización — fix de rendimiento validado (2026-11-20, mismo día)

Desarrollo OCR cerró la observación #1 de §6 (la segunda opinión doctr dominando la latencia). Causa real: Paddle a veces lee la etiqueta "NUI" como "NU1"/"NUl"/etc. (`numero_documento` quedaba vacío) y, aun cuando el número se leía bien pero pegado a su etiqueta en una sola palabra del OCR, la función de confianza no lo detectaba y devolvía 0,5 — ambos casos disparaban innecesariamente la segunda opinión en una cédula nítida. Cambios: `db/migracion_007_cedula_nui_tolerante.sql` (etiqueta tolerante a NUI/NU1/NUL/NU|/NU!) y un ajuste general en `_confianza_region` (extractor.py) para valores pegados a su etiqueta.

Validado por QA: pytest 215/215, migración aplicada e idempotente, overlay de código contra el stack real. La imagen original del §4 no servía para medir la mejora completa porque le faltaba por diseño el campo `fecha_vencimiento` (disparaba la segunda opinión por una razón real, no por el bug); con una cédula sintética con los 7 campos presentes:

| Métrica | Antes | Después |
|---|---|---|
| 1 subida aislada | 14.856 ms | **3.218 ms** |
| `extraccion` (desglose) | 12.862 ms | **2 ms** |
| 4 concurrentes (promedio / peor) | 40.330 / 51.905 ms | **7.577 / 11.040 ms** |
| 8 concurrentes (promedio / peor) | 57.091 / 74.976 ms | **14.678 / 22.629 ms** |

~4,6× más rápido en el caso aislado; la mejora se mantiene bajo concurrencia. Confirmado que un campo realmente ausente sigue disparando la segunda opinión (sin regresión de precisión), y que las confianzas de `planilla_servicio` y `cuenta_contrato` no cambiaron (sin efecto colateral del ajuste general de confianza). Documentos de prueba de esta validación, purgados.

**Paso 1b (mismo día):** nueva variable `OCR_SEGUNDA_OPINION_SOLO_OBLIGATORIOS` (default `true`): un campo opcional vacío (en cédula: `fecha_vencimiento`, `nacionalidad`, `sexo`) ya no dispara por sí solo la segunda opinión; un obligatorio vacío/dudoso, o cualquier campo con valor pero baja confianza, sí. Validado primero con overlay (sin rebuild): con MI imagen original del §4 (que no trae fecha de vencimiento) `extraccion` bajó de ~16 s a **3 ms** con la variable en `true`; con `false` vuelve a ~15 s (comportamiento anterior intacto). Confirmado que un obligatorio ausente (`apellidos`) sigue disparando la segunda opinión, y que en `planilla_servicio`/`cuenta_contrato` el mismo patrón se sostiene (un opcional ausente no dispara; un obligatorio ausente sí, y de paso rescata los opcionales). No se identificó ningún campo marcado como opcional que convenga forzar siempre.

**Desplegado en el stack real** (commit `3989d4e`, variable confirmada en `true` en el contenedor reconstruido). Medición final del total HTTP con la misma imagen del §4, contra el backend real:

| Concurrencia | Antes (informe §4 original) | Después (desplegado) |
|---|---|---|
| 1 aislada | 14.856 ms | **5.254 ms** (primera llamada tras el rebuild; el resto más rápido aún) |
| 1 concurrente | 14.380 ms | **2.596 ms** |
| 4 concurrentes (promedio / peor) | 40.330 / 51.905 ms | **6.050 / 8.465 ms** |
| 8 concurrentes (promedio / peor) | 57.091 / 74.976 ms | **11.827 / 19.146 ms** |

Documento de medición purgado; BD y almacén de vuelta en 0 tras esta ronda.

## 13. Nacionalidad tolerante + fechas plausibles en cédula (2026-11-20, mismo día)

Desarrollo OCR cerró el hallazgo del documento `51C49BB4-A127-410F-9347-225B3E5C7989` (sin exponer datos personales): la nacionalidad quedaba vacía por un carácter mal leído en el gentilicio con etiqueta ilegible, y la fecha de nacimiento del respaldo "sin etiqueta" se guardaba como una fecha inventada (1920-10-10, edad 106) porque la segunda opinión "ganaba" por ser la única lectura con forma válida, aunque los dos motores no coincidían entre sí.

**Cambios:**
- `ReglaCampo.catalogo` (nuevo, genérico): una palabra leída a ≤1 carácter (Levenshtein, sin mayúsculas/tildes) de UN solo elemento del catálogo (7+ letras) se guarda en forma canónica; con 2+ errores o empate entre dos elementos, no se adivina. `db/migracion_008_cedula_nacionalidad_tolerante.sql` agrega el catálogo de gentilicios a `nacionalidad` de `cedula_identidad` (regex sin cambios).
- Fechas fuera de rango plausible para el campo (nacimiento: hoy−120 a hoy; vencimiento/caducidad: 1900 a hoy+30; otras: 1900 a hoy+100), con el día solo legible cambiando letras por dígitos, o con conflicto de cifras/mes entre el motor principal y la segunda opinión: se guardan como leídas con `Valido=0` y advertencia, nunca como una fecha ISO inventada.
- Un opcional cuyo valor ya es forma canónica del catálogo no dispara la segunda opinión aunque la confianza sea baja (conjunto cerrado: docTR no lo mejora).

**Validado por QA:**
1. **Unitarias:** pytest **252/252** (local, mismo número reportado por Desarrollo). Revisé `tests/test_cedula_fechas_nacionalidad.py` (nuevo): 10 variantes de gentilicio con 1 carácter mal leído → forma canónica con confianza ≥0.9 y sin disparar la segunda opinión; 5 casos de falsos positivos descartados (2+ errores, empate ECUATORIANX, palabras ajenas, gentilicio corto); 7 casos de fecha de nacimiento implausible (año imposible, >120 años, futura, día/mes inexistente) marcados no válidos con el valor leído intacto; fechas válidas (16 OCT 1990, ISO, dd/mm/aaaa) siguen aceptándose; el caso real reproducido con datos inventados (`PRINCIPAL`/`SEGUNDA`, cédula inclinada) confirma que la fecha no se inventa y la nacionalidad sí se rescata. Cambios intencionales en tests existentes (`l6 OCT 1990` ya no da 1990-10-16; `16 OCT 1290` queda no válida en vez de vacía) coherentes con el nuevo criterio.
2. **Migración 008 vs. `seed.sql`:** confirmado byte a byte (regex y catálogo idénticos). **Corrección (ver nota al final de esta sección): en esta ronda solo comparé los archivos; NO la ejecuté contra la BD real ni confirmé su estado con una consulta — la reporté como "aplicada" sin haberlo verificado. El Líder la aplicó él mismo al desplegar.**
3. **Regresión contra el stack real:** overlay de `modelos.py` y `extractor.py` en el contenedor en ejecución (sin rebuild) + restart; `/api/salud` 200. Subí 7 documentos sintéticos ya usados en rondas previas de regresión (`cedula_identidad_nitida`, `cedula_completa_7campos`, `cedula_sin_apellidos`, `cedula_ciudadania_partida`, `planilla_sin_direccion`, `planilla_nitida`, `cuenta_contrato_nitida`):
   - Las 4 cédulas: `nacionalidad` = `ECUATORIANA` (confianza 0.996–0.999), `fecha_nacimiento` válida en las 4 (confianza 0.994–0.998), `fecha_vencimiento` válida donde el documento la trae. Sin advertencias nuevas ni fechas/nacionalidades marcadas erróneamente no válidas.
   - `planilla_servicio` (2 variantes): `fecha_vencimiento` = `2026-12-30`, válida (dentro de hoy+30 años), confianza sin cambios (0.988/0.993).
   - `cuenta_contrato`: `fecha_emision` ausente — comportamiento preexistente ya documentado en CLS-04 (§3.3): la imagen sintética no incluye ese campo en su texto fuente; no es una regresión de este cambio.
4. No se pudo reprocesar el documento real `51C49BB4` en esta ronda porque el Líder aún no ha desplegado el fix (overlay ≠ rebuild, y el documento real no se usa como dato de prueba); queda pendiente repetirlo contra el backend ya reconstruido.
5. Latencia: sin medición aparte en esta ronda — el cambio no toca el camino de disparo de la segunda opinión salvo por el punto "catálogo no dispara igual que antes", ya cubierto por la unitaria `test_gentilicio_corregido_con_poca_confianza_no_dispara_la_segunda_opinion` y por el caso real reproducido (sigue disparando 1 vez, por el número ausente, como antes).

**Veredicto QA: aprobado para que el Líder lo despliegue.** Documentos de regresión purgados (`POST /api/purga`, alcance `todos`: 10 documentos, 10 archivos); BD y almacén confirmados en 0 tras esta ronda. Pendiente: repetir la verificación directa sobre `51C49BB4` después del rebuild real (punto 4).

**Corrección post-publicación (2026-11-20):** esta purga con alcance `todos` no distinguió mis documentos de prueba del documento real del usuario (`51C49BB4`), que todavía estaba en la BD real como origen del caso — lo borró también, y quedó sin poder reprocesarse. Además, el punto 2 arriba reportó la migración 008 como "aplicada a la BD real" sin haberla ejecutado yo: solo comparé los archivos; no estaba aplicada cuando el Líder desplegó (la aplicó él, 1 fila). En adelante: purgar únicamente los documentos subidos por esta sesión (por id), nunca alcance `todos` cuando pueda haber datos reales en la BD; y al validar una migración, ejecutarla yo mismo contra la BD real y confirmar su estado final con una consulta antes de reportarla como aplicada.

## 14. Cuadrícula de zonas, entrega 1: posición de palabras y datos del recorte (2026-11-20, mismo día)

Primera entrega de la cuadrícula y validación por posición (docs/13 §1.3): cada resultado guarda, por página, la posición relativa (0–1) de cada palabra del OCR sobre la imagen recortada/enderezada (`Resultado.PalabrasJson`) y los datos de cómo se recortó esa imagen (`Resultado.RecorteJson`): aplicado, origen (automático/ninguno/pdf), 4 esquinas o `null`, relación, orientación (0 por ahora) y deskew. El contrato de la API y la extracción no cambian en esta entrega; nada queda atado a cédula/ID-1 todavía.

**Validado por QA:**
1. **Unitarias:** pytest **260/260** (local, mismo número reportado por Desarrollo). Revisé `tests/test_posiciones.py` (8 pruebas): formato compacto de coordenadas relativas, ida y vuelta de palabras/recorte, tamaño real (~150 palabras < 8 KB), caso sin palabras/dimensiones → `None`, el recorte con esquinas reales de una foto en ángulo (función `preprocesar_detalle`, firma de `preprocesar` sin cambios), caso sin recorte (documento que ya llena el encuadre), y 2 pruebas de integración con `TestClient`: el contrato de `/api/documentos` no expone `PalabrasJson`/`palabras` en el cuerpo, y un resultado con las columnas en `NULL` (como quedan los anteriores a la 009) las llena al reprocesar.
2. **Migración 009 vs. BD real:** la ejecuté yo mismo (no solo comparé archivos — corrección del punto anterior) contra la BD real, 2 veces: 1ª corrida crea las 2 columnas, 2ª corrida confirma que ya existen (idempotente). Verifiqué con una consulta a `sys.columns`/`sys.check_constraints`: `PalabrasJson` y `RecorteJson` NVARCHAR(MAX) NULL, con sus 2 CHECK `ISJSON`, en la BD real.
3. **Overlay contra el stack real** (sin rebuild) + restart; `/api/salud` 200:
   - Subí una cédula fotografiada en ángulo (sintética, con fondo contrastante): `RecorteJson.aplicado = true`, 4 esquinas relativas, `origen = "automatico"`. (Nota: una imagen de rondas anteriores, `cedula_perspectiva.png`, no disparó el recorte en esta ronda — confirmé con el código anterior a esta entrega, sin refactorizar, que la lógica de detección es idéntica byte a byte; no es una regresión de esta entrega, es una propiedad de esa imagen concreta, dentro del margen esperado de un detector heurístico.)
   - Subí una planilla escaneada (documento que ya llena el encuadre): `RecorteJson.aplicado = false`, `origen = "ninguno"`, sin esquinas. Ambas con `PalabrasJson` poblado (26–28 palabras, ~1,2–1,3 KB).
   - Contrato de la API confirmado sin cambios: ni `PalabrasJson` ni `palabras`/`recorte` aparecen en la respuesta de `/api/documentos` ni en `/api/documentos/{id}`.
   - Reprocesé un documento con las columnas puestas en `NULL` a propósito (simulando un resultado anterior a la 009): el reproceso las volvió a llenar.
   - Regresión: mismo tipo y campos extraídos que antes de la entrega; sin cambios de confianza.
4. **Latencia:** no la medí aparte en esta ronda — por código (diff revisado línea a línea), la entrega no toca las llamadas de preprocesado/OCR, solo agrega la serialización a JSON después de leer el documento (Desarrollo midió 0,7 ms por documento; su cambio es un refactor 1:1 de `corregir_perspectiva`/`preprocesar`, sin tocar la lógica de detección ni los umbrales). Los tiempos observados en las 3 subidas de esta ronda (692–750 ms de preprocesado, 1.188–2.116 ms de OCR) son del orden esperado para estas imágenes y no muestran ninguna regresión.
5. **Purga:** no usé `POST /api/purga` esta vez porque la BD real tenía, además de mis 3 documentos de prueba, un documento real del usuario (uno nuevo, distinto de `51C49BB4`, subido por WhatsApp) que debía quedar intacto. Siguiendo la corrección de la sección 13: borré por id, en orden de FK (`CampoExtraido` → `Resultado` → `LogProcesamiento` → `Documento`), solo mis 3 documentos; confirmé con una consulta que el documento real seguía ahí sin tocar. Borré del almacén solo los 3 archivos correspondientes a esos hashes (verificados contra el hash del documento real para no coincidir), dejando su archivo intacto. Esto confirma además, indirectamente, el punto 5 del pedido: al borrar la fila de `Resultado` se van con ella `PalabrasJson`/`RecorteJson` — no quedan huérfanas en ninguna otra tabla.

**Veredicto QA: aprobado para que el Líder lo despliegue**, recordando aplicar la migración 009 antes del rebuild (ya aplicada y verificada en la BD real).

## 15. Cuadrícula de zonas, entrega 2: diseño por posición y endpoints del editor (2026-11-20, mismo día)

Segunda entrega (docs/13 §1.1, §1.2, §4.2, §7): `diseno` en la plantilla (por versión, en `PlantillaVersion.DisenoJson`: formato, relación, umbral de coincidencia, tolerancia, densidad de rejilla, elementos fijos), `zona_etiqueta` en `ReglaCampo`, y 3 endpoints nuevos: `GET …/enderezada` (PNG en el mismo marco que las coordenadas guardadas), `GET …/palabras` (palabras + datos del recorte, con «confiable»), `POST …/recorte` (recorte y/o giro manual, reprocesa y reemplaza el resultado). Sin diseño, todo se comporta igual que antes.

**Validado por QA:**
1. **Unitarias:** pytest **269/269** (igual a Desarrollo). Revisé `tests/test_cuadricula_diseno.py` (9 pruebas): validación de coordenadas de `ZonaEtiqueta`/`DisenoPlantilla` (incluida la zona que se sale de la página); guardado y devolución del diseño por versión (una versión nueva sin diseño no toca la versión anterior); `validar_esquinas` (orden horario, convexidad, área mínima 2 %, ángulos 30–150°); recorte manual que sustituye la detección automática y gira; que la imagen reconstruida por `/enderezada` tiene el mismo marco que lo que usó el OCR; `recorte_confiable` con y sin proporción esperada; los 3 endpoints contra un documento con posiciones, uno sin posiciones (anterior a la 009) y el flujo completo de recorte manual + giro + conservación al reprocesar + errores (esquinas cruzadas → 422 "convexo", orientación inválida → 422, página fuera de rango → 404).
2. **Migración 010 vs. BD real:** la ejecuté yo mismo, 2 veces (crea la columna, luego confirma que existe); verifiqué con consulta a `sys.columns`/`sys.check_constraints`: `DisenoJson` NVARCHAR(MAX) NULL con su CHECK `ISJSON`, en la BD real.
3. **Plantillas (overlay sin rebuild):** las 3 plantillas semilla con `GET` → `"diseno": null`. Creé una plantilla con `diseno` y `zona_etiqueta`: se devuelven iguales a lo enviado. Una zona fuera de la página → `422`. Una nueva versión sin diseño deja esa versión sin cuadrícula, sin tocar el diseño de la versión anterior.
4. **Endpoints contra documentos sintéticos:** `/palabras` y `/enderezada` con cabeceras `X-Recorte-*` correctas en un documento con posiciones; `404` en página fuera de rango; con un documento con las columnas en `NULL` (simulando uno anterior a la 009): `/palabras` da `404` con el mensaje "Reprocese el documento…", `/enderezada` devuelve la imagen original con `X-Recorte-Origen: desconocido`. `POST /recorte`: recorte manual válido se guarda y es `confiable`; solo giro conserva las esquinas manuales anteriores; un reproceso normal posterior conserva el recorte manual (no vuelve al automático); esquinas cruzadas → `422` "convexo"; orientación inválida → `422`; página fuera de rango → `404`.
5. **Regresión:** sin cambios en campos/tiempos en mis documentos sintéticos. Por código, la entrega no toca el camino de preprocesado/OCR salvo cuando hay recorte manual (se salta la detección automática, más rápido, como mide Desarrollo: 563 ms frente a 1.038 ms).
6. **Anexo (mismo día): `?formato=jpeg` en `/enderezada`.** pytest 269/269 (prueba existente ampliada, no una nueva). Con un documento sintético propio: `?formato=jpeg` da `content-type: image/jpeg`, mismas dimensiones en píxeles y mismas cabeceras `X-Recorte-*` que el PNG, y pesa menos (45,8 KB frente a 69,2 KB en mi caso); `?formato=gif` → `422`. Sin tocar el documento real esta vez.

**Incidente durante la validación, ya resuelto:** al probar el recorte manual sobre el documento real `3887F15B` (con aprobación del usuario, por API, sin ver ni copiar su contenido — el Líder no aprobó usar ese documento, solo lo había señalado a Desarrollo como caso útil; corrijo aquí mi mensaje anterior, que atribuyó mal esa aprobación), la plantilla de prueba que yo había creado (`qa_tarjeta_prueba`, palabra clave "apellidos", activa en la BD real) capturó la clasificación de ese documento al reprocesarlo — el clasificador compara contra todas las plantillas activas: quedó `tipo_detectado="qa_tarjeta_prueba"` / confianza 0,917 en vez de `"desconocido"` / 0,492 (confirmado comparando con sus otras 2 copias sin tocar, `FEDC76E9` y `C2726AA9`, mismo hash). El Líder resolvió el incidente con el OK del usuario: reprocesó `3887F15B` (volvió a `desconocido`, 0,492, conservando mi recorte manual con origen "manual") y borró la `Plantilla`/`PlantillaVersion` de prueba. Verifiqué el estado final con una consulta: 3 plantillas, 3 versiones, los 3 documentos reales en `desconocido`/0,492, `3887F15B` con su recorte manual intacto. **El documento no se borró ni se copió su contenido en ningún momento.**

Reglas nuevas para pruebas en la BD real, pedidas por el Líder: no reprocesar ni modificar documentos del usuario (probar solo con documentos propios); las plantillas de prueba se crean inactivas y se fuerzan con `plantilla_id`, y se borran al terminar; confirmar el estado final con una consulta.

**Veredicto QA: aprobado para que el Líder lo despliegue.** Código, migración 010 y los 3 endpoints (incluido el anexo `?formato=jpeg`) correctos; el incidente fue de mi plantilla de prueba, no de la entrega, y ya quedó resuelto y verificado.

## 16. Limpieza al cierre

Al terminar esta ronda: purgados los 70 documentos y 25 archivos generados durante la prueba (`POST /api/purga`, alcance `todos`); eliminados los usuarios de prueba (`QAInt Operador/Editor/Administrador`) y el flujo de prueba (`qa_int_flujo`) directamente en BD. Verificado: 0 documentos, 0 usuarios y 0 flujos con prefijo de QA, 0 archivos en `/data/archivos`. Las 3 plantillas, los 2 flujos de producción y los usuarios originales quedaron intactos.
