/**
 * Tipos TypeScript escritos a mano a partir del contrato de la API
 * (docs/02-backend.md sección 3 y docs/01-diseno-general.md sección 5).
 *
 * Cuando el backend exponga su OpenAPI, se pueden regenerar con
 * `npm run tipos:openapi` (ver README) y reemplazar estos poco a poco.
 */

// ---------------------------------------------------------------------------
// Plantillas
// ---------------------------------------------------------------------------

export const TIPOS_DATO = [
  'texto',
  'numero',
  'monto',
  'fecha',
  'rut',
  'cedula',
  'email',
  'telefono',
] as const
export type TipoDato = (typeof TIPOS_DATO)[number]

export const ETIQUETAS_TIPO_DATO: Record<TipoDato, string> = {
  texto: 'Texto',
  numero: 'Número',
  monto: 'Monto',
  fecha: 'Fecha',
  rut: 'RUT',
  cedula: 'Cédula',
  email: 'Correo',
  telefono: 'Teléfono',
}

export const METODOS_REGLA = ['ancla', 'regex', 'zona'] as const
export type MetodoRegla = (typeof METODOS_REGLA)[number]

/** Rectángulo relativo (0-1) sobre la página recortada y enderezada (docs/13 §1). */
export interface ZonaRelativa {
  x: number
  y: number
  ancho: number
  alto: number
  pagina?: number | null
}

/** Etiqueta fija impresa: texto que debe aparecer en esa zona (valida el diseño). */
export interface ZonaEtiqueta extends ZonaRelativa {
  texto_esperado: string
}

/** Zonas opcionales de cualquier regla (cuadrícula, docs/13 §1.1): la del valor y la de su etiqueta impresa. */
export interface ZonasDeRegla {
  x?: number | null
  y?: number | null
  ancho?: number | null
  alto?: number | null
  pagina?: number | null
  zona_etiqueta?: ZonaEtiqueta | null
}

/** Diseño por posición de una versión de plantilla (docs/13 §1.2). Nada atado a un formato concreto. */
export interface DisenoPlantilla {
  formato: string
  /** Lado mayor / lado menor esperado (ID-1 1,586; A4 1,414...) */
  relacion?: number | null
  umbral_coincidencia: number
  tolerancia: number
  /** Solo de la UI, p. ej. "12x8" */
  densidad_rejilla?: string | null
  elementos_fijos: ZonaEtiqueta[]
}

export interface ReglaAncla extends ZonasDeRegla {
  metodo: 'ancla'
  /** Texto que precede al dato, p. ej. "N° Cliente" */
  ancla: string
  /** Filtro opcional sobre lo que sigue al ancla; el grupo 1 (o todo) es el valor */
  regex?: string
}

export interface ReglaRegex extends ZonasDeRegla {
  metodo: 'regex'
  /** Expresión sobre el texto completo; el grupo 1 es el valor */
  regex: string
}

export interface ReglaZona {
  metodo: 'zona'
  pagina: number
  zona_etiqueta?: ZonaEtiqueta | null
  /** Coordenadas relativas 0-1 respecto al tamaño de la página */
  x: number
  y: number
  ancho: number
  alto: number
}

export type Regla = ReglaAncla | ReglaRegex | ReglaZona

export interface Campo {
  nombre: string
  etiqueta: string
  tipo_dato: TipoDato
  obligatorio: boolean
  regla: Regla
}

export interface PalabraClave {
  texto: string
  peso: number // 1-5
}

/** Cuerpo de POST /plantillas y PUT /plantillas/{id} */
export interface PlantillaEntrada {
  codigo: string
  nombre: string
  descripcion?: string
  activa: boolean
  umbral_confianza: number
  palabras_clave: PalabraClave[]
  campos: Campo[]
  /** Cuadrícula de la versión; null = sin cuadrícula. Hay que reenviarlo al guardar o la versión nueva lo pierde. */
  diseno?: DisenoPlantilla | null
}

export interface Plantilla extends PlantillaEntrada {
  id: number
  /** Rol mínimo que puede editarla (docs/07). Lo cambia solo un Administrador. */
  rol_minimo_edicion?: Rol
  version?: number
  creada_en?: string
  actualizada_en?: string
  /** Cantidad de documentos procesados con esta plantilla (para la lista) */
  total_documentos?: number
}

export interface VersionPlantilla {
  version: number
  fecha: string
  comentario?: string
}

/** Respuesta de POST /plantillas/sugerir */
export interface SugerenciaPlantilla {
  palabras_clave: PalabraClave[]
  campos: Campo[]
}

// ---------------------------------------------------------------------------
// Roles, usuarios y flujos de captura (docs/07)
// ---------------------------------------------------------------------------

export type Rol = 'Administrador' | 'Editor' | 'Operador'
export const ROLES: Rol[] = ['Administrador', 'Editor', 'Operador']

/** Respuesta de GET /yo: quién es el dueño de la API key en uso. */
export interface Yo {
  usuario_id: number | null
  nombre: string
  rol: Rol
  /** ¿El servidor tiene habilitado el acceso público sin clave? (PUBLICO_HABILITADO) */
  publico_habilitado?: boolean
}

export interface PlantillaResumen {
  id: number
  codigo: string
  nombre: string
  activa: boolean
}

/** Cuerpo de POST /flujos-captura y PUT /flujos-captura/{id} */
export interface FlujoCapturaEntrada {
  codigo: string
  nombre: string
  instruccion?: string | null
  acepta_camara: boolean
  acepta_pdf: boolean
  activo: boolean
  /** Plantillas permitidas (al menos una) */
  plantilla_ids: number[]
}

export interface FlujoCaptura {
  id: number
  codigo: string
  nombre: string
  instruccion?: string | null
  acepta_camara: boolean
  acepta_pdf: boolean
  activo: boolean
  rol_minimo_edicion: Rol
  acceso_publico: boolean
  plantillas: PlantillaResumen[]
  creado_por_id?: number | null
  creado_en?: string | null
  actualizado_en?: string | null
}

/** Lo único que se expone sin API key de un flujo (GET /flujos-captura/{codigo}/publico). */
export interface FlujoPublico {
  codigo: string
  nombre: string
  instruccion?: string | null
  acepta_camara: boolean
  acepta_pdf: boolean
  /** Días que se conserva un documento antes de eliminarse (0 = sin caducidad automática) */
  retencion_dias: number
  /** Versión del aviso de privacidad vigente: se envía al subir y queda registrada junto con la fecha */
  aviso_version: string
}

/** Respuesta REDUCIDA que recibe quien sube un documento sin clave: sin texto OCR completo ni datos internos. */
export interface ResultadoPublico {
  documento_id: string
  archivo: string
  estado: EstadoDocumento
  clasificacion: { tipo: string; confianza: number }
  campos: Record<string, { valor: string | number | null; confianza: number; etiqueta?: string }>
  confianza_global: number
  advertencias: Advertencia[]
  flujo_captura?: string
}

/** Cuánto se eliminaría con cada alcance de purga (GET /purga) */
export interface ResumenPurga {
  documentos: number
  archivos: number
  bytes: number
}

export interface VistaPreviaPurga {
  retencion_dias: number
  /** ¿La purga automática diaria está encendida en este servidor? */
  automatica: boolean
  vencidos: ResumenPurga
  todos: ResumenPurga
}

export interface Usuario {
  id: number
  nombre: string
  rol: Rol
  activo: boolean
  creado_en?: string | null
}

/** Al crear o regenerar: la API key en claro se entrega UNA sola vez. */
export interface UsuarioConClave extends Usuario {
  api_key: string
}

// ---------------------------------------------------------------------------
// Documentos
// ---------------------------------------------------------------------------

export type EstadoDocumento = 'RECIBIDO' | 'PROCESANDO' | 'COMPLETADO' | 'ERROR' | 'NO_COINCIDE'

export interface Documento {
  id: string
  archivo: string
  fecha: string // ISO 8601
  paginas: number
  estado: EstadoDocumento
  tipo: string | null // código de plantilla o "desconocido"
  plantilla_id: number | null
  plantilla_version?: number | null
  confianza: number | null
  mensaje_error?: string | null
}

export interface FiltrosDocumentos {
  tipo?: string
  estado?: EstadoDocumento | ''
  desde?: string
  hasta?: string
  pagina?: number
  tamano?: number
}

export interface ListaPaginada<T> {
  items: T[]
  total: number
  pagina: number
  tamano: number
}

// ---------------------------------------------------------------------------
// Resultado (contrato JSON del diseño general, sección 5)
// ---------------------------------------------------------------------------

export interface CajaRelativa {
  x: number
  y: number
  ancho: number
  alto: number
}

// ---------------------------------------------------------------------------
// Cuadrícula de zonas: recorte y posiciones (docs/13 §7)
// ---------------------------------------------------------------------------

export type OrigenRecorte = 'automatico' | 'manual' | 'ninguno' | 'pdf' | 'desconocido'
export type Orientacion = 0 | 90 | 180 | 270

export interface RecorteInfo {
  confiable: boolean
  aplicado: boolean
  origen: OrigenRecorte
  /** 4 esquinas relativas a la imagen ORIGINAL: arriba-izq, arriba-der, abajo-der, abajo-izq */
  esquinas: [number, number][] | null
  relacion: number | null
  orientacion: Orientacion
}

export interface PalabraPosicion {
  texto: string
  x: number
  y: number
  ancho: number
  alto: number
  confianza: number
}

export interface PalabrasPagina {
  pagina: number
  recorte: RecorteInfo
  palabras: PalabraPosicion[]
}

export interface ImagenEnderezada {
  blob: Blob
  confiable: boolean
  origen: OrigenRecorte
  orientacion: Orientacion
}

export interface CampoExtraido {
  valor: string | number | null
  confianza: number
  pagina: number
  /** Motor OCR que dio la lectura final (null si el campo no se encontró) */
  motor?: 'paddle' | 'doctr' | 'tesseract' | 'pdf-nativo' | null
  /** Coordenadas relativas de donde salió el valor (para resaltar en la imagen) */
  caja?: CajaRelativa
}

export interface Alternativa {
  tipo: string
  confianza: number
}

export interface Clasificacion {
  tipo: string // código o "desconocido"
  plantilla_id: number | null
  plantilla_version?: number | null
  confianza: number
  alternativas: Alternativa[]
}

export interface TiemposMs {
  ocr: number
  clasificacion: number
  extraccion: number
  total: number
  [etapa: string]: number
}

export interface Advertencia {
  codigo: string // p. ej. "campo_obligatorio_faltante"
  campo?: string
  mensaje: string
}

export interface EntradaLog {
  paso: string
  mensaje: string
  duracion_ms: number
  nivel?: 'info' | 'advertencia' | 'error'
  fecha?: string
}

export interface PalabraOCR {
  texto: string
  pagina: number
  x: number
  y: number
  ancho: number
  alto: number
  confianza: number
}

export interface Resultado {
  documento_id: string
  archivo: string
  paginas: number
  estado: EstadoDocumento
  clasificacion: Clasificacion
  campos: Record<string, CampoExtraido>
  palabras_clave: string[]
  texto_completo: string
  confianza_global: number
  advertencias: Advertencia[]
  tiempos_ms: TiemposMs
  /** Código del flujo de captura con que se procesó (si fue por un flujo) */
  flujo_captura?: string
  /** Opcionales: los devuelve el detalle para auditoría */
  log?: EntradaLog[]
  palabras_ocr?: PalabraOCR[]
}

// ---------------------------------------------------------------------------
// Sistema
// ---------------------------------------------------------------------------

export type EstadoComponente = 'ok' | 'degradado' | 'error'

export interface Salud {
  api: EstadoComponente
  base_datos: EstadoComponente
  tesseract: EstadoComponente
  paddleocr?: string
  motor_ocr_configurado?: string
  version?: string
}

// ---------------------------------------------------------------------------
// Errores
// ---------------------------------------------------------------------------

export class ErrorApi extends Error {
  constructor(
    public readonly status: number,
    message: string,
    public readonly detalle?: unknown,
  ) {
    super(message)
    this.name = 'ErrorApi'
  }
}
