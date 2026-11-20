import { useRef, useState } from 'react'
import type { PalabraPosicion, ZonaRelativa } from '@/tipos'
import { ajustarACeldas, celdaEn, CONFIANZA_BAJA, palabraEn, type Densidad } from '@/utilidades/cuadricula'

export interface ZonaDibujo {
  id: string
  zona: ZonaRelativa
  tipo: 'valor' | 'etiqueta'
  color: string
  etiqueta: string
  atenuada?: boolean
}

interface Props {
  src: string | null
  densidad: Densidad
  mostrarRejilla: boolean
  zonas: ZonaDibujo[]
  palabras: PalabraPosicion[]
  herramienta: 'dibujar' | 'borrar'
  /** Sin recorte fiable: no se dibuja hasta confirmar o "usar de todos modos" */
  bloqueado?: boolean
  /** `palabra`: si la zona salió de un clic sobre una palabra (su texto sirve de texto esperado de una etiqueta) */
  onZona: (zona: ZonaRelativa, palabra?: PalabraPosicion) => void
  onBorrar: (id: string) => void
}

type Punto = { x: number; y: number }

/**
 * La página enderezada con la rejilla encima. Arrastrar marca un rectángulo ajustado a las celdas; un clic sobre una
 * palabra marca las celdas que ocupa esa palabra, y un clic en vacío, una celda. Con "borrar", un clic quita la zona.
 * Funciona con mouse, lápiz y dedo (pointer events; el desplazamiento táctil se bloquea solo sobre el lienzo).
 */
export default function LienzoCuadricula({ src, densidad, mostrarRejilla, zonas, palabras, herramienta, bloqueado, onZona, onBorrar }: Props) {
  const ref = useRef<HTMLDivElement>(null)
  const [inicio, setInicio] = useState<Punto | null>(null)
  // el punto inicial también en una ref: pointerup puede llegar antes de que React vuelva a pintar
  const inicioRef = useRef<Punto | null>(null)
  const [actual, setActual] = useState<Punto | null>(null)

  const relativo = (e: React.PointerEvent): Punto => {
    const r = ref.current!.getBoundingClientRect()
    return { x: Math.min(1, Math.max(0, (e.clientX - r.left) / r.width)), y: Math.min(1, Math.max(0, (e.clientY - r.top) / r.height)) }
  }

  const alPresionar = (e: React.PointerEvent) => {
    if (bloqueado || herramienta !== 'dibujar' || !src) return
    try {
      ;(e.target as Element).setPointerCapture?.(e.pointerId)
    } catch {
      /* sin captura (puntero ya liberado): el arrastre sigue funcionando dentro del lienzo */
    }
    const p = relativo(e)
    inicioRef.current = p
    setInicio(p)
    setActual(p)
  }
  const alMover = (e: React.PointerEvent) => {
    if (inicioRef.current) setActual(relativo(e))
  }
  const alSoltar = (e: React.PointerEvent) => {
    const inicio = inicioRef.current
    inicioRef.current = null
    if (!inicio) return
    const actual = relativo(e)
    const ancho = Math.abs(actual.x - inicio.x)
    const alto = Math.abs(actual.y - inicio.y)
    setInicio(null)
    setActual(null)
    if (ancho < 0.01 && alto < 0.01) {
      // clic: la palabra bajo el puntero (todas sus celdas) o la celda
      const palabra = palabraEn(palabras, inicio.x, inicio.y)
      if (palabra) onZona(ajustarACeldas({ x: palabra.x, y: palabra.y, ancho: palabra.ancho, alto: palabra.alto }, densidad), palabra)
      else onZona(celdaEn(inicio.x, inicio.y, densidad))
      return
    }
    onZona(ajustarACeldas({ x: Math.min(inicio.x, actual.x), y: Math.min(inicio.y, actual.y), ancho, alto }, densidad))
  }

  const enCurso =
    inicio && actual
      ? ajustarACeldas(
          { x: Math.min(inicio.x, actual.x), y: Math.min(inicio.y, actual.y), ancho: Math.abs(actual.x - inicio.x), alto: Math.abs(actual.y - inicio.y) },
          densidad,
        )
      : null

  const pct = (v: number) => `${v * 100}%`

  return (
    <div className="tarjeta overflow-hidden">
      <div
        ref={ref}
        className="relative select-none bg-slate-100"
        style={{ cursor: bloqueado ? 'not-allowed' : herramienta === 'borrar' ? 'pointer' : 'crosshair', touchAction: herramienta === 'dibujar' && !bloqueado ? 'none' : 'auto' }}
        onPointerDown={alPresionar}
        onPointerMove={alMover}
        onPointerUp={alSoltar}
        onPointerCancel={() => {
          inicioRef.current = null
          setInicio(null)
          setActual(null)
        }}
      >
        {src ? (
          <img src={src} alt="Documento de ejemplo recortado y enderezado" className="block w-full" draggable={false} />
        ) : (
          <div className="flex h-72 items-center justify-center text-sm text-slate-400">Elige un documento de ejemplo</div>
        )}

        {/* palabras del OCR: contorno tenue; en gris las de lectura poco confiable */}
        {src &&
          palabras.map((p, i) => (
            <div
              key={i}
              title={`${p.texto} · confianza ${Math.round(p.confianza * 100)} %`}
              className={`pointer-events-none absolute rounded-[2px] ${p.confianza < CONFIANZA_BAJA ? 'bg-slate-400/35' : 'border border-slate-400/30'}`}
              style={{ left: pct(p.x), top: pct(p.y), width: pct(p.ancho), height: pct(p.alto) }}
            />
          ))}

        {src && mostrarRejilla && (
          <div
            className="pointer-events-none absolute inset-0"
            style={{
              backgroundImage:
                'linear-gradient(to right, rgba(79,70,229,.28) 1px, transparent 1px), linear-gradient(to bottom, rgba(79,70,229,.28) 1px, transparent 1px)',
              backgroundSize: `${100 / densidad.columnas}% ${100 / densidad.filas}%`,
            }}
          />
        )}

        {zonas.map((z) => (
          <div
            key={z.id}
            onPointerDown={(e) => {
              if (herramienta !== 'borrar') return
              e.stopPropagation()
              onBorrar(z.id)
            }}
            className={`absolute rounded-sm border-2 ${herramienta === 'borrar' ? 'cursor-pointer hover:opacity-60' : 'pointer-events-none'} ${z.atenuada ? 'opacity-30' : ''}`}
            style={{
              left: pct(z.zona.x),
              top: pct(z.zona.y),
              width: pct(z.zona.ancho),
              height: pct(z.zona.alto),
              borderColor: z.color,
              borderStyle: z.tipo === 'etiqueta' ? 'dashed' : 'solid',
              background:
                z.tipo === 'etiqueta'
                  ? `repeating-linear-gradient(45deg, ${z.color}22 0 6px, transparent 6px 12px)`
                  : `${z.color}22`,
            }}
          >
            <span
              className="absolute -top-[18px] left-0 whitespace-nowrap rounded px-1 text-[10px] font-semibold leading-4 text-white"
              style={{ background: z.color }}
            >
              {z.etiqueta}
            </span>
          </div>
        ))}

        {enCurso && (
          <div
            className="pointer-events-none absolute border-2 border-dashed border-indigo-600 bg-indigo-600/15"
            style={{ left: pct(enCurso.x), top: pct(enCurso.y), width: pct(enCurso.ancho), height: pct(enCurso.alto) }}
          />
        )}

        {bloqueado && src && <div className="pointer-events-none absolute inset-0 bg-white/50" />}
      </div>
    </div>
  )
}
