# 07 — Flujos de captura y permisos

> Origen: revisión con Jesús (líder de aplicaciones) sobre el uso funcional real del sistema. Agrega dos conceptos nuevos al diseño original: **flujos de captura** (qué le puede pedir cada pantalla a un usuario final) y **permisos por rol** sobre las plantillas. No reemplaza nada de `docs/01`-`04`; se apoya en ellos.

## 1. El problema que resuelve

Hasta ahora, "Procesar" (`docs/03` §4.1) era una pantalla genérica: el usuario sube cualquier documento y el sistema adivina el tipo entre **todas** las plantillas activas. Eso es correcto para un operador interno que recibe documentos variados, pero no para un caso de uso dirigido: por ejemplo, un formulario de alta de cliente donde **solo** se debe pedir la cédula, o un trámite de servicios básicos donde solo se aceptan planillas de luz/agua/gas.

La idea de Jesús: un administrador **configura de antemano** qué puede solicitar cada punto de captura, y el usuario final ve una experiencia dirigida ("sube tu cédula"), no un cajón genérico. Además, quiere poder **activar/desactivar plantillas** (ya existía) y ahora también **controlar quién puede editarlas** (permisos).

## 2. Concepto nuevo: Flujo de captura

Un **flujo de captura** es un perfil reutilizable que dice: *"para este punto de entrada, solo acepto estos tipos de documento, y al usuario le muestro este texto"*.

```
Flujo de captura: "Alta de cliente — cédula"
  Plantillas permitidas: [cedula_identidad]
  Instrucción al usuario: "Sube o escanea tu cédula de identidad"
  Acepta foto desde cámara: sí
  Acepta PDF: no

Flujo de captura: "Regularización de servicios"
  Plantillas permitidas: [planilla_servicio_electrico, planilla_agua, planilla_gas]
  Instrucción al usuario: "Sube tu última planilla de servicios"
  Acepta foto desde cámara: sí
  Acepta PDF: sí
```

Dentro de un flujo con varias plantillas permitidas, el clasificador sigue decidiendo cuál de ellas aplica (igual que hoy), pero **nunca** elige una plantilla fuera de esa lista. Si ninguna de las permitidas supera el umbral, el resultado es "no coincide con lo esperado en este flujo" (distinto de "desconocido" general: aquí sí sabemos qué se esperaba y no llegó).

Un flujo de captura no reemplaza el modo "Procesar" genérico que ya existe para el operador interno (que sigue viendo todas las plantillas activas); es un **modo adicional**, pensado para incrustar en otro proceso o compartir como link dirigido.

## 3. Concepto nuevo: Permisos por rol

Hasta ahora la API solo tenía una clave única (`X-API-Key`, `docs/02` §3). Eso alcanza para aislar el acceso de afuera, pero no para distinguir "quién puede crear/editar plantillas" de "quién solo sube documentos". Se agrega un modelo mínimo de roles:

| Rol | Puede |
|---|---|
| **Administrador** | Todo: crear/editar/activar plantillas y flujos de captura, ver historial completo, gestionar usuarios |
| **Editor** | Crear y editar plantillas y flujos de captura, pero no gestionar usuarios ni permisos |
| **Operador** | Solo procesar documentos (modo genérico o por flujo) y ver resultados; no puede crear ni editar plantillas |

Cada plantilla (y cada flujo de captura) puede además fijar un **rol mínimo requerido para editarla** (`RolMinimoEdicion`), para casos donde una plantilla sensible (ej. cédula de identidad) solo la pueda tocar un Administrador aunque existan Editores para otras.

Esto es deliberadamente simple: no se diseña aquí un sistema de autenticación completo (login, sesiones, SSO). Cada `X-API-Key` se asocia a **un usuario con un rol**; sigue siendo autenticación por clave, pero ya diferenciada. Si más adelante se necesita login real, este modelo de roles no cambia, solo cambia cómo se identifica al usuario.

## 4. Modelo de datos (ampliación de `docs/04`)

```
┌─────────────────────┐        ┌──────────────────────────────┐
│ Usuario              │1      *│ (FK en Documento.CreadoPorId,│
│──────────────────────│────────│  para auditoría de quién subió)│
│ UsuarioId (PK)       │        └────────────────────────────────┘
│ Nombre               │
│ ApiKeyHash           │
│ Rol  (Administrador/Editor/Operador)
│ Activo               │
│ CreadoEn             │
└──────────────────────┘

┌───────────────────────┐        ┌──────────────────────────────┐
│ FlujoCaptura           │1      *│ FlujoCapturaPlantilla         │
│────────────────────────│────────│────────────────────────────── │
│ FlujoCapturaId (PK)    │        │ FlujoCapturaId (FK)           │
│ Codigo (UQ)            │        │ PlantillaId (FK)              │
│ Nombre                 │        └────────────────────────────── │
│ Instruccion            │
│ AceptaCamara (BIT)     │
│ AceptaPdf (BIT)        │
│ Activo                 │
│ RolMinimoEdicion       │
│ CreadoPorId (FK Usuario)│
│ CreadoEn, ActualizadoEn │
└────────────────────────┘
```

Cambios sobre tablas existentes (`docs/04`):
- `Plantilla`: se agrega `RolMinimoEdicion NVARCHAR(20)` (default `Editor`).
- `Documento`: se agrega `FlujoCapturaId INT NULL FK` (si llegó por un flujo dirigido) y `CreadoPorId INT NULL FK → Usuario`.

Script: `db/schema_flujos_captura.sql` (incremental, no reemplaza `db/schema.sql`). **Implementado** (fase 1) y verificado contra SQL Server en una instalación nueva y en una BD con datos; `aplicar.ps1`/`aplicar.sh` lo ejecutan entre `schema.sql` y `seed.sql`.

Decisiones de implementación (fase 1):
- `Usuario.ApiKeyHash` guarda el **SHA-256 en hexadecimal** (CHAR(64)) de la clave; la clave en claro se muestra una sola vez al crearla. Las claves son aleatorias de alta entropía, por lo que un hash rápido es suficiente (no hace falta bcrypt).
- `Documento.Estado` admite el valor persistido **`NO_COINCIDE`** (flujo dirigido donde ninguna plantilla permitida supera el umbral), para poder filtrarlo en el historial; el `CHECK` se amplía en la migración.
- La clave única del entorno (`API_KEY`) sigue funcionando como **Administrador del sistema** sin fila en `Usuario` (así no se rompe ningún despliegue existente); `CreadoPorId` queda `NULL` para ella.
- `seed.sql` agrega dos flujos de ejemplo (`alta_cliente_cedula`, `regularizacion_servicios`).

## 5. API (ampliación de `docs/02`)

| Método | Ruta | Rol mínimo | Descripción |
|---|---|---|---|
| `GET` | `/flujos-captura` | Operador | Lista flujos activos (lo que ve el selector en "Procesar") |
| `GET` | `/flujos-captura/{codigo}` | Operador | Detalle: instrucción, plantillas permitidas, si acepta cámara/PDF |
| `POST` | `/flujos-captura` | Editor | Crea flujo |
| `PUT` | `/flujos-captura/{id}` | Editor | Edita |
| `PATCH` | `/flujos-captura/{id}/estado` | Editor | Activa/desactiva |
| `POST` | `/flujos-captura/{codigo}/documentos` | Operador | Variante de `POST /documentos`: procesa, pero solo clasifica contra las plantillas del flujo; si ninguna aplica devuelve `estado=NO_COINCIDE` en vez de `desconocido` |
| `PATCH` | `/plantillas/{id}/permisos` | Administrador | Fija `RolMinimoEdicion` |
| `POST` | `/usuarios` | Administrador | Crea usuario con rol y genera su API key |
| `PATCH` | `/usuarios/{id}` | Administrador | Cambia rol o activa/desactiva |

Toda ruta de escritura sobre plantillas o flujos ahora valida el rol del usuario asociado a la `X-API-Key`, no solo que la clave sea válida.

### 5.1 Implementación (fase 2) — detalles y decisiones

- **Identidad:** `X-API-Key` → (1) coincide con la `API_KEY` del entorno = *Administrador del sistema* (sin fila de usuario; `CreadoPorId` = NULL); (2) su SHA-256 coincide con un `Usuario` activo; si no, **401** (también para un usuario inactivo). Un rol insuficiente da **403**.
- **Matriz de roles:** lectura (listar/obtener plantillas, flujos activos, documentos, resultados) y procesar documentos = *Operador*; crear/editar/activar plantillas, sugerir/probar/reprocesar plantilla y crear/editar/activar flujos = *Editor*; `PATCH …/permisos` y `/usuarios` = *Administrador*.
- **`RolMinimoEdicion`:** al editar o activar/desactivar una plantilla (o flujo) se exige el **mayor** entre *Editor* y el `RolMinimoEdicion` del recurso. `GET /plantillas` devuelve `rol_minimo_edicion` a todos; la UI solo lo muestra/edita al Administrador.
- **Rutas añadidas respecto a la tabla de arriba:** `GET /usuarios` (listado), `POST /usuarios/{id}/clave` (regenera la API key; la anterior deja de valer y la nueva se muestra una sola vez), `PATCH /flujos-captura/{id}/permisos` (Administrador) y `GET /flujos-captura?todos=true` (Editor o superior: incluye inactivos para el administrador de flujos; un Operador solo ve activos y recibe 404 en un flujo inactivo).
- **Protección contra bloqueo:** un usuario no puede desactivarse ni quitarse el rol de Administrador a sí mismo (400).
- **`POST /flujos-captura/{codigo}/documentos`:** clasifica solo entre las plantillas activas del flujo; si ninguna supera el umbral el documento queda en estado **`NO_COINCIDE`** (se guarda, con el flujo y el usuario que lo subió). Reprocesarlo mantiene la restricción. Un flujo con `AceptaPdf = 0` rechaza PDF con 400 en el servidor; **`AceptaCamara` es solo una indicación para la UI** (el servidor no puede distinguir una foto de cámara de un archivo elegido).
- **Trazabilidad:** `POST /documentos` también registra `CreadoPorId` (si la clave pertenece a un usuario).

### 5.2 Acceso público a un flujo (sin API key) — única excepción de la API

> **Estado: FASE 4, implementada pero APAGADA.** Está detrás del interruptor global `PUBLICO_HABILITADO` (por defecto `false`). Apagado, no existe el modo anónimo: las dos rutas de abajo exigen clave como el resto de la API y `PATCH …/acceso-publico` responde 409. Solo se enciende (`PUBLICO_HABILITADO=true`) cuando Dev QA OCR cierre su propio ciclo de revisión adversarial de esta fase.

Decisión del usuario: el punto de captura (`/procesar/{codigo}`) es **público**: un cliente externo sube su cédula desde un link, sin cuenta. Como abre una superficie sin autenticar, está acotada así:

| Protección | Detalle |
|---|---|
| **Opt-in por flujo** | `FlujoCaptura.AccesoPublico` (por defecto **0**). Solo un flujo **activo** con `AccesoPublico = 1` acepta subidas sin clave. Lo cambia únicamente un **Administrador** (`PATCH /flujos-captura/{id}/acceso-publico`); un Editor no puede abrirlo ni editando el flujo. Cada activación queda en el log del servidor. |
| **Solo dos rutas** | `GET /flujos-captura/{codigo}/publico` (instrucción y formatos aceptados; sin plantillas ni ids) y `POST /flujos-captura/{codigo}/documentos`. Todo lo demás exige clave; `tests/test_acceso_publico.py::test_ninguna_ruta_queda_sin_proteger` recorre **todas** las rutas de la app sin clave y falla si alguna distinta de `/salud` y estas dos responde algo que no sea 401. |
| **Sin enumeración** | Flujo inexistente, inactivo o no público responden 404 con el mismo mensaje. Una clave inválida en estas rutas es 401 (nunca se trata como anónimo). |
| **Límite por IP** | Ventana deslizante de 60 s en memoria: `PUBLICO_LIMITE_IP_POR_MINUTO` (10) para subir y `PUBLICO_LIMITE_INFO_POR_MINUTO` (60) para el GET. Cuentan también los intentos contra flujos inexistentes. Exceso → **429** con `Retry-After`. |
| **Límite global** | `PUBLICO_LIMITE_GLOBAL_POR_MINUTO` (60) para todas las subidas anónimas juntas (protege aunque el atacante cambie de IP). |
| **Tope de concurrencia** | `PUBLICO_MAX_CONCURRENTES` (2) procesamientos públicos a la vez; el resto → **503** con `Retry-After`. El OCR es lo caro y no debe acapararlo una avalancha anónima. |
| **Tamaño y formato** | Tope propio `PUBLICO_MAX_TAMANO_MB` (10; se aplica el menor con `MAX_TAMANO_MB`) porque cada subida se guarda en disco. Se rechaza por `Content-Length` **antes** de leer el cuerpo (413), y la lectura por bloques corta igualmente sin `Content-Length`; nginx fija `client_max_body_size 25m`. Siguen aplicando tipo de archivo y `AceptaPdf` del flujo (400). |
| **Bomba de píxeles** | Hallazgo de QA: un PNG de ~250 KB que decodifica a 9000×9000 px (81 MP) ocupaba un cupo ~50 s. La ingesta (`ingesta.py`, para **toda** subida, con clave o sin ella) lee solo la cabecera y rechaza con 400 lo que supere `OCR_MAX_MEGAPIXELES` (50) **antes de decodificar**; lo grande pero legítimo (foto de celular de 24 MP) se reduce a `OCR_MEGAPIXELES_PROCESADO` (20); PDF/TIFF se limitan a `OCR_MAX_PAGINAS` (30) y una página de PDF con MediaBox gigante se renderiza a resolución acotada. |
| **Respuesta reducida** | A un anónimo se le devuelve solo `documento_id`, `estado`, tipo y confianza de la clasificación, `campos` (valor y confianza), `advertencias` y `confianza_global`: **sin** texto OCR completo, tiempos, palabras clave ni páginas. El resultado completo y el archivo siguen exigiendo clave. Los errores 500 no exponen el detalle interno. |
| **Auditoría** | `CreadoPorId` queda NULL y se escribe en `LogProcesamiento` (paso `acceso`) una línea `Origen: PÚBLICO sin usuario identificado (flujo X, huella IP abc123…)`; lo que sube personal interno dice `Origen: usuario #N Rol` o `clave del sistema`. La IP se guarda solo como **huella** (SHA-256 con sal, 12 caracteres): permite correlacionar abusos sin conservar la IP. |

**IP real detrás del proxy:** con `PUBLICO_CONFIAR_PROXY=true` (así lo deja `docker-compose.yml`) se usa la **última** entrada de `X-Forwarded-For` (la que agrega nginx; las anteriores las puede escribir el cliente). Sin esa opción se usa la IP de la conexión (detrás de nginx serían todos "la misma IP"). Es seguro solo si el backend **no** es alcanzable directamente desde internet: en producción no publiques el puerto 8000; si lo estuviera, un cliente podría falsear su IP, aunque el límite global y el de concurrencia seguirían protegiendo.

**Retención y consentimiento:** resueltos en §5.3 (el aviso de privacidad con consentimiento obligatorio y la purga de documentos).

**Limitaciones conocidas (aceptables en esta fase; revisar antes de producción abierta):**
- El limitador está en **memoria de un proceso**: con varios workers o réplicas cada uno lleva su propia cuenta. Habría que moverlo a un almacén compartido (Redis).
- No hay **captcha** ni verificación de que el archivo sea realmente un documento: un anónimo puede gastar OCR (acotado por los topes) y ocupar disco hasta 10 MB por subida y 60 por minuto. La retención está resuelta en §5.3.
- Los datos extraídos de una cédula son personales y se devuelven al anónimo que subió el archivo; el `documento_id` es un UUID no enumerable, pero conviene no mostrarlo ni conservarlo en la pantalla pública.

### 5.3 Aviso de privacidad, consentimiento y retención de documentos

Se van a juntar cédulas reales de varias personas para pruebas, así que hay una política única para **todo** documento (no una por origen).

**Aviso y consentimiento (pantalla pública `/captura/:codigo`):**
- Antes de poder subir, la persona ve «Antes de subir tu documento: este documento se procesa para leer sus datos automáticamente; se usa solo para esta prueba y se elimina pasados *N* días; no se comparte con terceros» y debe marcar «Entiendo y autorizo el uso de mi documento para esta prueba». Hasta marcarla, «Usar cámara» y «Elegir archivo» están deshabilitados (y un archivo inyectado a mano también se ignora). *N* sale del servidor (`GET …/publico` → `retencion_dias`), así que el texto siempre dice lo que de verdad se hace; con retención 0 dice «se conserva hasta que el administrador lo elimine».
- **El servidor lo exige**: `POST …/documentos` sin clave rechaza con 400 si falta `consentimiento=true` o si `aviso_version` no es la vigente (`AVISO_PRIVACIDAD_VERSION`: se sube cuando cambia el texto, y una pantalla vieja no vale como consentimiento). No se lee ni un byte del archivo antes.
- **Constancia:** el propio registro del documento guarda `ConsentimientoEn` (UTC) y `AvisoVersion`, y el log de auditoría añade «consentimiento al aviso de privacidad vN, retención M días». Lo que sube el personal con clave no exige ni registra consentimiento.
- El texto del aviso vive en la pantalla (`CapturaPublica.tsx`); si se modifica, hay que subir `AVISO_PRIVACIDAD_VERSION`.

**Retención y purga (`DOC_RETENCION_DIAS`, por defecto 30; 0 = sin caducidad automática):**
- **Qué se borra** de un documento: su registro, su resultado (campos extraídos), su log de procesamiento y el archivo original. Las plantillas y flujos no se tocan; si una plantilla usaba el documento como ejemplo, esa referencia pasa a NULL.
- **Archivos compartidos:** el almacén guarda por hash (la misma cédula subida dos veces es un solo archivo con dos registros). El archivo solo se borra cuando ya ningún documento que se conserva lo usa.
- **Automática:** un hilo del propio backend (`purga_automatica.py`, sin scheduler externo) purga los vencidos 60 s después de arrancar y luego cada `DOC_PURGA_INTERVALO_HORAS` (24). Apagada por defecto en el código (para no borrar bases de desarrollo por sorpresa); `docker-compose.yml` la enciende (`DOC_PURGA_AUTOMATICA=true`). Un fallo se registra y se reintenta en el siguiente ciclo. Con varias réplicas cada una purgaría: es idempotente.
- **Manual (solo Administrador):** `GET /api/purga` (política vigente y cuánto se eliminaría, sin borrar) y `POST /api/purga` con `{"alcance": "vencidos" | "todos", "confirmar": true}` (irreversible: sin `confirmar` es 400; «vencidos» con retención 0 es 400). En la UI: Documentos → «Retención y purga»; «Eliminar TODOS» sirve para limpiar tras una tanda de pruebas y pide escribir ELIMINAR. Cada purga queda en el log del servidor con el usuario.
- **Se aplica a todo** documento por su fecha de recepción (`RecibidoEn`), venga de donde venga.
- **Límites conocidos:** la purga no toca copias fuera de la aplicación (respaldos de la BD, del volumen `archivos-data` o del contenedor): hay que cubrirlos en la política de respaldos. Una subida idéntica concurrente con la purga del mismo archivo puede, con una probabilidad muy baja, dejar un registro sin archivo (queda un error legible al abrirlo).

## 6. UI (ampliación de `docs/03`)

### 6.1 "Procesar" con flujo dirigido

Nueva variante de la pantalla, accesible por link directo (`/procesar/{codigo-flujo}`) o embebible como componente:

```
┌──────────────────────────────────────────────┐
│  Sube tu cédula de identidad                   │  ← instrucción del flujo
│                                                │
│  ┌──────────────────────────┐                 │
│  │   📷  Usar cámara         │                 │
│  │   📁  Elegir archivo      │                 │
│  └──────────────────────────┘                 │
│  Formatos aceptados: JPG, PNG                   │
└──────────────────────────────────────────────┘
```

Sin selector de tipo, sin ver otras plantillas: el usuario final no necesita saber qué es una "plantilla". El modo "Procesar" genérico (`/`, con selector "Detectar automático") se mantiene para el operador interno.

### 6.2 Administrador de flujos de captura (`/flujos-captura`)

Mismo patrón que el administrador de plantillas: lista, crear, editar, activar/desactivar. Al crear uno, se eligen las plantillas permitidas de una lista (checkboxes) y se escribe la instrucción para el usuario final.

### 6.2.1 Pantalla pública `/captura/:codigo` y acceso público (fase 4, UI)

Para una persona externa que llega desde un enlace, sin cuenta. **No es** la pantalla `/procesar/:codigo` (esa es interna, con clave y dentro del menú).

- **Sin sesión:** está fuera del layout interno (sin menú, fondo en degradado, columna de 460 px, tarjeta de radio 16). Solo llama a `GET /flujos-captura/{codigo}/publico` y `POST /flujos-captura/{codigo}/documentos`, con un cliente que **nunca adjunta `X-API-Key`** (ni siquiera si el navegador tiene una guardada) y `credentials: 'omit'`. Verificado en el navegador: con una clave guardada, la página hace una sola petición, sin la cabecera, y no carga `/yo` ni `/salud`.
- **Qué ve:** la instrucción del flujo, «Usar cámara» (si el flujo la acepta) y «Elegir archivo»; luego «Recibimos tu documento» con los datos leídos (rótulo legible + valor, y «Revísalo» si la confianza es baja o el valor falta), o «Este documento no es el que se esperaba» si el estado es `NO_COINCIDE`. No se muestra el id del documento ni enlaces internos.
- **Errores en lenguaje llano:** 400 (el motivo del servidor: PDF no aceptado, imagen demasiado grande…), 401/404 («este punto de captura no está disponible»), 413 («archivo demasiado pesado»), 429 («demasiados intentos; espera N segundos», con el `Retry-After`), 503 («servicio ocupado»), sin conexión y error genérico.
- **Interruptor «Acceso público»** en el editor de un flujo (`/flujos-captura/:id`): solo lo ve un **Administrador** y solo si el servidor tiene `PUBLICO_HABILITADO=true` (`GET /yo` informa `publico_habilitado`). Pide confirmación al abrir, muestra el enlace para compartir (`/captura/{codigo}`) y la lista de flujos marca con «Público» los abiertos. Si el flujo está inactivo avisa que el enlace no funcionará.
- La respuesta reducida del servidor incluye por campo `valor`, `confianza` y `etiqueta` (el rótulo de la plantilla, p. ej. «Número de cliente»).

### 6.3 Plantillas: permisos

En `/plantillas/:id`, nueva sección "Permisos": selector de `RolMinimoEdicion` (Administrador/Editor/Operador). Solo un Administrador ve y puede cambiar este campo.

### 6.4 Gestión de usuarios (`/usuarios`, solo Administrador)

Lista de usuarios con su rol, estado activo/inactivo, y botón para generar una nueva API key (se muestra una sola vez al crearla).

## 7. Impacto en lo ya construido

- **No rompe nada existente.** El modo "Procesar" genérico y el administrador de plantillas siguen funcionando igual; esto se agrega encima.
- **Backend:** nuevas tablas, endpoints y una dependencia de autorización por rol sobre las rutas de escritura ya existentes (`crear_plantilla`, `actualizar_plantilla`, etc.). El pipeline de OCR (PaddleOCR/docTR/Tesseract, `docs/06`) no cambia.
- **Frontend:** nueva pantalla "Procesar con flujo", nuevo administrador de flujos, nueva sección de permisos y pantalla de usuarios.
- **Base de datos:** script incremental sobre lo que ya entregó el agente de BD.

## 8. Siguiente paso

Esto queda documentado como la **siguiente iteración** (no se re-abre lo ya construido y verificado del backend). Al retomar, el orden sugerido es: 1) tabla `Usuario` y roles, 2) endpoints de flujos de captura, 3) UI de flujos y permisos.
