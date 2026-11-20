/* ----------------------------------------------------------------------
   Migración 001: variantes/abreviaturas en las palabras clave de las plantillas semilla.
   Formato: "a|b|c" = variantes de UNA misma clave (cuentan una vez, sin diluir el puntaje).
   Idempotente: solo actualiza la fila cuyo Texto es exactamente el valor original (v1 de la
   plantilla); si ya fue migrada o editada por el usuario, no la toca. Reejecutable.
   ---------------------------------------------------------------------- */
SET NOCOUNT ON;

DECLARE @cambios TABLE (Codigo NVARCHAR(100), Original NVARCHAR(200), Nuevo NVARCHAR(200));
INSERT INTO @cambios (Codigo, Original, Nuevo) VALUES
        ('cuenta_contrato', 'numero de contrato', 'numero de contrato|n de contrato|nro contrato|n contrato'),
        ('cuenta_contrato', 'fecha de emision', 'fecha de emision|fecha emision|emitido el'),
        ('cuenta_contrato', 'monto total', 'monto total|importe total|total contrato'),
        ('planilla_servicio', 'consumo kwh', 'consumo kwh|kwh consumidos|consumo energia'),
        ('planilla_servicio', 'total a pagar', 'total a pagar|total pagar|monto a pagar|importe a pagar'),
        ('planilla_servicio', 'lectura anterior', 'lectura anterior|lect anterior|lectura anter'),
        ('planilla_servicio', 'numero de cliente', 'numero de cliente|n cliente|nro cliente|num cliente|no cliente'),
        ('planilla_servicio', 'fecha de vencimiento', 'fecha de vencimiento|vencimiento|fecha vencim|vence el'),
        ('cedula_identidad', 'cedula de identidad', 'cedula de identidad|cedula identidad|carnet de identidad|carnet identidad'),
        ('cedula_identidad', 'fecha de nacimiento', 'fecha de nacimiento|fecha nacimiento|nacimiento'),
        ('cedula_identidad', 'numero de documento', 'numero de documento|n documento|nro documento|num documento|run');

UPDATE pc
   SET pc.Texto = c.Nuevo
  FROM dbo.PalabraClave pc
  JOIN dbo.PlantillaVersion v ON v.PlantillaVersionId = pc.PlantillaVersionId AND v.Numero = 1
  JOIN dbo.Plantilla p ON p.PlantillaId = v.PlantillaId
  JOIN @cambios c ON c.Codigo = p.Codigo AND c.Original = pc.Texto;

PRINT CONCAT('Palabras clave actualizadas: ', @@ROWCOUNT);
GO
