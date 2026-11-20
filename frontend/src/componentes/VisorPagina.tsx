import { useCallback, useRef, useState } from 'react'
import type { CajaRelativa } from '@/tipos'

export interface CajaResaltada extends CajaRelativa {
  id: string
  color?: string
  etiqueta?: string
}

interface Props {
  /** URL de la imagen de la página (objectURL o ruta del API) */
  src: string | null
  /** Cajas a mostrar siempre (p. ej. el campo bajo el mouse en la tabla) */
  cajas?: CajaResaltada[]
  /** Si se indica, el usuario puede dibujar una zona arrastrando el mouse */
  modoDibujo?: boolean
  /** Se llama con la zona relativa (0-1) recién dibujada */
  onZonaDibujada?: (zona: CajaRelativa) => void
  alturaMaxima?: number
}

export default function VisorPagina({ src, cajas = [], modoDibujo = false, onZonaDibujada, alturaMaxima = 640 }: Props) {
  const contenedorRef = useRef<HTMLDivElement>(null)
  const [inicio, setInicio] = useState<{ x: number; y: number } | null>(null)
  const [actual, setActual] = useState<{ x: number; y: number } | null>(null)

  const posicionRelativa = useCallback((clientX: number, clientY: number) => {
    const rect = contenedorRef.current?.getBoundingClientRect()
    if (!rect) return { x: 0, y: 0 }
    const x = Math.min(1, Math.max(0, (clientX - rect.left) / rect.width))
    const y = Math.min(1, Math.max(0, (clientY - rect.top) / rect.height))
    return { x, y }
  }, [])

  const alMouseDown: React.MouseEventHandler<HTMLDivElement> = (e) => {
    if (!modoDibujo) return
    const p = posicionRelativa(e.clientX, e.clientY)
    setInicio(p)
    setActual(p)
  }

  const alMouseMove: React.MouseEventHandler<HTMLDivElement> = (e) => {
    if (!modoDibujo || !inicio) return
    setActual(posicionRelativa(e.clientX, e.clientY))
  }

  const terminarDibujo = () => {
    if (!modoDibujo || !inicio || !actual) return
    const x = Math.min(inicio.x, actual.x)
    const y = Math.min(inicio.y, actual.y)
    const ancho = Math.abs(actual.x - inicio.x)
    const alto = Math.abs(actual.y - inicio.y)
    setInicio(null)
    setActual(null)
    if (ancho > 0.005 && alto > 0.005) {
      onZonaDibujada?.({ x, y, ancho, alto })
    }
  }

  const zonaEnCurso =
    inicio && actual
      ? {
          x: Math.min(inicio.x, actual.x),
          y: Math.min(inicio.y, actual.y),
          ancho: Math.abs(actual.x - inicio.x),
          alto: Math.abs(actual.y - inicio.y),
        }
      : null

  return (
    <div className="tarjeta overflow-x-auto">
      <div
        ref={contenedorRef}
        className="relative select-none bg-slate-100"
        style={{ maxHeight: alturaMaxima, overflow: 'auto', cursor: modoDibujo ? 'crosshair' : 'default' }}
        onMouseDown={alMouseDown}
        onMouseMove={alMouseMove}
        onMouseUp={terminarDibujo}
        onMouseLeave={() => {
          if (inicio) terminarDibujo()
        }}
      >
        {src ? (
          <img src={src} alt="Página del documento" className="block w-full" draggable={false} />
        ) : (
          <div className="flex h-64 items-center justify-center text-sm text-slate-400">Sin vista previa</div>
        )}

        {cajas.map((c) => (
          <div
            key={c.id}
            title={c.etiqueta}
            className="pointer-events-none absolute rounded-sm border-2"
            style={{
              left: `${c.x * 100}%`,
              top: `${c.y * 100}%`,
              width: `${c.ancho * 100}%`,
              height: `${c.alto * 100}%`,
              borderColor: c.color ?? '#4f46e5',
              backgroundColor: `${c.color ?? '#4f46e5'}22`,
            }}
          />
        ))}

        {zonaEnCurso && (
          <div
            className="pointer-events-none absolute border-2 border-dashed border-indigo-600 bg-indigo-600/10"
            style={{
              left: `${zonaEnCurso.x * 100}%`,
              top: `${zonaEnCurso.y * 100}%`,
              width: `${zonaEnCurso.ancho * 100}%`,
              height: `${zonaEnCurso.alto * 100}%`,
            }}
          />
        )}
      </div>
      {modoDibujo && (
        <p className="border-t border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-500">
          Dibuja un rectángulo sobre el dato que quieres extraer.
        </p>
      )}
    </div>
  )
}
