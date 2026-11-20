/* ----------------------------------------------------------------------
   Migracion 004: cedula ecuatoriana "CEDULA DE CIUDADANIA" (formato nuevo, foto de celular).
   - numero_documento: ademas de "CC N:" / "DOCUMENTO", acepta el numero impreso como 9 digitos + guion + digito
     ("#########-#"), que el validador normaliza a 10 digitos.
   - fecha_nacimiento / fecha_vencimiento: acepta fecha ISO "aaaa-mm-dd".
   Nombres y apellidos no necesitan migracion: la etiqueta combinada "APELLIDOS Y NOMBRES" la resuelve el extractor.
   Se identifica la fila por (plantilla, campo) en la version 1. Idempotente. Los literales son ASCII puro.
   Aplicar con: sqlcmd ... -f 65001 -i <archivo>  (o db/aplicar.ps1 / aplicar.sh).
   Despues: POST /api/documentos/{id}/reprocesar o POST /api/plantillas/{id}/reprocesar.
   ---------------------------------------------------------------------- */
SET NOCOUNT ON;

DECLARE @cambios TABLE (Codigo NVARCHAR(100), Nombre NVARCHAR(100), Metodo NVARCHAR(20), Nuevo NVARCHAR(MAX));
INSERT INTO @cambios (Codigo, Nombre, Metodo, Nuevo) VALUES
        ('cedula_identidad', 'numero_documento', 'regex', N'{"metodo":"regex","regex":"(?i)(?:\\bcc\\s*N[:.]?\\s*(\\d{10})\\b|DOCUMENTO\\s*:?\\s*([\\d.-]{6,})|DOCUMENTO[\\s\\S]{0,60}?\\b(\\d{10})\\b|(?<!\\d)(\\d{9}\\s*-\\s*\\d)(?!\\d))"}'),
        ('cedula_identidad', 'fecha_nacimiento', 'regex', N'{"metodo":"regex","regex":"(?i)FECHA\\s+DE\\s+NACIMIEN\\w*\\s*:?(?:[^\\n]*\\n){0,4}?[^\\n]*?(\\d{4}-\\d{1,2}-\\d{1,2}|\\d{1,2}[/-]\\d{1,2}[/-]\\d{4}|\\d{1,2}\\s+[A-Za-z]{3,10}\\s+[A-Za-z]?\\d{3,4})"}'),
        ('cedula_identidad', 'fecha_vencimiento', 'regex', N'{"metodo":"regex","regex":"(?i)(?:FECHA\\s+DE\\s+)?VENC\\w*\\s*:?(?:[^\\n]*\\n){0,4}?[^\\n]*?(\\d{4}-\\d{1,2}-\\d{1,2}|\\d{1,2}[/-]\\d{1,2}[/-]\\d{4}|\\d{1,2}\\s+[A-Za-z]{3,10}\\s+[A-Za-z]?\\d{3,4})"}');

UPDATE cp
   SET cp.ReglaJson = c.Nuevo, cp.Metodo = c.Metodo
  FROM dbo.CampoPlantilla cp
  JOIN dbo.PlantillaVersion v ON v.PlantillaVersionId = cp.PlantillaVersionId AND v.Numero = 1
  JOIN dbo.Plantilla p ON p.PlantillaId = v.PlantillaId
  JOIN @cambios c ON c.Codigo = p.Codigo AND c.Nombre = cp.Nombre
 WHERE cp.ReglaJson <> c.Nuevo OR cp.Metodo <> c.Metodo;

PRINT CONCAT('Reglas de campo actualizadas: ', @@ROWCOUNT);
GO
