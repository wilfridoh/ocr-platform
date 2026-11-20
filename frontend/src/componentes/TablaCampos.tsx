import type { Campo, CampoExtraido } from '@/tipos'
import { colorConfianza, fondoConfianza, formatearPorcentaje, formatearValorCampo } from '@/utilidades/formato'

export interface FilaCampo {
  nombre: string
  etiqueta: string
  obligatorio?: boolean
  extraido?: CampoExtraido
}

interface Props {
  filas: FilaCampo[]
  campoResaltado?: string | null
  onResaltar?: (nombre: string | null) => void
}

export function filasDesdeResultado(campos: Campo[], extraidos: Record<string, CampoExtraido>): FilaCampo[] {
  return campos.map((c) => ({
    nombre: c.nombre,
    etiqueta: c.etiqueta,
    obligatorio: c.obligatorio,
    extraido: extraidos[c.nombre],
  }))
}

export default function TablaCampos({ filas, campoResaltado, onResaltar }: Props) {
  return (
    <div className="tarjeta overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
          <tr>
            <th className="px-3 py-2">Campo</th>
            <th className="px-3 py-2">Valor</th>
            <th className="px-3 py-2">Confianza</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {filas.map((f) => {
            const faltaObligatorio = Boolean(f.obligatorio) && (!f.extraido || f.extraido.valor === null || f.extraido.valor === '')
            const confianzaBaja = (f.extraido?.confianza ?? 1) < 0.7
            const fondo = faltaObligatorio ? 'bg-err-soft/40' : confianzaBaja ? 'bg-warn-soft/40' : ''
            const activa = campoResaltado === f.nombre
            return (
              <tr
                key={f.nombre}
                onMouseEnter={() => onResaltar?.(f.nombre)}
                onMouseLeave={() => onResaltar?.(null)}
                tabIndex={0}
                onFocus={() => onResaltar?.(f.nombre)}
                onBlur={() => onResaltar?.(null)}
                className={`${fondo} ${activa ? 'ring-2 ring-inset ring-brand' : ''} cursor-default`}
              >
                <td className="px-3 py-2 font-medium text-slate-700">
                  {f.etiqueta}
                  {f.obligatorio && <span className="ml-1 text-red-500">*</span>}
                  {faltaObligatorio && (
                    <span className="ml-2 rounded bg-red-100 px-1.5 py-0.5 text-[11px] font-normal text-red-700">
                      Obligatorio faltante
                    </span>
                  )}
                </td>
                <td className="px-3 py-2 text-slate-700">{formatearValorCampo(f.extraido?.valor ?? null)}</td>
                <td className="px-3 py-2">
                  <div className={`flex items-center gap-2 whitespace-nowrap font-semibold tabular-nums ${colorConfianza(f.extraido?.confianza)}`}>
                    <span className="h-1.5 w-[54px] flex-none overflow-hidden rounded-full bg-line-2" aria-hidden>
                      <span
                        className={`block h-full rounded-full ${fondoConfianza(f.extraido?.confianza)}`}
                        style={{ width: `${Math.round(Math.max(0, Math.min(1, f.extraido?.confianza ?? 0)) * 100)}%` }}
                      />
                    </span>
                    {formatearPorcentaje(f.extraido?.confianza)}
                  </div>
                </td>
              </tr>
            )
          })}
          {filas.length === 0 && (
            <tr>
              <td colSpan={3} className="px-3 py-6 text-center text-slate-400">
                No hay campos para mostrar.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  )
}
