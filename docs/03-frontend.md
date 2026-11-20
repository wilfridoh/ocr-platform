# 03 — Frontend: interfaz web

## 1. Propósito

La interfaz permite a una persona sin conocimientos técnicos:
1. **Subir un documento** y ver qué leyó el sistema.
2. **Administrar plantillas**: ver las existentes, crear una nueva a partir de un documento de ejemplo, editar sus campos y probarla.
3. **Revisar el historial** de documentos procesados.

## 2. Stack

| Pieza | Elección | Razón |
|---|---|---|
| Framework | React 18 + TypeScript | Estándar, tipado, componentes reutilizables |
| Build | Vite | Arranque y recarga rápidos |
| Rutas | React Router | Navegación entre pantallas |
| Datos | TanStack Query | Caché y estados de carga/error contra la API |
| Estilos | Tailwind CSS | Rápido de construir, consistente |
| Formularios | React Hook Form + Zod | Validación del editor de plantillas |
| Editor de zonas | Canvas propio (o `react-konva`) | Dibujar rectángulos sobre la imagen de la página |
| JSON viewer | `react-json-view-lite` | Mostrar el resultado plegable |
| Servidor en Docker | Nginx sirviendo el build estático y haciendo proxy a `/api` | Un solo origen, sin CORS |

## 3. Mapa de pantallas

```
/                      → Inicio / Procesar documento
/documentos            → Historial
/documentos/:id        → Detalle de resultado
/plantillas            → Administrador de plantillas (lista)
/plantillas/nueva      → Asistente de nueva plantilla (3 pasos)
/plantillas/:id        → Editar plantilla
```

Barra lateral fija con: **Procesar**, **Documentos**, **Plantillas**, y un indicador de estado del sistema (verde si `/salud` responde).

## 4. Pantallas

### 4.1 Procesar documento (`/`)

```
┌────────────────────────────────────────────────────────────────┐
│  Procesar documento                                            │
│                                                                │
│  ┌──────────────────────────┐   Tipo: [Detectar automático ▼] │
│  │  Arrastra aquí tu PDF    │                                  │
│  │  o imagen, o haz clic    │   [ Procesar ]                   │
│  └──────────────────────────┘                                  │
│                                                                │
│  ── Resultado ───────────────────────────────────────────────  │
│  Tipo detectado: Planilla servicio eléctrico   Confianza 91 %  │
│                                                                │
│  ┌─ Vista previa ──────┐  ┌─ Campos extraídos ──────────────┐ │
│  │  [imagen página 1]  │  │ Número cliente  1234567-8  95 % │ │
│  │  con cajas          │  │ Dirección       Av. ...    82 % │ │
│  │  resaltadas         │  │ Total a pagar   45.320     93 % │ │
│  │                     │  │ Vencimiento     30-11-2026 90 % │ │
│  └─────────────────────┘  └─────────────────────────────────┘ │
│                                                                │
│  Palabras clave: [dirección] [consumo] [total a pagar]         │
│  [ Ver JSON ]  [ Copiar JSON ]  [ Descargar ]  [ Reprocesar ]  │
└────────────────────────────────────────────────────────────────┘
```

Comportamiento:
- Al pasar el ratón por un campo, se resalta su zona en la imagen (usa las coordenadas que devuelve la API).
- Campos con confianza baja (< 70 %) se muestran en ámbar; obligatorios faltantes en rojo.
- Si el tipo es **desconocido**, aparece un aviso con botón **"Crear plantilla desde este documento"** que lleva al asistente con el documento ya cargado.

### 4.2 Historial (`/documentos`)
Tabla con: fecha, archivo, tipo, confianza, estado, acciones (ver, reprocesar, descargar). Filtros por tipo, estado y rango de fechas. Paginación.

### 4.3 Detalle de resultado (`/documentos/:id`)
Misma vista de resultado que en Procesar, más: texto OCR completo (pestaña), tiempos por etapa, log de procesamiento y versión de plantilla usada.

### 4.4 Administrador de plantillas (`/plantillas`)

```
┌────────────────────────────────────────────────────────────────┐
│  Plantillas                                  [ + Nueva ]       │
│                                                                │
│  Código                        Campos  Docs   Activa  Acciones │
│  planilla_servicio_electrico     6     142     ●      ✎  ⏻    │
│  cuenta_contrato                 5      87     ●      ✎  ⏻    │
│  cedula_identidad                7      23     ○      ✎  ⏻    │
└────────────────────────────────────────────────────────────────┘
```

### 4.5 Asistente de nueva plantilla (`/plantillas/nueva`)

**Paso 1 — Documento de ejemplo**
Subir un archivo o elegir uno del historial. El sistema lo procesa y muestra la imagen con el texto OCR.

**Paso 2 — Identificación**
- Código y nombre del tipo.
- Palabras clave: lista editable con peso (1-5). Vienen **pre-llenadas** con las sugerencias de la API (`/plantillas/sugerir`); el usuario quita, agrega o ajusta.

**Paso 3 — Campos**
Tabla de campos con: nombre, etiqueta, tipo de dato, obligatorio, método de regla. Vienen pre-llenados con los campos sugeridos (fechas, montos, números detectados).
Para cada campo el usuario elige el método:
- **Ancla**: escribe el texto que precede al dato (o hace clic sobre él en la imagen).
- **Regex**: escribe la expresión; se muestra el valor que captura en vivo.
- **Zona**: dibuja un rectángulo sobre la imagen; se guarda en coordenadas relativas.

Panel derecho siempre visible: **"Resultado con esta plantilla"**, que se actualiza al cambiar cualquier regla (llama a `/plantillas/{id}/probar` o a una versión en memoria para plantillas aún no guardadas).

Botón **Guardar y activar**.

### 4.6 Editar plantilla (`/plantillas/:id`)
Mismo formulario del paso 2 y 3 del asistente, con el historial de versiones y la opción de **reprocesar los documentos** que usaron esta plantilla.

## 5. Estructura del código

```
frontend/
├── src/
│   ├── api/                 # cliente HTTP tipado (fetch + tipos generados del OpenAPI)
│   ├── componentes/
│   │   ├── CargaArchivo.tsx
│   │   ├── VisorPagina.tsx          # imagen + cajas resaltadas + dibujo de zonas
│   │   ├── TablaCampos.tsx
│   │   ├── VisorJSON.tsx
│   │   ├── EditorPalabrasClave.tsx
│   │   └── EditorRegla.tsx          # ancla / regex / zona
│   ├── paginas/
│   │   ├── Procesar.tsx
│   │   ├── Documentos.tsx
│   │   ├── DetalleDocumento.tsx
│   │   ├── Plantillas.tsx
│   │   ├── NuevaPlantilla.tsx
│   │   └── EditarPlantilla.tsx
│   ├── tipos/               # tipos TS: Plantilla, Campo, Resultado...
│   ├── App.tsx
│   └── main.tsx
├── public/
├── index.html
├── nginx.conf               # sirve build y proxy /api → backend:8000
├── Dockerfile
└── package.json
```

## 6. Flujo de datos

```
Componente ──► TanStack Query ──► api/cliente.ts ──► /api/... (Nginx proxy) ──► FastAPI
                   ▲                                                              │
                   └──────────────── JSON tipado ◄────────────────────────────────┘
```

- La API key se guarda en `localStorage` tras una pantalla simple de "Configurar acceso"; se envía en `X-API-Key`.
- Los tipos TypeScript se generan desde el OpenAPI de FastAPI (`openapi-typescript`) para que front y back no se desincronicen.

## 7. Estados y mensajes

| Estado | Qué ve el usuario |
|---|---|
| Procesando | Barra de progreso indeterminada con el nombre del archivo y "Leyendo documento..." |
| Completado | Resultado |
| Tipo desconocido | Aviso ámbar + botón crear plantilla |
| Error de API | Mensaje con el detalle y botón reintentar |
| Sin plantillas | Pantalla vacía con llamada a crear la primera |

## 8. Accesibilidad e idioma

- Toda la interfaz en **español**.
- Contraste AA, navegación por teclado en tablas y formularios.
- Tamaños de fuente legibles en pantallas de 1366 px y superiores; uso en móvil no es prioridad en esta fase.

## 9. Docker

`frontend/Dockerfile` multi-etapa: `node:20` para construir, `nginx:alpine` para servir. `nginx.conf` redirige `/api/*` al servicio `backend` del Compose, así el navegador habla con un solo origen.
