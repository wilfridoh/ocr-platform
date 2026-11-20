/**
 * Utilidades del editor de cuadrícula (docs/12 y docs/13). Las zonas se guardan SIEMPRE como rectángulos relativos
 * (0-1); la rejilla solo sirve para dibujar y nombrar celdas, así que cambiar su densidad no pierde zonas.
 */
import type { DisenoPlantilla, PalabraPosicion, ZonaRelativa } from '@/tipos'

export interface Densidad {
  id: string
  columnas: number
  filas: number
  etiqueta: string
}

export const DENSIDADES: Densidad[] = [
  { id: '8x5', columnas: 8, filas: 5, etiqueta: '8 × 5 · grueso' },
  { id: '12x8', columnas: 12, filas: 8, etiqueta: '12 × 8 · recomendado' },
  { id: '16x10', columnas: 16, filas: 10, etiqueta: '16 × 10 · fino' },
  { id: '24x15', columnas: 24, filas: 15, etiqueta: '24 × 15 · muy fino' },
]

export function densidad(id: string | null | undefined): Densidad {
  return DENSIDADES.find((d) => d.id === id) ?? DENSIDADES[1]
}

/** Preajustes de formato: solo fijan la proporción esperada (lado mayor / menor). Nada queda atado a uno. */
export const FORMATOS: { id: string; etiqueta: string; relacion: number | null }[] = [
  { id: 'ID-1', etiqueta: 'Tarjeta ID-1 (85,6 × 54 mm)', relacion: 1.586 },
  { id: 'A4', etiqueta: 'Hoja A4', relacion: 1.414 },
  { id: 'carta', etiqueta: 'Hoja carta', relacion: 1.294 },
  { id: 'libre', etiqueta: 'Libre (la del documento de ejemplo)', relacion: null },
]

export const DISENO_POR_DEFECTO: DisenoPlantilla = {
  formato: 'ID-1',
  relacion: 1.586,
  umbral_coincidencia: 0.8,
  tolerancia: 0.03,
  densidad_rejilla: '12x8',
  elementos_fijos: [],
}

/** Umbral bajo el cual una palabra se muestra en gris (el mismo que dispara la segunda opinión). */
export const CONFIANZA_BAJA = 0.7

const redondear = (v: number) => Math.round(v * 10000) / 10000

/** Ajusta un rectángulo libre a las celdas que toca. */
export function ajustarACeldas(z: ZonaRelativa, d: Densidad): ZonaRelativa {
  const c0 = Math.max(0, Math.floor(z.x * d.columnas + 1e-6))
  const c1 = Math.min(d.columnas, Math.ceil((z.x + z.ancho) * d.columnas - 1e-6))
  const f0 = Math.max(0, Math.floor(z.y * d.filas + 1e-6))
  const f1 = Math.min(d.filas, Math.ceil((z.y + z.alto) * d.filas - 1e-6))
  return {
    x: redondear(c0 / d.columnas),
    y: redondear(f0 / d.filas),
    ancho: redondear(Math.max(1, c1 - c0) / d.columnas),
    alto: redondear(Math.max(1, f1 - f0) / d.filas),
    pagina: z.pagina ?? 1,
  }
}

/** Celda bajo un punto relativo. */
export function celdaEn(x: number, y: number, d: Densidad): ZonaRelativa {
  return ajustarACeldas({ x, y, ancho: 0.0001, alto: 0.0001 }, d)
}

function nombreColumna(c: number): string {
  return c < 26 ? String.fromCharCode(65 + c) : `${String.fromCharCode(64 + Math.floor(c / 26))}${String.fromCharCode(65 + (c % 26))}`
}

/** "E3:G3" (columna en letra, fila desde 1) para mostrar; la zona guardada es el rectángulo, no las celdas. */
export function rangoCeldas(z: ZonaRelativa, d: Densidad): string {
  const c0 = Math.max(0, Math.round(z.x * d.columnas))
  const f0 = Math.max(0, Math.round(z.y * d.filas))
  const c1 = Math.max(c0, Math.round((z.x + z.ancho) * d.columnas) - 1)
  const f1 = Math.max(f0, Math.round((z.y + z.alto) * d.filas) - 1)
  const a = `${nombreColumna(c0)}${f0 + 1}`
  const b = `${nombreColumna(c1)}${f1 + 1}`
  return a === b ? a : `${a}:${b}`
}

/** Las palabras cuyo centro cae en la zona, en orden de lectura. */
export function palabrasEnZona(palabras: PalabraPosicion[], z: ZonaRelativa): PalabraPosicion[] {
  const dentro = palabras.filter((p) => {
    const cx = p.x + p.ancho / 2
    const cy = p.y + p.alto / 2
    return cx >= z.x && cx <= z.x + z.ancho && cy >= z.y && cy <= z.y + z.alto
  })
  return dentro.sort((a, b) => (Math.abs(a.y - b.y) < Math.min(a.alto, b.alto) * 0.6 ? a.x - b.x : a.y - b.y))
}

export function textoEnZona(palabras: PalabraPosicion[], z: ZonaRelativa): string {
  return palabrasEnZona(palabras, z)
    .map((p) => p.texto)
    .join(' ')
    .trim()
}

/** Palabra bajo un punto relativo (la más pequeña si hay varias superpuestas). */
export function palabraEn(palabras: PalabraPosicion[], x: number, y: number): PalabraPosicion | null {
  const bajo = palabras.filter((p) => x >= p.x && x <= p.x + p.ancho && y >= p.y && y <= p.y + p.alto)
  return bajo.sort((a, b) => a.ancho * a.alto - b.ancho * b.alto)[0] ?? null
}

/**
 * Paleta por campo, distinta de los colores de estado (verde/ámbar/rojo). Todos con contraste AA (>= 4,5:1) para el
 * texto blanco del badge; el badge lleva siempre el nombre del campo, no se depende solo del color.
 */
const PALETA = ['#4f46e5', '#0f766e', '#a21caf', '#c2410c', '#0369a1', '#7c3aed', '#be185d', '#155e75', '#57534e', '#475569']

export function colorCampo(indice: number): string {
  return PALETA[indice % PALETA.length]
}

export function tieneZonaValor(r: { x?: number | null; y?: number | null; ancho?: number | null; alto?: number | null }): boolean {
  return r.x != null && r.y != null && !!r.ancho && !!r.alto
}
