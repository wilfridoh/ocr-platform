# 04 — Base de datos: SQL Server

## 1. Alcance

Persistir **plantillas** (qué tipos de documento conoce el sistema y cómo leerlos), **documentos** procesados, sus **resultados** campo por campo, y la **auditoría** del procesamiento. Los archivos binarios (PDF, imágenes) **no** se guardan en la base de datos, sino en el almacén de archivos; la base guarda su ruta y hash.

## 2. Motor y conexión

| Ítem | Valor |
|---|---|
| Motor | SQL Server 2022 (Developer en local, Standard o Azure SQL en nube) |
| Imagen Docker | `mcr.microsoft.com/mssql/server:2022-latest` |
| Base de datos | `ocr` |
| Collation | `Latin1_General_100_CI_AI_SC_UTF8` (insensible a mayúsculas y acentos, soporta UTF-8) |
| Acceso desde backend | SQLAlchemy 2 + pyodbc, ODBC Driver 18 |
| Migraciones | Alembic (versionadas en `backend/alembic/`) |

## 3. Diagrama entidad-relación

```
┌────────────────────┐        ┌────────────────────────┐
│ Plantilla          │1      *│ PlantillaVersion       │
│────────────────────│────────│────────────────────────│
│ PlantillaId (PK)   │        │ PlantillaVersionId(PK) │
│ Codigo (UQ)        │        │ PlantillaId (FK)       │
│ Nombre             │        │ Numero                 │
│ Descripcion        │        │ UmbralConfianza        │
│ Activa             │        │ CreadoEn, CreadoPor    │
│ VersionActualId    │        └─────┬────────────┬─────┘
│ CreadoEn, ActualizadoEn│          │1           │1
└────────────────────┘             *│           *│
                      ┌─────────────┴────┐  ┌────┴──────────────────┐
                      │ PalabraClave     │  │ CampoPlantilla        │
                      │──────────────────│  │───────────────────────│
                      │ PalabraClaveId   │  │ CampoPlantillaId (PK) │
                      │ PlantillaVersionId│ │ PlantillaVersionId(FK)│
                      │ Texto            │  │ Nombre                │
                      │ Peso             │  │ Etiqueta              │
                      └──────────────────┘  │ TipoDato              │
                                            │ Obligatorio           │
                                            │ Metodo (regex/ancla/zona)│
                                            │ ReglaJson             │
                                            │ Orden                 │
                                            └───────────────────────┘

┌────────────────────────┐        ┌──────────────────────────┐
│ Documento              │1      1│ Resultado                │
│────────────────────────│────────│──────────────────────────│
│ DocumentoId (PK, GUID) │        │ ResultadoId (PK)         │
│ NombreArchivo          │        │ DocumentoId (FK, UQ)     │
│ TipoMime               │        │ PlantillaVersionId (FK)  │ ─┐ (null si desconocido)
│ TamanoBytes            │        │ TipoDetectado            │  │
│ HashSha256             │        │ ConfianzaClasificacion   │  │
│ RutaAlmacen            │        │ ConfianzaGlobal          │  │
│ Paginas                │        │ TextoCompleto            │  │
│ Estado                 │        │ PalabrasClaveJson        │  │
│ PlantillaForzadaId     │        │ AlternativasJson         │  │
│ MensajeError           │        │ AdvertenciasJson         │  │
│ RecibidoEn             │        │ TiemposJson              │  │
│ ProcesadoEn            │        │ MotorOcr                 │  │
└───────────┬────────────┘        └────────────┬─────────────┘  │
            │1                                 │1               │
           *│                                 *│                │
┌───────────┴────────────┐        ┌────────────┴─────────────┐  │
│ LogProcesamiento       │        │ CampoExtraido            │  │
│────────────────────────│        │──────────────────────────│  │
│ LogId (PK)             │        │ CampoExtraidoId (PK)     │  │
│ DocumentoId (FK)       │        │ ResultadoId (FK)         │  │
│ Paso                   │        │ CampoPlantillaId (FK)    │ ◄┘
│ Nivel (INFO/WARN/ERROR)│        │ Nombre                   │
│ Mensaje                │        │ ValorTexto               │
│ DuracionMs             │        │ ValorNormalizadoJson     │
│ RegistradoEn           │        │ Confianza                │
└────────────────────────┘        │ Pagina                   │
                                  │ X, Y, Ancho, Alto        │
                                  │ Valido                   │
                                  └──────────────────────────┘
```

## 4. Tablas

### 4.1 `Plantilla`
Un tipo de documento. La definición concreta vive en `PlantillaVersion` para poder editar sin perder cómo se procesaron documentos anteriores.

| Columna | Tipo | Notas |
|---|---|---|
| `PlantillaId` | `INT IDENTITY` PK | |
| `Codigo` | `NVARCHAR(100)` UNIQUE | identificador estable, ej. `planilla_servicio_electrico` |
| `Nombre` | `NVARCHAR(200)` | |
| `Descripcion` | `NVARCHAR(1000)` NULL | |
| `Activa` | `BIT` default 1 | solo las activas participan en la clasificación |
| `VersionActualId` | `INT` NULL FK → `PlantillaVersion` | |
| `CreadoEn` | `DATETIME2` default `SYSUTCDATETIME()` | |
| `ActualizadoEn` | `DATETIME2` | |

### 4.2 `PlantillaVersion`
| Columna | Tipo | Notas |
|---|---|---|
| `PlantillaVersionId` | `INT IDENTITY` PK | |
| `PlantillaId` | `INT` FK | |
| `Numero` | `INT` | 1, 2, 3... único por plantilla |
| `UmbralConfianza` | `DECIMAL(4,3)` default 0.600 | |
| `DocumentoEjemploId` | `UNIQUEIDENTIFIER` NULL FK → `Documento` | documento con el que se creó |
| `CreadoEn`, `CreadoPor` | `DATETIME2`, `NVARCHAR(100)` | |

### 4.3 `PalabraClave`
| Columna | Tipo | Notas |
|---|---|---|
| `PalabraClaveId` | `INT IDENTITY` PK | |
| `PlantillaVersionId` | `INT` FK | |
| `Texto` | `NVARCHAR(200)` | se compara en minúsculas y sin acentos |
| `Peso` | `TINYINT` 1-5 | |

### 4.4 `CampoPlantilla`
| Columna | Tipo | Notas |
|---|---|---|
| `CampoPlantillaId` | `INT IDENTITY` PK | |
| `PlantillaVersionId` | `INT` FK | |
| `Nombre` | `NVARCHAR(100)` | clave en el JSON de salida, ej. `numero_cliente` |
| `Etiqueta` | `NVARCHAR(200)` | texto para la UI |
| `TipoDato` | `NVARCHAR(20)` CHECK en (`texto`,`numero`,`monto`,`fecha`,`rut`,`cedula`,`email`,`telefono`) | |
| `Obligatorio` | `BIT` | |
| `Metodo` | `NVARCHAR(10)` CHECK en (`regex`,`ancla`,`zona`) | |
| `ReglaJson` | `NVARCHAR(MAX)` CHECK `ISJSON(ReglaJson)=1` | parámetros del método |
| `Orden` | `INT` | orden de presentación |

Único: (`PlantillaVersionId`, `Nombre`).

### 4.5 `Documento`
| Columna | Tipo | Notas |
|---|---|---|
| `DocumentoId` | `UNIQUEIDENTIFIER` PK default `NEWSEQUENTIALID()` | se expone en la API |
| `NombreArchivo` | `NVARCHAR(260)` | |
| `TipoMime` | `NVARCHAR(100)` | |
| `TamanoBytes` | `BIGINT` | |
| `HashSha256` | `CHAR(64)` | detectar duplicados |
| `RutaAlmacen` | `NVARCHAR(500)` | ruta relativa en el almacén de archivos |
| `Paginas` | `INT` | |
| `Estado` | `NVARCHAR(20)` CHECK en (`RECIBIDO`,`PROCESANDO`,`COMPLETADO`,`ERROR`) | |
| `PlantillaForzadaId` | `INT` NULL FK → `Plantilla` | si el usuario forzó el tipo |
| `FlujoCapturaId` / `CreadoPorId` | `INT` NULL FK | flujo de captura por el que llegó y usuario que lo subió (docs/07) |
| `ConsentimientoEn` / `AvisoVersion` | `DATETIME2` NULL / `NVARCHAR(20)` NULL | cuándo aceptó la persona el aviso de privacidad (flujo público) y qué versión del aviso; NULL en lo que sube el personal (docs/07 §5.3) |
| `MensajeError` | `NVARCHAR(2000)` NULL | |
| `RecibidoEn` | `DATETIME2` | |
| `ProcesadoEn` | `DATETIME2` NULL | |

### 4.6 `Resultado`
Un registro por documento (el último procesamiento). Al reprocesar se reemplaza; el histórico queda en `LogProcesamiento`.

| Columna | Tipo | Notas |
|---|---|---|
| `ResultadoId` | `BIGINT IDENTITY` PK | |
| `DocumentoId` | `UNIQUEIDENTIFIER` FK UNIQUE | |
| `PlantillaVersionId` | `INT` NULL FK | versión exacta usada; NULL si desconocido |
| `TipoDetectado` | `NVARCHAR(100)` | código de plantilla o `desconocido` |
| `ConfianzaClasificacion` | `DECIMAL(4,3)` | |
| `ConfianzaGlobal` | `DECIMAL(4,3)` | |
| `TextoCompleto` | `NVARCHAR(MAX)` | índice de texto completo (ver §6) |
| `PalabrasClaveJson` | `NVARCHAR(MAX)` | `["dirección","consumo"]` |
| `AlternativasJson` | `NVARCHAR(MAX)` | otras plantillas candidatas |
| `AdvertenciasJson` | `NVARCHAR(MAX)` | |
| `TiemposJson` | `NVARCHAR(MAX)` | ms por etapa |
| `MotorOcr` | `NVARCHAR(30)` | `tesseract-5.3` / `paddle-2.7` / `pdf-nativo` |
| `CreadoEn` | `DATETIME2` | |

### 4.7 `CampoExtraido`
| Columna | Tipo | Notas |
|---|---|---|
| `CampoExtraidoId` | `BIGINT IDENTITY` PK | |
| `ResultadoId` | `BIGINT` FK | |
| `CampoPlantillaId` | `INT` NULL FK | |
| `Nombre` | `NVARCHAR(100)` | copia del nombre, por si la plantilla cambia |
| `ValorTexto` | `NVARCHAR(2000)` NULL | tal como se leyó |
| `ValorNormalizadoJson` | `NVARCHAR(MAX)` NULL | `45320`, `"2026-11-30"` |
| `Confianza` | `DECIMAL(4,3)` | |
| `Pagina` | `INT` NULL | |
| `X`, `Y`, `Ancho`, `Alto` | `DECIMAL(6,5)` NULL | coordenadas relativas 0-1 |
| `Valido` | `BIT` | pasó el validador del tipo de dato |
| `Motor` | `NVARCHAR(20)` NULL | motor OCR que dio la lectura final: `paddle`, `doctr`, `tesseract`, `pdf-nativo` |

### 4.8 `LogProcesamiento`
| Columna | Tipo | Notas |
|---|---|---|
| `LogId` | `BIGINT IDENTITY` PK | |
| `DocumentoId` | `UNIQUEIDENTIFIER` FK | |
| `Paso` | `NVARCHAR(30)` | `ingesta`, `preprocesado`, `ocr`, `clasificacion`, `extraccion`, `validacion` |
| `Nivel` | `NVARCHAR(10)` | `INFO`, `WARN`, `ERROR` |
| `Mensaje` | `NVARCHAR(2000)` | sin contenido del documento |
| `DuracionMs` | `INT` NULL | |
| `RegistradoEn` | `DATETIME2` | |

## 5. Índices

| Tabla | Índice | Para qué |
|---|---|---|
| `Plantilla` | UQ `Codigo`; filtrado `WHERE Activa = 1` | clasificación carga solo activas |
| `PlantillaVersion` | UQ (`PlantillaId`, `Numero`) | |
| `CampoPlantilla` | (`PlantillaVersionId`, `Orden`) | cargar plantilla completa |
| `Documento` | (`Estado`, `RecibidoEn` DESC); (`HashSha256`) | historial y duplicados |
| `Resultado` | (`TipoDetectado`, `CreadoEn` DESC) | filtros del historial |
| `CampoExtraido` | (`ResultadoId`); (`Nombre`, `ValorTexto`) | buscar "todos los documentos del cliente X" |
| `LogProcesamiento` | (`DocumentoId`, `RegistradoEn`) | |

## 6. Búsqueda de texto completo

Se habilita **Full-Text Search** sobre `Resultado.TextoCompleto` para consultas tipo "documentos que mencionan *Av. Siempre Viva*":

```sql
CREATE FULLTEXT CATALOG FtOcr;
CREATE FULLTEXT INDEX ON dbo.Resultado(TextoCompleto LANGUAGE 3082)  -- 3082 = español
    KEY INDEX PK_Resultado ON FtOcr WITH CHANGE_TRACKING AUTO;

-- uso
SELECT d.DocumentoId, d.NombreArchivo
FROM dbo.Resultado r JOIN dbo.Documento d ON d.DocumentoId = r.DocumentoId
WHERE CONTAINS(r.TextoCompleto, '"Siempre Viva"');
```

Nota: la imagen Docker estándar de SQL Server no incluye Full-Text; se usa la variante con `MSSQL_AGENT`/full-text habilitado o se instala el paquete `mssql-server-fts`. Si no está disponible, la búsqueda usa `LIKE` como respaldo.

## 7. Script de creación (resumen)

Se mantiene en `backend/alembic/versions/0001_inicial.py` (generado) y en `db/schema.sql` (legible). Fragmento representativo:

```sql
CREATE TABLE dbo.Plantilla (
    PlantillaId       INT IDENTITY(1,1) CONSTRAINT PK_Plantilla PRIMARY KEY,
    Codigo            NVARCHAR(100) NOT NULL CONSTRAINT UQ_Plantilla_Codigo UNIQUE,
    Nombre            NVARCHAR(200) NOT NULL,
    Descripcion       NVARCHAR(1000) NULL,
    Activa            BIT NOT NULL CONSTRAINT DF_Plantilla_Activa DEFAULT 1,
    VersionActualId   INT NULL,
    CreadoEn          DATETIME2 NOT NULL CONSTRAINT DF_Plantilla_CreadoEn DEFAULT SYSUTCDATETIME(),
    ActualizadoEn     DATETIME2 NOT NULL CONSTRAINT DF_Plantilla_ActualizadoEn DEFAULT SYSUTCDATETIME()
);

CREATE TABLE dbo.Documento (
    DocumentoId        UNIQUEIDENTIFIER NOT NULL CONSTRAINT PK_Documento PRIMARY KEY
                       CONSTRAINT DF_Documento_Id DEFAULT NEWSEQUENTIALID(),
    NombreArchivo      NVARCHAR(260) NOT NULL,
    TipoMime           NVARCHAR(100) NOT NULL,
    TamanoBytes        BIGINT NOT NULL,
    HashSha256         CHAR(64) NOT NULL,
    RutaAlmacen        NVARCHAR(500) NOT NULL,
    Paginas            INT NOT NULL CONSTRAINT DF_Documento_Paginas DEFAULT 0,
    Estado             NVARCHAR(20) NOT NULL
                       CONSTRAINT CK_Documento_Estado CHECK (Estado IN ('RECIBIDO','PROCESANDO','COMPLETADO','ERROR')),
    PlantillaForzadaId INT NULL CONSTRAINT FK_Documento_Plantilla REFERENCES dbo.Plantilla(PlantillaId),
    MensajeError       NVARCHAR(2000) NULL,
    RecibidoEn         DATETIME2 NOT NULL CONSTRAINT DF_Documento_RecibidoEn DEFAULT SYSUTCDATETIME(),
    ProcesadoEn        DATETIME2 NULL
);
CREATE INDEX IX_Documento_Estado_Recibido ON dbo.Documento(Estado, RecibidoEn DESC);
CREATE INDEX IX_Documento_Hash ON dbo.Documento(HashSha256);
```

## 8. Datos semilla

Al crear la base se insertan tres plantillas de ejemplo (`cuenta_contrato`, `planilla_servicio`, `cedula_identidad`) con palabras clave y campos genéricos, para que la plataforma funcione desde el primer arranque. Se ajustan luego con documentos reales desde la UI.

## 9. Consultas frecuentes

```sql
-- Plantillas activas con su versión actual, para el clasificador
SELECT p.PlantillaId, p.Codigo, v.PlantillaVersionId, v.UmbralConfianza
FROM dbo.Plantilla p JOIN dbo.PlantillaVersion v ON v.PlantillaVersionId = p.VersionActualId
WHERE p.Activa = 1;

-- Historial paginado
SELECT d.DocumentoId, d.NombreArchivo, d.Estado, d.RecibidoEn, r.TipoDetectado, r.ConfianzaGlobal
FROM dbo.Documento d LEFT JOIN dbo.Resultado r ON r.DocumentoId = d.DocumentoId
ORDER BY d.RecibidoEn DESC
OFFSET @offset ROWS FETCH NEXT @tamano ROWS ONLY;

-- Todos los documentos de un número de cliente
SELECT d.DocumentoId, d.NombreArchivo, c.ValorTexto
FROM dbo.CampoExtraido c
JOIN dbo.Resultado r ON r.ResultadoId = c.ResultadoId
JOIN dbo.Documento d ON d.DocumentoId = r.DocumentoId
WHERE c.Nombre = 'numero_cliente' AND c.ValorTexto = '1234567-8';

-- Exactitud por plantilla (campos válidos / campos obligatorios)
SELECT r.TipoDetectado, AVG(CAST(c.Valido AS FLOAT)) AS TasaValidos, COUNT(DISTINCT r.ResultadoId) AS Documentos
FROM dbo.Resultado r JOIN dbo.CampoExtraido c ON c.ResultadoId = r.ResultadoId
GROUP BY r.TipoDetectado;
```

## 10. Operación

- **Respaldos**: `BACKUP DATABASE ocr` diario a volumen externo; en nube, respaldo automático de Azure SQL.
- **Retención**: job que borra `LogProcesamiento` > 90 días y, opcionalmente, archivos de documentos > N días según política del cliente.
- **Docker Compose**: servicio `mssql` con volumen `mssql-data`, variable `MSSQL_SA_PASSWORD` desde `.env`, y un contenedor `db-init` que espera a que arranque y ejecuta las migraciones.
