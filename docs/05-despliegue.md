# 05 — Despliegue

> Cómo levantar la plataforma OCR en local con Docker Compose, cómo conectarse a la base de datos y al servidor MCP, cómo llevarla a la nube, y resolución de problemas frecuentes.

## 1. Requisitos

| Requisito | Detalle |
|---|---|
| Docker Desktop | Windows 11 + WSL2, con el motor Linux habilitado. Probado con Docker 29 / Compose v2 (`docker compose`, sin guion) |
| RAM disponible para Docker | Mínimo 4 GB asignados (SQL Server por sí solo pide ~2 GB) |
| Espacio en disco | ~6 GB para las imágenes (`mssql/server` pesa ~2.3 GB) más el volumen de datos |
| Puertos libres en el host | 1433 (SQL Server), 8000 (API), 8001 (MCP), 3000 (frontend) — todos configurables en `.env` |
| PowerShell | 5.1 (los scripts en `scripts\` usan sintaxis compatible, sin `&&`/`||`) |

Los `Dockerfile` de `backend/` y `frontend/` y los scripts `db/*.sql` / `db/aplicar.sh` los construyen los agentes de backend, frontend y base de datos respectivamente (ver §7 "Supuestos"). Este documento asume que existen con los contratos descritos en `docs/02-backend.md`, `docs/03-frontend.md` y `docs/04-base-de-datos.md`.

## 2. Levantar todo en local

```powershell
cd C:\OCR
.\scripts\levantar.ps1
```

Qué hace:
1. Verifica que Docker responda.
2. Si no existe `.env`, lo crea copiando `.env.example` (valores de desarrollo, no usar en producción).
3. Avisa si algún puerto configurado ya está ocupado (no lo bloquea: puede ser un contenedor propio de una corrida anterior).
4. `docker compose up -d --build`.
5. Espera a que `GET http://localhost:8000/api/salud` responda `200` (hasta 240 s por defecto).
6. Imprime las URLs y la API key de desarrollo.

Parámetros útiles:
```powershell
.\scripts\levantar.ps1 -SinBuild                 # no reconstruye imágenes
.\scripts\levantar.ps1 -Servicios mssql,db-init   # solo esos servicios
```

Otros scripts:
```powershell
.\scripts\logs.ps1                 # logs de todos los servicios, en vivo
.\scripts\logs.ps1 backend         # logs solo del backend
.\scripts\logs.ps1 db-init -SinSeguir   # imprime y sale, no sigue
.\scripts\bajar.ps1                # docker compose down (conserva datos)
.\scripts\bajar.ps1 -BorrarDatos   # down -v (borra BD y archivos), pide confirmación
.\scripts\reiniciar-bd.ps1          # baja, borra solo el volumen de SQL Server, vuelve a levantar
.\scripts\reiniciar-bd.ps1 -BorrarArchivos  # además borra los archivos subidos
```

### Orden de arranque

```
mssql (healthy) ──► db-init (aplica db/aplicar.sh, corre una vez) ──► backend (healthy) ──► mcp
                                                                                  └────────► frontend
```

`db-init` usa la imagen de `mssql/server` (ya trae `sqlcmd`) solo como cliente: monta `./db` de solo lectura, normaliza los finales de línea (por si el repo se clonó en Windows con CRLF) y ejecuta `db/aplicar.sh mssql sa <MSSQL_SA_PASSWORD>`. El backend no arranca hasta que `db-init` termina con éxito (`service_completed_successfully`).

## 3. Conectarse a la base de datos

Con la plataforma arriba, SQL Server queda expuesto en el host en el puerto `MSSQL_PUERTO_HOST` (por defecto `1433`; si ese puerto ya lo usa otra instancia en la máquina, cambiarlo en `.env`, por ejemplo a `14330`, y volver a levantar).

**SQL Server Management Studio (SSMS)**
- Servidor: `localhost,1433` (o el puerto que se configuró)
- Autenticación: SQL Server
- Usuario: `sa`
- Contraseña: valor de `MSSQL_SA_PASSWORD` en `.env`
- Marcar **"Trust server certificate"** (o "Confiar en el certificado del servidor") en la pestaña de conexión, porque el contenedor usa un certificado autofirmado.

**Azure Data Studio**
- Server: `localhost,1433`
- Authentication type: SQL Login
- User / Password: igual que arriba
- En "Advanced", poner `Trust server certificate = True`.

**Desde línea de comandos (dentro del contenedor, sin exponer puerto)**
```powershell
docker exec -it ocr-mssql /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P "Ocr_Dev_2026!" -C -d ocr -Q "SELECT name FROM sys.tables"
```

## 4. Conectar un cliente MCP

El servidor MCP vive en la misma imagen del backend (`python -m mcp_server.server`), y soporta dos transportes (ver `docs/02-backend.md` §6):

### 4.1 Por stdio, desde Claude Desktop o Claude Code (local, sin Docker)

Requiere tener el backend accesible (por ejemplo, levantado con `docker compose up -d backend` y expuesto en `localhost:8000`) y el entorno Python del backend instalado localmente, o ejecutar el comando dentro del contenedor.

Configuración de ejemplo (`claude_desktop_config.json` o el archivo de configuración MCP de Claude Code):
```json
{
  "mcpServers": {
    "ocr-platform": {
      "command": "python",
      "args": ["-m", "mcp_server.server"],
      "env": {
        "OCR_API_URL": "http://localhost:8000/api",
        "OCR_API_KEY": "clave-dev-cambiar"
      }
    }
  }
}
```
Si no se quiere instalar el entorno Python en el host, se puede ejecutar el mismo comando dentro del contenedor del backend:
```json
{
  "mcpServers": {
    "ocr-platform": {
      "command": "docker",
      "args": ["exec", "-i", "ocr-backend", "python", "-m", "mcp_server.server"]
    }
  }
}
```
(en este segundo caso las variables `OCR_API_URL`/`OCR_API_KEY` ya están definidas dentro del contenedor backend vía `.env`).

### 4.2 Por HTTP, contra el contenedor `mcp`

El servicio `mcp` del Compose arranca el mismo servidor con `MCP_TRANSPORT=http` en el puerto `8001` (host `MCP_PUERTO_HOST`, por defecto `8001`).

```json
{
  "mcpServers": {
    "ocr-platform": {
      "url": "http://localhost:8001/mcp"
    }
  }
}
```
**Supuesto a confirmar**: se asume que `mcp_server/server.py` lee `MCP_TRANSPORT`, `MCP_HOST` y `MCP_PORT` (o equivalentes) para decidir el transporte `streamable-http` y el puerto de escucha, y que expone el endpoint en la ruta `/mcp`. Si el agente de backend usa otros nombres de variable o otra ruta, ajustar el servicio `mcp` en `docker-compose.yml` y esta sección.

## 5. Pasar a la nube (sugerido: Azure Container Apps + Azure SQL)

Camino sugerido, sin cambiar la arquitectura ni el código de la aplicación:

| Pieza local | Equivalente en nube |
|---|---|
| Contenedor `mssql` | **Azure SQL Database** (o Managed Instance si se necesita paridad total con SQL Server on-prem, por ejemplo Full-Text Search con configuración particular) |
| Contenedor `db-init` | Un **job** (Azure Container Apps Job, o un paso de pipeline CI/CD) que corre `db/aplicar.sh` una vez contra la cadena de conexión de Azure SQL |
| Contenedor `backend` | **Azure Container App** (o Azure App Service for Containers) construido desde `backend/Dockerfile`, mismas variables de entorno |
| Contenedor `mcp` | Otra **Container App** desde la misma imagen de backend, con `MCP_TRANSPORT=http`, expuesta con su propio *ingress* (idealmente detrás de autenticación/Front Door) |
| Contenedor `frontend` | **Azure Static Web Apps** o Container App con el mismo `frontend/Dockerfile`; el proxy `/api` de Nginx debe apuntar al nombre público del backend |
| Volumen `archivos-data` | **Azure Files** montado en la Container App, o migrar `ALMACEN_RUTA` a **Azure Blob Storage** (requiere que el backend soporte ese backend de almacenamiento; ver `docs/02-backend.md`) |
| `.env` | **Secretos** en Azure Container Apps / Key Vault, nunca el archivo `.env` de desarrollo |

### Qué cambia
- `DATABASE_URL` pasa a usar el host de Azure SQL y, normalmente, autenticación por `Azure AD` o usuario SQL dedicado (no `sa`). Ejemplo: `mssql+pyodbc://usuario:clave@servidor.database.windows.net:1433/ocr?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes&TrustServerCertificate=no`.
- `TrustServerCertificate` pasa de `yes` (certificado autofirmado del contenedor local) a `no` (Azure SQL tiene certificado válido).
- Los contenedores ya no comparten una red Docker local: cada servicio necesita su propia URL pública o reglas de red privada (VNet) entre las Container Apps.
- El healthcheck de `/api/salud` se reutiliza igual como *liveness probe* de la Container App.
- Las imágenes se publican en un registro (Azure Container Registry) en vez de construirse localmente.

### Qué NO cambia
- El código de la aplicación (backend, frontend, MCP) y sus `Dockerfile`.
- El contrato de variables de entorno (`DATABASE_URL`, `API_KEY`, `OCR_*`, `ALMACEN_RUTA`, etc.).
- El esquema de base de datos (`db/schema.sql`, `db/vistas.sql`) y los datos semilla, salvo ajustar el `CREATE FULLTEXT ...` si la variante de Azure SQL elegida no lo soporta igual (ver `docs/04-base-de-datos.md` §6).
- El formato de salida JSON ni las herramientas MCP.

## 5.1 Requisitos de producción (seguridad)

Lo que `docker-compose.yml` deja cómodo para desarrollo **no es válido tal cual en producción**:

- **No publiques el puerto 8000 del backend.** Hoy `docker-compose.yml` lo mapea al host (`8000:8000`) para poder probar con `curl`/Swagger. En producción solo debe ser alcanzable el **frontend/nginx**, que reenvía `/api/` por la red interna de Docker. Motivo: el acceso público a flujos de captura (`docs/07` §5.2, fase 4) usa `PUBLICO_CONFIAR_PROXY=true`, que toma la IP real de la **última** entrada de `X-Forwarded-For` (la que agrega nginx). Si el backend es alcanzable directamente, un cliente puede falsear esa cabecera y esquivar el límite por IP (siguen protegiendo el límite global y el tope de concurrencia, pero ya no es un límite por cliente). Basta con quitar la línea `ports:` del servicio `backend` (y dejar `expose: 8000`).
- **`PUBLICO_HABILITADO` debe seguir en `false`** hasta que la fase 4 (acceso público sin API key) haya pasado su revisión adversarial y se hayan resuelto sus pendientes: política de retención de datos personales, captcha y, si hay varias réplicas, un limitador compartido (Redis). Ver `docs/07` §5.2.
- Cambia `API_KEY` y `MSSQL_SA_PASSWORD` (los valores de `.env.example` son de ejemplo), y sirve el sitio detrás de HTTPS.
- El servidor MCP (puerto 8001) también publica su puerto al host en desarrollo; aplica el mismo criterio.

## 6. Resolución de problemas frecuentes

### Puerto 1433 ocupado
Síntoma: `docker compose up` falla con `Bind for 0.0.0.0:1433 failed: port is already allocated` (frecuente si ya hay otra instancia de SQL Server, local o de otro proyecto, escuchando en ese puerto).

Solución: cambiar `MSSQL_PUERTO_HOST` en `.env` a un puerto libre (por ejemplo `14330`) y volver a levantar. El servicio interno sigue llamándose `mssql` y escuchando en `1433` **dentro** de la red de Docker, así que `DATABASE_URL` no cambia (el backend se conecta por el puerto interno, no por el del host).

```powershell
(Get-Content .env) -replace '^MSSQL_PUERTO_HOST=.*', 'MSSQL_PUERTO_HOST=14330' | Set-Content .env
.\scripts\levantar.ps1
```

### Docker Desktop apagado
Síntoma: cualquier comando `docker` responde `error during connect ... open //./pipe/dockerDesktopLinuxEngine` o `the docker API ... check if the daemon is running`.

Solución: abrir Docker Desktop manualmente (ícono de la bandeja, o buscar "Docker Desktop" en el menú de inicio) y esperar a que el ícono deje de animarse (estado "Engine running"). Si no está anclado, su ejecutable típicamente vive en `C:\Program Files\Docker\Docker\Docker Desktop.exe`, o bajo `%LOCALAPPDATA%\Programs\DockerDesktop\Docker Desktop.exe` en instalaciones por usuario. Reintentar `docker version` cada 10 s hasta un par de minutos: el motor puede tardar en responder justo después de iniciar.

### Contraseña SA inválida
Síntoma: `mssql` arranca y luego se reinicia en bucle, o el log muestra `Password validation failed` / `Login failed for user 'sa'`.

Causa: SQL Server exige que `MSSQL_SA_PASSWORD` tenga al menos 8 caracteres e incluya mayúscula, minúscula, dígito y símbolo (por ejemplo `Ocr_Dev_2026!`, el valor por defecto de `.env.example`).

Solución: ajustar `MSSQL_SA_PASSWORD` en `.env` para que cumpla la política, borrar el volumen si ya se había inicializado con una contraseña distinta (`.\scripts\reiniciar-bd.ps1`) y volver a levantar. Si la contraseña incluye caracteres como `@ : / ? #`, evitarlos o definir `DATABASE_URL` completa a mano en `.env`, porque el compose la inserta sin codificar al construir la cadena de conexión por defecto.

### Healthcheck fallando
Síntoma: `docker compose ps` muestra `mssql` o `backend` como `unhealthy`, o `levantar.ps1` se queda esperando y nunca ve `/api/salud` en 200.

Pasos:
1. Ver logs del servicio con problema: `.\scripts\logs.ps1 mssql` o `.\scripts\logs.ps1 backend`.
2. Para `mssql`: suele ser contraseña inválida (ver arriba) o falta de memoria asignada a Docker Desktop (subir el límite de RAM en la configuración de Docker Desktop, SQL Server necesita al menos ~2 GB).
3. Para `backend`: revisar que `db-init` haya terminado con éxito (`docker compose ps db-init` debe mostrar `Exited (0)`); si `db-init` falló, el backend nunca arranca (`condition: service_completed_successfully`). Ver sus logs con `.\scripts\logs.ps1 db-init -SinSeguir`.
4. Confirmar que el contenedor relevante tenga la variable `MSSQL_SA_PASSWORD`/`DATABASE_URL` correcta: `docker exec ocr-backend printenv DATABASE_URL`.
5. Como último recurso, reiniciar desde cero la base: `.\scripts\reiniciar-bd.ps1`.

## 7. Supuestos sobre los otros componentes (a confirmar al integrar)

Estos supuestos se tomaron porque `backend/`, `frontend/` y `db/` los construyen otros agentes en paralelo y, al momento de escribir este documento, pueden no existir todavía. `docker-compose.yml` se escribió para que coincida con los contratos descritos en `docs/02-backend.md`, `docs/03-frontend.md` y `docs/04-base-de-datos.md`; si la implementación final difiere, ajustar el Compose en los puntos marcados:

1. **`db/aplicar.sh`** acepta los argumentos posicionales `<servidor> <usuario> <password>` (así lo invoca el servicio `db-init`: `aplicar.sh mssql sa "$MSSQL_SA_PASSWORD"`). Si en cambio solo lee variables de entorno (`DB_SERVIDOR`, `DB_USUARIO`, `DB_PASSWORD`, ya pasadas igualmente al contenedor `db-init`), el script debería funcionar igual sin cambios; si usa otros nombres de variable o un orden de parámetros distinto, ajustar el `command` del servicio `db-init`.
2. **`db-init`** asume que `aplicar.sh` usa `/opt/mssql-tools18/bin/sqlcmd -C` (certificado no verificado) y que es idempotente o seguro de correr una sola vez por despliegue; no se reintenta automáticamente si falla a mitad de camino.
3. **`backend/Dockerfile`** expone el puerto `8000` y el `CMD`/entrypoint de la imagen permite sobrescribir el comando de arranque (el Compose fija explícitamente `uvicorn app.main:app --host 0.0.0.0 --port 8000` para el servicio `backend` y `python -m mcp_server.server` para `mcp`, reutilizando la misma imagen).
4. **Servidor MCP HTTP**: se asume que lee `MCP_TRANSPORT=http`, y variables `MCP_HOST`/`MCP_PORT` (o que por defecto escucha en `0.0.0.0:8001`), expuesto en la ruta `/mcp`. Si el SDK `FastMCP` usado expone otras variables o rutas, ajustar el servicio `mcp`.
5. **`GET /api/salud`** devuelve `200` cuando la API y la conexión a SQL Server están sanas (así lo usa el healthcheck de `backend` y `scripts\levantar.ps1`). Si además valida Tesseract y eso puede fallar en el primer arranque (instalación de paquetes de idioma, por ejemplo), el healthcheck podría tardar más que el `start_period` configurado (30 s) — ajustar si es necesario.
6. **`frontend/Dockerfile`** produce una imagen Nginx en el puerto `80` cuyo `nginx.conf` hace proxy de `/api/` al host `backend` (nombre del servicio en la red de Docker, no `localhost`). Esto requiere que `frontend` y `backend` compartan red, lo cual ya está dado por la red única `ocr-red` del Compose.
7. **Variable `ALMACEN_RUTA`**: se fija a `/data/archivos` dentro del contenedor backend (coincide con el volumen `archivos-data` montado en esa ruta). Si el backend espera otra ruta por defecto, ajustar el volumen o la variable.
8. **Collation / Full-Text Search**: se asume que la imagen estándar `mcr.microsoft.com/mssql/server:2022-latest` es suficiente para el schema inicial; si `db/schema.sql` incluye `CREATE FULLTEXT ...` (ver `docs/04-base-de-datos.md` §6) y la imagen no lo soporta, `db-init` fallará en ese paso — confirmar si se necesita la variante con Full-Text habilitado o si el backend cae a `LIKE` como respaldo.
9. **Nombres de servicio**: `mssql`, `backend`, `mcp`, `frontend`, `db-init` son los nombres usados en esta infraestructura; si otro agente los referencia por otro nombre de host (por ejemplo en `nginx.conf` o en algún `docker-compose.override.yml`), deben coincidir exactamente para que la resolución DNS interna de Docker funcione.
