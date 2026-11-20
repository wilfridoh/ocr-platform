# Informe QA — Backend OCR Platform (C:\OCR\backend)

Autor: sesión **Dev QA OCR**. Alcance: auditoría de la suite de tests ya entregada, cierre de huecos de cobertura con tests nuevos, y pruebas manuales E2E contra el servidor real. No se modificó código de producción en ningún momento.

## 1. Resultado real de la suite (antes de mis cambios)

```
cd C:\OCR\backend
.venv\Scripts\python.exe -m pytest -q -v
```
→ **2 failed, 30 passed** (no 32/32 como dice el README/checklist).

Las 2 fallas: `tests/test_api.py::test_subir_documento_y_obtener_resultado` y
`tests/test_pipeline_e2e.py::test_pipeline_end_to_end_planilla_sintetica`.

## 2. Hallazgo real #1 (bug, no corregido por mí — es trabajo del agente de backend)

**`TESSDATA_PREFIX` nunca se autodetecta, pese a lo que promete el comentario.**

- `app/config.py` (línea ~33-34) documenta: *"Carpeta con \*.traineddata. Vacío = autodetectar (backend/tessdata si contiene el idioma)"*.
- Esa autodetección **no existe en el código**. `app/pipeline/ocr.py:216` hace `tessdata_prefix=settings.TESSDATA_PREFIX or None` — con el default `""`, siempre pasa `None`, y nunca se setea `TESSDATA_PREFIX` en el entorno del proceso.
- `backend/tessdata/spa.traineddata` **sí existe** en el repo, pero no se usa salvo que alguien exporte `TESSDATA_PREFIX` manualmente antes de levantar pytest/uvicorn (tal como indica `docs/08` en el bloque de comandos).
- Por eso el checklist reporta "32 tests pasando": probablemente se corrió en una sesión donde esa variable ya estaba exportada en el shell. En un entorno nuevo (shell limpio, que es el estado real de "clonar y correr"), la suite falla reproduciblemente con:
  ```
  Error opening data file C:\Program Files\Tesseract-OCR/tessdata/spa.traineddata ...
  ```
- **Impacto:** cualquier CI, agente nuevo, o desarrollador que corra `pytest` sin exportar la variable a mano ve fallos falsos-negativos. Rompe la promesa de "autodetectar".
- **Reproducible:** corriendo en un shell limpio (`env | grep -i tess` vacío) se repite siempre.
- **No lo arreglé** (instrucción explícita de la tarea): esto es para el agente de backend — opciones razonables serían implementar la autodetección real en `config.py`/`ocr.py` apuntando a `backend/tessdata` cuando existe, o al menos documentar que es obligatorio exportar la variable.

## 3. Tests nuevos agregados (cierre de huecos de cobertura)

No se tocó código de producción, solo se añadieron tests. Resultado final tras mis cambios:

```
2 failed (las mismas 2 de siempre, por el bug de TESSDATA_PREFIX), 65 passed
```

- **`tests/test_validadores.py`** (+22 tests): fecha ISO passthrough, día/mes inválido (31/feb, mes 13), umbral de siglo en año de 2 dígitos (69→2069, 70→1970), fecha vacía, monto sin separador, monto con varios puntos de miles, monto sin dígitos, RUT con letras (inválido), RUT con DV=K, cédula en los límites (6 y 13 dígitos), email/teléfono/número inválidos, texto vacío y con espacios.
- **`tests/test_clasificador.py`** (+4 tests): sin ninguna plantilla activa (caso extremo de "tipo desconocido"), plantilla sin palabras clave (evita división por cero), texto vacío, tolerancia a confusión OCR típica `0/O` y `1/l`.
- **`tests/test_extractor.py`** (+6 tests): campo obligatorio ausente con confianza 0 (no el "0.5 por defecto"), ancla en página 2 de un documento multi-página, ancla con valor en la línea siguiente, zona sin palabras dentro del recorte, zona en página que no existe, monto sin separadores de miles.
- **`tests/test_ensamblador.py`** (archivo nuevo, 8 tests): este módulo **no tenía ningún test** antes. Cubre `construir_advertencias` (obligatorio faltante, obligatorio con texto pero inválido, opcional no válido, todo válido) y `confianza_global` (sin campos, combinación normal, penalización por campo con confianza 0), más un `ensamblar()` end-to-end para el caso "desconocido sin campos".

Huecos que **no cerré** (quedan para una siguiente pasada, requieren más tiempo o datos reales):
- `app/api/*.py` más allá de los 4 endpoints ya cubiertos (no hay tests de `PUT /plantillas/{id}`, `PATCH .../estado`, `POST .../sugerir`, `POST .../probar`, `GET /documentos` con filtros, `POST .../reprocesar`, ni los 400/404 documentados en docs/02 §8 para archivo corrupto o plantilla forzada inexistente).
- Documentos PDF multi-página reales (solo probé multi-página a nivel de `extraer_campo` con páginas sintéticas en memoria, no subiendo un PDF de 2 páginas a la API).
- `mcp_server/server.py` no tiene tests.

## 4. Pruebas manuales E2E (servidor real, uvicorn + SQLite, Tesseract forzado)

Comando usado: `TESSDATA_PREFIX` y `OCR_MOTOR=tesseract` exportados a mano (sorteando el bug #1 solo para poder probar), `DATABASE_URL=sqlite:///./qa_manual.db`.

### Caso 1 — documento que clasifica bien
Imagen sintética con las 4 líneas de la planilla de referencia. Resultado real:
```json
{
  "estado": "COMPLETADO",
  "clasificacion": {"tipo": "planilla_servicio_electrico", "confianza": 0.571},
  "campos": {
    "numero_cliente": {"valor": "1234567-8", "confianza": 0.92},
    "total_pagar": {"valor": null, "confianza": 0.0},
    "fecha_vencimiento": {"valor": "2026-11-30", "confianza": 0.87}
  },
  "advertencias": ["campo_obligatorio_faltante:total_pagar"]
}
```

**Hallazgo real #2**: `total_pagar` (método `regex` sobre el texto completo) **no se extrajo** pese a que el monto está en el texto OCR. Causa: Tesseract (PSM 6) devolvió el texto con el **orden de palabras mezclado entre líneas**:
```
"Total Planilla a pagar de servicio $ 45.320 el\ufffdctrico\nVencimiento N Cliente: 1234567-8 30/11/2026"
```
"Total" ya no queda seguido de "a pagar" en el texto concatenado, así que la regex `Total a pagar\s*\$?\s*([\d.,]+)` no matchea. En cambio, los campos con método `ancla` (`numero_cliente`, `fecha_vencimiento`) sí se extrajeron bien, porque la búsqueda de ancla se hace línea por línea con fuzzy-matching, más tolerante a este tipo de ruido.

**Por qué importa:** esto no es un bug de código (el regex funciona correctamente dado el texto que recibe), es un **riesgo real del método `regex` combinado con Tesseract**: cualquier plantilla que use `regex` sobre texto multi-palabra es frágil al orden de lectura del motor OCR. Recomendación para cuando se corra `scripts/evaluar.py` (§6.2 del checklist): comparar explícitamente cuántos campos `regex` fallan por reordenamiento entre PaddleOCR/docTR vs. Tesseract — es evidencia concreta para la decisión de motor de `docs/06`, y un argumento para preferir `ancla` sobre `regex` de texto libre en las plantillas reales.

### Caso 2 — ningún tipo supera el umbral (desconocido)
Imagen sin relación con la plantilla registrada. Resultado:
```json
{
  "estado": "COMPLETADO",
  "clasificacion": {"tipo": "desconocido", "confianza": 0.0, "alternativas": [{"tipo": "planilla_servicio_electrico", "confianza": 0.0}]},
  "campos": {},
  "advertencias": []
}
```
Comportamiento correcto según contrato (docs/02 §8: "Ningún tipo supera umbral" → 200, `COMPLETADO`, tipo `desconocido`).

### Caso 3 — campo obligatorio ilegible/faltante
Primer intento (quité las etiquetas "Vencimiento"/"N Cliente" del todo) terminó clasificando como `desconocido` en vez de disparar la advertencia de campo faltante — porque esas mismas palabras son también palabras clave de clasificación, así que quitarlas baja el score de clasificación por debajo de `UMBRAL_DESCONOCIDO` (0.5, que pisa el `umbral_confianza` de la plantilla, 0.3, vía `max(...)`). **No es un bug**, pero es una interacción a tener presente: en una plantilla real, un campo que sirve de palabra clave y de campo extraído a la vez puede hacer que, si falta, el documento caiga a "desconocido" entero en vez de "clasificado con advertencia", cambiando el flujo de error que ve el usuario.

Repetí el caso dejando la etiqueta "N Cliente:" presente pero sin valor después (campo ilegible/vacío real). Resultado correcto:
```json
{
  "clasificacion": {"tipo": "planilla_servicio_electrico", "confianza": 1.0},
  "campos": {
    "numero_cliente": {"valor": null, "confianza": 0.0},
    "total_pagar": {"valor": 12500.0, "confianza": 0.96},
    "fecha_vencimiento": {"valor": "2026-12-19", "confianza": 0.77}
  },
  "advertencias": ["campo_obligatorio_faltante:numero_cliente"]
}
```

**Hallazgo real #3 (accuracy, no de código)**: la fecha de vencimiento real era `15/12/2026` y Tesseract la leyó como `19/12/2026` (confundió "5" con "9"). El validador la aceptó como fecha válida porque `19/12/2026` es una fecha real — **el sistema no tiene forma de detectar un error de OCR que produce un valor plausible pero incorrecto**. Esto es exactamente lo que el checklist (§6.2) prevé medir con muestras reales etiquetadas y `scripts/evaluar.py`: la exactitud por campo, no solo si el campo "parece válido". Vale la pena dejarlo anotado para cuando lleguen muestras reales.

## 5. Resumen para el usuario

| Tipo | Hallazgo | Estado |
|---|---|---|
| Bug real | `TESSDATA_PREFIX` no se autodetecta (comentario de `config.py` no implementado) | Reportado, sin corregir — es del agente de backend |
| Riesgo real | Campos con método `regex` sobre texto completo son frágiles al reordenamiento de palabras de Tesseract | Documentado con evidencia reproducible (caso 1) |
| Observación | Un campo que es a la vez palabra clave y campo obligatorio puede hacer caer el documento a "desconocido" en vez de "advertencia de campo faltante" si falta | Documentado (caso 3, primer intento) |
| Observación | OCR puede confundir dígitos (5↔9) y producir una fecha "válida" pero incorrecta: el validador no detecta error semántico | Documentado (caso 3, segundo intento) — relevante para §6.2 del checklist |
| Cobertura cerrada | 40 tests nuevos (validadores, clasificador, extractor, ensamblador — este último sin tests previos) | 65 passed, 2 failed (las mismas de siempre) |
| Cobertura pendiente | Endpoints de plantillas (PUT/PATCH/sugerir/probar), filtros de listado, 400/404 documentados, PDF multi-página real, servidor MCP | No cerrada — para siguiente pasada |

Quedo disponible para seguir profundizando o para correr `scripts/evaluar.py` / diseñarlo cuando lleguen las muestras reales de `C:\OCR\muestras\` (§6.1 del checklist).
