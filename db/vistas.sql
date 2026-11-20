/* ============================================================================
   OCR Platform — vistas.sql
   Vistas de consulta sobre el modelo de docs/04-base-de-datos.md.
   Idempotente: usa CREATE OR ALTER.
   Ejecutar después de schema.sql (y opcionalmente seed.sql).
   ============================================================================ */

SET NOCOUNT ON;
GO
USE ocr;
GO

/* ----------------------------------------------------------------------
   vw_PlantillaActual
   Plantilla + su versión actual (la que usa el clasificador), ver §9 del doc.
   ---------------------------------------------------------------------- */
CREATE OR ALTER VIEW dbo.vw_PlantillaActual AS
SELECT
    p.PlantillaId,
    p.Codigo,
    p.Nombre,
    p.Descripcion,
    p.Activa,
    v.PlantillaVersionId,
    v.Numero            AS VersionNumero,
    v.UmbralConfianza,
    v.CreadoEn           AS VersionCreadoEn,
    v.CreadoPor          AS VersionCreadoPor
FROM dbo.Plantilla p
LEFT JOIN dbo.PlantillaVersion v ON v.PlantillaVersionId = p.VersionActualId;
GO

/* ----------------------------------------------------------------------
   vw_HistorialDocumentos
   Documento + su resultado (si existe), para el historial paginado.
   ---------------------------------------------------------------------- */
CREATE OR ALTER VIEW dbo.vw_HistorialDocumentos AS
SELECT
    d.DocumentoId,
    d.NombreArchivo,
    d.TipoMime,
    d.TamanoBytes,
    d.Paginas,
    d.Estado,
    d.MensajeError,
    d.RecibidoEn,
    d.ProcesadoEn,
    r.ResultadoId,
    r.TipoDetectado,
    r.ConfianzaClasificacion,
    r.ConfianzaGlobal,
    r.MotorOcr,
    r.CreadoEn           AS ResultadoCreadoEn
FROM dbo.Documento d
LEFT JOIN dbo.Resultado r ON r.DocumentoId = d.DocumentoId;
GO

/* ----------------------------------------------------------------------
   vw_ExactitudPorPlantilla
   Tasa de campos válidos / documentos por tipo detectado, ver §9 del doc.
   ---------------------------------------------------------------------- */
CREATE OR ALTER VIEW dbo.vw_ExactitudPorPlantilla AS
SELECT
    r.TipoDetectado,
    COUNT(DISTINCT r.ResultadoId)               AS Documentos,
    COUNT(c.CampoExtraidoId)                     AS CamposTotales,
    SUM(CAST(c.Valido AS INT))                   AS CamposValidos,
    CAST(AVG(CAST(c.Valido AS FLOAT)) AS DECIMAL(5,4)) AS TasaValidos,
    AVG(r.ConfianzaGlobal)                        AS ConfianzaGlobalPromedio
FROM dbo.Resultado r
JOIN dbo.CampoExtraido c ON c.ResultadoId = r.ResultadoId
GROUP BY r.TipoDetectado;
GO

PRINT 'vistas.sql aplicado correctamente.';
GO
