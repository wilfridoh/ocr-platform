# 08 — Guía visual del frontend (lenguaje de diseño)

> Fuente de verdad visual: `diseno/maqueta.html` (abrir y comparar). Este documento traduce esa maqueta a tokens y patrones para implementarlos en React + Tailwind. Idioma de toda la UI: español. Solo tema claro. Pensado para ≥ 1366 px.

## 1. Tokens de color

| Token | Valor | Uso |
|---|---|---|
| `bg` | `#F5F6FA` | Fondo de página |
| `surface` | `#FFFFFF` | Tarjetas, inputs, modales |
| `ink` | `#0F172A` | Texto principal, títulos |
| `ink2` | `#475569` | Texto secundario, etiquetas de formulario |
| `ink3` | `#64748B` | Texto de ayuda, metadatos, encabezados de tabla |
| `line` | `#E2E8F0` | Bordes de tarjeta, separadores |
| `line2` | `#F1F5F9` | Separadores suaves de filas, chips neutros, fondos de hover |
| `brand` | `#4338CA` | Botón primario, enlaces activos, foco, paso actual |
| `brand-h` | `#3730A3` | Hover del primario |
| `brand-soft` | `#EEF0FF` | Fondo de chips de marca, hover de filas/botones, ícono de empty state |
| `brand-line` | `#C7CCF8` | Borde de elementos de marca suaves, dropzone |
| `ok` / `ok-soft` | `#047857` / `#E6F6EF` | Completado, confianza alta, "Activa" |
| `warn` / `warn-soft` | `#B45309` / `#FEF3C7` | Confianza < 70 %, advertencias, desconocido |
| `err` / `err-soft` | `#B91C1C` / `#FEE2E2` | Error, campo obligatorio faltante |
| `side` | `#0F172A` | Fondo de la barra lateral |
| `side-ink` | `#94A3B8` | Texto de la barra lateral (activo: `#FFFFFF` sobre `#312E81`; hover: `#1E293B`) |

Bordes de input: `#CBD5E1`. Borde de alerta warn `#FCD34D`, err `#FCA5A5`.

### Tailwind (`tailwind.config`)

```js
theme: { extend: {
  colors: {
    bg:'#F5F6FA', surface:'#fff', ink:{DEFAULT:'#0F172A',2:'#475569',3:'#64748B'},
    line:{DEFAULT:'#E2E8F0',2:'#F1F5F9'},
    brand:{DEFAULT:'#4338CA',h:'#3730A3',soft:'#EEF0FF',line:'#C7CCF8'},
    ok:{DEFAULT:'#047857',soft:'#E6F6EF'}, warn:{DEFAULT:'#B45309',soft:'#FEF3C7'}, err:{DEFAULT:'#B91C1C',soft:'#FEE2E2'},
    side:{DEFAULT:'#0F172A',ink:'#94A3B8',on:'#312E81'}
  },
  fontFamily:{ sans:['Inter','Segoe UI','system-ui','sans-serif'], mono:['JetBrains Mono','Consolas','monospace'] },
  borderRadius:{ card:'10px' },
  boxShadow:{ card:'0 1px 2px rgba(15,23,42,.06),0 1px 3px rgba(15,23,42,.05)' }
}}
```

## 2. Tipografía

- Familia: **Inter** (400/500/600/700); código y valores técnicos: **JetBrains Mono** (`font-mono`, 12.5 px).
- Base 14 px / interlineado 1.5. Título de página (`h1`) 22 px bold, tracking −0.01em, con subtítulo 14 px `ink3`.
- Título de tarjeta 13 px semibold. Etiqueta de campo 12 px semibold `ink2`. Ayuda 12 px `ink3`.
- Encabezado de tabla: 11.5 px MAYÚSCULAS, tracking .04em, `ink3`, fondo `#F8FAFC`.
- Números en tablas: `tabular-nums`.

## 3. Forma y espaciado

- Radios: tarjetas y alertas 10 px; botones e inputs 8 px; chips pill (`rounded-full`); ícono de empty state 18 px (64 px de lado).
- Contenido: `main` con padding 28 × 32 px, ancho máx. 1280 px. Barra lateral fija de 232 px.
- Separación entre tarjetas 14–18 px. Padding de tarjeta (`cb`) 16 px; cabecera de tarjeta (`ch`) 12 × 16 px con borde inferior.
- Íconos: set **Lucide**, 16 px, trazo 2 (stroke `currentColor`).

## 4. Componentes

### Tarjeta (`card` / `ch` / `cb`)
`bg-surface border border-line rounded-card shadow-card`. Cabecera opcional: `px-4 py-3 text-[13px] font-semibold border-b border-line flex items-center justify-between`. Cuerpo: `p-4`. Las tablas van directo dentro de la tarjeta y la tarjeta hace `overflow-x-auto` (nunca desborda la página).

### Botones
- **Primario** `.btn.pri`: `bg-brand text-white border-brand hover:bg-brand-h`, `px-3.5 py-2 rounded-lg font-semibold text-[13px]`, ícono 16 px a la izquierda con gap 7 px.
- **Secundario** `.btn`: `bg-white border-line text-ink hover:bg-line2`, mismas medidas.
- **Fantasma** `.btn.gh`: sin borde ni fondo, `text-ink2 hover:bg-line2` (acciones de fila, "Cancelar").
- **Pequeño** `.sm`: `px-2.5 py-1 text-xs`. En tablas las acciones son solo ícono con `title` y `aria-label`.
- Deshabilitado: opacidad .45 y sin eventos. Foco visible: `outline 2px brand, offset 2px`.

### Chips y badges de estado (`chip`)
`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold`. Variantes: neutro (`line2`/`ink2`), `ok`, `warn`, `err`, `br` (marca: `brand-soft`/`brand`). Con punto de estado opcional (6 px, `currentColor`).

| Estado | Chip |
|---|---|
| COMPLETADO | `ok` con punto |
| ERROR | `err` con punto |
| PROCESANDO | `br` con punto |
| Tipo desconocido | `warn` |
| Plantilla/flujo activo | `ok`; inactivo: texto `ink3` + interruptor apagado |
| Rol mínimo de edición | neutro con ícono candado 12 px |

### Confianza (`conf`)
Barra de 54 × 6 px + porcentaje en semibold. ≥ 70 %: `ok`; 1–69 %: `warn`; 0 % o faltante: `err`.

### Inputs
`w-full border border-[#CBD5E1] rounded-lg px-[11px] py-2 text-[13px] bg-white`. Foco: borde `brand` + anillo `brand-line` 2 px. Etiqueta arriba (`label.l`), ayuda debajo (`help`). Variante `mono` para códigos/claves. Deshabilitado: fondo `#F8FAFC`. Buscador: ícono lupa a la izquierda (padding-left 32 px).

### Interruptor (`sw`)
34 × 20 px, pill; apagado `#CBD5E1`, encendido `ok`; perilla blanca de 16 px.

### Segmentado (`seg`) y pills de filtro
Segmentado: fondo `line2`, radio 8, opción activa blanca con texto `brand`. Tabs: borde inferior 2 px `brand` en la activa.

### Alertas (`alert`)
Caja 10 px con ícono 18 px, título en negrita y texto. Variantes `info` (brand-soft), `warn`, `err`. Botón de acción alineado a la derecha.

### Empty state (patrón `empty` + `ic`)
Centrado, padding 56 px: **ícono circular** (64 × 64, radio 18, fondo `brand-soft`, ícono `brand` de 30 px) → título 18 px semibold → texto `ink3` (máx. 420 px) → botón primario. Variantes de color del ícono: `warn-soft`/`warn`, `err-soft`/`err`, `ok-soft`/`ok` según el caso (sin permiso, error, listo).

### Tabla
Cabecera descrita arriba; celdas `px-3 py-[11px]`, borde inferior `line2`; fila con hover `#F8FAFF` y cursor de mano si es clicable. Pie con paginación: botones de 32 px, activa en `brand`.

### Barra lateral
Fondo `side`, ancho 232 px. Logo 30 px con degradado `#6366F1 → #4338CA`. Ítems con ícono, radio 8, activo `side-on`. Contadores en pill `#1E293B`. Bloque inferior "Sistema operativo" con punto verde `#10B981` (halo `rgba(16,185,129,.2)`). Sección "Administración" con rótulo en mayúsculas `#64748B`.

### Modal y toast
Modal: velo `rgba(15,23,42,.55)`, caja blanca radio 14, cabecera con borde. Toast: pastilla `#0F172A` centrada abajo, texto blanco, ícono check, dura 1.8 s.

## 5. Pantalla de referencia: "Configurar acceso" (`/acceso`)

Tarjeta de 520 px centrada (margen superior 40 px), padding 30 px:
1. Empty-pattern: ícono circular **llave** (brand-soft), título "Configurar acceso" 18 px, descripción "Ingresa la clave de API que te entregó el administrador. Se guarda solo en este navegador."
2. Campo **Clave de API** (`type=password`, mono) con ayuda "Se envía en cada petición como `X-API-Key`."
3. Campo **Servidor** (mono, deshabilitado, valor `/api`).
4. Badge de verificación: caja verde `#F0FDF4`, borde `#BBF7D0`, texto `#14532D`, ícono check, "Conexión verificada · API 1.0.3" (en el real: aparece solo tras probar la clave contra `/salud`; si falla, alerta `err`).
5. Pie: botón fantasma **Cancelar** (izquierda) y primario **Guardar y entrar** (derecha), margen superior 20 px.

## 6. Otras pantallas (mismo lenguaje)

Procesar, Documentos, Detalle, Plantillas, Asistente de plantilla, Editar plantilla, Flujos de captura, Captura dirigida, Usuarios. Todas son composiciones de los componentes de arriba; abrir la maqueta y copiar la estructura. Particularidades:
- **Captura dirigida** (`/captura/:codigo`): sin barra lateral, fondo con degradado `#EEF0FF → #F5F6FA`, columna de 460 px, tarjeta con radio 16.
- **Visor de documento**: cajas sobre la imagen en `brand` (correcto), ámbar (< 70 %) y rojo punteado (faltante); al pasar el ratón por un campo se resalta su caja.
- **Roles**: el menú y las acciones se ocultan o pasan a solo lectura según rol (Administrador > Editor > Operador); sin permiso se muestra un empty state con candado.

## 7. Accesibilidad

Contraste AA con esta paleta; foco visible en todo control; interruptores con `role="switch"` y `aria-label`; botones de solo ícono con `aria-label`; no depender solo del color (los estados llevan texto o ícono).
