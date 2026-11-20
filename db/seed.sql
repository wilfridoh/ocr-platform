/* ============================================================================
   OCR Platform — seed.sql
   Datos semilla idempotentes: 3 plantillas (cuenta_contrato, planilla_servicio,
   cedula_identidad), cada una con su versión 1, palabras clave y campos.
   Los métodos/ReglaJson siguen el formato de docs/02-backend.md
   ("Modelo de plantilla"): { "metodo": "regex|ancla|zona", ... }.
   Ejecutar después de schema.sql y schema_flujos_captura.sql. Seguro de re-ejecutar.
   ============================================================================ */

SET NOCOUNT ON;
GO
USE ocr;
GO

/* ============================================================================
   Procedimiento auxiliar temporal: crea una plantilla + versión 1 si no existe
   (se hace en bloques independientes por plantilla, sin procs permanentes,
   para mantener el script simple e idempotente).
   ============================================================================ */

/* ----------------------------------------------------------------------
   1. cuenta_contrato
   ---------------------------------------------------------------------- */
IF NOT EXISTS (SELECT 1 FROM dbo.Plantilla WHERE Codigo = 'cuenta_contrato')
BEGIN
    INSERT INTO dbo.Plantilla (Codigo, Nombre, Descripcion, Activa)
    VALUES ('cuenta_contrato', 'Cuenta de contrato', 'Contrato de servicio con titular, dirección y monto.', 1);
END
GO

IF NOT EXISTS (
    SELECT 1 FROM dbo.PlantillaVersion v
    JOIN dbo.Plantilla p ON p.PlantillaId = v.PlantillaId
    WHERE p.Codigo = 'cuenta_contrato' AND v.Numero = 1
)
BEGIN
    DECLARE @PlantillaId INT = (SELECT PlantillaId FROM dbo.Plantilla WHERE Codigo = 'cuenta_contrato');
    DECLARE @VersionId INT;

    INSERT INTO dbo.PlantillaVersion (PlantillaId, Numero, UmbralConfianza, CreadoPor)
    VALUES (@PlantillaId, 1, 0.600, 'seed.sql');

    SET @VersionId = SCOPE_IDENTITY();

    INSERT INTO dbo.PalabraClave (PlantillaVersionId, Texto, Peso) VALUES
        (@VersionId, 'contrato', 4),
        (@VersionId, 'titular', 3),
        (@VersionId, 'numero de contrato|n de contrato|nro contrato|n contrato', 5),
        (@VersionId, 'monto total|importe total|total contrato', 2),
        (@VersionId, 'fecha de emision|fecha emision|emitido el', 2);

    INSERT INTO dbo.CampoPlantilla (PlantillaVersionId, Nombre, Etiqueta, TipoDato, Obligatorio, Metodo, ReglaJson, Orden) VALUES
        (@VersionId, 'numero_contrato', 'Número de contrato', 'texto', 1, 'ancla',
            N'{"metodo":"ancla","ancla":"N\u00b0 de Contrato","regex":"[A-Z0-9.-]+"}', 1),
        (@VersionId, 'titular', 'Titular', 'texto', 1, 'ancla',
            N'{"metodo":"ancla","ancla":"Titular","regex":"[^\\n]+"}', 2),
        (@VersionId, 'direccion', 'Dirección', 'texto', 0, 'ancla',
            N'{"metodo":"ancla","ancla":"Direcci\u00f3n","regex":"[^\\n]+"}', 3),
        (@VersionId, 'fecha_emision', 'Fecha de emisión', 'fecha', 1, 'regex',
            N'{"metodo":"regex","regex":"(?:Fecha de\\s+)?[Ee]misi[o\u00f3]n\\s*:?\\s*(\\d{2}[/-]\\d{2}[/-]\\d{4})"}', 4),
        (@VersionId, 'monto_total', 'Monto total', 'monto', 1, 'regex',
            N'{"metodo":"regex","regex":"Monto [Tt]otal\\s*\\$?\\s*([\\d.,]+)"}', 5);

    UPDATE dbo.Plantilla SET VersionActualId = @VersionId, ActualizadoEn = SYSUTCDATETIME() WHERE PlantillaId = @PlantillaId;

    PRINT 'Plantilla cuenta_contrato (v1) insertada.';
END
ELSE
BEGIN
    PRINT 'Plantilla cuenta_contrato (v1) ya existe.';
END
GO

/* ----------------------------------------------------------------------
   2. planilla_servicio
   ---------------------------------------------------------------------- */
IF NOT EXISTS (SELECT 1 FROM dbo.Plantilla WHERE Codigo = 'planilla_servicio')
BEGIN
    INSERT INTO dbo.Plantilla (Codigo, Nombre, Descripcion, Activa)
    VALUES ('planilla_servicio', 'Planilla de servicio', 'Boleta/factura de servicio (agua, luz, gas, etc.).', 1);
END
GO

IF NOT EXISTS (
    SELECT 1 FROM dbo.PlantillaVersion v
    JOIN dbo.Plantilla p ON p.PlantillaId = v.PlantillaId
    WHERE p.Codigo = 'planilla_servicio' AND v.Numero = 1
)
BEGIN
    DECLARE @PlantillaId INT = (SELECT PlantillaId FROM dbo.Plantilla WHERE Codigo = 'planilla_servicio');
    DECLARE @VersionId INT;

    INSERT INTO dbo.PlantillaVersion (PlantillaId, Numero, UmbralConfianza, CreadoPor)
    VALUES (@PlantillaId, 1, 0.600, 'seed.sql');

    SET @VersionId = SCOPE_IDENTITY();

    INSERT INTO dbo.PalabraClave (PlantillaVersionId, Texto, Peso) VALUES
        (@VersionId, 'consumo kwh|kwh consumidos|consumo energia', 3),
        (@VersionId, 'total a pagar|total pagar|monto a pagar|importe a pagar', 3),
        (@VersionId, 'lectura anterior|lect anterior|lectura anter', 2),
        (@VersionId, 'numero de cliente|n cliente|nro cliente|num cliente|no cliente', 4),
        (@VersionId, 'fecha de vencimiento|vencimiento|fecha vencim|vence el', 2);

    INSERT INTO dbo.CampoPlantilla (PlantillaVersionId, Nombre, Etiqueta, TipoDato, Obligatorio, Metodo, ReglaJson, Orden) VALUES
        (@VersionId, 'numero_cliente', 'Número de cliente', 'texto', 1, 'ancla',
            N'{"metodo":"ancla","ancla":"N\u00b0 Cliente","regex":"[\\d.-]+"}', 1),
        (@VersionId, 'direccion', 'Dirección', 'texto', 0, 'ancla',
            N'{"metodo":"ancla","ancla":"Direcci\u00f3n","regex":"[^\\n]+"}', 2),
        (@VersionId, 'periodo', 'Período facturado', 'texto', 0, 'ancla',
            N'{"metodo":"ancla","ancla":"Periodo","regex":"[^\\n]+"}', 3),
        (@VersionId, 'consumo', 'Consumo', 'numero', 0, 'regex',
            N'{"metodo":"regex","regex":"Consumo\\s*(?:\\(?kWh\\)?)?\\s*:?\\s*([\\d.,]+)"}', 4),
        (@VersionId, 'total_pagar', 'Total a pagar', 'monto', 1, 'regex',
            N'{"metodo":"regex","regex":"Total a pagar\\s*\\$?\\s*([\\d.,]+)"}', 5),
        (@VersionId, 'fecha_vencimiento', 'Fecha de vencimiento', 'fecha', 1, 'regex',
            N'{"metodo":"regex","regex":"(?:Fecha de\\s+)?[Vv]encimiento\\s*:?\\s*(\\d{2}[/-]\\d{2}[/-]\\d{4})"}', 6);

    UPDATE dbo.Plantilla SET VersionActualId = @VersionId, ActualizadoEn = SYSUTCDATETIME() WHERE PlantillaId = @PlantillaId;

    PRINT 'Plantilla planilla_servicio (v1) insertada.';
END
ELSE
BEGIN
    PRINT 'Plantilla planilla_servicio (v1) ya existe.';
END
GO

/* ----------------------------------------------------------------------
   3. cedula_identidad
   ---------------------------------------------------------------------- */
IF NOT EXISTS (SELECT 1 FROM dbo.Plantilla WHERE Codigo = 'cedula_identidad')
BEGIN
    INSERT INTO dbo.Plantilla (Codigo, Nombre, Descripcion, Activa)
    VALUES ('cedula_identidad', 'Cédula de identidad', 'Documento nacional de identidad.', 1);
END
GO

IF NOT EXISTS (
    SELECT 1 FROM dbo.PlantillaVersion v
    JOIN dbo.Plantilla p ON p.PlantillaId = v.PlantillaId
    WHERE p.Codigo = 'cedula_identidad' AND v.Numero = 1
)
BEGIN
    DECLARE @PlantillaId INT = (SELECT PlantillaId FROM dbo.Plantilla WHERE Codigo = 'cedula_identidad');
    DECLARE @VersionId INT;

    INSERT INTO dbo.PlantillaVersion (PlantillaId, Numero, UmbralConfianza, CreadoPor)
    VALUES (@PlantillaId, 1, 0.600, 'seed.sql');

    SET @VersionId = SCOPE_IDENTITY();

    INSERT INTO dbo.PalabraClave (PlantillaVersionId, Texto, Peso) VALUES
        (@VersionId, 'cedula de identidad|cedula identidad|carnet de identidad|carnet identidad', 5),
        (@VersionId, 'nacionalidad', 2),
        (@VersionId, 'fecha de nacimiento|fecha nacimiento|nacimiento', 3),
        (@VersionId, 'sexo', 1),
        (@VersionId, 'numero de documento|n documento|nro documento|num documento|run', 4);

    INSERT INTO dbo.CampoPlantilla (PlantillaVersionId, Nombre, Etiqueta, TipoDato, Obligatorio, Metodo, ReglaJson, Orden) VALUES
        (@VersionId, 'numero_documento', 'Número de documento', 'cedula', 1, 'regex',
            N'{"metodo":"regex","regex":"(?i)(?:\\bcc\\s*N[:.]?\\s*(\\d{10})\\b|DOCUMENTO\\s*:?\\s*([\\d.-]{6,})|DOCUMENTO[\\s\\S]{0,60}?\\b(\\d{10})\\b)"}', 1),
        (@VersionId, 'nombres', 'Nombres', 'texto', 1, 'ancla',
            N'{"metodo":"ancla","ancla":"Nombres","regex":"[^\\n]+"}', 2),
        (@VersionId, 'apellidos', 'Apellidos', 'texto', 1, 'ancla',
            N'{"metodo":"ancla","ancla":"Apellidos","regex":"[^\\n]+"}', 3),
        (@VersionId, 'fecha_nacimiento', 'Fecha de nacimiento', 'fecha', 1, 'regex',
            N'{"metodo":"regex","regex":"(?i)FECHA\\s+DE\\s+NACIMIEN\\w*\\s*:?(?:[^\\n]*\\n){0,4}?[^\\n]*?(\\d{1,2}[/-]\\d{1,2}[/-]\\d{4}|\\d{1,2}\\s+[A-Za-z]{3,10}\\s+[A-Za-z]?\\d{3,4})"}', 4),
        (@VersionId, 'fecha_vencimiento', 'Fecha de vencimiento', 'fecha', 0, 'regex',
            N'{"metodo":"regex","regex":"(?i)(?:FECHA\\s+DE\\s+)?VENC\\w*\\s*:?(?:[^\\n]*\\n){0,4}?[^\\n]*?(\\d{1,2}[/-]\\d{1,2}[/-]\\d{4}|\\d{1,2}\\s+[A-Za-z]{3,10}\\s+[A-Za-z]?\\d{3,4})"}', 5),
        (@VersionId, 'nacionalidad', 'Nacionalidad', 'texto', 0, 'regex',
            N'{"metodo":"regex","regex":"(?i)(?:NACIONALIDAD\\s*:\\s*([A-Za-z\u00f1\u00d1]+)|\\b(ECUATORIAN[OA]|COLOMBIAN[OA]|PERUAN[OA]|VENEZOLAN[OA]|CHILEN[OA]|ARGENTIN[OA]|MEXICAN[OA]|BOLIVIAN[OA]|CUBAN[OA]|ESPA[\u00d1N]OL[A]?)\\b)"}', 6),
        (@VersionId, 'sexo', 'Sexo', 'texto', 0, 'regex',
            N'{"metodo":"regex","regex":"(?i)(?:\\bSEXO\\s*:?\\s*([MF])\\b|\\b(HOMBRE|MUJER)\\b)"}', 7);

    UPDATE dbo.Plantilla SET VersionActualId = @VersionId, ActualizadoEn = SYSUTCDATETIME() WHERE PlantillaId = @PlantillaId;

    PRINT 'Plantilla cedula_identidad (v1) insertada.';
END
ELSE
BEGIN
    PRINT 'Plantilla cedula_identidad (v1) ya existe.';
END
GO

/* ----------------------------------------------------------------------
   4. Flujos de captura de ejemplo (docs/07). Requiere schema_flujos_captura.sql.
      Se omite sin error si esa ampliacion aun no se aplico.
   ---------------------------------------------------------------------- */
IF OBJECT_ID('dbo.FlujoCaptura', 'U') IS NOT NULL
BEGIN
    IF NOT EXISTS (SELECT 1 FROM dbo.FlujoCaptura WHERE Codigo = 'alta_cliente_cedula')
    BEGIN
        INSERT INTO dbo.FlujoCaptura (Codigo, Nombre, Instruccion, AceptaCamara, AceptaPdf, Activo)
        VALUES ('alta_cliente_cedula', N'Alta de cliente — cédula',
                N'Sube o escanea tu cédula de identidad', 1, 0, 1);
        INSERT INTO dbo.FlujoCapturaPlantilla (FlujoCapturaId, PlantillaId)
        SELECT f.FlujoCapturaId, p.PlantillaId
          FROM dbo.FlujoCaptura f CROSS JOIN dbo.Plantilla p
         WHERE f.Codigo = 'alta_cliente_cedula' AND p.Codigo = 'cedula_identidad';
        PRINT 'Flujo alta_cliente_cedula insertado.';
    END
    ELSE PRINT 'Flujo alta_cliente_cedula ya existe.';

    IF NOT EXISTS (SELECT 1 FROM dbo.FlujoCaptura WHERE Codigo = 'regularizacion_servicios')
    BEGIN
        INSERT INTO dbo.FlujoCaptura (Codigo, Nombre, Instruccion, AceptaCamara, AceptaPdf, Activo)
        VALUES ('regularizacion_servicios', N'Regularización de servicios',
                N'Sube tu última planilla de servicios', 1, 1, 1);
        INSERT INTO dbo.FlujoCapturaPlantilla (FlujoCapturaId, PlantillaId)
        SELECT f.FlujoCapturaId, p.PlantillaId
          FROM dbo.FlujoCaptura f CROSS JOIN dbo.Plantilla p
         WHERE f.Codigo = 'regularizacion_servicios' AND p.Codigo = 'planilla_servicio';
        PRINT 'Flujo regularizacion_servicios insertado.';
    END
    ELSE PRINT 'Flujo regularizacion_servicios ya existe.';
END
GO

PRINT 'seed.sql aplicado correctamente.';
GO
