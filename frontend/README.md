# OCR Platform — Frontend

Interfaz web (React + TypeScript + Vite) para subir documentos, ver el resultado del OCR/clasificación/extracción
y administrar las plantillas de tipos de documento. Ver la especificación completa en
[`../docs/03-frontend.md`](../docs/03-frontend.md).

## Stack

React 18, TypeScript, Vite, React Router, TanStack Query, Tailwind CSS, React Hook Form + Zod,
`react-json-view-lite`, y un editor de zonas propio (SVG/`div` sobre la imagen, sin librerías de canvas pesadas).

## Cómo correr en desarrollo

```powershell
cd frontend
npm install
npm run dev
```

Abre `http://localhost:5173`.

### Con el backend real

Por defecto `vite.config.ts` hace proxy de `/api` a `http://localhost:8000` (donde corre FastAPI). Basta con tener
el backend levantado (`docker compose up backend` o `uvicorn` local) y poner en `.env.development`:

```
VITE_USAR_MOCK=false
```

### Con datos de ejemplo (sin backend) — modo mock

El repo trae `.env.development` con:

```
VITE_USAR_MOCK=true
```

Con esa variable, `src/api/index.ts` usa `src/api/mock/` en lugar de llamar a `/api`: datos en memoria con
3 plantillas (`planilla_servicio_electrico`, `cuenta_contrato`, `cedula_identidad`), 5 documentos de historial y
1 resultado completo según el contrato de `docs/01-diseno-general.md` sección 5. Permite ver y probar toda la
interfaz — Procesar, Documentos, Detalle, Plantillas, el asistente de 3 pasos y Editar plantilla — sin que el
backend exista todavía. El estado del mock vive solo en memoria del navegador y se reinicia al recargar la página.

Para apagar el mock y hablar con un backend real, cambia la variable a `false` (o bórrala) y reinicia `npm run dev`.

## Estructura

```
frontend/
├── src/
│   ├── api/
│   │   ├── index.ts        # elige apiHttp o apiMock según VITE_USAR_MOCK
│   │   ├── contrato.ts     # interfaz ClienteApi común a ambas implementaciones
│   │   ├── apiHttp.ts      # cliente real contra /api (fetch + X-API-Key)
│   │   ├── http.ts         # helper fetch + manejo de errores (ErrorApi)
│   │   ├── claveApi.ts     # guardar/leer la API key en localStorage
│   │   └── mock/           # datos de ejemplo + implementación en memoria
│   ├── componentes/
│   │   ├── CargaArchivo.tsx         # drag & drop
│   │   ├── VisorPagina.tsx          # imagen + cajas resaltadas + dibujo de zonas
│   │   ├── TablaCampos.tsx          # colores por confianza / obligatorio faltante
│   │   ├── VisorJSON.tsx            # copiar / descargar
│   │   ├── EditorPalabrasClave.tsx  # peso 1-5
│   │   ├── EditorRegla.tsx          # pestañas ancla / regex / zona
│   │   ├── EditorCampos.tsx         # lista de campos del asistente/editor
│   │   ├── BarraLateral.tsx         # navegación + indicador de /salud
│   │   └── Layout.tsx
│   ├── paginas/
│   │   ├── Procesar.tsx
│   │   ├── Documentos.tsx
│   │   ├── DetalleDocumento.tsx
│   │   ├── Plantillas.tsx
│   │   ├── NuevaPlantilla.tsx      # asistente de 3 pasos
│   │   ├── EditarPlantilla.tsx
│   │   └── ConfigurarAcceso.tsx    # guarda la API key
│   ├── tipos/index.ts       # tipos TS escritos a mano a partir del contrato
│   ├── utilidades/          # formato.ts, probarEnMemoria.ts (vista previa del asistente)
│   ├── App.tsx              # rutas
│   └── main.tsx
├── nginx.conf                # sirve el build y hace proxy de /api al servicio "backend"
├── Dockerfile                # multi-etapa: node:20-alpine (build) → nginx:alpine (runtime)
└── vite.config.ts            # proxy /api → localhost:8000 en desarrollo
```

## Mapa de pantallas

| Ruta | Pantalla |
|---|---|
| `/` | Procesar documento |
| `/documentos` | Historial |
| `/documentos/:id` | Detalle de resultado (resultado, texto OCR, tiempos, log) |
| `/plantillas` | Administrador de plantillas |
| `/plantillas/nueva` | Asistente de nueva plantilla (3 pasos) |
| `/plantillas/:id` | Editar plantilla (+ versiones, reprocesar documentos) |
| `/configurar-acceso` | Guardar la API key (`X-API-Key`) en `localStorage` |

## Generar tipos desde el OpenAPI del backend (más adelante)

Hoy `src/tipos/index.ts` está escrito a mano porque el backend aún no existe. Cuando FastAPI esté corriendo y
expongga su esquema, se puede generar un archivo complementario con `openapi-typescript` y migrar los tipos
de forma incremental:

```powershell
npm install -D openapi-typescript
npm run tipos:openapi   # usa http://localhost:8000/openapi.json -> src/tipos/openapi.d.ts
```

(el script ya está en `package.json`; falta solo instalar `openapi-typescript` cuando se use por primera vez).
Recomendación: ir reemplazando los tipos manuales de `src/tipos/index.ts` por los generados, sin romper
`ClienteApi`, para que ambas implementaciones (`apiHttp`, `apiMock`) sigan compilando.

## Docker

```powershell
docker build -t ocr-frontend .
docker run -p 8080:80 ocr-frontend
```

El `Dockerfile` es multi-etapa: `node:20-alpine` instala dependencias y corre `npm run build` (con
`VITE_USAR_MOCK=false`), y `nginx:alpine` sirve `dist/` con *fallback* a `index.html` para las rutas de React
Router. `nginx.conf` reenvía `/api/`, `/docs` y `/openapi.json` al servicio `backend` definido en
`docker-compose.yml` (puerto 8000), así el navegador habla con un solo origen.

## Verificación

```powershell
npm run build   # tsc -b && vite build — debe terminar sin errores de TypeScript
npm run dev      # arranca el servidor de desarrollo en :5173
```

## Desviaciones respecto a `docs/03-frontend.md`

- El scaffolding inicial de `npm create vite@latest` trae React 19 / Vite 8 / TS 7; se fijaron versiones
  estables (React 18.3, Vite 5, TS 5.6) acordes al stack pedido en la spec.
- Los tipos TS se escribieron a mano (`src/tipos/index.ts`) en vez de generarse desde el OpenAPI, porque el
  backend todavía no existe; queda el script `npm run tipos:openapi` listo para cuando sí exista.
- El editor de zonas es un `div`/imagen con eventos de mouse (sin canvas ni `react-konva`), tal como permite la
  spec ("Canvas propio (o `react-konva`)").
- La vista previa en vivo del asistente ("Resultado con esta plantilla") para una plantilla todavía no guardada
  se calcula en el navegador (`src/utilidades/probarEnMemoria.ts`) aplicando regex/ancla sobre el texto OCR del
  documento de ejemplo; el método "zona" no puede recortar la imagen sin backend, así que muestra un valor
  marcador. Cuando el backend exista, esto puede cambiar a llamar `POST /plantillas/{id}/probar` con una
  plantilla temporal si el backend ofrece ese modo.
- `listarVersionesPlantilla` y `reprocesarDocumentosDePlantilla` (usadas en Editar plantilla) no están en la
  tabla de endpoints de `docs/02-backend.md`; se asumieron rutas `GET /plantillas/{id}/versiones` y
  `POST /plantillas/{id}/reprocesar` razonables para lo que pide `docs/03-frontend.md` sección 4.6. Ajustar
  `src/api/apiHttp.ts` si el backend expone otras rutas.
