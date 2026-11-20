import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/api'
import { ROLES, type Rol, type Usuario, type UsuarioConClave } from '@/tipos'
import CargandoIndicador from '@/componentes/CargandoIndicador'
import MensajeError from '@/componentes/MensajeError'
import SinPermiso from '@/componentes/SinPermiso'
import Interruptor from '@/componentes/Interruptor'
import { Icono } from '@/componentes/Iconos'
import { formatearFecha } from '@/utilidades/formato'
import { useYo } from '@/utilidades/useYo'

const DESCRIPCION_ROL: Record<Rol, string> = {
  Administrador: 'Todo: plantillas, flujos, usuarios y permisos',
  Editor: 'Crea y edita plantillas y flujos; no gestiona usuarios',
  Operador: 'Solo procesa documentos y ve resultados',
}

/** Gestión de usuarios y sus API keys (docs/07 §6.4). Solo Administrador. */
export default function Usuarios() {
  const queryClient = useQueryClient()
  const { yo, rol, cargando, puede } = useYo()
  const habilitado = puede('Administrador')

  const [nombre, setNombre] = useState('')
  const [rolNuevo, setRolNuevo] = useState<Rol>('Operador')
  const [clave, setClave] = useState<UsuarioConClave | null>(null)
  const [copiada, setCopiada] = useState(false)

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['usuarios'],
    queryFn: () => api.listarUsuarios(),
    enabled: habilitado,
  })

  const refrescar = () => queryClient.invalidateQueries({ queryKey: ['usuarios'] })

  const crear = useMutation({
    mutationFn: () => api.crearUsuario({ nombre: nombre.trim(), rol: rolNuevo }),
    onSuccess: (u) => {
      setClave(u)
      setCopiada(false)
      setNombre('')
      setRolNuevo('Operador')
      void refrescar()
    },
  })

  const actualizar = useMutation({
    mutationFn: ({ id, cambios }: { id: number; cambios: { rol?: Rol; activo?: boolean } }) => api.actualizarUsuario(id, cambios),
    onSuccess: () => {
      void refrescar()
    },
  })

  const regenerar = useMutation({
    mutationFn: (id: number) => api.regenerarClaveUsuario(id),
    onSuccess: (u) => {
      setClave(u)
      setCopiada(false)
    },
  })

  if (cargando) return <CargandoIndicador />
  if (!habilitado) return <SinPermiso requiere="Administrador" rolActual={rol} />

  const copiar = async () => {
    if (!clave) return
    try {
      await navigator.clipboard.writeText(clave.api_key)
      setCopiada(true)
    } catch {
      setCopiada(false)
    }
  }

  const esYo = (u: Usuario) => yo?.usuario_id !== null && yo?.usuario_id === u.id
  const error_ = crear.error ?? actualizar.error ?? regenerar.error

  return (
    <div>
      <div className="mb-4">
        <h2 className="text-[22px] font-bold tracking-[-0.01em] text-ink">Usuarios</h2>
        <p className="text-sm text-ink-3">Cada persona o sistema entra con su propia API key y un rol.</p>
      </div>

      {clave && (
        <div className="mb-4 rounded-card border border-[#FCD34D] bg-warn-soft p-4" role="alert">
          <div className="flex items-start gap-3">
            <Icono nombre="alerta" tamano={18} className="mt-0.5 text-warn" />
            <div className="min-w-0 flex-1">
              <p className="font-semibold text-warn">API key de {clave.nombre}</p>
              <p className="mb-2 text-[13px] text-ink-2">Cópiala ahora: <b>no se volverá a mostrar</b>. Si se pierde, genera una nueva.</p>
              <div className="flex flex-wrap items-center gap-2">
                <code className="min-w-0 flex-1 break-all rounded-lg border border-line bg-white px-3 py-2 font-mono text-[12.5px] text-ink" data-testid="api-key-nueva">
                  {clave.api_key}
                </code>
                <button type="button" className="boton-secundario" onClick={copiar}>
                  <Icono nombre={copiada ? 'check' : 'copiar'} /> {copiada ? 'Copiada' : 'Copiar'}
                </button>
                <button type="button" className="boton-secundario" onClick={() => setClave(null)}>
                  Ya la guardé
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {error_ && (
        <div className="mb-4">
          <MensajeError mensaje={(error_ as Error).message} />
        </div>
      )}

      <form
        className="tarjeta mb-4"
        onSubmit={(e) => {
          e.preventDefault()
          if (nombre.trim()) crear.mutate()
        }}
      >
        <div className="border-b border-line px-4 py-3 text-[13px] font-semibold">Nuevo usuario</div>
        <div className="flex flex-wrap items-end gap-3 p-4">
          <div className="min-w-[220px] flex-1">
            <label className="etiqueta-campo" htmlFor="usuario-nombre">
              Nombre
            </label>
            <input id="usuario-nombre" className="campo-entrada" value={nombre} onChange={(e) => setNombre(e.target.value)} placeholder="Nombre de la persona o del sistema" maxLength={200} />
          </div>
          <div className="w-52">
            <label className="etiqueta-campo" htmlFor="usuario-rol">
              Rol
            </label>
            <select id="usuario-rol" className="campo-entrada" value={rolNuevo} onChange={(e) => setRolNuevo(e.target.value as Rol)}>
              {ROLES.map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </select>
          </div>
          <button type="submit" className="boton-primario" disabled={!nombre.trim() || crear.isPending}>
            <Icono nombre="mas" /> {crear.isPending ? 'Creando...' : 'Crear y generar clave'}
          </button>
        </div>
        <p className="px-4 pb-3 text-xs text-ink-3">{DESCRIPCION_ROL[rolNuevo]}.</p>
      </form>

      {isLoading && <CargandoIndicador etiqueta="Cargando usuarios..." />}
      {isError && <MensajeError mensaje={(error as Error).message} onReintentar={() => refetch()} />}

      {data && (
        <div className="tarjeta overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-left">
              <tr>
                <th className="px-3 py-2">Usuario</th>
                <th className="px-3 py-2">Rol</th>
                <th className="px-3 py-2">Activo</th>
                <th className="px-3 py-2">Creado</th>
                <th className="px-3 py-2">Clave</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line-2">
              {data.map((u) => (
                <tr key={u.id} className={u.activo ? '' : 'opacity-70'}>
                  <td className="px-3 py-[11px]">
                    <span className="font-semibold text-ink">{u.nombre}</span>
                    {esYo(u) && <span className="chip chip-marca ml-2">Tú</span>}
                  </td>
                  <td className="px-3 py-[11px]">
                    <select
                      className="campo-entrada !w-40 !py-1"
                      value={u.rol}
                      aria-label={`Rol de ${u.nombre}`}
                      disabled={esYo(u) || actualizar.isPending}
                      title={esYo(u) ? 'No puedes cambiar tu propio rol' : DESCRIPCION_ROL[u.rol]}
                      onChange={(e) => actualizar.mutate({ id: u.id, cambios: { rol: e.target.value as Rol } })}
                    >
                      {ROLES.map((r) => (
                        <option key={r} value={r}>
                          {r}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td className="px-3 py-[11px]">
                    <div className="flex items-center gap-2">
                      <Interruptor
                        activo={u.activo}
                        etiqueta={`${u.activo ? 'Desactivar' : 'Activar'} a ${u.nombre}`}
                        deshabilitado={esYo(u) || actualizar.isPending}
                        titulo={esYo(u) ? 'No puedes desactivarte a ti mismo' : undefined}
                        onCambio={(activo) => actualizar.mutate({ id: u.id, cambios: { activo } })}
                      />
                      <span className={u.activo ? 'chip chip-ok' : 'text-xs text-ink-3'}>{u.activo ? 'Activo' : 'Inactivo'}</span>
                    </div>
                  </td>
                  <td className="whitespace-nowrap px-3 py-[11px] tabular-nums text-ink-3">{u.creado_en ? formatearFecha(u.creado_en) : '—'}</td>
                  <td className="px-3 py-[11px]">
                    <button
                      type="button"
                      className="inline-flex items-center gap-1 whitespace-nowrap text-brand hover:underline disabled:text-ink-3"
                      disabled={regenerar.isPending}
                      onClick={() => {
                        if (window.confirm(`¿Generar una API key nueva para ${u.nombre}? La anterior dejará de funcionar de inmediato.`)) regenerar.mutate(u.id)
                      }}
                    >
                      <Icono nombre="refrescar" tamano={14} /> Generar nueva
                    </button>
                  </td>
                </tr>
              ))}
              {data.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-3 py-8 text-center text-ink-3">
                    Todavía no hay usuarios. La clave del sistema (variable API_KEY) sigue funcionando como Administrador.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
