import { NavLink } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/api'
import { useYo } from '@/utilidades/useYo'
import { Icono, type NombreIcono } from './Iconos'

interface Enlace {
  to: string
  etiqueta: string
  icono: NombreIcono
  /** Rol mínimo para ver la opción (docs/07): lo que no corresponde al rol no se muestra */
  rol?: 'Editor' | 'Administrador'
}

const ENLACES: Enlace[] = [
  { to: '/', etiqueta: 'Procesar', icono: 'procesar' },
  { to: '/documentos', etiqueta: 'Documentos', icono: 'documentos' },
  { to: '/plantillas', etiqueta: 'Plantillas', icono: 'plantillas' },
  { to: '/flujos-captura', etiqueta: 'Flujos de captura', icono: 'flujos', rol: 'Editor' },
]

const ENLACES_ADMIN: Enlace[] = [
  { to: '/usuarios', etiqueta: 'Usuarios', icono: 'usuarios', rol: 'Administrador' },
  { to: '/configurar-acceso', etiqueta: 'Configurar acceso', icono: 'llave' },
]

const claseEnlace = ({ isActive }: { isActive: boolean }) =>
  `flex items-center gap-2.5 rounded-lg px-3 py-2 text-[13px] font-medium transition-colors ${
    isActive ? 'bg-side-on text-white' : 'text-side-ink hover:bg-[#1E293B] hover:text-white'
  }`

export default function BarraLateral({ abierto = false, onCerrar }: { abierto?: boolean; onCerrar?: () => void }) {
  const { data, isError, isPending } = useQuery({
    queryKey: ['salud'],
    queryFn: () => api.salud(),
    refetchInterval: 30_000,
    retry: 1,
  })
  const { yo, puede } = useYo()

  const ok = !isError && data?.api === 'ok' && data?.base_datos === 'ok'
  const visibles = (lista: Enlace[]) => lista.filter((e) => !e.rol || puede(e.rol))

  return (
    <>
      {/* Fondo oscuro detrás del cajón (solo móvil) */}
      {abierto && <div className="fixed inset-0 z-40 bg-black/50 md:hidden" onClick={onCerrar} aria-hidden />}
    <aside
      className={`fixed inset-y-0 left-0 z-50 flex w-[260px] flex-none flex-col overflow-y-auto bg-side transition-transform duration-200 md:sticky md:top-0 md:z-auto md:h-screen md:w-[232px] md:translate-x-0 ${
        abierto ? 'translate-x-0' : '-translate-x-full'
      }`}
    >
      <div className="flex items-center gap-2.5 px-4 py-5">
        <div
          className="grid h-[30px] w-[30px] flex-none place-items-center rounded-lg text-white"
          style={{ background: 'linear-gradient(135deg,#6366F1,#4338CA)' }}
          aria-hidden
        >
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M3 7V5a2 2 0 0 1 2-2h2M17 3h2a2 2 0 0 1 2 2v2M21 17v2a2 2 0 0 1-2 2h-2M7 21H5a2 2 0 0 1-2-2v-2M7 12h10" />
          </svg>
        </div>
        <div>
          <h1 className="text-sm font-bold leading-tight text-white">OCR Platform</h1>
          <p className="text-[11px] leading-tight text-side-ink">Lectura inteligente de documentos</p>
        </div>
      </div>

      <nav className="flex-1 space-y-1 px-3" aria-label="Principal">
        {visibles(ENLACES).map((e) => (
          <NavLink key={e.to} to={e.to} end={e.to === '/'} className={claseEnlace}>
            <Icono nombre={e.icono} />
            {e.etiqueta}
          </NavLink>
        ))}
      </nav>

      <div className="border-t border-[#1E293B] p-3">
        <p className="px-3 pb-1 text-[10.5px] font-semibold uppercase tracking-[.06em] text-[#64748B]">Administración</p>
        {visibles(ENLACES_ADMIN).map((e) => (
          <NavLink key={e.to} to={e.to} className={claseEnlace}>
            <Icono nombre={e.icono} />
            {e.etiqueta}
          </NavLink>
        ))}
        {yo && (
          <p className="mt-2 truncate px-3 text-[11px] text-side-ink" title={`${yo.nombre} · ${yo.rol}`}>
            {yo.nombre} · <span className="font-semibold text-white">{yo.rol}</span>
          </p>
        )}
        <div className="mt-1 flex items-center gap-2 px-3 py-1 text-xs text-side-ink" role="status">
          <span
            className="h-2 w-2 flex-none rounded-full"
            style={
              isPending
                ? { background: '#94A3B8' }
                : ok
                  ? { background: '#10B981', boxShadow: '0 0 0 3px rgba(16,185,129,.2)' }
                  : { background: '#F87171', boxShadow: '0 0 0 3px rgba(248,113,113,.2)' }
            }
            aria-hidden
          />
          {isPending ? 'Comprobando…' : ok ? 'Sistema disponible' : 'Sistema sin conexión'}
        </div>
      </div>
    </aside>
    </>
  )
}
