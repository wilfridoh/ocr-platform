/* ----------------------------------------------------------------------
   Migracion 010: diseno por posicion de cada version de plantilla (docs/13 1.2).
   Segunda entrega de la cuadricula de zonas: PlantillaVersion.DisenoJson guarda la proporcion esperada, el umbral de
   coincidencia, la tolerancia, la densidad de la rejilla (solo UI) y las etiquetas fijas sin campo. Las zonas de cada
   campo van en su ReglaJson (claves x/y/ancho/alto y zona_etiqueta), sin cambio de esquema.
   Solo agrega una columna NULL: no toca filas existentes (NULL = plantilla sin cuadricula, se comporta como antes).
   Idempotente; ASCII. Aplicar con -f 65001 ANTES de desplegar el backend que la usa.
   ---------------------------------------------------------------------- */
SET NOCOUNT ON;

IF COL_LENGTH('dbo.PlantillaVersion', 'DisenoJson') IS NULL
BEGIN
    ALTER TABLE dbo.PlantillaVersion ADD DisenoJson NVARCHAR(MAX) NULL;
    PRINT 'Columna dbo.PlantillaVersion.DisenoJson creada.';
END
ELSE
    PRINT 'Columna dbo.PlantillaVersion.DisenoJson ya existe.';
GO

IF NOT EXISTS (SELECT 1 FROM sys.check_constraints WHERE name = 'CK_PlantillaVersion_DisenoJson')
    ALTER TABLE dbo.PlantillaVersion ADD CONSTRAINT CK_PlantillaVersion_DisenoJson CHECK (DisenoJson IS NULL OR ISJSON(DisenoJson) = 1);
GO
