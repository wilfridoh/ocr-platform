# 10 — Traspaso al equipo que continúa

> Para quien retome este proyecto: qué hay, cómo levantarlo, qué está validado (y cómo se validó), qué falta, qué trampas ya nos mordieron y qué decisiones no conviene deshacer sin leer el porqué. Complementa a `docs/01`–`09`; no los reemplaza. Fecha de corte: 2026-11-18.

## 1. Qué es y en qué punto está

Plataforma OCR para leer documentos (PDF/imagen), **clasificarlos** contra plantillas y **extraer campos** estructurados (JSON). Tres piezas más la base de datos: API (FastAPI) + pipeline OCR, frontend (React + Tailwind) y servidor MCP; SQL Server como almacén. Es una **prueba de concepto validada, no producción abierta**.

Hecho y verificado:
- Pipeline OCR con **PaddleOCR** (principal), **docTR** (segunda opinión por campo) y **Tesseract** (respaldo). Clasificador, extractor (reglas `regex`/`ancla`/`zona`), validadores y sugeridor de plantillas.
- 3 plantillas semilla (cédula de identidad, planilla de servicios, cuenta de contrato) y un caso real de cédula ecuatoriana validado (ver `docs/08`).
- **Flujos de captura** (qué documento acepta cada punto de captura), **roles** (Administrador/Editor/Operador) con API key por usuario, **acceso público opcional** (apagado), **aviso de privacidad + consentimiento**, **retención y purga** de documentos. Detalle y decisiones en `docs/07`.
- Frontend completo con la guía visual (`docs/09`) y un modo demostración sin backend.

## 2. Levantar y probar

**Todo con Docker (recomendado):**
```powershell
cd C:\OCR
.\scripts\levantar.ps1          # crea .env desde .env.example si falta, construye y espera a /api/salud
```
Puertos: frontend `3000`, API `8000` (Swagger en `/docs`), MCP `8001`, SQL Server `1433` (configurables en `.env`). Otros scripts: `logs.ps1`, `bajar.ps1`, `reiniciar-bd.ps1` (ver `docs/05`).

> La primera construcción es lenta: los modelos de PaddleOCR/docTR se **hornean en la imagen** (`backend/precargar_modelos.py`) para que la imagen funcione sin internet y el primer request no descargue nada.

**Backend sin Docker** (SQLite en memoria por defecto; ver `backend/README.md`): crear venv, `pip install -r requirements.txt -r requirements-ocr-extra.txt`, `uvicorn app.main:app`. Tesseract necesita el idioma español: instalarlo con el sistema (`tesseract-ocr-spa`) o dejar `spa.traineddata` en `backend/tessdata/` (se autodetecta; esa carpeta **no está en el repositorio**, hay que descargarla). En Docker ya viene instalado.

**Frontend sin Docker:**
```powershell
cd frontend
npm install
npm run dev:mock     # http://localhost:5180 — datos de ejemplo, sin backend; selector de rol en «Configurar acceso»
npm run dev:real     # http://localhost:5181 — contra el backend real en :8000 (proxy /api)
npm run build        # tsc -b && vite build
```
En modo demostración, un archivo cuyo nombre contenga `429`, `503`, `413` o `400` simula ese error en la pantalla pública, y `otro` simula «no coincide».

**Pruebas:**
```powershell
cd backend
.venv\Scripts\python.exe -m pytest -q      # 185 pruebas (OCR con Tesseract y SQLite; no necesita SQL Server)
```
Las pruebas que dependen de Tesseract se saltan solas si no está instalado.

## 3. Base de datos: orden de los scripts

`db/aplicar.ps1` (o `aplicar.sh`) aplica, **en este orden y de forma idempotente**: `schema.sql` → `schema_flujos_captura.sql` → `seed.sql` → `vistas.sql`. Es lo que hay que usar en una instalación nueva.

Sobre una **BD ya existente** (con datos), aplica solo lo que falte, en este orden:
1. `schema_flujos_captura.sql` — tablas `Usuario`, `FlujoCaptura`, `FlujoCapturaPlantilla`; columnas `Plantilla.RolMinimoEdicion`, `Documento.FlujoCapturaId/CreadoPorId/ConsentimientoEn/AvisoVersion`, `FlujoCaptura.AccesoPublico`; el `CHECK` de `Documento.Estado` admite `NO_COINCIDE`. Se puede volver a ejecutar sin riesgo y **debe aplicarse antes** de reconstruir el backend (con el esquema viejo, las consultas de plantillas fallan).
2. `migracion_001_variantes_palabras_clave.sql` → `migracion_002_reglas_campos.sql` → `migracion_003_reglas_cedula_ecuador.sql` → `migracion_004_cedula_ciudadania.sql` → `migracion_005_cedula_ciudadania_palabras_clave.sql` → `migracion_006_cedula_robusta.sql` (la 006 añade «NUI.», apellidos en dos líneas y la clave estructural «republica del ecuador/registro civil», y requiere el backend que entiende `lineas`; clasifica «CÉDULA DE CIUDADANÍA»; reglas de las plantillas semilla; la 003 requiere la 002 y la 004 la 003; son idempotentes. La 004 añade a la cédula el número `#########-#` y la fecha ISO; la etiqueta combinada «APELLIDOS Y NOMBRES» la resuelve el extractor, sin migración).
3. `migracion_007_cedula_nui_tolerante.sql` → `migracion_008_cedula_nacionalidad_tolerante.sql` (la 008 añade a la regla de nacionalidad un `catalogo` de gentilicios: una palabra a un carácter de distancia se guarda en su forma canónica; requiere el backend que entiende `catalogo` y que deja como no válidas las fechas implausibles). Una instalación nueva no las necesita: `seed.sql` ya deja el mismo estado.

**Siempre con `sqlcmd ... -f 65001`.** Aplicar un `.sql` UTF-8 sin ese flag corrompió acentos (`Dirección` → `DirecciÃ³n`) y rompió una migración que comparaba el texto original. Por eso las migraciones usan literales ASCII (acentos como escapes JSON `\uXXXX`) y `aplicar.*` ya pasa el flag. Hay un test que comprueba que migraciones y `seed.sql` terminan en el mismo estado.

## 4. Seguridad, roles y variables que importan

- Toda la API exige `X-API-Key`, salvo `/api/salud` y, **solo si se habilita**, las dos rutas públicas de un flujo. La `API_KEY` del `.env` es el **Administrador del sistema** (no tiene fila en `Usuario`; también la usa el servidor MCP). Cada usuario adicional tiene su propia clave (se guarda solo el SHA-256; se muestra una vez al crearla o regenerarla).
- **Acceso público (sin API key) está APAGADO**: `PUBLICO_HABILITADO=false` por defecto. Para encenderlo hace falta la variable **y** que un Administrador abra el flujo concreto (`AccesoPublico`). Sus protecciones (límite por IP y global, tope de concurrencia, tope de tamaño y de píxeles, respuesta reducida, auditoría) están en `docs/07` §5.2.
- **Retención:** `DOC_RETENCION_DIAS=30` y purga automática diaria encendida solo en `docker-compose.yml`. **Ojo con una BD que ya tiene documentos de prueba**: al reconstruir se conservarán solo los de los últimos 30 días; sube el valor o ponlo en 0 si no quieres perderlos.
- Variables completas en `docs/02` §7. Cambia `API_KEY` y `MSSQL_SA_PASSWORD` (los de `.env.example` son de ejemplo) y no subas `.env`.
- **Datos personales:** hay cédulas reales de prueba. Viven en `doc_md/` (excluida del repositorio) y en el volumen Docker `archivos-data`, que no está en el árbol del repo. No añadas documentos reales a pruebas, fixtures ni informes; las pruebas del repositorio usan datos sintéticos.

## 5. Qué está validado y cómo

Todo cambio pasó por una sesión de QA independiente (agente «Dev QA OCR») **antes** de integrarse, incluida revisión adversarial de lo sensible. Informes anteriores en `qa/`.

| Área | Cómo se validó |
|---|---|
| Motores OCR y pipeline | Pruebas sintéticas con los 3 motores (`scripts/evaluar.py`: CER, exactitud por campo y acierto de clasificación); cédula real (`docs/08`) |
| Autorización por rol | Matriz de roles probada con 40+ casos en vivo (escalada, claves inactivas/regeneradas, `RolMinimoEdicion`, fuga de `api_key`) y test que recorre **todas** las rutas sin clave |
| Acceso público | Ataque en vivo con el interruptor encendido (opt-in, enumeración, límites con hilos reales, 413, archivos hostiles, fuga de datos). Un hallazgo (bomba de píxeles) corregido y re-verificado |
| Consentimiento y purga | Ataque a bypass de consentimiento, roles de `/purga`, integridad con 1200 documentos contra **SQL Server real** (archivos compartidos por hash, FKs, lotes). Un hallazgo (carrera purga/reprocesar → 500) corregido |
| Frontend | Roles contra backend real aislado, accesibilidad básica, que la pantalla pública no envía la API key, mensajes de error legibles |

## 6. Pendiente (en orden aproximado de importancia)

**Antes de abrir el acceso público a gente real:**
1. **Captcha** en `/captura/:codigo`: los límites acotan el abuso pero no lo eliminan (un anónimo con archivos normales puede mantener ocupados los 2 cupos de OCR; cada documento cuesta segundos).
2. **No publicar el puerto 8000** del backend (solo nginx). `PUBLICO_CONFIAR_PROXY=true` toma la IP de `X-Forwarded-For` y un cliente que llegue directo al backend podría falsearla (`docs/05` §5.1). Aplica igual al puerto 8001 del MCP.
3. **Limitador compartido** (Redis) si hay más de un worker o réplica: hoy está en memoria de un proceso.
4. **Retención en respaldos:** la purga no alcanza copias fuera de la aplicación (respaldos de la BD y del volumen de archivos).
5. HTTPS, rotación de claves y revisión legal del texto del aviso de privacidad (`CapturaPublica.tsx`; al cambiarlo sube `AVISO_PRIVACIDAD_VERSION`).

**Mejoras funcionales:**
6. Medición formal de éxito (`docs/08` §6.2) con **más documentos reales etiquetados** y `scripts/evaluar.py`.
7. **Apellido compuesto en la cédula:** el método `ancla` lee una sola línea; en esta cédula los apellidos salen en líneas separadas del OCR. Requiere una regla por zona o un parámetro `lineas_valor`, validado con más de una cédula antes de generalizar.
8. **Reconocimiento de etiquetas con ruido:** en la cédula real la etiqueta «APELLIDOS» no se lee y `apellidos` depende de la segunda opinión de docTR; mejorar lectura/resolución o usar zonas.
9. `nacionalidad` solo reconoce gentilicios de una lista; el sugeridor de plantillas no detecta «Etiqueta Nombre» sin `:` ni dígitos.
10. Tesseract rinde muy por debajo de PaddleOCR/docTR en la prueba sintética: revisar `--psm` y binarización si se usa como motor activo.
11. Rendimiento: una imagen de ~50 MP (se reduce a 20 MP) tarda 10–17 s; bajar `OCR_MEGAPIXELES_PROCESADO` a 12 lo acortaría sin tocar código.
12. Pantallas pendientes de `docs/07` §6: ninguna bloqueante; el permiso de edición del *flujo* (`PATCH /flujos-captura/{id}/permisos`) existe en la API pero no tiene UI.

## 7. Trampas que ya nos mordieron (no las repitas)

- **Endpoints `async` que llaman a código bloqueante** congelan todo el servidor (ni `/salud` responde). El pipeline OCR corre con `run_in_threadpool`; `/salud` no importa `paddleocr` (usa `find_spec`).
- **Modelos OCR descargados en caliente** en el primer request tumbaron el API; ahora van horneados en la imagen y hay un semáforo (`OCR_MAX_CONCURRENTES`), un lock al inicializar motores y un timeout en la segunda opinión.
- **SQLAlchemy `.is_(True)` compila a `IS 1`**, inválido en T-SQL: usar `== True` (`# noqa: E712`).
- **El almacén guarda por hash**: la misma cédula subida dos veces es un solo archivo con dos registros; la purga solo borra el archivo cuando ningún documento lo usa.
- **El ancla ambigua** ("Nombres" dentro de "APELLIDOS Y NOMBRES DEL PADRE") devolvía un valor equivocado con alta confianza y sin aviso: `extractor.py` descarta etiquetas compuestas, y un campo vacío con advertencia es preferible a uno equivocado.
- **Fechas del backend sin zona horaria**: el frontend las interpreta como UTC (`adaptadores.ts`).
- **`/salud` no valida la clave**; para comprobar una clave se llama a un endpoint autenticado (`verificarConexion.ts`).
- **Contrato API ↔ UI:** el backend usa `nombre_archivo`, `recibido_en`, etc. y las advertencias como `codigo:campo`; `frontend/src/api/adaptadores.ts` traduce. Si cambias el backend, cambia el adaptador (hay un test que fija los nombres).
- **`.env.development.local`** (si existe) cambia el modo del dev server a backend real; para no depender de él usa `npm run dev:mock` / `dev:real`.
- Tests que simulan una purga concurrente deben confirmar el borrado en otra conexión (un `rollback` lo deshace) y usar `synchronize_session=False`.

## 8. Dónde mirar

| Tema | Documento / código |
|---|---|
| Arquitectura y contrato JSON | `docs/01`, `docs/02` |
| Por qué PaddleOCR + docTR | `docs/06` |
| Flujos, roles, acceso público, consentimiento, retención | `docs/07` |
| Estado de la PoC y checklist | `docs/08` |
| Guía visual del frontend | `docs/09` y `diseno/maqueta.html` |
| Despliegue y requisitos de producción | `docs/05` |
| Evaluación de motores | `scripts/evaluar.py` |
