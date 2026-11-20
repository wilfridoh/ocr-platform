# 13. Cuadrícula de zonas y validación por posición: diseño técnico (propuesta)

> Estado: **propuesta técnica, sin implementar**. Es para revisión del Líder y del usuario antes de empezar.
>
> Complementa el diseño de UX en [12-diseno-cuadricula-zonas.md](12-diseno-cuadricula-zonas.md), cuya maqueta está en
> `diseno/maqueta.html` → `#/plantillas/zonas`.
>
> El §8 resume qué partes del contrato de UX se adoptan tal cual y dónde conviene cambiarlo.
>
> No hay datos personales en este documento: los ejemplos de etiquetas son textos impresos del formato, no datos del
> titular.

## 0. Resumen

El editor dibuja una rejilla sobre la tarjeta ya recortada y enderezada (formato ID-1, 85,6 × 54 mm, relación
1,586). Sobre ella se marcan dos tipos de zona:

- **Zona de valor** (máximo una por campo): dónde está el dato. Se usa para extraer por posición, o para confirmar
  lo que encontró la etiqueta.
- **Zona de etiqueta fija** (máximo una por campo, más "elementos fijos" sin campo, como el encabezado): qué texto
  impreso se espera y dónde. Con ellas se calcula el **puntaje de coincidencia de diseño**.

La propuesta reutiliza lo que ya existe y no cambia nada en las plantillas que no tengan zonas:

- el método `zona` (`_extraer_zona` en `pipeline/extractor.py`);
- la corrección de perspectiva (`corregir_perspectiva` en `pipeline/preprocesado.py`);
- las coordenadas de palabra que ya devuelven los motores OCR.

**Prerrequisito que hoy falta:** las cajas de las palabras no se guardan. El resultado persistido solo tiene
`TextoCompleto`, y `CampoExtraido.X/Y` queda en NULL. Sin cajas guardadas no funcionan:

- el "Lee: …" del panel de la maqueta;
- `/probar` con zonas (hoy reconstruye una página sin cajas);
- la validación de diseño sobre documentos ya procesados.

Es la primera pieza a implementar (§1.3).

## 1. Modelo de datos

Todas las zonas se guardan en **coordenadas relativas 0–1** (`x, y, ancho, alto`) sobre la tarjeta en horizontal,
como decidió UX. **No se guardan celdas.** La densidad de la rejilla es solo una preferencia del editor, y cambiarla
no pierde zonas.

### 1.1 Zonas de un campo: claves en `ReglaJson`

| Clave | Contenido |
|---|---|
| `x, y, ancho, alto, pagina` (ya existen) | **Zona de valor.** Con método `zona` extrae solo por posición (como hoy). Con `ancla`/`regex`, la etiqueta busca el valor y la zona lo confirma o desempata (§2.2). |
| `zona_etiqueta` (nueva, opcional) | `{"x", "y", "ancho", "alto", "texto_esperado"}`. La **etiqueta fija** de ese campo, que se usa para validar el diseño. |

Ejemplo:

```json
{"metodo": "ancla", "ancla": "Apellidos", "regex": "[^\\n]+", "lineas": 2,
 "x": 0.31, "y": 0.27, "ancho": 0.40, "alto": 0.10,
 "zona_etiqueta": {"x": 0.31, "y": 0.21, "ancho": 0.14, "alto": 0.05, "texto_esperado": "APELLIDOS"}}
```

- Esto **reemplaza el `tipo_zona` plano que pedía UX** (§8): un único rectángulo con discriminador no permite tener
  a la vez la zona de valor y la de etiqueta de un mismo campo, que la maqueta sí permite.
- No hace falta cambiar el `CHECK` de `Metodo`.

### 1.2 Diseño de la versión: columna nueva `PlantillaVersion.DisenoJson`

Guarda lo que no pertenece a un solo campo:

```json
{
  "formato": "ID-1", "relacion": 1.586,
  "umbral_coincidencia": 0.8,
  "tolerancia": 0.03,
  "densidad_rejilla": "12x8",
  "elementos_fijos": [
    {"x": 0.30, "y": 0.02, "ancho": 0.40, "alto": 0.06, "texto_esperado": "REPUBLICA DEL ECUADOR"}
  ]
}
```

| Clave | Uso |
|---|---|
| `umbral_coincidencia` | Valor por defecto de la maqueta, 80 %. Ver la nota de calibración en §3.1. |
| `tolerancia` | Desplazamiento admitido, como fracción del ancho y del alto (§2.3). |
| `densidad_rejilla` | Solo para que el editor vuelva a abrir con la misma rejilla. El backend no lo usa. |
| `elementos_fijos` | Etiquetas fijas sin campo, como el encabezado. |

- **Nada atado a la cédula ni a ID-1** (criterio del usuario: habrá n tipos de documento creados desde una foto o un
  documento).
  - `formato` es solo una etiqueta del preajuste elegido en el editor (`ID-1`, `A4`, `carta`, `libre`).
  - Lo que usa el backend es `relacion` (lado mayor / lado menor esperado), que va en el diseño de cada plantilla. En
    `libre` se toma del documento de ejemplo.
  - `recorte_confiable` compara la relación del recorte con **esa** relación (±8 %).
  - Las zonas llevan `pagina`, así que un PDF de varias páginas puede tener diseño por página.
- `NULL` = plantilla sin diseño. Se comporta exactamente como hoy; es el caso de las planillas y los PDF de página
  completa.
- Va en la **versión**, no en `Plantilla`: guardar una plantilla ya crea una versión nueva, así que el umbral y las
  zonas quedan versionados con los campos. El editor lo muestra como "umbral de la plantilla".
- **¿JSON o tabla nueva?** JSON:
  - se lee y escribe completo con la versión;
  - no se consulta por partes;
  - sigue el patrón de `ReglaJson`.

### 1.3 Cajas de palabras y datos del recorte en el resultado

Columnas nuevas en `Resultado`:

| Columna | Contenido |
|---|---|
| `PalabrasJson NVARCHAR(MAX) NULL` | Por página: `[{texto, x, y, ancho, alto, confianza}]` relativas (0..1) a la imagen enderezada. Unos 60–150 palabras por cédula → 5–15 KB. |
| `RecorteJson NVARCHAR(MAX) NULL` | Por página guarda solo hechos: `{aplicado, origen: "automatico"\|"manual"\|"ninguno"\|"pdf", esquinas, relacion, orientacion, deskew}`. Las `esquinas` son las 4, relativas a la imagen original. `recorte_confiable` **se calcula al leer**, comparando `relacion` con el formato de la plantilla, y no se guarda. |
| `CoincidenciaJson NVARCHAR(MAX) NULL` | El bloque `coincidencia` del resultado (§3.3). Llega en la entrega 4, con su propia migración. |

**Implementado en la entrega 2:** `PlantillaVersion.DisenoJson` (migración 010), `ReglaCampo.zona_etiqueta` y
`diseno` en el DTO de plantilla.
- **Dónde va `diseno`:** al nivel de la plantilla, igual que `umbral_confianza`, pero se guarda por versión.
- **Endpoints del editor:** `enderezada`, `palabras` y `recorte` (§7).
- **Reprocesar** conserva el recorte manual.
- **`X-Recorte-Confiable` sin proporción esperada** (`?relacion=` ni diseño en la plantilla) vale `true` solo si
  hubo recorte, automático o manual.

**Implementado en la entrega 1:** `PalabrasJson` y `RecorteJson`, con la migración 009. El formato compacto está en
`pipeline/posiciones.py` y en docs/04 §4.6.

**Datos personales:** `PalabrasJson` contiene los mismos datos que `TextoCompleto` (ya guardado), solo que con su
posición. Hereda la misma retención, la misma purga (`purgar_documentos` borra el `Resultado`) y los mismos permisos.

### 1.4 Migración

Una migración por entrega, todas idempotentes, ASCII y con `-f 65001`:

- **Entrega 1** (`db/migracion_009_resultado_posiciones.sql`, hecha): `Resultado.PalabrasJson` y `RecorteJson`, con
  `CHECK ISJSON`.
- **Entrega 2:** `PlantillaVersion.DisenoJson`, con `CHECK ISJSON`.
- **Entrega 4:** `Resultado.CoincidenciaJson`.
- `ReglaJson` no necesita cambios de esquema: `zona_etiqueta` es una clave nueva del JSON.
- **No toca filas existentes.** Ninguna plantilla semilla trae zonas. Los documentos anteriores quedan sin cajas
  hasta que se reprocesan.
- **Orden de despliegue:** primero la migración y después el backend.

## 2. Extracción

### 2.1 Marco de coordenadas

Las cajas de Paddle y docTR se expresan sobre la imagen ya procesada (recortada → enderezada → reescalada).

- **Reescalar** no altera las coordenadas relativas.
- **El enderezado fino** (menos de ±15°) gira la imagen sin cambiar su tamaño. El pequeño error que introduce lo
  absorbe la corrección de desplazamiento (§2.3).
- **Sin recorte fiable**, la "página" es la foto entera, y las zonas no se usan para extraer (§4.2).

### 2.2 Zona de valor + etiqueta: qué gana cuando discrepan

Para un campo con zona de valor y método `ancla` o `regex`:

1. La etiqueta (o la regex) produce candidatos, como hoy, y cada uno se ubica mediante las cajas de sus palabras.
2. **Si un candidato cae dentro de la zona** (con tolerancia), gana ese, aunque no sea el primero del texto. Esto
   evita los "valores de otro campo": el nombre del padre, la fecha de emisión tomada como fecha de nacimiento.
3. **Si ningún candidato cae en la zona** y la zona contiene un valor que pasa el validador del tipo de dato:
   - con recorte fiable y diseño que coincide, gana la zona, con confianza ×0,8 y la advertencia
     `campo_fuera_de_zona:<campo>`;
   - si no, gana la etiqueta, que es el comportamiento de hoy, con la misma advertencia.
4. **Si la etiqueta no encuentra nada**, se usa la zona como respaldo, con confianza ×0,8. Esto rescata etiquetas
   ilegibles.
5. **Si los dos coinciden**, la confianza sube 0,05 (tope 1,0). Esto además evita segundas opiniones innecesarias.

### 2.3 Tolerancia y corrección de desplazamiento

- Antes de extraer, se estima un **desplazamiento global** (dx, dy): la mediana de la diferencia entre la posición
  esperada y la encontrada de las etiquetas fijas halladas. Hacen falta al menos 2; con menos, no se corrige.
- Todas las zonas se mueven ese desplazamiento.
- Después, cada zona se agranda en `tolerancia` (3 %) por lado.
- Una palabra cuenta como "dentro" si su **centro** cae en la zona ampliada.
- Si la escala estimada con las etiquetas se aparta más del 10 %, el recorte se trata como no fiable.

## 3. Validación de diseño (coincidencia)

### 3.1 Puntaje: 70 % etiquetas + 30 % alineación (la fórmula de UX, con dos ajustes)

Para cada etiqueta fija (de un campo o elemento fijo):

- se buscan las palabras **dentro de su zona**, ya desplazada y con tolerancia;
- se calcula la similitud con `texto_esperado`: `fuzz.ratio` normalizado, sin tildes ni mayúsculas.

Si no aparece en su zona, se busca en toda la página: en ese caso cuenta para la similitud, pero queda marcada
`parcial` (desplazada).

| Estado por zona | Condición |
|---|---|
| `coincide` | Similitud ≥ 0,8 y dentro de su zona. |
| `parcial` | Similitud entre 0,6 y 0,8, o encontrada fuera de su zona. |
| `no_coincide` | Similitud < 0,6, o no aparece. |

```
etiquetas  = media de la similitud de cada etiqueta (0 si no aparece)
alineacion = 1 − min(1, desplazamiento_medio / (2 · tolerancia))
puntaje    = 0,7 · etiquetas + 0,3 · alineacion
```

- **Ajuste 1: la alineación se mide en fracción de la tarjeta, no en celdas.** Esto difiere de UX, que la medía en
  celdas (§8). La densidad de rejilla es solo de UI, y medir en celdas haría que el mismo documento puntúe distinto
  según la rejilla elegida. La UI puede **mostrar** el desplazamiento en celdas convirtiéndolo con su densidad.
- **Ajuste 2: el desplazamiento medio solo se calcula con las etiquetas encontradas.** Una etiqueta ilegible no tiene
  posición, y ya penaliza en el término de etiquetas.
- **No verificable.** Si menos de la mitad de las etiquetas son legibles, el resultado es `verificable: false` en vez
  de "No coincide". Así no se acusa de distinto a un documento que solo está borroso.
- **Calibración del umbral (80 % en la maqueta).** Lo dejaría como valor inicial, pero hay que calibrarlo con un corpus
  real antes de usarlo para algo más que informar (§6.3).

### 3.2 Qué significa (y qué no)

**Valida el diseño, no la autenticidad.** Confirma que los textos impresos del formato están donde la plantilla dice.

- Sirve para detectar que se subió otro tipo de documento, una variante distinta (cédula antigua frente a la nueva),
  una foto mal recortada o un documento girado.
- **No** detecta falsificaciones, datos alterados, fotocopias ni capturas de pantalla.
- No revisa elementos de seguridad.

La UI dice «coincidencia de diseño», no «documento válido» ni «auténtico». La maqueta ya usa *Coincide /
Coincidencia parcial / No coincide*, que es correcto.

### 3.3 Exposición en la API y advertencias

Bloque nuevo `coincidencia` en el resultado (`GET /documentos/{id}/resultado`, respuesta de `/probar` y salida del
MCP). Usa los nombres de UX:

```json
"coincidencia": {
  "verificable": true,
  "puntaje": 0.86, "umbral": 0.8, "veredicto": "coincide",
  "etiquetas_ok": 6, "etiquetas_total": 7,
  "desplazamiento_medio": 0.012,
  "valores_legibles": 5, "valores_total": 6,
  "recorte_confiable": true, "recorte_origen": "automatico", "orientacion": 0,
  "zonas": [
    {"campo": "apellidos", "tipo": "etiqueta", "estado": "coincide", "esperado": "APELLIDOS", "leido": "APELLIDOS",
     "x": 0.31, "y": 0.21, "ancho": 0.14, "alto": 0.05},
    {"campo": "apellidos", "tipo": "valor", "estado": "coincide", "leido_ok": true}
  ]
}
```

- `veredicto`: `coincide` (≥ umbral), `parcial` (≥ umbral − 0,15, el corte que pidió UX) o `no_coincide`. Es
  `null` si `verificable: false`.
- Cada zona de etiqueta trae además `similitud` (0–1), para que la UI explique un `parcial` del tipo
  "APELIDOS" frente a "APELLIDOS".
- `desplazamiento_medio` va en fracción de la tarjeta; la UI lo pasa a celdas para mostrarlo.
- **Zonas de valor sin `leido`** (cambio respecto a UX, §8): el valor ya está en `campos[]` del mismo resultado, con
  su confianza. Repetirlo duplicaría un dato personal en otro bloque. Por zona de valor solo va `leido_ok` (si se leyó
  algo válido) y la UI toma el texto de `campos[]`. Las zonas de etiqueta sí llevan `leido`, porque es texto impreso.
- **`coincidencia` es `null`** si la plantilla no tiene diseño.

Advertencias nuevas en la lista existente `advertencias`:

| Advertencia | Cuándo |
|---|---|
| `diseno_no_coincide` | El veredicto es `no_coincide`. |
| `diseno_no_verificable` | No hay recorte fiable, o hay demasiadas etiquetas ilegibles. |
| `recorte_sin_verificar` | Se usó la imagen "de todos modos". |
| `campo_fuera_de_zona:<campo>` | Ver §2.2. |

**Por ahora solo informa.** No cambia el estado del documento ni la clasificación.

**"¿Otro tipo de documento?"** cuando el puntaje es muy bajo: es viable sin coste extra. Se calcula el puntaje con
las cajas ya leídas para las otras plantillas **con diseño** que aparecen en `alternativas` de la clasificación (son
3 como máximo; < 10 ms). Se devuelve `coincidencia.sugerencia = {plantilla_id, puntaje}` si alguna supera el umbral.

## 4. Dependencia del recorte

### 4.1 Qué tan fiable es hoy `corregir_perspectiva`

El método: GrabCut separa la tarjeta del fondo, se ajusta un cuadrilátero y se exigen:

- apoyo en bordes ≥ 0,6;
- contraste con el fondo ≥ 50;
- ángulos entre 55° y 125°.

Si algo falla, no recorta. Nunca fuerza una transformación dudosa.

Mediciones de esta propuesta:

- **Corpus real:** no se pudo medir. Los archivos guardados están purgados y el almacén está vacío.
- **Casos sintéticos y 2 fotos locales** (equipo de desarrollo; solo métricas):

| Caso | ¿Recorta? | Relación resultante (ID-1 = 1,59) | Tiempo |
|---|---|---|---|
| Tarjeta frontal sobre fondo oscuro | sí | 1,58 | ~1,1 s |
| Inclinada 8° / 25° | sí / sí | 1,57 / 1,60 | 1,7–2,0 s |
| Perspectiva fuerte / perspectiva + 15° | sí / sí | 1,65 / 1,62 | 1,8–2,0 s |
| Girada 90° | sí, pero queda **vertical** | 1,58 | ~1,0 s |
| Girada 180° | sí, pero queda **cabeza abajo** | 1,58 | ~1,2 s |
| Fondo claro, poco contraste | **no** | — | 4,3 s |
| Tarjeta que casi llena el encuadre | sí | 1,54 | ~1,6 s |
| Foto real de cédula | sí | 1,62 | ~1,3 s |
| La misma foto con perspectiva fuerte | **no** | — | 8,4 s |

Lectura de los resultados:

- **Con fondo contrastado**, el recorte es bueno: relación dentro de ±5 % de ID-1.
- **Falla con fondo claro y con perspectivas muy marcadas en fotos reales**, que son justo los casos del aviso ámbar
  de la maqueta. La guía de encuadre previa a la cámara (fondo oscuro, 4 esquinas visibles) ataca la causa principal.
- **`recorte_confiable`** = recorte aplicado y relación a ±8 % de 1,586. También es confiable una imagen que ya es
  solo la tarjeta (un escaneo) cuando su relación está en ese rango.
- **Antes de fijar umbrales** hay que medir con 20–30 fotos reales variadas, a cargo de QA.
- **Mejora opcional:** un segundo detector por bordes y rectas cuando GrabCut falla. Costaría +0,3–0,8 s, solo en
  esos casos.

### 4.2 Cuando no hay recorte fiable

**Recorte manual: viable.** Se proponen dos vías:

- **En el editor**, para el documento de ejemplo: «Ajustar esquinas» → `POST /api/documentos/{id}/paginas/{n}/recorte` con
  `{"esquinas": [[x,y]×4]}` relativas a la imagen original, en orden arriba-izquierda, arriba-derecha,
  abajo-derecha, abajo-izquierda.
  - El backend valida que formen un cuadrilátero convexo con ángulos razonables.
  - Guarda `RecorteJson.origen = "manual"` y reprocesa el documento **usando esas esquinas** en vez de GrabCut, lo
    que además es más rápido.
  - Devuelve el resultado nuevo.
- **En la revisión** de un documento recibido por un flujo, el mismo endpoint, con el mismo rol que hoy permite
  reprocesar.

Comportamiento sin recorte fiable:

- **Extracción:** las zonas no se usan y se vuelve a etiqueta y regex, exactamente como hoy, con la advertencia
  `diseno_no_verificable`.
- **Validación:** `verificable: false`, `veredicto: null`.
- **Cambio respecto a la maqueta (§8):** la maqueta propone mostrar igual el puntaje («puede ser inferior al real»).
  Recomiendo **no** calcular un puntaje sobre una imagen sin recorte. Las zonas caerían en cualquier parte, y el
  número bajo se lee como "no coincide" aunque el documento sea correcto.
- **«Usar de todos modos»** sigue sirviendo en el editor para dibujar zonas, con la marca `recorte_sin_verificar`. En
  la validación de un documento muestra "no verificable" hasta que se ajusten las esquinas.

### 4.3 Orientación 90° / 180°

- **Paddle ya corrige 180° por línea** (`use_angle_cls=True`): el texto se lee bien, pero las posiciones quedan
  invertidas.
- **Un giro de 90°** hoy no se corrige.

Propuesta, sin OCR extra:

1. **Vertical tras el recorte:** se gira 90° antes del OCR, con coste ~0. Así siempre queda horizontal.
2. **Duda entre 0° y 180°**, en plantillas con diseño: se calcula el puntaje con las cajas tal cual y rotadas 180°
   (una transformación de coordenadas, sin releer). Gana la mayor, se informa `orientacion` y la imagen enderezada se
   sirve ya girada.
3. **Sin diseño:** se toma la orientación del clasificador de ángulo de Paddle, por mayoría de líneas.

## 5. Sugeridor de palabras clave (`pipeline/sugeridor.py`)

### 5.1 Qué falla hoy

Con un solo ejemplo de licencia bilingüe devolvió fragmentos ("th", "sexo sex fecha"), texto mal leído y un dato del
titular. Las causas:

- **Con un solo ejemplo, TF-IDF premia lo único**, y los datos del titular son lo más único.
- **Los n-gramas cruzan las dos mitades de una etiqueta bilingüe** ("SEXO / SEX").
- **Se aceptan tokens de 2 letras** y no hay palabras vacías en inglés.
- **Sin cajas guardadas no hay confianza por palabra.**

### 5.2 Mejoras propuestas

1. **Varios ejemplos.** `POST /plantillas/sugerir` acepta varios `documento_id`.
   - Las palabras clave y las etiquetas fijas son los n-gramas presentes en **todos** los ejemplos (difuso ≥ 85).
   - Los datos del titular cambian entre documentos, así que quedan fuera solos.
   - TF-IDF frente a otros tipos se usa solo para ordenar.
2. **Con un solo ejemplo**, cada sugerencia sale con `revisar: true`. Además:
   - solo se proponen n-gramas del léxico de etiquetas conocido o de la franja superior (encabezado, el 20 % de
     arriba);
   - se descartan las líneas que el propio sugeridor identifica como valor.
3. **Cortar en `/`, `|` y en los dos puntos** antes de formar n-gramas. Se prefiere la mitad en español.
4. **Tokens de 3 letras como mínimo**, salvo siglas de una lista (`NUI`, `RUC`, `RUT`, `CC`), y palabras vacías en
   inglés.
5. **Descartar tokens con confianza OCR < 0,85** (requiere `PalabrasJson`), y filtrar "texto que no es palabra":
   letras y dígitos mezclados, o sin vocales.
6. **Priorizar el encabezado** (×1,5): franja superior o letra más alta que la mediana.
7. **Excluir valores:** fechas, números, montos, correos y líneas de valor nunca son palabra clave.

Con las mismas cajas, la sugerencia devuelve también `zonas_sugeridas`: etiquetas fijas con su rectángulo, para
precargar la cuadrícula.

## 6. Latencia, esfuerzo y riesgos

### 6.1 Impacto en latencia (procesamiento de un documento)

| Pieza | Coste | Cuándo |
|---|---|---|
| Recorte automático (ya existe) | 1–2 s (hasta 4–8 s cuando falla) | Igual que hoy |
| Recorte manual (esquinas dadas) | < 50 ms (sin GrabCut) | Al ajustar esquinas |
| Giro a horizontal | ~0 | Solo si queda vertical |
| Coincidencia, desplazamiento, 0°/180°, sugerencia de otra plantilla | < 10 ms | Plantillas con diseño |
| Zona + etiqueta | < 5 ms | Campos con zona |
| Guardar `PalabrasJson` (5–15 KB) | ~5 ms | Siempre |
| Detector alternativo de recorte (opcional) | +0,3–0,8 s | Solo cuando GrabCut falla |

Sin el detector alternativo, el impacto es despreciable, y la zona puede **ahorrar** segundas opiniones. La imagen
enderezada del editor se calcula al vuelo (1–2 s) y no afecta el procesamiento.

### 6.2 Esfuerzo estimado (backend; el editor lo dimensionan UX y frontend)

| Pieza | Días |
|---|---|
| Migración 009, modelo y DTO (`zona_etiqueta`, `DisenoJson`) | 0,5 |
| Guardar cajas y recorte; endpoints `enderezada` y `palabras`; `/probar` con cajas | 1,0 |
| Recorte manual (endpoint de esquinas y reproceso con esquinas) | 1,0 |
| Extracción zona + etiqueta, desplazamiento y tolerancia | 1,5 |
| Coincidencia (puntaje, estados por zona, API y MCP, advertencias, sugerencia de otra plantilla) | 1,0 |
| Orientación 90° / 180° | 0,5–1,0 |
| Sugeridor | 1,5 |
| **Total backend** | **≈ 7–8 días** más QA (pruebas propias incluidas en cada pieza) |

Orden sugerido:

1. Guardar cajas.
2. Endpoints del editor y recorte manual, para que el frontend pueda empezar.
3. Coincidencia, solo informativa.
4. Extracción combinada.
5. Sugeridor.

### 6.3 Riesgos

- **Dependencia del recorte.** Con fondo claro o perspectivas fuertes no hay recorte automático. Mitigación:
  - guía de encuadre;
  - recorte manual;
  - vuelta total a etiqueta y regex;
  - medir con un corpus real antes de fijar umbrales.
- **Umbral 80 % sin calibrar.** Mitigación: la coincidencia solo informa en la primera iteración. Con 20–30 cédulas
  reales se mide la distribución del puntaje y se ajusta.
- **Variantes del mismo documento.** Cada variante necesita su propio diseño. Mitigación: una versión o plantilla por
  variante; la sugerencia de "otro tipo de documento" ayuda.
- **Falsos "no coincide" en documentos borrosos.** Mitigación: `verificable: false`.
- **Malinterpretarlo como autenticidad.** Mitigación: textos de la UI (§3.2).
- **Datos personales.** `PalabrasJson` agrega posición al texto ya guardado, con la misma purga y permisos. Las zonas
  de valor no repiten el dato en `coincidencia`. La imagen enderezada expone lo mismo que el `/paginas/{n}` existente.
- **Documentos anteriores sin cajas.** El editor y `/probar` con zonas requieren reprocesar el ejemplo. El 404 lo
  explica.

## 7. Contrato de API

| Endpoint | Cambio |
|---|---|
| `GET /api/documentos/{id}/paginas/{n}/enderezada` | **Nuevo.** PNG (o JPEG calidad 90 con `?formato=jpeg`, para móvil) de la tarjeta recortada, enderezada y horizontal, en color. Cabeceras `X-Recorte-Confiable: true\|false`, `X-Recorte-Origen` y `X-Orientacion`. Sin recorte fiable devuelve la página original (para el aviso ámbar y el ajuste de esquinas). |
| `GET /api/documentos/{id}/paginas/{n}/palabras` | **Nuevo.** `{recorte: {confiable, origen, esquinas, orientacion, relacion}, palabras: [{texto, x, y, ancho, alto, confianza}]}`, relativas a la imagen enderezada. Alimenta el "Lee: …" del panel. 404 si el documento es anterior al cambio. |
| `POST /api/documentos/{id}/paginas/{n}/recorte` | **Nuevo.** Cuerpo: `{esquinas: [[x,y]×4], orientacion?: 0\|90\|180\|270}`, con las esquinas relativas a la imagen original. `orientacion` sirve para el «Girar 90°» manual que pidió UX. Valida, guarda (`origen: "manual"`) y reprocesa con esas esquinas. Devuelve el resultado; la imagen se vuelve a pedir a `…/enderezada`. |
| `GET/PUT /api/plantillas/{id}` | `version.diseno` (§1.2) y `campo.regla.zona_etiqueta` (§1.1). La zona de valor usa `x, y, ancho, alto` de la regla. Guardar crea una versión nueva. |
| `POST /api/plantillas/{id}/probar` | Usa las cajas guardadas y devuelve `coincidencia`. Acepta en el cuerpo un `diseno` y unas reglas sin guardar, para la pestaña "Validar un documento" mientras se editan las zonas. |
| `GET /api/documentos/{id}/resultado` | Bloque `coincidencia` (§3.3) y advertencias nuevas. |
| `POST /api/plantillas/sugerir` | De 1 a **3** `documento_id` (más no mejora y alarga el asistente); `revisar` por sugerencia; `zonas_sugeridas`. |

Convenciones acordadas con UX:
- **Palabras de baja confianza:** se marcan en gris si `confianza < 0,7`, el mismo umbral que dispara la segunda
  opinión. El filtro del sugeridor (0,85) es más estricto, a propósito.
- **Etiquetas:** no tienen `peso` en la UI; todas pesan 1.
- **Nombre de celda:** el editor muestra "A1" (columna en letra, fila desde 1) y lo convierte desde el rectángulo
  relativo con su densidad.

## 8. Contraste con el contrato de UX (`12-diseno-cuadricula-zonas.md` §5)

| Pedido de UX | Propuesta técnica | Motivo |
|---|---|---|
| Zonas en coordenadas relativas 0–1, no en celdas | **Se adopta tal cual.** | Coincide con `ReglaCampo` y con el extractor actual. |
| `tipo_zona` (`valor`/`etiqueta`) como discriminador | **Cambiar:** la zona de valor queda en `x/y/ancho/alto` y la etiqueta va en `zona_etiqueta` anidada. | Un campo puede tener las dos zonas a la vez (la maqueta lo permite); un único rectángulo con discriminador no alcanza. |
| `texto_esperado` | **Se adopta**, dentro de `zona_etiqueta` y en `elementos_fijos`. | — |
| `umbral_coincidencia` "de la plantilla" | **Se adopta**, guardado en la **versión** (`DisenoJson`). Valor inicial 80 %, a calibrar. | Las versiones son inmutables: el umbral queda versionado con las zonas. |
| `densidad_rejilla` (solo UI) | **Se adopta**, en `DisenoJson`; el backend no lo usa. | — |
| Puntaje 70 % etiquetas + 30 % alineación | **Se adopta, con alineación en fracción de la tarjeta (no en celdas)** y solo con las etiquetas encontradas. | En celdas, el puntaje dependería de la densidad elegida, que es solo de UI. La UI puede mostrarlo en celdas. |
| `coincidencia.puntaje`, `etiquetas_ok/total`, `desplazamiento_medio` | **Se adopta**, más `verificable`, `veredicto`, `valores_legibles` y `orientacion`. | — |
| Por zona `{estado, esperado, leido}` | **Se adopta para etiquetas.** Estados `coincide` / `parcial` / `no_coincide`. **Las zonas de valor no llevan `leido`**: llevan `leido_ok`, y el texto se toma de `campos[]`. | No duplicar datos personales del titular en otro bloque. |
| `recorte_confiable: bool` | **Se adopta**, más `recorte_origen` y `orientacion`. | — |
| Recorte manual con 4 esquinas y reenderezar | **Viable**: `POST /documentos/{id}/recorte`, reproceso sin GrabCut. | +1 día de backend. |
| Validar sin recorte fiable mostrando el puntaje («puede ser inferior al real») | **Cambiar:** `verificable: false`, sin puntaje, hasta ajustar las esquinas. «Usar de todos modos» sigue valiendo para dibujar en el editor. | Un número bajo sobre una imagen sin recortar se lee como "no coincide" aunque el documento esté bien. |
| «¿Otro tipo de documento?» si el puntaje es bajo | **Viable**: `coincidencia.sugerencia` con las alternativas de la clasificación que tengan diseño. | < 10 ms, sin OCR extra. |
| Guía de encuadre previa a la cámara | **Muy recomendable**, sin coste de backend. | Ataca la causa principal de los fallos de recorte (fondo claro). |
| Máximo una zona de valor y una de etiqueta por campo | **Se adopta**; el modelo lo refleja. | — |
