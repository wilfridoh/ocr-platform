/* ----------------------------------------------------------------------
   Migracion 011: coincidencia de diseno con la plantilla en dbo.Resultado (docs/13 3.3).
   Cuarta entrega de la cuadricula de zonas: el resultado guarda el bloque "coincidencia" (puntaje 70 % etiquetas
   fijas + 30 % alineacion, veredicto, estado por zona). Valida el DISENO del documento, no su autenticidad.
   Solo agrega una columna NULL: no toca filas existentes (NULL = plantilla sin cuadricula o resultado anterior).
   Idempotente; ASCII. Aplicar con -f 65001 ANTES de desplegar el backend que la usa.
   ---------------------------------------------------------------------- */
SET NOCOUNT ON;

IF COL_LENGTH('dbo.Resultado', 'CoincidenciaJson') IS NULL
BEGIN
    ALTER TABLE dbo.Resultado ADD CoincidenciaJson NVARCHAR(MAX) NULL;
    PRINT 'Columna dbo.Resultado.CoincidenciaJson creada.';
END
ELSE
    PRINT 'Columna dbo.Resultado.CoincidenciaJson ya existe.';
GO

IF NOT EXISTS (SELECT 1 FROM sys.check_constraints WHERE name = 'CK_Resultado_CoincidenciaJson')
    ALTER TABLE dbo.Resultado ADD CONSTRAINT CK_Resultado_CoincidenciaJson CHECK (CoincidenciaJson IS NULL OR ISJSON(CoincidenciaJson) = 1);
GO
