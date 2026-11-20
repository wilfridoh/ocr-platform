import { Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/api'
import type { FlujoCaptura } from '@/tipos'
import CargandoIndicador from '@/componentes/CargandoIndicador'
import MensajeError from '@/componentes/MensajeError'
import SinPermiso from '@/componentes/SinPermiso'
import Interruptor from '@/componentes/Interruptor'
import { Icono } from '@/componentes/Iconos'
import { rolMayor } from '@/utilidades/roles'
import { useYo } from '@/utilidades/useYo'

export default function Flujos() {
  const queryClient = useQueryClient()
  const { rol, cargando, puede } = useYo()
  const habilitado = puede('Editor')

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['flujos', 'todos'],
    queryFn: () => api.listarFlujos(true),
    enabled: habilitado,
  })

  const cambiarEstado = useMutation({
    mutationFn: ({ id, activo }: { id: number; activo: boolean }) => api.cambiarEstadoFlujo(id, activo),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['flujos'] }),
  })

  if (cargando) return <CargandoIndicador />
  if (!habilitado) return <SinPermiso requiere="Editor" rolActual={rol} />

  /** Un Editor no puede tocar un flujo cuyo rol mínimo de edición es Administrador. */
  const puedeEditar = (f: FlujoCaptura) => puede(rolMayor('Editor', f.rol_minimo_edicion))

  return (
    <div>
      <div className="mb-4 flex items-center justify-between gap-3">
        <div>
          <h2 className="text-[22px] font-bold tracking-[-0.01em] text-ink">Flujos de captura</h2>
          <p className="text-sm text-ink-3">
            Qué documentos acepta cada punto de captura y qué instrucción ve la persona que sube el archivo.
          </p>
        </div>
        <Link to="/flujos-captura/nuevo" className="boton-primario">
          <Icono nombre="mas" /> Nuevo flujo
        </Link>
      </div>

      {isLoading && <CargandoIndicador etiqueta="Cargando flujos..." />}
      {isError && <MensajeError mensaje={(error as Error).message} onReintentar={() => refetch()} />}
      {cambiarEstado.isError && <MensajeError mensaje={(cambiarEstado.error as Error).message} />}

      {data && data.length === 0 && (
        <div className="tarjeta px-5 py-14 text-center">
          <div className="mx-auto mb-4 grid h-16 w-16 place-items-center rounded-[18px] bg-brand-soft text-brand">
            <Icono nombre="flujos" tamano={30} />
          </div>
          <h3 className="mb-1.5 text-lg font-semibold text-ink">Todavía no hay flujos de captura</h3>
          <p className="mx-auto mb-5 max-w-[420px] text-ink-3">
            Un flujo limita qué tipos de documento acepta un punto de captura, por ejemplo «solo la cédula».
          </p>
          <Link to="/flujos-captura/nuevo" className="boton-primario">
            Crear el primer flujo
          </Link>
        </div>
      )}

      {data && data.length > 0 && (
        <div className="tarjeta overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-left">
              <tr>
                <th className="px-3 py-2">Flujo</th>
                <th className="px-3 py-2">Plantillas permitidas</th>
                <th className="px-3 py-2">Acepta</th>
                <th className="px-3 py-2">Activo</th>
                <th className="px-3 py-2">Acciones</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line-2">
              {data.map((f) => {
                const editable = puedeEditar(f)
                return (
                  <tr key={f.id} className={f.activo ? '' : 'opacity-70'}>
                    <td className="px-3 py-[11px]">
                      <div className="flex items-center gap-2 font-semibold text-ink">
                        {f.nombre}
                        {f.acceso_publico && (
                          <span className="chip chip-warn" title="Cualquier persona con el enlace puede subir documentos sin clave">
                            Público
                          </span>
                        )}
                      </div>
                      <div className="font-mono text-[12px] text-ink-3">{f.codigo}</div>
                    </td>
                    <td className="px-3 py-[11px]">
                      <div className="flex flex-wrap gap-1.5">
                        {f.plantillas.map((p) => (
                          <span key={p.id} className={`chip ${p.activa ? 'chip-marca' : ''}`} title={p.activa ? undefined : 'Plantilla inactiva'}>
                            {p.codigo}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="px-3 py-[11px]">
                      <div className="flex flex-wrap gap-1.5">
                        {f.acepta_camara && (
                          <span className="chip">
                            <Icono nombre="camara" tamano={12} /> Cámara
                          </span>
                        )}
                        <span className="chip">{f.acepta_pdf ? 'Imagen y PDF' : 'Solo imagen'}</span>
                      </div>
                    </td>
                    <td className="px-3 py-[11px]">
                      <div className="flex items-center gap-2">
                        <Interruptor
                          activo={f.activo}
                          etiqueta={`${f.activo ? 'Desactivar' : 'Activar'} el flujo ${f.nombre}`}
                          deshabilitado={!editable || cambiarEstado.isPending}
                          titulo={editable ? undefined : `Solo ${f.rol_minimo_edicion} puede cambiarlo`}
                          onCambio={(activo) => cambiarEstado.mutate({ id: f.id, activo })}
                        />
                        <span className={f.activo ? 'chip chip-ok' : 'text-xs text-ink-3'}>{f.activo ? 'Activo' : 'Inactivo'}</span>
                      </div>
                    </td>
                    <td className="px-3 py-[11px]">
                      <div className="flex items-center gap-3 whitespace-nowrap">
                        {editable ? (
                          <Link to={`/flujos-captura/${f.id}`} className="inline-flex items-center gap-1 text-brand hover:underline" aria-label={`Editar ${f.nombre}`}>
                            <Icono nombre="editar" tamano={14} /> Editar
                          </Link>
                        ) : (
                          <span className="chip" title={`Solo ${f.rol_minimo_edicion} puede editar este flujo`}>
                            <Icono nombre="candado" tamano={12} /> {f.rol_minimo_edicion}
                          </span>
                        )}
                        {f.activo && (
                          <Link to={`/procesar/${f.codigo}`} className="text-brand hover:underline">
                            Abrir
                          </Link>
                        )}
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
