import { Link } from 'react-router-dom'
import type { Rol } from '@/tipos'
import { Icono } from './Iconos'

/** Empty state con candado (docs/09 §4 y §6): la sección existe pero el rol del usuario no alcanza. */
export default function SinPermiso({ requiere, rolActual, detalle }: { requiere: Rol; rolActual?: Rol; detalle?: string }) {
  return (
    <div className="tarjeta px-5 py-14 text-center">
      <div className="mx-auto mb-4 grid h-16 w-16 place-items-center rounded-[18px] bg-warn-soft text-warn">
        <Icono nombre="candado" tamano={30} />
      </div>
      <h2 className="mb-1.5 text-lg font-semibold text-ink">No tienes permiso para ver esto</h2>
      <p className="mx-auto mb-5 max-w-[420px] text-ink-3">
        {detalle ?? `Esta sección requiere el rol ${requiere} o superior${rolActual ? ` (tu rol: ${rolActual})` : ''}.`} Pídele al
        administrador que revise tu acceso.
      </p>
      <Link to="/" className="boton-secundario">
        Volver a Procesar
      </Link>
    </div>
  )
}
