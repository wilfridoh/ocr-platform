/* ----------------------------------------------------------------------
   Migracion 008: cedula ecuatoriana, nacionalidad tolera un caracter mal leido en el gentilicio.
   El motor principal lee a veces "ECUATORIANA" con la primera letra cambiada ("LCUATORIANA", "CCUATORIANA") y,
   si ademas la etiqueta NACIONALIDAD sale ilegible, el campo quedaba vacio. La regla agrega un "catalogo" de
   gentilicios: una palabra a UN caracter de uno de ellos (solo los de 7+ letras) se guarda en su forma canonica.
   La regex no cambia. Idempotente; literales ASCII. Aplicar con -f 65001 (db/aplicar.ps1 / aplicar.sh).
   ---------------------------------------------------------------------- */
SET NOCOUNT ON;

DECLARE @cambios TABLE (Codigo NVARCHAR(100), Nombre NVARCHAR(100), Metodo NVARCHAR(20), Nuevo NVARCHAR(MAX));
INSERT INTO @cambios (Codigo, Nombre, Metodo, Nuevo) VALUES
        ('cedula_identidad', 'nacionalidad', 'regex', N'{"metodo":"regex","regex":"(?i)(?:NACIONALIDAD\\s*:\\s*([A-Za-z\u00f1\u00d1]+)|\\b(ECUATORIAN[OA]|COLOMBIAN[OA]|PERUAN[OA]|VENEZOLAN[OA]|CHILEN[OA]|ARGENTIN[OA]|MEXICAN[OA]|BOLIVIAN[OA]|CUBAN[OA]|ESPA[\u00d1N]OL[A]?)\\b)","catalogo":["ECUATORIANA","ECUATORIANO","COLOMBIANA","COLOMBIANO","PERUANA","PERUANO","VENEZOLANA","VENEZOLANO","CHILENA","CHILENO","ARGENTINA","ARGENTINO","MEXICANA","MEXICANO","BOLIVIANA","BOLIVIANO","CUBANA","CUBANO","ESPA\u00d1OLA","ESPA\u00d1OL"]}');

UPDATE cp
   SET cp.ReglaJson = c.Nuevo, cp.Metodo = c.Metodo
  FROM dbo.CampoPlantilla cp
  JOIN dbo.PlantillaVersion v ON v.PlantillaVersionId = cp.PlantillaVersionId AND v.Numero = 1
  JOIN dbo.Plantilla p ON p.PlantillaId = v.PlantillaId
  JOIN @cambios c ON c.Codigo = p.Codigo AND c.Nombre = cp.Nombre
 WHERE cp.ReglaJson <> c.Nuevo OR cp.Metodo <> c.Metodo;

PRINT CONCAT('Reglas de campo actualizadas: ', @@ROWCOUNT);
GO
