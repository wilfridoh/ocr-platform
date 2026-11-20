/* ----------------------------------------------------------------------
   Migración 002: corrige reglas de extracción de los campos de las plantillas semilla (v1).
   - direccion (cuenta_contrato, planilla_servicio): de 'zona' (coordenadas fijas, frágil: tomaba la
     línea de otro campo) a 'ancla' "Dirección".
   - consumo: acepta "Consumo: 145 kWh" (unidad después del número).
   - fechas (vencimiento, nacimiento, emisión): el prefijo "Fecha de" es opcional y acepta '-' o '/'.
   Idempotente: solo actualiza la fila (v1) cuyo ReglaJson es exactamente el original; si ya fue
   migrada o el usuario la editó, no la toca. Reejecutable. Para ver el efecto en documentos ya
   procesados, reprocesarlos (POST /api/plantillas/{id}/reprocesar).
   ---------------------------------------------------------------------- */
SET NOCOUNT ON;

DECLARE @cambios TABLE (Codigo NVARCHAR(100), Nombre NVARCHAR(100), MetodoOrig NVARCHAR(20), MetodoNuevo NVARCHAR(20),
                        Original NVARCHAR(MAX), Nuevo NVARCHAR(MAX));
INSERT INTO @cambios (Codigo, Nombre, MetodoOrig, MetodoNuevo, Original, Nuevo) VALUES
        ('cuenta_contrato', 'direccion', 'zona', 'ancla', N'{"metodo":"zona","pagina":1,"x":0.05,"y":0.18,"ancho":0.6,"alto":0.06}', N'{"metodo":"ancla","ancla":"Direcci\u00f3n","regex":"[^\\n]+"}'),
        ('planilla_servicio', 'direccion', 'zona', 'ancla', N'{"metodo":"zona","pagina":1,"x":0.05,"y":0.18,"ancho":0.5,"alto":0.06}', N'{"metodo":"ancla","ancla":"Direcci\u00f3n","regex":"[^\\n]+"}'),
        ('planilla_servicio', 'consumo', 'regex', 'regex', N'{"metodo":"regex","regex":"Consumo\\s*\\(?kWh\\)?\\s*:?\\s*([\\d.,]+)"}', N'{"metodo":"regex","regex":"Consumo\\s*(?:\\(?kWh\\)?)?\\s*:?\\s*([\\d.,]+)"}'),
        ('planilla_servicio', 'fecha_vencimiento', 'regex', 'regex', N'{"metodo":"regex","regex":"Fecha de [Vv]encimiento\\s*:?\\s*(\\d{2}/\\d{2}/\\d{4})"}', N'{"metodo":"regex","regex":"(?:Fecha de\\s+)?[Vv]encimiento\\s*:?\\s*(\\d{2}[/-]\\d{2}[/-]\\d{4})"}'),
        ('cedula_identidad', 'fecha_vencimiento', 'regex', 'regex', N'{"metodo":"regex","regex":"Fecha de [Vv]encimiento\\s*:?\\s*(\\d{2}/\\d{2}/\\d{4})"}', N'{"metodo":"regex","regex":"(?:Fecha de\\s+)?[Vv]encimiento\\s*:?\\s*(\\d{2}[/-]\\d{2}[/-]\\d{4})"}'),
        ('cedula_identidad', 'fecha_nacimiento', 'regex', 'regex', N'{"metodo":"regex","regex":"Fecha de [Nn]acimiento\\s*:?\\s*(\\d{2}/\\d{2}/\\d{4})"}', N'{"metodo":"regex","regex":"(?:Fecha de\\s+)?[Nn]acimiento\\s*:?\\s*(\\d{2}[/-]\\d{2}[/-]\\d{4})"}'),
        ('cuenta_contrato', 'fecha_emision', 'regex', 'regex', N'{"metodo":"regex","regex":"Fecha de [Ee]misi[o\u00f3]n\\s*:?\\s*(\\d{2}/\\d{2}/\\d{4})"}', N'{"metodo":"regex","regex":"(?:Fecha de\\s+)?[Ee]misi[o\u00f3]n\\s*:?\\s*(\\d{2}[/-]\\d{2}[/-]\\d{4})"}');

UPDATE cp
   SET cp.ReglaJson = c.Nuevo, cp.Metodo = c.MetodoNuevo
  FROM dbo.CampoPlantilla cp
  JOIN dbo.PlantillaVersion v ON v.PlantillaVersionId = cp.PlantillaVersionId AND v.Numero = 1
  JOIN dbo.Plantilla p ON p.PlantillaId = v.PlantillaId
  JOIN @cambios c ON c.Codigo = p.Codigo AND c.Nombre = cp.Nombre
                 AND c.MetodoOrig = cp.Metodo AND c.Original = cp.ReglaJson;

PRINT CONCAT('Reglas de campo actualizadas: ', @@ROWCOUNT);
GO
