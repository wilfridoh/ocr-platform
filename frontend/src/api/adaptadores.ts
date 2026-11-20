/**
 * Adaptadores entre las respuestas REALES del backend y los tipos del frontend (src/tipos).
 * El backend devuelve `nombre_archivo`, `recibido_en`, `tipo_detectado`, `confianza_global` en los
 * documentos y las advertencias como texto "codigo:campo"; la UI trabaja con `archivo`, `fecha`,
 * `tipo`, `confianza` y advertencias como objetos. El modo mock ya usa la forma de la UI y no pasa por aquí.
 */
import type { Advertencia, Documento, EstadoDocumento, Plantilla, Resultado } from '@/tipos'

/** Forma de un documento tal como lo devuelve GET /documentos y GET /documentos/{id}. */
export interface DocumentoApi {
  id: string
  nombre_archivo: string
  paginas: number
  estado: EstadoDocumento
  plantilla_forzada_id?: number | null
  mensaje_error?: string | null
  recibido_en?: string | null
  procesado_en?: string | null
  tipo_detectado?: string | null
  confianza_global?: number | null
}

/** El backend serializa fechas UTC sin sufijo de zona ("2026-11-17T14:03:11"): se interpretan como UTC. */
export function aFechaIso(valor: string | null | undefined): string {
  if (!valor) return ''
  return /(Z|[+-]\d{2}:?\d{2})$/.test(valor) ? valor : `${valor}Z`
}

export function adaptarDocumento(d: DocumentoApi): Documento {
  return {
    id: d.id,
    archivo: d.nombre_archivo,
    fecha: aFechaIso(d.recibido_en ?? d.procesado_en),
    paginas: d.paginas,
    estado: d.estado,
    tipo: d.tipo_detectado ?? null,
    plantilla_id: d.plantilla_forzada_id ?? null,
    confianza: d.confianza_global ?? null,
    mensaje_error: d.mensaje_error ?? null,
  }
}

function legible(campo: string): string {
  return campo.replace(/_/g, ' ')
}

const MENSAJES: Record<string, (campo: string) => string> = {
  campo_obligatorio_faltante: (c) => `Falta el campo obligatorio «${legible(c)}»`,
  campo_no_valido: (c) => `El valor del campo «${legible(c)}» no pasó la validación`,
}

/** "campo_obligatorio_faltante:numero_documento" -> { codigo, campo, mensaje } */
export function adaptarAdvertencia(a: string | Advertencia): Advertencia {
  if (typeof a !== 'string') return a
  const i = a.indexOf(':')
  const codigo = i < 0 ? a : a.slice(0, i)
  const campo = i < 0 ? undefined : a.slice(i + 1)
  const mensaje = MENSAJES[codigo]?.(campo ?? '') ?? (campo ? `${legible(codigo)}: ${legible(campo)}` : legible(codigo))
  return { codigo, campo, mensaje }
}

export function adaptarResultado(r: Resultado): Resultado {
  return { ...r, advertencias: (r.advertencias ?? []).map((a) => adaptarAdvertencia(a as string | Advertencia)) }
}

/** Las plantillas del backend traen `creado_en`/`actualizado_en`; el tipo de la UI usa `creada_en`/`actualizada_en`. */
export function adaptarPlantilla(p: Plantilla & { creado_en?: string; actualizado_en?: string }): Plantilla {
  const { creado_en, actualizado_en, ...resto } = p
  return {
    ...resto,
    creada_en: p.creada_en ?? (creado_en ? aFechaIso(creado_en) : undefined),
    actualizada_en: p.actualizada_en ?? (actualizado_en ? aFechaIso(actualizado_en) : undefined),
  }
}
