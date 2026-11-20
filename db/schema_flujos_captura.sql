/* ============================================================================
   OCR Platform — schema_flujos_captura.sql
   Ampliacion INCREMENTAL de db/schema.sql para docs/07-flujos-captura-y-permisos.md:
     - dbo.Usuario                 (API key por usuario + rol)
     - dbo.FlujoCaptura            (perfil de captura dirigida)
     - dbo.FlujoCapturaPlantilla   (plantillas permitidas por flujo, M:N)
     - dbo.FlujoCaptura.AccesoPublico (opt-in: el flujo acepta subidas sin API key)
     - dbo.Documento.ConsentimientoEn / AvisoVersion (constancia del consentimiento de privacidad)
     - dbo.Plantilla.RolMinimoEdicion
     - dbo.Documento.FlujoCapturaId / CreadoPorId
     - dbo.Documento.Estado admite 'NO_COINCIDE' (flujo dirigido sin plantilla aplicable)

   IDEMPOTENTE: seguro de re-ejecutar y de aplicar sobre una BD ya viva (con documentos
   reales): solo agrega objetos que faltan; no modifica ni borra datos existentes.
   Orden de aplicacion: schema.sql -> schema_flujos_captura.sql -> seed.sql -> vistas.sql
   (aplicar.ps1 / aplicar.sh ya lo hacen). Para una BD existente basta con este archivo:
       sqlcmd -S <srv> -U sa -P <pwd> -C -b -I -f 65001 -i schema_flujos_captura.sql
   ============================================================================ */

SET NOCOUNT ON;
GO

USE ocr;
GO

/* ----------------------------------------------------------------------
   1. Usuario
      ApiKeyHash = SHA-256 (hex, 64 caracteres) de la API key. La clave en claro se muestra
      una sola vez al crearla y NO se guarda. La clave unica del entorno (API_KEY) sigue
      valiendo como Administrador del sistema sin necesitar una fila aqui.
   ---------------------------------------------------------------------- */
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'Usuario' AND schema_id = SCHEMA_ID('dbo'))
BEGIN
    CREATE TABLE dbo.Usuario (
        UsuarioId   INT IDENTITY(1,1) CONSTRAINT PK_Usuario PRIMARY KEY,
        Nombre      NVARCHAR(200) NOT NULL,
        ApiKeyHash  CHAR(64) NOT NULL CONSTRAINT UQ_Usuario_ApiKeyHash UNIQUE,
        Rol         NVARCHAR(20) NOT NULL
                    CONSTRAINT CK_Usuario_Rol CHECK (Rol IN ('Administrador','Editor','Operador')),
        Activo      BIT NOT NULL CONSTRAINT DF_Usuario_Activo DEFAULT 1,
        CreadoEn    DATETIME2 NOT NULL CONSTRAINT DF_Usuario_CreadoEn DEFAULT SYSUTCDATETIME()
    );
    PRINT 'Tabla dbo.Usuario creada.';
END
ELSE
BEGIN
    PRINT 'Tabla dbo.Usuario ya existe.';
END
GO

/* ----------------------------------------------------------------------
   2. FlujoCaptura
   ---------------------------------------------------------------------- */
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'FlujoCaptura' AND schema_id = SCHEMA_ID('dbo'))
BEGIN
    CREATE TABLE dbo.FlujoCaptura (
        FlujoCapturaId    INT IDENTITY(1,1) CONSTRAINT PK_FlujoCaptura PRIMARY KEY,
        Codigo            NVARCHAR(100) NOT NULL CONSTRAINT UQ_FlujoCaptura_Codigo UNIQUE,
        Nombre            NVARCHAR(200) NOT NULL,
        Instruccion       NVARCHAR(500) NULL,
        AceptaCamara      BIT NOT NULL CONSTRAINT DF_FlujoCaptura_AceptaCamara DEFAULT 1,
        AceptaPdf         BIT NOT NULL CONSTRAINT DF_FlujoCaptura_AceptaPdf DEFAULT 1,
        Activo            BIT NOT NULL CONSTRAINT DF_FlujoCaptura_Activo DEFAULT 1,
        RolMinimoEdicion  NVARCHAR(20) NOT NULL CONSTRAINT DF_FlujoCaptura_RolMinimoEdicion DEFAULT 'Editor'
                          CONSTRAINT CK_FlujoCaptura_RolMinimoEdicion CHECK (RolMinimoEdicion IN ('Administrador','Editor','Operador')),
        CreadoPorId       INT NULL CONSTRAINT FK_FlujoCaptura_Usuario REFERENCES dbo.Usuario(UsuarioId),
        CreadoEn          DATETIME2 NOT NULL CONSTRAINT DF_FlujoCaptura_CreadoEn DEFAULT SYSUTCDATETIME(),
        ActualizadoEn     DATETIME2 NOT NULL CONSTRAINT DF_FlujoCaptura_ActualizadoEn DEFAULT SYSUTCDATETIME()
    );
    PRINT 'Tabla dbo.FlujoCaptura creada.';
END
ELSE
BEGIN
    PRINT 'Tabla dbo.FlujoCaptura ya existe.';
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_FlujoCaptura_Activo' AND object_id = OBJECT_ID('dbo.FlujoCaptura'))
BEGIN
    CREATE INDEX IX_FlujoCaptura_Activo ON dbo.FlujoCaptura(Activo) WHERE Activo = 1;
END
GO

/* ----------------------------------------------------------------------
   3. FlujoCapturaPlantilla (M:N)
   ---------------------------------------------------------------------- */
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'FlujoCapturaPlantilla' AND schema_id = SCHEMA_ID('dbo'))
BEGIN
    CREATE TABLE dbo.FlujoCapturaPlantilla (
        FlujoCapturaId  INT NOT NULL CONSTRAINT FK_FlujoCapturaPlantilla_Flujo REFERENCES dbo.FlujoCaptura(FlujoCapturaId),
        PlantillaId     INT NOT NULL CONSTRAINT FK_FlujoCapturaPlantilla_Plantilla REFERENCES dbo.Plantilla(PlantillaId),
        CONSTRAINT PK_FlujoCapturaPlantilla PRIMARY KEY (FlujoCapturaId, PlantillaId)
    );
    PRINT 'Tabla dbo.FlujoCapturaPlantilla creada.';
END
ELSE
BEGIN
    PRINT 'Tabla dbo.FlujoCapturaPlantilla ya existe.';
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_FlujoCapturaPlantilla_Plantilla' AND object_id = OBJECT_ID('dbo.FlujoCapturaPlantilla'))
BEGIN
    CREATE INDEX IX_FlujoCapturaPlantilla_Plantilla ON dbo.FlujoCapturaPlantilla(PlantillaId);
END
GO

/* ----------------------------------------------------------------------
   4. Plantilla.RolMinimoEdicion  (filas existentes quedan en 'Editor')
   ---------------------------------------------------------------------- */
IF COL_LENGTH('dbo.Plantilla', 'RolMinimoEdicion') IS NULL
BEGIN
    ALTER TABLE dbo.Plantilla
        ADD RolMinimoEdicion NVARCHAR(20) NOT NULL CONSTRAINT DF_Plantilla_RolMinimoEdicion DEFAULT 'Editor';
    PRINT 'Columna dbo.Plantilla.RolMinimoEdicion agregada.';
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.check_constraints WHERE name = 'CK_Plantilla_RolMinimoEdicion' AND parent_object_id = OBJECT_ID('dbo.Plantilla'))
BEGIN
    ALTER TABLE dbo.Plantilla
        ADD CONSTRAINT CK_Plantilla_RolMinimoEdicion CHECK (RolMinimoEdicion IN ('Administrador','Editor','Operador'));
END
GO

/* ----------------------------------------------------------------------
   5. Documento.FlujoCapturaId / CreadoPorId  (NULL en los documentos existentes)
   ---------------------------------------------------------------------- */
IF COL_LENGTH('dbo.Documento', 'FlujoCapturaId') IS NULL
BEGIN
    ALTER TABLE dbo.Documento
        ADD FlujoCapturaId INT NULL CONSTRAINT FK_Documento_FlujoCaptura REFERENCES dbo.FlujoCaptura(FlujoCapturaId);
    PRINT 'Columna dbo.Documento.FlujoCapturaId agregada.';
END
GO

IF COL_LENGTH('dbo.Documento', 'CreadoPorId') IS NULL
BEGIN
    ALTER TABLE dbo.Documento
        ADD CreadoPorId INT NULL CONSTRAINT FK_Documento_Usuario REFERENCES dbo.Usuario(UsuarioId);
    PRINT 'Columna dbo.Documento.CreadoPorId agregada.';
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_Documento_FlujoCaptura' AND object_id = OBJECT_ID('dbo.Documento'))
BEGIN
    CREATE INDEX IX_Documento_FlujoCaptura ON dbo.Documento(FlujoCapturaId) WHERE FlujoCapturaId IS NOT NULL;
END
GO

/* ----------------------------------------------------------------------
   6. Documento.Estado admite 'NO_COINCIDE' (se recrea el CHECK solo si aun no lo incluye)
   ---------------------------------------------------------------------- */
IF EXISTS (SELECT 1 FROM sys.check_constraints
           WHERE name = 'CK_Documento_Estado' AND parent_object_id = OBJECT_ID('dbo.Documento')
             AND definition NOT LIKE '%NO_COINCIDE%')
BEGIN
    ALTER TABLE dbo.Documento DROP CONSTRAINT CK_Documento_Estado;
    ALTER TABLE dbo.Documento
        ADD CONSTRAINT CK_Documento_Estado CHECK (Estado IN ('RECIBIDO','PROCESANDO','COMPLETADO','ERROR','NO_COINCIDE'));
    PRINT 'CK_Documento_Estado ahora admite NO_COINCIDE.';
END
GO

/* ----------------------------------------------------------------------
   7. FlujoCaptura.AccesoPublico: interruptor por flujo (por defecto 0 = privado). Solo un flujo con
      AccesoPublico = 1 y Activo = 1 acepta POST /flujos-captura/{codigo}/documentos SIN API key.
      Lo cambia unicamente un Administrador (PATCH /flujos-captura/{id}/acceso-publico).
   ---------------------------------------------------------------------- */
IF COL_LENGTH('dbo.FlujoCaptura', 'AccesoPublico') IS NULL
BEGIN
    ALTER TABLE dbo.FlujoCaptura
        ADD AccesoPublico BIT NOT NULL CONSTRAINT DF_FlujoCaptura_AccesoPublico DEFAULT 0;
    PRINT 'Columna dbo.FlujoCaptura.AccesoPublico agregada.';
END
GO

/* ----------------------------------------------------------------------
   8. Documento.ConsentimientoEn / AvisoVersion: constancia de que la persona vio y acepto el aviso de
      privacidad antes de subir (flujo publico). NULL en lo que sube el personal interno y en lo anterior.
   ---------------------------------------------------------------------- */
IF COL_LENGTH('dbo.Documento', 'ConsentimientoEn') IS NULL
BEGIN
    ALTER TABLE dbo.Documento ADD ConsentimientoEn DATETIME2 NULL;
    PRINT 'Columna dbo.Documento.ConsentimientoEn agregada.';
END
GO

IF COL_LENGTH('dbo.Documento', 'AvisoVersion') IS NULL
BEGIN
    ALTER TABLE dbo.Documento ADD AvisoVersion NVARCHAR(20) NULL;
    PRINT 'Columna dbo.Documento.AvisoVersion agregada.';
END
GO

PRINT 'schema_flujos_captura.sql aplicado correctamente.';
GO
