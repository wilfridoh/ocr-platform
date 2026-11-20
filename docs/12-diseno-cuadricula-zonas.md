# 11 — Diseño: cuadrícula de zonas (mapeo y validación por posición)

> Maqueta: `diseno/maqueta.html` → `#/plantillas/zonas` (también se llega desde el paso "Campos" del asistente y desde Editar plantilla con el botón **Cuadrícula** del visor y **Mapear con cuadrícula** en la regla "Zona"). Datos de la maqueta: tarjeta ficticia, sin personas reales ni fotos; la "foto" es una silueta.

## 1. Decisiones

| Tema | Decisión |
|---|---|
| Activación | Botón **Cuadrícula** en la barra del `VisorPagina` abre el modo cuadrícula (mismo visor ampliado + panel "Campos y zonas"). Interruptor para mostrar u ocultar la rejilla sin perder zonas. |
| Rejilla | Estilo hoja de cálculo: columnas A–L, filas 1–8, encabezados visibles. **12 × 8** por defecto (celda casi cuadrada en ID-1, 1,5 vs 1,586). Configurable: 8×5 grueso, 12×8 recomendado, 16×10 fino, 24×15 muy fino. |
| Almacenamiento | Las zonas se guardan en **coordenadas relativas 0–1** (`x, y, ancho, alto`, igual que `ReglaCampo`), no en celdas. Cambiar la densidad no pierde zonas; la rejilla solo ajusta el trazo. |
| Selección | Arrastre rectangular (mouse, lápiz y táctil con pointer events). Un clic = una celda. Lectura en vivo: `Fecha de nacimiento · H7:J7 · 3×1 celdas`. |
| Asignación | 1) elegir campo en el panel (o chip `+ Valor` / `+ Etiqueta fija`), 2) elegir tipo, 3) arrastrar. Al asignar un valor, el foco salta al siguiente campo sin zona. |
| Varias zonas | Un color por campo (paleta distinta de los colores de estado), badge con el nombre sobre cada zona; pasar el ratón por un campo atenúa las demás. Máximo una zona de **valor** y una de **etiqueta** por campo. |
| Corregir / borrar | Volver a dibujar reemplaza; herramienta **Borrar** (arrastre), `×` en el chip de cada zona, **Deshacer** (Ctrl+Z). |
| Tipos de zona | **Valor** (relleno sólido): dato a extraer. **Etiqueta fija** (borde punteado y rayado): texto impreso esperado, sirve para validar. Existen también "elementos fijos" sin campo (p. ej. encabezado). |
| Ayudas | El panel muestra lo que la zona lee en el documento de ejemplo ("Lee: …") y lo que la etiqueta debe decir ("Debe decir: …"). Avisos: zona vacía, zona superpuesta. |

## 2. Validación de un documento (pestaña "Validar un documento")

- **Coincidencia de diseño con la plantilla** (nunca "documento auténtico": valida la disposición): puntaje en un anillo (0–100 %) con veredicto *Coincide* (≥ umbral), *Coincidencia parcial* (entre umbral − 15 puntos y el umbral) o *No coincide*. Umbral por plantilla (60 % por defecto, como en el contrato de API).
- La fórmula del puntaje la define Desarrollo OCR; la maqueta solo muestra el resultado y su desglose.
- **Clic sobre una palabra** propone todas sus celdas (Mayús + clic = una sola celda). Requiere las palabras con posición de la API; sin ellas ("documento antiguo") solo funciona el arrastre.
- Desglose: etiquetas fijas OK (n de m), desplazamiento medio, valores legibles.
- El documento recibido se muestra con las zonas de la plantilla encima: verde ✓ coincide, ámbar ≈ parcial/desplazada, rojo ✕ no coincide.
- Tabla "Detalle por zona": celdas, esperado, leído, estado; filtro **Solo diferencias** y resaltado cruzado fila ↔ zona.
- Si el puntaje es muy bajo se sugiere otra plantilla ("¿Otro tipo de documento?").

## 3. Estados

| Estado | Comportamiento |
|---|---|
| Imagen sin recorte fiable | Aviso ámbar; la cuadrícula se desactiva hasta **Ajustar esquinas** (4 manijas) → **Confirmar recorte**, o **Usar de todos modos** (queda la marca "Recorte sin verificar"). En validación el puntaje puede ser inferior al real. |
| Cargando imagen | Esqueleto animado "Preparando la imagen enderezada de la tarjeta… (1–2 s)" mientras responde `.../enderezada`. |
| Documento antiguo | Aviso informativo (404 de palabras): "no tiene posiciones guardadas" con botón **Reprocesar documento**; el arrastre sigue funcionando. |
| Plantilla sin zonas | Estado vacío con ícono en el panel + globo "Arrastra para marcar las celdas del valor" sobre el visor; **Guardar zonas** deshabilitado. En validación: aviso de que se necesita al menos una etiqueta fija. |
| Móvil < 768 px | Barra superior con menú; una columna; barra inferior fija con campo activo, Valor/Etiqueta, Borrar y Deshacer; **Modo dibujo táctil** (bloquea el scroll mientras se dibuja; apagado, el dedo desplaza la página). |

## 4. Boceto: guía de encuadre previa a la cámara

Al pulsar "Usar cámara" en un flujo de cédula aparece una hoja con el marco ID-1 (85,6 × 54 mm), cuatro esquinas y tres consejos (fondo oscuro y liso, ocupar el marco con las 4 esquinas visibles, de frente y sin reflejos), con **Abrir cámara** / **Elegir archivo**. El marco en vivo sobre la cámara queda para cuando haya HTTPS.

## 4 bis. Paso 1 del asistente: de 1 a 3 documentos de ejemplo

- Contador "n de 3" y filas seleccionables con número de orden; al llegar a 3 la zona de carga se deshabilita ("Quita uno para agregar otro"). Pestañas "Ejemplo 1/2/3" en la vista previa.
- **1 ejemplo**: aviso ámbar "las sugerencias llegan para revisar" y chip `revisar` en cada palabra clave sugerida. **2 o 3**: aviso verde ("lo que se repite pasa a ser palabra clave o etiqueta fija; los datos del titular quedan fuera"). **0**: estado vacío y "Siguiente" deshabilitado.
- Tarjeta "Qué sugerirá el sistema" con vista previa de las palabras clave.
- **Palabras en gris** (confianza < 0,7, mismo umbral de la segunda opinión): en el texto OCR del paso 1 y sobre la tarjeta en el editor de cuadrícula, con leyenda.
- **Girar 90°** en el aviso de recorte no fiable (`POST …/recorte` con `orientacion`).

## 4 ter. Recorte manual y origen del recorte (contrato de la entrega 2)

- Chip "Recorte: automático | manual | no detectado | desconocido" en la cabecera del editor (de `X-Recorte-Origen` / `X-Recorte-Confiable`).
- **Ajustar esquinas** muestra 4 manijas (orden arriba-izq, arriba-der, abajo-der, abajo-izq, relativas a la imagen original) y **Confirmar recorte** llama a `POST …/recorte`. Mientras responde: esqueleto "Recortando… (unos segundos)" y sin botones.
- Error 422: alerta roja "No se pudo aplicar el recorte" con el `detail` del servidor tal cual; las manijas siguen visibles para corregir.
- **Girar 90°** envía solo `orientacion` (conserva las esquinas manuales previas).
- Documento anterior (origen `desconocido`): aviso con botón **Reprocesar para ver posiciones**; el arrastre sigue funcionando.
- Imagen enderezada: PNG está bien para el editor de escritorio (~0,2 s); en móvil conviene JPEG calidad ~90 si pesa 1–2 MB.

## 5. Dependencias de API (para coordinar con Desarrollo OCR)

- `ReglaCampo` ya tiene `x, y, ancho, alto, pagina`; falta distinguir `tipo_zona` (`valor` | `etiqueta`) y guardar `texto_esperado` de las etiquetas; la plantilla necesita `umbral_coincidencia` y `densidad_rejilla` (solo UI).
- El resultado necesita: `coincidencia.puntaje`, `etiquetas_ok/total`, `desplazamiento_medio`, y por zona `{estado, esperado, leido}`.
- El procesamiento debe informar `recorte_confiable: bool` (bordes de tarjeta detectados y enderezado).
- Propuesta para que el recorte manual funcione: aceptar 4 esquinas (relativas) y reenderezar.
