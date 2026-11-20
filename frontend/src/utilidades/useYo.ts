import { useQuery } from '@tanstack/react-query'
import { api } from '@/api'
import type { Rol, Yo } from '@/tipos'
import { tieneRol } from './roles'

/** Quién soy y qué rol tengo (GET /yo). Mientras carga o si falla, `puede()` devuelve false: nunca se muestra de más. */
export function useYo(): {
  yo: Yo | undefined
  rol: Rol | undefined
  cargando: boolean
  puede: (minimo: Rol) => boolean
} {
  const q = useQuery({ queryKey: ['yo'], queryFn: () => api.yo(), retry: false, staleTime: 60_000 })
  return {
    yo: q.data,
    rol: q.data?.rol,
    cargando: q.isPending,
    puede: (minimo: Rol) => tieneRol(q.data?.rol, minimo),
  }
}
