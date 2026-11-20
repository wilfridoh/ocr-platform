/* ----------------------------------------------------------------------
   Migracion 006: cedula ecuatoriana, tercera variante ("CEDULA DE IDENTIDAD" nueva, con "NUI.").
   - numero_documento: acepta ademas "NUI. <10 digitos>".
   - apellidos: "lineas": 2 (dos apellidos impresos en dos lineas bajo la etiqueta).
   - palabra clave del numero: agrega "nui" y "numero unico de identificacion".
   - palabra clave nueva (peso 3): "republica del ecuador|registro civil" (senal estructural del documento: clasifica
     aunque el OCR rompa otras etiquetas).
   Idempotente; literales ASCII. Aplicar con -f 65001 (db/aplicar.ps1 / aplicar.sh). Requiere el backend que
   entiende "lineas" (un backend anterior ignora el campo).
   ---------------------------------------------------------------------- */
SET NOCOUNT ON;

DECLARE @cambios TABLE (Codigo NVARCHAR(100), Nombre NVARCHAR(100), Metodo NVARCHAR(20), Nuevo NVARCHAR(MAX));
INSERT INTO @cambios (Codigo, Nombre, Metodo, Nuevo) VALUES
        ('cedula_identidad', 'numero_documento', 'regex', N'{"metodo":"regex","regex":"(?i)(?:\\bcc\\s*N[:.]?\\s*(\\d{10})\\b|DOCUMENTO\\s*:?\\s*([\\d.-]{6,})|DOCUMENTO[\\s\\S]{0,60}?\\b(\\d{10})\\b|(?<!\\d)(\\d{9}\\s*-\\s*\\d)(?!\\d)|\\bNUI\\W{0,3}(\\d{9}-?\\d)\\b)"}'),
        ('cedula_identidad', 'apellidos', 'ancla', N'{"metodo":"ancla","ancla":"Apellidos","regex":"[^\\n]+","lineas":2}');

UPDATE cp
   SET cp.ReglaJson = c.Nuevo, cp.Metodo = c.Metodo
  FROM dbo.CampoPlantilla cp
  JOIN dbo.PlantillaVersion v ON v.PlantillaVersionId = cp.PlantillaVersionId AND v.Numero = 1
  JOIN dbo.Plantilla p ON p.PlantillaId = v.PlantillaId
  JOIN @cambios c ON c.Codigo = p.Codigo AND c.Nombre = cp.Nombre
 WHERE cp.ReglaJson <> c.Nuevo OR cp.Metodo <> c.Metodo;

PRINT CONCAT('Reglas de campo actualizadas: ', @@ROWCOUNT);
GO

UPDATE pc
   SET pc.Texto = 'numero de documento|n documento|nro documento|num documento|run|nui|numero unico de identificacion'
  FROM dbo.PalabraClave pc
  JOIN dbo.PlantillaVersion v ON v.PlantillaVersionId = pc.PlantillaVersionId AND v.Numero = 1
  JOIN dbo.Plantilla p ON p.PlantillaId = v.PlantillaId
 WHERE p.Codigo = 'cedula_identidad' AND pc.Texto = 'numero de documento|n documento|nro documento|num documento|run';

PRINT CONCAT('Palabras clave actualizadas: ', @@ROWCOUNT);
GO

INSERT INTO dbo.PalabraClave (PlantillaVersionId, Texto, Peso)
SELECT v.PlantillaVersionId, 'republica del ecuador|registro civil', 3
  FROM dbo.PlantillaVersion v
  JOIN dbo.Plantilla p ON p.PlantillaId = v.PlantillaId
 WHERE p.Codigo = 'cedula_identidad' AND v.Numero = 1
   AND NOT EXISTS (SELECT 1 FROM dbo.PalabraClave pc
                    WHERE pc.PlantillaVersionId = v.PlantillaVersionId AND pc.Texto LIKE '%registro civil%');

PRINT CONCAT('Palabras clave insertadas: ', @@ROWCOUNT);
GO
