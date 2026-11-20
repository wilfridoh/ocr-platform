/* ----------------------------------------------------------------------
   Migracion 003: reglas de extraccion de las plantillas semilla (v1) ajustadas a documentos reales.
   - direccion (cuenta_contrato, planilla_servicio): ancla "Direccion" (repara tambien la 002 si se aplico
     con una codificacion incorrecta y dejo "DirecciA3n").
   - cedula_identidad (cedula ecuatoriana real leida por OCR, con etiquetas y valores separados por varias lineas):
       numero_documento: de ancla a regex ("CC N: <10 digitos>" del certificado de votacion, o "DOCUMENTO <numero>");
       fecha_nacimiento / fecha_vencimiento: valor hasta 4 lineas despues de la etiqueta; acepta "03 NOV 1996";
       sexo: acepta HOMBRE / MUJER ademas de M / F;
       nacionalidad: regex por gentilicios comunes o "Nacionalidad: X".
   Los literales son ASCII puro (acentos como escapes JSON \uXXXX): no dependen de la pagina de codigos con la
   que sqlcmd lea el archivo. Aun asi, se recomienda aplicar con:  sqlcmd ... -f 65001 -i <archivo>.
   Se identifica la fila por (plantilla, campo) en la version 1 (la version semilla; editar una plantilla desde la
   API crea una version nueva, no modifica la 1). Idempotente: solo actualiza si la regla es distinta.
   Despues: POST /api/documentos/{id}/reprocesar o POST /api/plantillas/{id}/reprocesar.
   ---------------------------------------------------------------------- */
SET NOCOUNT ON;

DECLARE @cambios TABLE (Codigo NVARCHAR(100), Nombre NVARCHAR(100), Metodo NVARCHAR(20), Nuevo NVARCHAR(MAX));
INSERT INTO @cambios (Codigo, Nombre, Metodo, Nuevo) VALUES
        ('cuenta_contrato', 'direccion', 'ancla', N'{"metodo":"ancla","ancla":"Direcci\u00f3n","regex":"[^\\n]+"}'),
        ('planilla_servicio', 'direccion', 'ancla', N'{"metodo":"ancla","ancla":"Direcci\u00f3n","regex":"[^\\n]+"}'),
        ('cedula_identidad', 'numero_documento', 'regex', N'{"metodo":"regex","regex":"(?i)(?:\\bcc\\s*N[:.]?\\s*(\\d{10})\\b|DOCUMENTO\\s*:?\\s*([\\d.-]{6,})|DOCUMENTO[\\s\\S]{0,60}?\\b(\\d{10})\\b)"}'),
        ('cedula_identidad', 'fecha_nacimiento', 'regex', N'{"metodo":"regex","regex":"(?i)FECHA\\s+DE\\s+NACIMIEN\\w*\\s*:?(?:[^\\n]*\\n){0,4}?[^\\n]*?(\\d{1,2}[/-]\\d{1,2}[/-]\\d{4}|\\d{1,2}\\s+[A-Za-z]{3,10}\\s+[A-Za-z]?\\d{3,4})"}'),
        ('cedula_identidad', 'fecha_vencimiento', 'regex', N'{"metodo":"regex","regex":"(?i)(?:FECHA\\s+DE\\s+)?VENC\\w*\\s*:?(?:[^\\n]*\\n){0,4}?[^\\n]*?(\\d{1,2}[/-]\\d{1,2}[/-]\\d{4}|\\d{1,2}\\s+[A-Za-z]{3,10}\\s+[A-Za-z]?\\d{3,4})"}'),
        ('cedula_identidad', 'sexo', 'regex', N'{"metodo":"regex","regex":"(?i)(?:\\bSEXO\\s*:?\\s*([MF])\\b|\\b(HOMBRE|MUJER)\\b)"}'),
        ('cedula_identidad', 'nacionalidad', 'regex', N'{"metodo":"regex","regex":"(?i)(?:NACIONALIDAD\\s*:\\s*([A-Za-z\u00f1\u00d1]+)|\\b(ECUATORIAN[OA]|COLOMBIAN[OA]|PERUAN[OA]|VENEZOLAN[OA]|CHILEN[OA]|ARGENTIN[OA]|MEXICAN[OA]|BOLIVIAN[OA]|CUBAN[OA]|ESPA[\u00d1N]OL[A]?)\\b)"}');

UPDATE cp
   SET cp.ReglaJson = c.Nuevo, cp.Metodo = c.Metodo
  FROM dbo.CampoPlantilla cp
  JOIN dbo.PlantillaVersion v ON v.PlantillaVersionId = cp.PlantillaVersionId AND v.Numero = 1
  JOIN dbo.Plantilla p ON p.PlantillaId = v.PlantillaId
  JOIN @cambios c ON c.Codigo = p.Codigo AND c.Nombre = cp.Nombre
 WHERE cp.ReglaJson <> c.Nuevo OR cp.Metodo <> c.Metodo;

PRINT CONCAT('Reglas de campo actualizadas: ', @@ROWCOUNT);
GO
