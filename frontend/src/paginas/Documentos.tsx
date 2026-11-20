import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/api'
import type { EstadoDocumento, FiltrosDocumentos } from '@/tipos'
import InsigniaEstado from '@/componentes/InsigniaEstado'
import CargandoIndicador from '@/componentes/CargandoIndicador'
import MensajeError from '@/componentes/MensajeError'
import PanelPurga from '@/componentes/PanelPurga'
import { useYo } from '@/utilidades/useYo'
import { formatearFecha, formatearPorcentaje } from '@/utilidades/formato'

const TAMANO_PAGINA = 10

export default function Documentos() {
  const [filtros, setFiltros] = useState<FiltrosDocumentos>({ pagina: 1, tamano: TAMANO_PAGINA })
  const queryClient = useQueryClient()
  const { puede } = useYo()
  const [panelPurga, setPanelPurga] = useState(false)

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['documentos', filtros],
    queryFn: () => api.listarDocumentos(filtros),
  })

  const reprocesar = useMutation({
    mutationFn: (id: string) => api.reprocesarDocumento(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['documentos'] }),
  })

  const actualizarFiltro = (parcial: Partial<FiltrosDocumentos>) =>
    setFiltros((f) => ({ ...f, ...parcial, pagina: 1 }))

  const totalPaginas = data ? Math.max(1, Math.ceil(data.total / (filtros.tamano ?? TAMANO_PAGINA))) : 1

  return (
    <div>
      <div className="mb-4 flex items-center justify-between gap-3">
        <h2 className="text-[22px] font-bold tracking-[-0.01em] text-ink">Documentos</h2>
        {puede('Administrador') && (
          <button type="button" className="boton-secundario" aria-expanded={panelPurga} onClick={() => setPanelPurga((v) => !v)}>
            Retención y purga
          </button>
        )}
      </div>

      {panelPurga && puede('Administrador') && <PanelPurga onCerrar={() => setPanelPurga(false)} />}

      <div className="tarjeta mb-4 flex flex-wrap gap-3 p-4">
        <div>
          <label className="etiqueta-campo">Tipo</label>
          <input
            className="campo-entrada"
            placeholder="código de plantilla"
            value={filtros.tipo ?? ''}
            onChange={(e) => actualizarFiltro({ tipo: e.target.value || undefined })}
          />
        </div>
        <div>
          <label className="etiqueta-campo">Estado</label>
          <select
            className="campo-entrada"
            value={filtros.estado ?? ''}
            onChange={(e) => actualizarFiltro({ estado: (e.target.value || undefined) as EstadoDocumento | undefined })}
          >
            <option value="">Todos</option>
            <option value="RECIBIDO">Recibido</option>
            <option value="PROCESANDO">Procesando</option>
            <option value="COMPLETADO">Completado</option>
            <option value="ERROR">Error</option>
            <option value="NO_COINCIDE">No coincide</option>
          </select>
        </div>
        <div>
          <label className="etiqueta-campo">Desde</label>
          <input
            type="date"
            className="campo-entrada"
            value={filtros.desde ?? ''}
            onChange={(e) => actualizarFiltro({ desde: e.target.value || undefined })}
          />
        </div>
        <div>
          <label className="etiqueta-campo">Hasta</label>
          <input
            type="date"
            className="campo-entrada"
            value={filtros.hasta ?? ''}
            onChange={(e) => actualizarFiltro({ hasta: e.target.value || undefined })}
          />
        </div>
      </div>

      {isLoading && <CargandoIndicador etiqueta="Cargando documentos..." />}
      {isError && <MensajeError mensaje={(error as Error).message} onReintentar={() => refetch()} />}

      {data && (
        <>
          <div className="tarjeta overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-3 py-2">Fecha</th>
                  <th className="px-3 py-2">Archivo</th>
                  <th className="px-3 py-2">Tipo</th>
                  <th className="px-3 py-2">Confianza</th>
                  <th className="px-3 py-2">Estado</th>
                  <th className="px-3 py-2">Acciones</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data.items.map((d) => (
                  <tr key={d.id}>
                    <td className="whitespace-nowrap px-3 py-2 tabular-nums text-ink-3">{formatearFecha(d.fecha)}</td>
                    <td className="px-3 py-2 font-medium text-slate-700">{d.archivo}</td>
                    <td className="px-3 py-2 text-slate-600">{d.tipo ?? '—'}</td>
                    <td className="px-3 py-2 text-slate-600">{formatearPorcentaje(d.confianza)}</td>
                    <td className="px-3 py-2">
                      <InsigniaEstado estado={d.estado} />
                    </td>
                    <td className="px-3 py-2">
                      <div className="flex gap-3">
                        <Link to={`/documentos/${d.id}`} className="text-indigo-600 hover:underline">
                          Ver
                        </Link>
                        <button
                          type="button"
                          className="text-indigo-600 hover:underline disabled:text-slate-300"
                          disabled={reprocesar.isPending}
                          onClick={() => reprocesar.mutate(d.id)}
                        >
                          Reprocesar
                        </button>
                        <a
                          href={`/api/documentos/${d.id}/archivo`}
                          className="text-indigo-600 hover:underline"
                          target="_blank"
                          rel="noreferrer"
                        >
                          Descargar
                        </a>
                      </div>
                    </td>
                  </tr>
                ))}
                {data.items.length === 0 && (
                  <tr>
                    <td colSpan={6} className="px-3 py-8 text-center text-slate-400">
                      No hay documentos que coincidan con los filtros.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          <div className="mt-3 flex items-center justify-between text-sm text-slate-500">
            <span>
              Página {filtros.pagina ?? 1} de {totalPaginas} · {data.total} documentos
            </span>
            <div className="flex gap-2">
              <button
                type="button"
                className="boton-secundario"
                disabled={(filtros.pagina ?? 1) <= 1}
                onClick={() => setFiltros((f) => ({ ...f, pagina: (f.pagina ?? 1) - 1 }))}
              >
                Anterior
              </button>
              <button
                type="button"
                className="boton-secundario"
                disabled={(filtros.pagina ?? 1) >= totalPaginas}
                onClick={() => setFiltros((f) => ({ ...f, pagina: (f.pagina ?? 1) + 1 }))}
              >
                Siguiente
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
