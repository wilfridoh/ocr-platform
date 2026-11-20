import type { ReactNode } from 'react'
import type { Rol } from '@/tipos'
import { useYo } from '@/utilidades/useYo'
import CargandoIndicador from './CargandoIndicador'
import SinPermiso from './SinPermiso'

/** Envuelve una pantalla que exige un rol mínimo: si no alcanza, muestra el estado «sin permiso» en lugar de la pantalla. */
export default function RequiereRol({ minimo, children }: { minimo: Rol; children: ReactNode }) {
  const { rol, cargando, puede } = useYo()
  if (cargando) return <CargandoIndicador />
  if (!puede(minimo)) return <SinPermiso requiere={minimo} rolActual={rol} />
  return <>{children}</>
}
