/* ----------------------------------------------------------------------
   Migracion 009: posicion de las palabras del OCR y datos del recorte en dbo.Resultado (docs/13 1.3).
   Primera entrega de la cuadricula de zonas: el resultado guarda, por pagina, cada palabra con su caja relativa
   (0-1) sobre la imagen recortada/enderezada y como se recorto la imagen. Son los mismos datos que TextoCompleto,
   con su posicion: misma retencion, purga y permisos.
   Solo agrega dos columnas NULL; no toca filas existentes (los resultados anteriores quedan con NULL hasta que se
   reprocesan). Idempotente; ASCII. Aplicar con -f 65001 ANTES de desplegar el backend que las usa.
   ---------------------------------------------------------------------- */
SET NOCOUNT ON;

IF COL_LENGTH('dbo.Resultado', 'PalabrasJson') IS NULL
BEGIN
    ALTER TABLE dbo.Resultado ADD PalabrasJson NVARCHAR(MAX) NULL;
    PRINT 'Columna dbo.Resultado.PalabrasJson creada.';
END
ELSE
    PRINT 'Columna dbo.Resultado.PalabrasJson ya existe.';
GO

IF COL_LENGTH('dbo.Resultado', 'RecorteJson') IS NULL
BEGIN
    ALTER TABLE dbo.Resultado ADD RecorteJson NVARCHAR(MAX) NULL;
    PRINT 'Columna dbo.Resultado.RecorteJson creada.';
END
ELSE
    PRINT 'Columna dbo.Resultado.RecorteJson ya existe.';
GO

IF NOT EXISTS (SELECT 1 FROM sys.check_constraints WHERE name = 'CK_Resultado_PalabrasJson')
    ALTER TABLE dbo.Resultado ADD CONSTRAINT CK_Resultado_PalabrasJson CHECK (PalabrasJson IS NULL OR ISJSON(PalabrasJson) = 1);
GO

IF NOT EXISTS (SELECT 1 FROM sys.check_constraints WHERE name = 'CK_Resultado_RecorteJson')
    ALTER TABLE dbo.Resultado ADD CONSTRAINT CK_Resultado_RecorteJson CHECK (RecorteJson IS NULL OR ISJSON(RecorteJson) = 1);
GO
