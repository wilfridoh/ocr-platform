import { useState } from 'react'
import type { PalabraClave } from '@/tipos'

interface Props {
  valor: PalabraClave[]
  onCambiar: (valor: PalabraClave[]) => void
}

export default function EditorPalabrasClave({ valor, onCambiar }: Props) {
  const [texto, setTexto] = useState('')

  const agregar = () => {
    const limpio = texto.trim().toLowerCase()
    if (!limpio) return
    if (valor.some((p) => p.texto === limpio)) {
      setTexto('')
      return
    }
    onCambiar([...valor, { texto: limpio, peso: 3 }])
    setTexto('')
  }

  const quitar = (texto_: string) => onCambiar(valor.filter((p) => p.texto !== texto_))

  const cambiarPeso = (texto_: string, peso: number) =>
    onCambiar(valor.map((p) => (p.texto === texto_ ? { ...p, peso } : p)))

  return (
    <div>
      <div className="mb-3 flex gap-2">
        <input
          className="campo-entrada"
          placeholder="Agregar palabra o frase clave"
          value={texto}
          onChange={(e) => setTexto(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault()
              agregar()
            }
          }}
        />
        <button type="button" className="boton-secundario" onClick={agregar}>
          Agregar
        </button>
      </div>

      {valor.length === 0 ? (
        <p className="text-sm text-slate-400">Sin palabras clave todavía.</p>
      ) : (
        <ul className="divide-y divide-slate-100 rounded-md border border-slate-200">
          {valor.map((p) => (
            <li key={p.texto} className="flex items-center gap-3 px-3 py-2">
              <span className="flex-1 text-sm text-slate-700">{p.texto}</span>
              <label className="flex items-center gap-2 text-xs text-slate-500">
                Peso
                <input
                  type="range"
                  min={1}
                  max={5}
                  value={p.peso}
                  onChange={(e) => cambiarPeso(p.texto, Number(e.target.value))}
                />
                <span className="w-4 text-center font-medium text-slate-700">{p.peso}</span>
              </label>
              <button
                type="button"
                onClick={() => quitar(p.texto)}
                className="text-slate-400 hover:text-red-600"
                aria-label={`Quitar ${p.texto}`}
              >
                ✕
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
