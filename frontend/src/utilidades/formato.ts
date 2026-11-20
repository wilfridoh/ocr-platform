export function formatearFecha(iso: string | null | undefined): string {
  if (!iso) return '—'
  try {
    const d = new Date(iso)
    return d.toLocaleString('es-CL', { dateStyle: 'short', timeStyle: 'short' })
  } catch {
    return iso
  }
}

export function formatearFechaCorta(iso: string | null | undefined): string {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleDateString('es-CL', { dateStyle: 'medium' })
  } catch {
    return iso
  }
}

export function formatearPorcentaje(valor: number | null | undefined): string {
  if (valor === null || valor === undefined || Number.isNaN(valor)) return '—'
  return `${Math.round(valor * 100)} %`
}

export function formatearValorCampo(valor: string | number | null): string {
  if (valor === null || valor === undefined || valor === '') return '—'
  if (typeof valor === 'number') return valor.toLocaleString('es-CL')
  return String(valor)
}

/** Clase de color según el nivel de confianza (umbral 0.7 = bajo) */
/** Guía visual: >= 70 % ok; 1-69 % warn; 0 % o faltante err. */
export function colorConfianza(confianza: number | null | undefined): string {
  if (confianza === null || confianza === undefined || confianza <= 0) return 'text-err'
  if (confianza < 0.7) return 'text-warn'
  return 'text-ok'
}

/** Color de relleno de la barra de confianza (mismas reglas que colorConfianza). */
export function fondoConfianza(confianza: number | null | undefined): string {
  if (confianza === null || confianza === undefined || confianza <= 0) return 'bg-err'
  if (confianza < 0.7) return 'bg-warn'
  return 'bg-ok'
}

export function tonoFilaConfianza(confianza: number | null | undefined, obligatorioFaltante: boolean): string {
  if (obligatorioFaltante) return 'bg-err-soft/40'
  if (confianza !== null && confianza !== undefined && confianza < 0.7) return 'bg-warn-soft/40'
  return ''
}

/** 1536 -> "1,5 KB"; 3_400_000 -> "3,2 MB" */
export function formatearTamano(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  const unidades = ['KB', 'MB', 'GB']
  let valor = bytes / 1024
  let i = 0
  while (valor >= 1024 && i < unidades.length - 1) {
    valor /= 1024
    i++
  }
  return `${valor.toLocaleString('es', { maximumFractionDigits: 1 })} ${unidades[i]}`
}
