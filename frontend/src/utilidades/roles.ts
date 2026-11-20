import type { Rol } from '@/tipos'

const RANGO: Record<Rol, number> = { Operador: 1, Editor: 2, Administrador: 3 }

/** ¿`rol` alcanza al menos el rol `minimo`? (Administrador > Editor > Operador) */
export function tieneRol(rol: Rol | undefined, minimo: Rol): boolean {
  return rol !== undefined && RANGO[rol] >= RANGO[minimo]
}

/** El mayor de dos roles: para editar una plantilla se exige el mayor entre Editor y su rol mínimo. */
export function rolMayor(a: Rol, b: Rol): Rol {
  return RANGO[a] >= RANGO[b] ? a : b
}
