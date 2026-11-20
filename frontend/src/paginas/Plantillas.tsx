import { Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/api'
import CargandoIndicador from '@/componentes/CargandoIndicador'
import MensajeError from '@/componentes/MensajeError'
import { Icono } from '@/componentes/Iconos'
import { rolMayor } from '@/utilidades/roles'
import { useYo } from '@/utilidades/useYo'

export default function Plantillas() {
  const queryClient = useQueryClient()
  const { puede } = useYo()
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['plantillas'],
    queryFn: () => api.listarPlantillas(),
  })

  const cambiarEstado = useMutation({
    mutationFn: ({ id, activa }: { id: number; activa: boolean }) => api.cambiarEstadoPlantilla(id, activa),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['plantillas'] }),
  })

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-[22px] font-bold tracking-[-0.01em] text-ink">Plantillas</h2>
        {puede('Editor') && (
          <Link to="/plantillas/nueva" className="boton-primario">
            <Icono nombre="mas" /> Nueva
          </Link>
        )}
      </div>

      {isLoading && <CargandoIndicador etiqueta="Cargando plantillas..." />}
      {isError && <MensajeError mensaje={(error as Error).message} onReintentar={() => refetch()} />}

      {data && data.length === 0 && (
        <div className="tarjeta p-10 text-center">
          <p className="mb-4 text-slate-500">Todavía no hay plantillas registradas.</p>
          <Link to="/plantillas/nueva" className="boton-primario">
            Crear la primera plantilla
          </Link>
        </div>
      )}

      {data && data.length > 0 && (
        <div className="tarjeta overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-3 py-2">Código</th>
                <th className="px-3 py-2">Campos</th>
                <th className="px-3 py-2">Docs</th>
                <th className="px-3 py-2">Activa</th>
                {puede('Editor') && <th className="px-3 py-2">Acciones</th>}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {data.map((p) => (
                <tr key={p.id}>
                  <td className="px-3 py-2">
                    <div className="font-medium text-slate-800">{p.codigo}</div>
                    <div className="text-xs text-slate-400">{p.nombre}</div>
                  </td>
                  <td className="px-3 py-2 text-slate-600">{p.campos.length}</td>
                  <td className="px-3 py-2 text-slate-600">{p.total_documentos ?? 0}</td>
                  <td className="px-3 py-2">
                    {p.activa ? (
                      <span className="chip chip-ok">Activa</span>
                    ) : (
                      <span className="text-xs text-ink-3">Inactiva</span>
                    )}
                  </td>
                  {puede('Editor') && (
                    <td className="px-3 py-2">
                      {puede(rolMayor('Editor', p.rol_minimo_edicion ?? 'Editor')) ? (
                        <div className="flex items-center gap-3">
                          <Link to={`/plantillas/${p.id}`} className="inline-flex items-center gap-1 text-brand hover:underline" aria-label={`Editar ${p.codigo}`}>
                            <Icono nombre="editar" tamano={14} /> Editar
                          </Link>
                          <button
                            type="button"
                            className="text-brand hover:underline disabled:text-ink-3"
                            disabled={cambiarEstado.isPending}
                            onClick={() => cambiarEstado.mutate({ id: p.id, activa: !p.activa })}
                          >
                            {p.activa ? 'Desactivar' : 'Activar'}
                          </button>
                        </div>
                      ) : (
                        <span className="chip" title={`Solo ${p.rol_minimo_edicion} puede editar esta plantilla`}>
                          <Icono nombre="candado" tamano={12} /> {p.rol_minimo_edicion}
                        </span>
                      )}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
