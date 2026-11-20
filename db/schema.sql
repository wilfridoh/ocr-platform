/* ============================================================================
   OCR Platform — schema.sql
   Script T-SQL idempotente: crea la base `ocr` y todas las tablas descritas
   en docs/04-base-de-datos.md. Nombres de tabla/columna EXACTOS al documento
   (contrato con el backend / SQLAlchemy).
   Ejecutar con sqlcmd. Seguro de re-ejecutar.
   ============================================================================ */

SET NOCOUNT ON;
GO

/* ----------------------------------------------------------------------
   1. Base de datos
   ---------------------------------------------------------------------- */
IF NOT EXISTS (SELECT 1 FROM sys.databases WHERE name = N'ocr')
BEGIN
    PRINT 'Creando base de datos ocr...';
    EXEC('CREATE DATABASE ocr COLLATE Latin1_General_100_CI_AI_SC_UTF8');
END
ELSE
BEGIN
    PRINT 'La base de datos ocr ya existe.';
END
GO

USE ocr;
GO

/* ----------------------------------------------------------------------
   2. Plantilla
   ---------------------------------------------------------------------- */
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'Plantilla' AND schema_id = SCHEMA_ID('dbo'))
BEGIN
    CREATE TABLE dbo.Plantilla (
        PlantillaId       INT IDENTITY(1,1) CONSTRAINT PK_Plantilla PRIMARY KEY,
        Codigo            NVARCHAR(100)  NOT NULL CONSTRAINT UQ_Plantilla_Codigo UNIQUE,
        Nombre            NVARCHAR(200)  NOT NULL,
        Descripcion       NVARCHAR(1000) NULL,
        Activa            BIT NOT NULL CONSTRAINT DF_Plantilla_Activa DEFAULT 1,
        VersionActualId   INT NULL,
        CreadoEn          DATETIME2 NOT NULL CONSTRAINT DF_Plantilla_CreadoEn DEFAULT SYSUTCDATETIME(),
        ActualizadoEn     DATETIME2 NOT NULL CONSTRAINT DF_Plantilla_ActualizadoEn DEFAULT SYSUTCDATETIME()
    );
    PRINT 'Tabla dbo.Plantilla creada.';
END
ELSE
BEGIN
    PRINT 'Tabla dbo.Plantilla ya existe.';
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_Plantilla_Activa' AND object_id = OBJECT_ID('dbo.Plantilla'))
BEGIN
    CREATE INDEX IX_Plantilla_Activa ON dbo.Plantilla(Activa) WHERE Activa = 1;
END
GO

/* ----------------------------------------------------------------------
   3. PlantillaVersion
   ---------------------------------------------------------------------- */
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'PlantillaVersion' AND schema_id = SCHEMA_ID('dbo'))
BEGIN
    CREATE TABLE dbo.PlantillaVersion (
        PlantillaVersionId  INT IDENTITY(1,1) CONSTRAINT PK_PlantillaVersion PRIMARY KEY,
        PlantillaId         INT NOT NULL CONSTRAINT FK_PlantillaVersion_Plantilla REFERENCES dbo.Plantilla(PlantillaId),
        Numero              INT NOT NULL,
        UmbralConfianza     DECIMAL(4,3) NOT NULL CONSTRAINT DF_PlantillaVersion_Umbral DEFAULT 0.600,
        DocumentoEjemploId  UNIQUEIDENTIFIER NULL,
        CreadoEn            DATETIME2 NOT NULL CONSTRAINT DF_PlantillaVersion_CreadoEn DEFAULT SYSUTCDATETIME(),
        CreadoPor           NVARCHAR(100) NULL,
        CONSTRAINT UQ_PlantillaVersion_Plantilla_Numero UNIQUE (PlantillaId, Numero)
    );
    PRINT 'Tabla dbo.PlantillaVersion creada.';
END
ELSE
BEGIN
    PRINT 'Tabla dbo.PlantillaVersion ya existe.';
END
GO

/* ----------------------------------------------------------------------
   4. PalabraClave
   ---------------------------------------------------------------------- */
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'PalabraClave' AND schema_id = SCHEMA_ID('dbo'))
BEGIN
    CREATE TABLE dbo.PalabraClave (
        PalabraClaveId      INT IDENTITY(1,1) CONSTRAINT PK_PalabraClave PRIMARY KEY,
        PlantillaVersionId  INT NOT NULL CONSTRAINT FK_PalabraClave_PlantillaVersion REFERENCES dbo.PlantillaVersion(PlantillaVersionId),
        Texto               NVARCHAR(200) NOT NULL,
        Peso                TINYINT NOT NULL CONSTRAINT CK_PalabraClave_Peso CHECK (Peso BETWEEN 1 AND 5)
    );
    PRINT 'Tabla dbo.PalabraClave creada.';
END
ELSE
BEGIN
    PRINT 'Tabla dbo.PalabraClave ya existe.';
END
GO

/* ----------------------------------------------------------------------
   5. CampoPlantilla
   ---------------------------------------------------------------------- */
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'CampoPlantilla' AND schema_id = SCHEMA_ID('dbo'))
BEGIN
    CREATE TABLE dbo.CampoPlantilla (
        CampoPlantillaId    INT IDENTITY(1,1) CONSTRAINT PK_CampoPlantilla PRIMARY KEY,
        PlantillaVersionId  INT NOT NULL CONSTRAINT FK_CampoPlantilla_PlantillaVersion REFERENCES dbo.PlantillaVersion(PlantillaVersionId),
        Nombre              NVARCHAR(100) NOT NULL,
        Etiqueta            NVARCHAR(200) NOT NULL,
        TipoDato            NVARCHAR(20) NOT NULL
                             CONSTRAINT CK_CampoPlantilla_TipoDato CHECK (TipoDato IN ('texto','numero','monto','fecha','rut','cedula','email','telefono')),
        Obligatorio         BIT NOT NULL CONSTRAINT DF_CampoPlantilla_Obligatorio DEFAULT 0,
        Metodo              NVARCHAR(10) NOT NULL
                             CONSTRAINT CK_CampoPlantilla_Metodo CHECK (Metodo IN ('regex','ancla','zona')),
        ReglaJson           NVARCHAR(MAX) NOT NULL
                             CONSTRAINT CK_CampoPlantilla_ReglaJson CHECK (ISJSON(ReglaJson) = 1),
        Orden               INT NOT NULL CONSTRAINT DF_CampoPlantilla_Orden DEFAULT 0,
        CONSTRAINT UQ_CampoPlantilla_Version_Nombre UNIQUE (PlantillaVersionId, Nombre)
    );
    PRINT 'Tabla dbo.CampoPlantilla creada.';
END
ELSE
BEGIN
    PRINT 'Tabla dbo.CampoPlantilla ya existe.';
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_CampoPlantilla_Version_Orden' AND object_id = OBJECT_ID('dbo.CampoPlantilla'))
BEGIN
    CREATE INDEX IX_CampoPlantilla_Version_Orden ON dbo.CampoPlantilla(PlantillaVersionId, Orden);
END
GO

/* ----------------------------------------------------------------------
   6. Documento
   ---------------------------------------------------------------------- */
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'Documento' AND schema_id = SCHEMA_ID('dbo'))
BEGIN
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
                           CONSTRAINT CK_Documento_Estado CHECK (Estado IN ('RECIBIDO','PROCESANDO','COMPLETADO','ERROR','NO_COINCIDE')),
        PlantillaForzadaId INT NULL CONSTRAINT FK_Documento_Plantilla REFERENCES dbo.Plantilla(PlantillaId),
        MensajeError       NVARCHAR(2000) NULL,
        RecibidoEn         DATETIME2 NOT NULL CONSTRAINT DF_Documento_RecibidoEn DEFAULT SYSUTCDATETIME(),
        ProcesadoEn        DATETIME2 NULL
    );
    PRINT 'Tabla dbo.Documento creada.';
END
ELSE
BEGIN
    PRINT 'Tabla dbo.Documento ya existe.';
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_Documento_Estado_Recibido' AND object_id = OBJECT_ID('dbo.Documento'))
BEGIN
    CREATE INDEX IX_Documento_Estado_Recibido ON dbo.Documento(Estado, RecibidoEn DESC);
END
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_Documento_Hash' AND object_id = OBJECT_ID('dbo.Documento'))
BEGIN
    CREATE INDEX IX_Documento_Hash ON dbo.Documento(HashSha256);
END
GO

/* ----------------------------------------------------------------------
   7. FK circular Plantilla.VersionActualId -> PlantillaVersion
      (se agrega ahora que ambas tablas existen)
   ---------------------------------------------------------------------- */
IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name = 'FK_Plantilla_VersionActual')
BEGIN
    ALTER TABLE dbo.Plantilla
        ADD CONSTRAINT FK_Plantilla_VersionActual
        FOREIGN KEY (VersionActualId) REFERENCES dbo.PlantillaVersion(PlantillaVersionId);
    PRINT 'FK FK_Plantilla_VersionActual agregada.';
END
GO

/* También la FK de PlantillaVersion.DocumentoEjemploId -> Documento (opcional, documentada en 4.2) */
IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name = 'FK_PlantillaVersion_DocumentoEjemplo')
BEGIN
    ALTER TABLE dbo.PlantillaVersion
        ADD CONSTRAINT FK_PlantillaVersion_DocumentoEjemplo
        FOREIGN KEY (DocumentoEjemploId) REFERENCES dbo.Documento(DocumentoId);
    PRINT 'FK FK_PlantillaVersion_DocumentoEjemplo agregada.';
END
GO

/* ----------------------------------------------------------------------
   8. Resultado
   ---------------------------------------------------------------------- */
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'Resultado' AND schema_id = SCHEMA_ID('dbo'))
BEGIN
    CREATE TABLE dbo.Resultado (
        ResultadoId             BIGINT IDENTITY(1,1) CONSTRAINT PK_Resultado PRIMARY KEY,
        DocumentoId             UNIQUEIDENTIFIER NOT NULL
                                CONSTRAINT FK_Resultado_Documento REFERENCES dbo.Documento(DocumentoId),
        PlantillaVersionId      INT NULL
                                CONSTRAINT FK_Resultado_PlantillaVersion REFERENCES dbo.PlantillaVersion(PlantillaVersionId),
        TipoDetectado           NVARCHAR(100) NOT NULL,
        ConfianzaClasificacion  DECIMAL(4,3) NOT NULL,
        ConfianzaGlobal         DECIMAL(4,3) NOT NULL,
        TextoCompleto           NVARCHAR(MAX) NULL,
        PalabrasClaveJson       NVARCHAR(MAX) NULL,
        AlternativasJson        NVARCHAR(MAX) NULL,
        AdvertenciasJson        NVARCHAR(MAX) NULL,
        TiemposJson             NVARCHAR(MAX) NULL,
        MotorOcr                NVARCHAR(30) NULL,
        -- posicion de las palabras y datos del recorte (docs/13 1.3; en BD existentes: migracion_009)
        PalabrasJson            NVARCHAR(MAX) NULL CONSTRAINT CK_Resultado_PalabrasJson CHECK (PalabrasJson IS NULL OR ISJSON(PalabrasJson) = 1),
        RecorteJson             NVARCHAR(MAX) NULL CONSTRAINT CK_Resultado_RecorteJson CHECK (RecorteJson IS NULL OR ISJSON(RecorteJson) = 1),
        CreadoEn                DATETIME2 NOT NULL CONSTRAINT DF_Resultado_CreadoEn DEFAULT SYSUTCDATETIME(),
        CONSTRAINT UQ_Resultado_Documento UNIQUE (DocumentoId)
    );
    PRINT 'Tabla dbo.Resultado creada.';
END
ELSE
BEGIN
    PRINT 'Tabla dbo.Resultado ya existe.';
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_Resultado_Tipo_Creado' AND object_id = OBJECT_ID('dbo.Resultado'))
BEGIN
    CREATE INDEX IX_Resultado_Tipo_Creado ON dbo.Resultado(TipoDetectado, CreadoEn DESC);
END
GO

/* ----------------------------------------------------------------------
   9. CampoExtraido
   ---------------------------------------------------------------------- */
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'CampoExtraido' AND schema_id = SCHEMA_ID('dbo'))
BEGIN
    CREATE TABLE dbo.CampoExtraido (
        CampoExtraidoId       BIGINT IDENTITY(1,1) CONSTRAINT PK_CampoExtraido PRIMARY KEY,
        ResultadoId           BIGINT NOT NULL
                              CONSTRAINT FK_CampoExtraido_Resultado REFERENCES dbo.Resultado(ResultadoId),
        CampoPlantillaId      INT NULL
                              CONSTRAINT FK_CampoExtraido_CampoPlantilla REFERENCES dbo.CampoPlantilla(CampoPlantillaId),
        Nombre                NVARCHAR(100) NOT NULL,
        ValorTexto            NVARCHAR(2000) NULL,
        ValorNormalizadoJson  NVARCHAR(MAX) NULL,
        Confianza             DECIMAL(4,3) NOT NULL,
        Pagina                INT NULL,
        X                     DECIMAL(6,5) NULL,
        Y                     DECIMAL(6,5) NULL,
        Ancho                 DECIMAL(6,5) NULL,
        Alto                  DECIMAL(6,5) NULL,
        Valido                BIT NOT NULL CONSTRAINT DF_CampoExtraido_Valido DEFAULT 0,
        Motor                 NVARCHAR(20) NULL
    );
    PRINT 'Tabla dbo.CampoExtraido creada.';
END
ELSE
BEGIN
    PRINT 'Tabla dbo.CampoExtraido ya existe.';
END
GO

/* Migración idempotente: motor OCR que dio cada campo (paddle/doctr/tesseract/pdf-nativo). */
IF COL_LENGTH('dbo.CampoExtraido', 'Motor') IS NULL
BEGIN
    ALTER TABLE dbo.CampoExtraido ADD Motor NVARCHAR(20) NULL;
    PRINT 'Columna dbo.CampoExtraido.Motor agregada.';
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_CampoExtraido_Resultado' AND object_id = OBJECT_ID('dbo.CampoExtraido'))
BEGIN
    CREATE INDEX IX_CampoExtraido_Resultado ON dbo.CampoExtraido(ResultadoId);
END
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_CampoExtraido_Nombre_Valor' AND object_id = OBJECT_ID('dbo.CampoExtraido'))
BEGIN
    CREATE INDEX IX_CampoExtraido_Nombre_Valor ON dbo.CampoExtraido(Nombre, ValorTexto);
END
GO

/* ----------------------------------------------------------------------
   10. LogProcesamiento
   ---------------------------------------------------------------------- */
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'LogProcesamiento' AND schema_id = SCHEMA_ID('dbo'))
BEGIN
    CREATE TABLE dbo.LogProcesamiento (
        LogId          BIGINT IDENTITY(1,1) CONSTRAINT PK_LogProcesamiento PRIMARY KEY,
        DocumentoId    UNIQUEIDENTIFIER NOT NULL
                       CONSTRAINT FK_LogProcesamiento_Documento REFERENCES dbo.Documento(DocumentoId),
        Paso           NVARCHAR(30) NOT NULL,
        Nivel          NVARCHAR(10) NOT NULL
                       CONSTRAINT CK_LogProcesamiento_Nivel CHECK (Nivel IN ('INFO','WARN','ERROR')),
        Mensaje        NVARCHAR(2000) NOT NULL,
        DuracionMs     INT NULL,
        RegistradoEn   DATETIME2 NOT NULL CONSTRAINT DF_LogProcesamiento_RegistradoEn DEFAULT SYSUTCDATETIME()
    );
    PRINT 'Tabla dbo.LogProcesamiento creada.';
END
ELSE
BEGIN
    PRINT 'Tabla dbo.LogProcesamiento ya existe.';
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_LogProcesamiento_Documento_Registrado' AND object_id = OBJECT_ID('dbo.LogProcesamiento'))
BEGIN
    CREATE INDEX IX_LogProcesamiento_Documento_Registrado ON dbo.LogProcesamiento(DocumentoId, RegistradoEn);
END
GO

/* ----------------------------------------------------------------------
   11. Full-Text Search sobre Resultado.TextoCompleto (sección 6 del doc)
       Se omite con un PRINT si el servicio Full-Text no está instalado.
   ---------------------------------------------------------------------- */
IF (SELECT ISNULL(FULLTEXTSERVICEPROPERTY('IsFullTextInstalled'), 0)) = 1
BEGIN
    IF NOT EXISTS (SELECT 1 FROM sys.fulltext_catalogs WHERE name = 'FtOcr')
    BEGIN
        EXEC('CREATE FULLTEXT CATALOG FtOcr');
        PRINT 'Catálogo FtOcr creado.';
    END

    IF NOT EXISTS (
        SELECT 1 FROM sys.fulltext_indexes fi
        WHERE fi.object_id = OBJECT_ID('dbo.Resultado')
    )
    BEGIN
        EXEC('CREATE FULLTEXT INDEX ON dbo.Resultado(TextoCompleto LANGUAGE 3082)
              KEY INDEX PK_Resultado ON FtOcr WITH CHANGE_TRACKING AUTO');
        PRINT 'Índice Full-Text creado en dbo.Resultado(TextoCompleto).';
    END
    ELSE
    BEGIN
        PRINT 'Índice Full-Text en dbo.Resultado ya existe.';
    END
END
ELSE
BEGIN
    PRINT 'Full-Text Search no está instalado en esta instancia: se omite el índice full-text (la búsqueda usará LIKE como respaldo, según docs/04-base-de-datos.md §6).';
END
GO

PRINT 'schema.sql aplicado correctamente.';
GO
