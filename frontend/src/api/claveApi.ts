const CLAVE_STORAGE = 'ocr_api_key'

export function obtenerClaveApi(): string {
  try {
    return localStorage.getItem(CLAVE_STORAGE) ?? ''
  } catch {
    return ''
  }
}

export function guardarClaveApi(clave: string): void {
  try {
    if (clave) localStorage.setItem(CLAVE_STORAGE, clave)
    else localStorage.removeItem(CLAVE_STORAGE)
  } catch {
    /* almacenamiento no disponible */
  }
}
