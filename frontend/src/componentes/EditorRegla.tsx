import { useState } from 'react'
import type { CajaRelativa, MetodoRegla, Regla } from '@/tipos'
import VisorPagina from './VisorPagina'

interface Props {
  regla: Regla
  onCambiar: (regla: Regla) => void
  /** Imagen de la página de ejemplo, para anclar con clic o dibujar zona */
  imagenSrc?: string | null
  /** Valor que capturaría la regla sobre el texto de ejemplo, para la vista en vivo */
  valorEnVivo?: string | null
}

const PESTANAS: { id: MetodoRegla; etiqueta: string }[] = [
  { id: 'ancla', etiqueta: 'Ancla' },
  { id: 'regex', etiqueta: 'Regex' },
  { id: 'zona', etiqueta: 'Zona' },
]

export default function EditorRegla({ regla, onCambiar, imagenSrc, valorEnVivo }: Props) {
  const [pestana, setPestana] = useState<MetodoRegla>(regla.metodo)

  const cambiarMetodo = (metodo: MetodoRegla) => {
    setPestana(metodo)
    if (metodo === regla.metodo) return
    // las zonas marcadas en la cuadrícula (valor y etiqueta) no dependen del método: se conservan al cambiarlo
    const { x, y, ancho, alto, pagina, zona_etiqueta } = regla
    const zonas = { x, y, ancho, alto, pagina, zona_etiqueta }
    if (metodo === 'ancla') onCambiar({ ...zonas, metodo: 'ancla', ancla: '', regex: '' })
    else if (metodo === 'regex') onCambiar({ ...zonas, metodo: 'regex', regex: '' })
    else
      onCambiar({
        metodo: 'zona',
        pagina: pagina ?? 1,
        x: x ?? 0.1,
        y: y ?? 0.1,
        ancho: ancho ?? 0.3,
        alto: alto ?? 0.05,
        zona_etiqueta,
      })
  }

  return (
    <div>
      <div className="mb-3 flex gap-1 rounded-md bg-slate-100 p-1 text-sm">
        {PESTANAS.map((p) => (
          <button
            key={p.id}
            type="button"
            onClick={() => cambiarMetodo(p.id)}
            className={`flex-1 rounded-md px-3 py-1.5 font-medium transition-colors ${
              pestana === p.id ? 'bg-white text-indigo-700 shadow-sm' : 'text-slate-500 hover:text-slate-700'
            }`}
          >
            {p.etiqueta}
          </button>
        ))}
      </div>

      {regla.metodo === 'ancla' && (
        <div className="space-y-3">
          <div>
            <label className="etiqueta-campo">Texto ancla (precede al dato)</label>
            <input
              className="campo-entrada"
              placeholder='Ej: "N° Cliente"'
              value={regla.ancla}
              onChange={(e) => onCambiar({ ...regla, ancla: e.target.value })}
            />
            <p className="mt-1 text-xs text-slate-400">
              También puedes hacer clic sobre el texto en la imagen si el documento de ejemplo está disponible.
            </p>
          </div>
          <div>
            <label className="etiqueta-campo">Regex opcional (filtra lo que sigue al ancla)</label>
            <input
              className="campo-entrada font-mono"
              placeholder="[\\d.-]+"
              value={regla.regex ?? ''}
              onChange={(e) => onCambiar({ ...regla, regex: e.target.value })}
            />
          </div>
        </div>
      )}

      {regla.metodo === 'regex' && (
        <div>
          <label className="etiqueta-campo">Expresión regular (el grupo 1 es el valor)</label>
          <input
            className="campo-entrada font-mono"
            placeholder="Total a pagar\\s*\\$?\\s*([\\d.,]+)"
            value={regla.regex}
            onChange={(e) => onCambiar({ ...regla, regex: e.target.value })}
          />
        </div>
      )}

      {regla.metodo === 'zona' && (
        <div className="space-y-3">
          <p className="text-xs text-slate-500">Dibuja el rectángulo sobre la imagen donde está el dato.</p>
          <VisorPagina
            src={imagenSrc ?? null}
            alturaMaxima={360}
            modoDibujo
            cajas={[{ id: 'actual', x: regla.x, y: regla.y, ancho: regla.ancho, alto: regla.alto, color: '#4f46e5' }]}
            onZonaDibujada={(zona: CajaRelativa) => onCambiar({ ...regla, ...zona })}
          />
          <div className="grid grid-cols-4 gap-2 text-xs">
            <span>x: {regla.x.toFixed(2)}</span>
            <span>y: {regla.y.toFixed(2)}</span>
            <span>ancho: {regla.ancho.toFixed(2)}</span>
            <span>alto: {regla.alto.toFixed(2)}</span>
          </div>
        </div>
      )}

      {valorEnVivo !== undefined && valorEnVivo !== null && (
        <div className="mt-3 rounded-md bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
          Valor capturado: <span className="font-mono font-medium">{valorEnVivo || '(sin coincidencia)'}</span>
        </div>
      )}
    </div>
  )
}
