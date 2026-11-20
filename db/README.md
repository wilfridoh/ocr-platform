# `db/` — Base de datos SQL Server

Scripts T-SQL para crear y poblar la base `ocr` que usa el backend (OCR
Platform). El modelo de datos completo y su justificación están en
[`../docs/04-base-de-datos.md`](../docs/04-base-de-datos.md); este directorio
es la implementación ejecutable de ese contrato. **No modifiques nombres de
tabla/columna sin actualizar ese documento y los modelos SQLAlchemy del
backend** (`backend/`), que asumen exactamente esos nombres.

## Contenido

| Archivo | Qué hace |
|---|---|
| `schema.sql` | Crea la base `ocr` (collation `Latin1_General_100_CI_AI_SC_UTF8`) y las 8 tablas: `Plantilla`, `PlantillaVersion`, `PalabraClave`, `CampoPlantilla`, `Documento`, `Resultado`, `CampoExtraido`, `LogProcesamiento`, con PK/FK/CHECK/DEFAULT/UNIQUE e índices. Idempotente (usa `IF NOT EXISTS`). Agrega al final el índice Full-Text sobre `Resultado.TextoCompleto`, si el servicio Full-Text está instalado; si no, imprime un aviso y se omite (la búsqueda cae a `LIKE`). |
| `seed.sql` | Inserta 3 plantillas de ejemplo (`cuenta_contrato`, `planilla_servicio`, `cedula_identidad`) con su versión 1, palabras clave ponderadas (1-5) y campos con reglas `regex`/`ancla`/`zona` en `ReglaJson`. Idempotente. |
| `vistas.sql` | Vistas de consulta: `vw_PlantillaActual`, `vw_HistorialDocumentos`, `vw_ExactitudPorPlantilla`. Usa `CREATE OR ALTER` (idempotente). |
| `migracion_001_variantes_palabras_clave.sql` | Para BD ya sembradas: actualiza las palabras clave de la v1 de las 3 plantillas semilla al formato con variantes `a\|b\|c` (idempotente; no toca filas ya migradas o editadas). `seed.sql` ya trae el formato nuevo para instalaciones limpias. Se aplica a mano: `sqlcmd -S ... -C -d <bd> -i migracion_001_variantes_palabras_clave.sql`. |
| `schema_flujos_captura.sql` | Ampliación incremental de docs/07: tablas `Usuario`, `FlujoCaptura`, `FlujoCapturaPlantilla`; columnas `Plantilla.RolMinimoEdicion`, `Documento.FlujoCapturaId/CreadoPorId`; y `Documento.Estado` admite `NO_COINCIDE`. Incluye `FlujoCaptura.AccesoPublico` (por defecto 0: el flujo exige API key; solo un Administrador lo abre al público). Idempotente y segura sobre una BD viva (no toca datos); si ya se aplicó una versión anterior, volver a ejecutarlo solo agrega las columnas que faltan. Para una BD existente basta con aplicar solo este archivo: `sqlcmd -S ... -C -b -I -f 65001 -i schema_flujos_captura.sql`. |
| `aplicar.ps1` | Aplica los 3 scripts en orden con `sqlcmd`, en Windows/PowerShell. |
| `aplicar.sh` | Equivalente para Linux/contenedor `db-init`. |

## Cómo aplicar

### Windows (PowerShell)

```powershell
cd C:\OCR\db
.\aplicar.ps1 -Servidor "localhost,1433" -Usuario sa -Password "<tu_password>"
```

Parámetros: `-Servidor` (default `localhost,1433`), `-Usuario` (default `sa`),
`-Password` (obligatorio). Usa `sqlcmd` del PATH o, si no está,
`C:\Program Files\Microsoft SQL Server\Client SDK\ODBC\170\Tools\Binn\SQLCMD.EXE`.
Se conecta con `-C` (confía en el certificado del servidor, útil en local/dev).

### Linux / contenedor `db-init`

```bash
./aplicar.sh -S localhost,1433 -U sa -P "<tu_password>"
# o con variables de entorno:
DB_SERVIDOR=mssql,1433 DB_USUARIO=sa DB_PASSWORD="<tu_password>" ./aplicar.sh
```

Usa `/opt/mssql-tools18/bin/sqlcmd` (o `/opt/mssql-tools/bin/sqlcmd`, o el que
esté en PATH).

### Manual (sqlcmd directo)

```bash
sqlcmd -S localhost,1433 -U sa -P "<password>" -C -i schema.sql
sqlcmd -S localhost,1433 -U sa -P "<password>" -C -i seed.sql
sqlcmd -S localhost,1433 -U sa -P "<password>" -C -i vistas.sql
```

Los tres scripts son idempotentes: se pueden ejecutar varias veces sin
duplicar datos ni fallar por objetos existentes.

## Diagrama ER resumido

```
Plantilla 1──* PlantillaVersion 1──* PalabraClave
    │                  │
    │                  └──* CampoPlantilla
    │ (VersionActualId → PlantillaVersion, FK agregada con ALTER)
    │
Documento 1──1 Resultado 1──* CampoExtraido ──FK opcional──> CampoPlantilla
    │                  (PlantillaVersionId FK opcional)
    └──* LogProcesamiento
```

Ver el diagrama completo y la descripción de cada columna en
`../docs/04-base-de-datos.md` (secciones 3 y 4).

## Convenciones de nombres

- Esquema `dbo`, tablas y columnas en `PascalCase` (español), exactamente como
  en `docs/04-base-de-datos.md` — es el contrato con los modelos SQLAlchemy
  del backend.
- Constraints con prefijo por tipo: `PK_`, `FK_`, `UQ_`, `CK_`, `DF_`, `IX_`,
  seguido de `Tabla` y, si aplica, `Columna`.
- Claves primarias: `IDENTITY` para tablas de catálogo/auditoría (`INT`/`BIGINT`),
  `UNIQUEIDENTIFIER DEFAULT NEWSEQUENTIALID()` para `Documento` (se expone en
  la API).
- Fechas en `DATETIME2`, UTC, con default `SYSUTCDATETIME()`.
- Campos de configuración variable (reglas de extracción, JSON de resultado)
  en `NVARCHAR(MAX)` con `CHECK (ISJSON(...) = 1)` cuando deben ser JSON válido.
- `Codigo` de `Plantilla` es el identificador estable usado en la API y en
  `Resultado.TipoDetectado` (ej. `planilla_servicio`, `desconocido`).

## Verificación

Este directorio se verificó levantando una instancia temporal de SQL Server
en Docker (`mcr.microsoft.com/mssql/server:2022-latest`) y ejecutando
`aplicar.ps1` dos veces para confirmar la idempotencia. Ver el reporte de la
tarea para el detalle de la corrida (o reprodúcelo localmente con los
comandos de la sección "Cómo aplicar").
