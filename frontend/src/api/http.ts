import { ErrorApi } from '@/tipos'
import { obtenerClaveApi } from './claveApi'

export const BASE_URL = '/api'

interface Opciones extends Omit<RequestInit, 'body'> {
  body?: unknown
  /** Si es true, `body` se envía tal cual (FormData) sin cabecera JSON */
  crudo?: boolean
}

async function extraerMensaje(res: Response): Promise<{ mensaje: string; detalle?: unknown }> {
  const texto = await res.text()
  try {
    const json = JSON.parse(texto) as { detail?: unknown; mensaje?: string }
    if (typeof json.detail === 'string') return { mensaje: json.detail, detalle: json }
    if (json.mensaje) return { mensaje: json.mensaje, detalle: json }
    return { mensaje: texto || res.statusText, detalle: json }
  } catch {
    return { mensaje: texto || res.statusText }
  }
}

export async function solicitar<T>(ruta: string, opciones: Opciones = {}): Promise<T> {
  const { body, crudo, headers, ...resto } = opciones
  const cabeceras = new Headers(headers)
  const clave = obtenerClaveApi()
  if (clave) cabeceras.set('X-API-Key', clave)
  cabeceras.set('Accept', 'application/json')

  let cuerpo: BodyInit | undefined
  if (body !== undefined) {
    if (crudo) {
      cuerpo = body as BodyInit
    } else {
      cabeceras.set('Content-Type', 'application/json')
      cuerpo = JSON.stringify(body)
    }
  }

  const res = await fetch(`${BASE_URL}${ruta}`, { ...resto, headers: cabeceras, body: cuerpo })

  if (!res.ok) {
    const { mensaje, detalle } = await extraerMensaje(res)
    if (res.status === 401) {
      throw new ErrorApi(res.status, 'Acceso no autorizado. Configura la API key en "Configurar acceso".', detalle)
    }
    // 403: la clave es válida pero el rol no alcanza; el servidor explica qué rol hace falta.
    if (res.status === 403) {
      throw new ErrorApi(res.status, mensaje || 'No tienes permiso para esta acción.', detalle)
    }
    throw new ErrorApi(res.status, mensaje, detalle)
  }

  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

export async function solicitarBlob(ruta: string): Promise<Blob> {
  const cabeceras = new Headers()
  const clave = obtenerClaveApi()
  if (clave) cabeceras.set('X-API-Key', clave)
  const res = await fetch(`${BASE_URL}${ruta}`, { headers: cabeceras })
  if (!res.ok) {
    const { mensaje } = await extraerMensaje(res)
    throw new ErrorApi(res.status, mensaje)
  }
  return res.blob()
}

export function aQuery(params: Record<string, string | number | boolean | undefined | null>): string {
  const sp = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== '') sp.set(k, String(v))
  }
  const s = sp.toString()
  return s ? `?${s}` : ''
}

/** Mensaje legible para un error de la ruta pública, según el estado HTTP (docs/07 §5.2). */
function mensajePublico(status: number, detalle: string | undefined, reintentarEn: number | null): string {
  switch (status) {
    case 400:
      return detalle || 'No pudimos leer ese archivo. Prueba con otra foto o archivo.'
    case 401:
    case 404:
      return 'Este punto de captura no está disponible. Revisa el enlace o pide uno nuevo a quien te lo envió.'
    case 409:
      return 'No pudimos guardar tu documento. Vuelve a subirlo.'
    case 413:
      return 'El archivo es demasiado pesado. Prueba con una foto o un archivo más liviano.'
    case 429:
      return reintentarEn
        ? `Hiciste demasiados intentos en poco tiempo. Espera ${reintentarEn} segundos y vuelve a intentarlo.`
        : 'Hiciste demasiados intentos en poco tiempo. Espera un momento y vuelve a intentarlo.'
    case 503:
      return 'El servicio está ocupado en este momento. Inténtalo de nuevo en unos segundos.'
    default:
      return 'No pudimos procesar el documento. Inténtalo de nuevo; si el problema sigue, avisa a quien te envió el enlace.'
  }
}

/**
 * Petición PÚBLICA (docs/07 §5.2): NUNCA envía X-API-Key, aunque haya una guardada en este navegador (por ejemplo
 * porque alguien del personal abrió el enlace). Lo usan solo las pantallas sin sesión (/captura/:codigo).
 * Los errores llegan con un mensaje ya legible para una persona externa.
 */
export async function solicitarPublico<T>(ruta: string, opciones: { method?: string; body?: FormData } = {}): Promise<T> {
  let res: Response
  try {
    res = await fetch(`${BASE_URL}${ruta}`, {
      method: opciones.method ?? 'GET',
      body: opciones.body,
      headers: { Accept: 'application/json' }, // sin X-API-Key a propósito
      credentials: 'omit',
    })
  } catch {
    throw new ErrorApi(0, 'No se pudo conectar. Revisa tu conexión a internet e inténtalo de nuevo.')
  }
  if (res.ok) return (await res.json()) as T
  let detalle: string | undefined
  try {
    const json = (await res.json()) as { detail?: unknown }
    if (typeof json.detail === 'string') detalle = json.detail
  } catch {
    /* cuerpo no JSON */
  }
  const ra = Number(res.headers.get('Retry-After'))
  throw new ErrorApi(res.status, mensajePublico(res.status, detalle, Number.isFinite(ra) && ra > 0 ? Math.ceil(ra) : null))
}
