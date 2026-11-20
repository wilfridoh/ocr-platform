import { BASE_URL } from './http'
import { USAR_MOCK } from './index'
import { saludMock } from './mock/datos'
import type { Salud } from '@/tipos'

export type ResultadoConexion =
  | { estado: 'ok'; version?: string }
  | { estado: 'sin_clave' }
  | { estado: 'clave_invalida' }
  | { estado: 'sin_conexion'; detalle?: string }

/**
 * Comprueba el servidor con la clave dada SIN guardarla:
 *  1. GET /salud (no exige clave): ¿hay servidor? y, si lo informa, su versión.
 *  2. GET /documentos?tamano=1 (exige clave): ¿la clave es válida? (/salud no la valida).
 */
export async function verificarConexion(clave: string): Promise<ResultadoConexion> {
  if (USAR_MOCK) return { estado: 'ok', version: saludMock.version }

  let version: string | undefined
  try {
    const res = await fetch(`${BASE_URL}/salud`, { headers: { Accept: 'application/json' } })
    if (!res.ok) return { estado: 'sin_conexion', detalle: `El servidor respondió ${res.status}` }
    version = ((await res.json()) as Salud).version
  } catch (e) {
    return { estado: 'sin_conexion', detalle: e instanceof Error ? e.message : undefined }
  }

  if (!clave) return { estado: 'sin_clave' }

  try {
    const res = await fetch(`${BASE_URL}/documentos?pagina=1&tamano=1`, {
      headers: { Accept: 'application/json', 'X-API-Key': clave },
    })
    if (res.status === 401 || res.status === 403) return { estado: 'clave_invalida' }
    if (!res.ok) return { estado: 'sin_conexion', detalle: `El servidor respondió ${res.status}` }
  } catch (e) {
    return { estado: 'sin_conexion', detalle: e instanceof Error ? e.message : undefined }
  }
  return { estado: 'ok', version }
}
