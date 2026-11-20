import { useState } from 'react'
import type { Campo, Regla, TipoDato } from '@/tipos'
import { ETIQUETAS_TIPO_DATO, TIPOS_DATO } from '@/tipos'
import EditorRegla from './EditorRegla'

interface Props {
  campos: Campo[]
  onCambiar: (campos: Campo[]) => void
  imagenSrc?: string | null
}

function campoVacio(): Campo {
  return {
    nombre: '',
    etiqueta: '',
    tipo_dato: 'texto',
    obligatorio: false,
    regla: { metodo: 'regex', regex: '' },
  }
}

export default function EditorCampos({ campos, onCambiar, imagenSrc }: Props) {
  const [expandido, setExpandido] = useState<number | null>(campos.length > 0 ? 0 : null)

  const actualizar = (idx: number, parcial: Partial<Campo>) =>
    onCambiar(campos.map((c, i) => (i === idx ? { ...c, ...parcial } : c)))

  const actualizarRegla = (idx: number, regla: Regla) => actualizar(idx, { regla })

  const agregar = () => {
    onCambiar([...campos, campoVacio()])
    setExpandido(campos.length)
  }

  const quitar = (idx: number) => {
    onCambiar(campos.filter((_, i) => i !== idx))
    setExpandido(null)
  }

  return (
    <div className="space-y-3">
      {campos.map((c, idx) => (
        <div key={idx} className="tarjeta overflow-x-auto">
          <button
            type="button"
            onClick={() => setExpandido(expandido === idx ? null : idx)}
            className="flex w-full items-center justify-between px-4 py-3 text-left"
          >
            <span className="text-sm font-medium text-slate-700">
              {c.etiqueta || c.nombre || `Campo ${idx + 1}`}
              {c.obligatorio && <span className="ml-1 text-red-500">*</span>}
              <span className="ml-2 text-xs text-slate-400">({ETIQUETAS_TIPO_DATO[c.tipo_dato]} · {c.regla.metodo})</span>
            </span>
            <span className="text-slate-400">{expandido === idx ? '▲' : '▼'}</span>
          </button>

          {expandido === idx && (
            <div className="space-y-4 border-t border-slate-100 p-4">
              <div className="grid gap-3 sm:grid-cols-2">
                <div>
                  <label className="etiqueta-campo">Nombre interno (snake_case)</label>
                  <input
                    className="campo-entrada font-mono"
                    value={c.nombre}
                    onChange={(e) => actualizar(idx, { nombre: e.target.value })}
                    placeholder="numero_cliente"
                  />
                </div>
                <div>
                  <label className="etiqueta-campo">Etiqueta visible</label>
                  <input
                    className="campo-entrada"
                    value={c.etiqueta}
                    onChange={(e) => actualizar(idx, { etiqueta: e.target.value })}
                    placeholder="Número de cliente"
                  />
                </div>
                <div>
                  <label className="etiqueta-campo">Tipo de dato</label>
                  <select
                    className="campo-entrada"
                    value={c.tipo_dato}
                    onChange={(e) => actualizar(idx, { tipo_dato: e.target.value as TipoDato })}
                  >
                    {TIPOS_DATO.map((t) => (
                      <option key={t} value={t}>
                        {ETIQUETAS_TIPO_DATO[t]}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="flex items-end">
                  <label className="flex items-center gap-2 text-sm text-slate-700">
                    <input
                      type="checkbox"
                      checked={c.obligatorio}
                      onChange={(e) => actualizar(idx, { obligatorio: e.target.checked })}
                    />
                    Obligatorio
                  </label>
                </div>
              </div>

              <div>
                <label className="etiqueta-campo">Regla de extracción</label>
                <EditorRegla regla={c.regla} onCambiar={(r) => actualizarRegla(idx, r)} imagenSrc={imagenSrc} />
              </div>

              <button type="button" className="boton-peligro" onClick={() => quitar(idx)}>
                Eliminar campo
              </button>
            </div>
          )}
        </div>
      ))}

      <button type="button" className="boton-secundario" onClick={agregar}>
        + Agregar campo
      </button>
    </div>
  )
}
