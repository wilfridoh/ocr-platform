import { useRef, useState } from 'react'

type Esquina = [number, number]

interface Props {
  /** Imagen ORIGINAL de la página (las esquinas son relativas a ella) */
  src: string | null
  inicial: Esquina[] | null
  enCurso: boolean
  error?: string | null
  onConfirmar: (esquinas: Esquina[]) => void
  onCancelar: () => void
}

const NOMBRES = ['arriba-izquierda', 'arriba-derecha', 'abajo-derecha', 'abajo-izquierda']
const POR_DEFECTO: Esquina[] = [
  [0.08, 0.08],
  [0.92, 0.08],
  [0.92, 0.92],
  [0.08, 0.92],
]

/** 4 manijas sobre la imagen original, en orden arriba-izq, arriba-der, abajo-der, abajo-izq (docs/13 §4.2). */
export default function AjusteEsquinas({ src, inicial, enCurso, error, onConfirmar, onCancelar }: Props) {
  const ref = useRef<HTMLDivElement>(null)
  const [esquinas, setEsquinas] = useState<Esquina[]>(inicial && inicial.length === 4 ? inicial : POR_DEFECTO)
  const [arrastrando, setArrastrando] = useState<number | null>(null)

  const mover = (e: React.PointerEvent) => {
    if (arrastrando === null || !ref.current) return
    const r = ref.current.getBoundingClientRect()
    const x = Math.min(1, Math.max(0, (e.clientX - r.left) / r.width))
    const y = Math.min(1, Math.max(0, (e.clientY - r.top) / r.height))
    setEsquinas((es) => es.map((p, i) => (i === arrastrando ? [Math.round(x * 10000) / 10000, Math.round(y * 10000) / 10000] : p)))
  }

  return (
    <div className="tarjeta overflow-hidden">
      <div className="border-b border-slate-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
        Arrastra cada manija a una esquina de la tarjeta en la foto original. El orden importa: 1 arriba-izquierda, 2
        arriba-derecha, 3 abajo-derecha y 4 abajo-izquierda.
      </div>
      <div
        ref={ref}
        className="relative select-none bg-slate-100"
        style={{ touchAction: 'none' }}
        onPointerMove={mover}
        onPointerUp={() => setArrastrando(null)}
        onPointerCancel={() => setArrastrando(null)}
      >
        {src ? <img src={src} alt="Página original" className="block w-full" draggable={false} /> : <div className="h-72" />}
        <svg className="pointer-events-none absolute inset-0 h-full w-full" viewBox="0 0 1 1" preserveAspectRatio="none">
          <polygon
            points={esquinas.map((p) => p.join(',')).join(' ')}
            fill="rgba(79,70,229,.12)"
            stroke="#4f46e5"
            strokeWidth={0.004}
            vectorEffect="non-scaling-stroke"
          />
        </svg>
        {esquinas.map((p, i) => (
          <button
            key={i}
            type="button"
            aria-label={`Esquina ${i + 1}: ${NOMBRES[i]}`}
            title={`${i + 1}: ${NOMBRES[i]}`}
            disabled={enCurso}
            onPointerDown={(e) => {
              try {
                ;(e.target as Element).setPointerCapture?.(e.pointerId)
              } catch {
                /* sin captura: se sigue arrastrando dentro de la imagen */
              }
              setArrastrando(i)
            }}
            className="absolute flex h-7 w-7 -translate-x-1/2 -translate-y-1/2 cursor-grab items-center justify-center rounded-full border-2 border-white bg-indigo-600 text-xs font-bold text-white shadow"
            style={{ left: `${p[0] * 100}%`, top: `${p[1] * 100}%` }}
          >
            {i + 1}
          </button>
        ))}
        {enCurso && (
          <div className="absolute inset-0 flex items-center justify-center bg-white/70 text-sm font-medium text-slate-700">
            Recortando… (unos segundos)
          </div>
        )}
      </div>
      {error && (
        <div role="alert" className="border-t border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          <b>No se pudo aplicar el recorte.</b> {error}
        </div>
      )}
      <div className="flex justify-end gap-2 border-t border-slate-200 px-3 py-2">
        <button type="button" className="boton-secundario" onClick={onCancelar} disabled={enCurso}>
          Cancelar
        </button>
        <button type="button" className="boton-primario" onClick={() => onConfirmar(esquinas)} disabled={enCurso}>
          Confirmar recorte
        </button>
      </div>
    </div>
  )
}
