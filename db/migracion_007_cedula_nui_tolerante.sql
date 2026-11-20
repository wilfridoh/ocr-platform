/* ----------------------------------------------------------------------
   Migracion 007: cedula ecuatoriana, numero_documento tolera la etiqueta "NUI" mal leida por el OCR.
   El motor principal lee a veces "NUI.1234567890" como "NU1.1234567890" (I -> 1; tambien l, | o !). Con la regla
   anterior el numero quedaba vacio y eso solo ya disparaba la segunda opinion (docTR, ~13 s) en una cedula nitida.
   Ahora la etiqueta acepta NUI / NU1 / NUL / NU| / NU! seguida de los 10 digitos.
   Idempotente; literales ASCII. Aplicar con -f 65001 (db/aplicar.ps1 / aplicar.sh).
   ---------------------------------------------------------------------- */
SET NOCOUNT ON;

DECLARE @cambios TABLE (Codigo NVARCHAR(100), Nombre NVARCHAR(100), Metodo NVARCHAR(20), Nuevo NVARCHAR(MAX));
INSERT INTO @cambios (Codigo, Nombre, Metodo, Nuevo) VALUES
        ('cedula_identidad', 'numero_documento', 'regex', N'{"metodo":"regex","regex":"(?i)(?:\\bcc\\s*N[:.]?\\s*(\\d{10})\\b|DOCUMENTO\\s*:?\\s*([\\d.-]{6,})|DOCUMENTO[\\s\\S]{0,60}?\\b(\\d{10})\\b|(?<!\\d)(\\d{9}\\s*-\\s*\\d)(?!\\d)|\\bNU[I1L|!]\\W{0,3}(\\d{9}-?\\d)\\b)"}');

UPDATE cp
   SET cp.ReglaJson = c.Nuevo, cp.Metodo = c.Metodo
  FROM dbo.CampoPlantilla cp
  JOIN dbo.PlantillaVersion v ON v.PlantillaVersionId = cp.PlantillaVersionId AND v.Numero = 1
  JOIN dbo.Plantilla p ON p.PlantillaId = v.PlantillaId
  JOIN @cambios c ON c.Codigo = p.Codigo AND c.Nombre = cp.Nombre
 WHERE cp.ReglaJson <> c.Nuevo OR cp.Metodo <> c.Metodo;

PRINT CONCAT('Reglas de campo actualizadas: ', @@ROWCOUNT);
GO
