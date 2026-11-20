/* ----------------------------------------------------------------------
   Migracion 005: la "CEDULA DE CIUDADANIA" (formato nuevo) no clasificaba como cedula_identidad: la palabra clave
   principal solo traia "cedula de identidad" y el documento dice "CEDULA DE CIUDADANIA" / "IDENTIFICACION Y CEDULACION".
   Se agregan esas variantes a la misma clave (cuentan una vez). Idempotente: solo actualiza la fila v1 cuyo Texto
   es exactamente el valor anterior (si ya fue migrada o editada por el usuario, no la toca). Literales ASCII.
   Despues: POST /api/plantillas/{id}/reprocesar o POST /api/documentos/{id}/reprocesar.
   ---------------------------------------------------------------------- */
SET NOCOUNT ON;

UPDATE pc
   SET pc.Texto = 'cedula de identidad|cedula identidad|carnet de identidad|carnet identidad|cedula de ciudadania|cedula ciudadania|identificacion y cedulacion'
  FROM dbo.PalabraClave pc
  JOIN dbo.PlantillaVersion v ON v.PlantillaVersionId = pc.PlantillaVersionId AND v.Numero = 1
  JOIN dbo.Plantilla p ON p.PlantillaId = v.PlantillaId
 WHERE p.Codigo = 'cedula_identidad' AND pc.Texto = 'cedula de identidad|cedula identidad|carnet de identidad|carnet identidad';

PRINT CONCAT('Palabras clave actualizadas: ', @@ROWCOUNT);
GO
