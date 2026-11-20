import type { ClienteApi } from '../contrato'
import { ErrorApi } from '@/tipos'
import type {
  Campo,
  Documento,
  FiltrosDocumentos,
  FlujoCaptura,
  FlujoCapturaEntrada,
  FlujoPublico,
  ListaPaginada,
  PalabraPosicion,
  Plantilla,
  PlantillaEntrada,
  RecorteInfo,
  Resultado,
  ResultadoPublico,
  ResumenPurga,
  Rol,
  SugerenciaPlantilla,
  Usuario,
  VersionPlantilla,
  VistaPreviaPurga,
} from '@/tipos'
import {
  documentosMock,
  plantillasMock,
  resultadoMockCompleto,
  resultadosMock,
  saludMock,
  versionesPlantillaMock,
} from './datos'

/** Simula latencia de red para que los estados de carga se vean reales */
function esperar<T>(valor: T, ms = 400): Promise<T> {
  return new Promise((resolve) => setTimeout(() => resolve(valor), ms))
}

// Estado mutable en memoria (se reinicia al recargar la página)
let plantillas: Plantilla[] = plantillasMock.map((p) => ({
  ...p,
  // demostración: la cédula solo la edita un Administrador
  rol_minimo_edicion: p.rol_minimo_edicion ?? (p.codigo.includes('cedula') ? 'Administrador' : 'Editor'),
}))
let documentos: Documento[] = [...documentosMock]
const resultados: Record<string, Resultado> = { ...resultadosMock }
let siguienteIdPlantilla = Math.max(...plantillas.map((p) => p.id)) + 1

// Cuadrícula: tarjeta ficticia con palabras en posiciones relativas (sin datos de personas reales)
const PALABRAS_TARJETA_MOCK: PalabraPosicion[] = [
  { texto: 'TARJETA DE EJEMPLO', x: 0.3, y: 0.03, ancho: 0.4, alto: 0.06, confianza: 0.98 },
  { texto: 'APELLIDOS', x: 0.33, y: 0.2, ancho: 0.15, alto: 0.04, confianza: 0.97 },
  { texto: 'MUESTRA EJEMPLO', x: 0.33, y: 0.26, ancho: 0.32, alto: 0.06, confianza: 0.95 },
  { texto: 'NOMBRES', x: 0.33, y: 0.38, ancho: 0.13, alto: 0.04, confianza: 0.96 },
  { texto: 'ALEX', x: 0.33, y: 0.44, ancho: 0.1, alto: 0.06, confianza: 0.93 },
  { texto: 'NACIMIENTO', x: 0.33, y: 0.58, ancho: 0.17, alto: 0.04, confianza: 0.94 },
  { texto: '01 ENE 1990', x: 0.33, y: 0.64, ancho: 0.2, alto: 0.06, confianza: 0.62 },
  { texto: 'VÁLIDA HASTA', x: 0.33, y: 0.78, ancho: 0.2, alto: 0.04, confianza: 0.95 },
  { texto: '01 ENE 2030', x: 0.33, y: 0.84, ancho: 0.2, alto: 0.06, confianza: 0.91 },
]
const recortesMock: Record<string, RecorteInfo> = {}

function recorteMock(id: string): RecorteInfo {
  return (
    recortesMock[id] ?? { confiable: true, aplicado: true, origen: 'automatico', esquinas: [[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9]], relacion: 1.586, orientacion: 0 }
  )
}

// --- Roles, flujos y usuarios de demostración (docs/07) ---------------------------------------------
const CLAVE_ROL_MOCK = 'ocr_mock_rol'
const ROLES_VALIDOS: Rol[] = ['Administrador', 'Editor', 'Operador']

/** Rol con el que "entra" la demostración (se cambia en Configurar acceso cuando el modo mock está activo). */
export function rolMock(): Rol {
  try {
    const r = localStorage.getItem(CLAVE_ROL_MOCK) as Rol | null
    return r && ROLES_VALIDOS.includes(r) ? r : 'Administrador'
  } catch {
    return 'Administrador'
  }
}

export function fijarRolMock(rol: Rol): void {
  try {
    localStorage.setItem(CLAVE_ROL_MOCK, rol)
  } catch {
    /* almacenamiento no disponible */
  }
}

function resumen(p: Plantilla) {
  return { id: p.id, codigo: p.codigo, nombre: p.nombre, activa: p.activa }
}

let flujos: FlujoCaptura[] = [
  {
    id: 1,
    codigo: 'alta_cliente_cedula',
    nombre: 'Alta de cliente — cédula',
    instruccion: 'Sube o escanea tu cédula de identidad',
    acepta_camara: true,
    acepta_pdf: false,
    activo: true,
    rol_minimo_edicion: 'Editor',
    acceso_publico: false,
    plantillas: plantillas.filter((p) => p.codigo.includes('cedula')).map(resumen),
  },
  {
    id: 2,
    codigo: 'regularizacion_servicios',
    nombre: 'Regularización de servicios',
    instruccion: 'Sube tu última planilla de servicios',
    acepta_camara: true,
    acepta_pdf: true,
    activo: true,
    rol_minimo_edicion: 'Editor',
    acceso_publico: false,
    plantillas: plantillas.filter((p) => p.codigo.includes('planilla')).map(resumen),
  },
]
let siguienteIdFlujo = 3

let usuarios: Usuario[] = [
  { id: 1, nombre: 'Claudio Hidalgo', rol: 'Administrador', activo: true, creado_en: '2026-10-01T09:00:00Z' },
  { id: 2, nombre: 'María Pérez', rol: 'Editor', activo: true, creado_en: '2026-10-12T14:30:00Z' },
  { id: 3, nombre: 'Operador ventanilla', rol: 'Operador', activo: true, creado_en: '2026-11-02T08:15:00Z' },
  { id: 4, nombre: 'Pasante (baja)', rol: 'Operador', activo: false, creado_en: '2026-09-20T10:00:00Z' },
]
let siguienteIdUsuario = 5

// Retención de documentos de demostración (los documentos de ejemplo son de 2026-11, así que "vencidos" depende de hoy)
const RETENCION_DIAS_MOCK = 30
const BYTES_POR_DOC_MOCK = 240_000

function resumenPurga(lista: Documento[]): ResumenPurga {
  return { documentos: lista.length, archivos: lista.length, bytes: lista.length * BYTES_POR_DOC_MOCK }
}

function vencidosMock(): Documento[] {
  const limite = Date.now() - RETENCION_DIAS_MOCK * 86_400_000
  return documentos.filter((d) => new Date(d.fecha).getTime() < limite)
}

function claveFalsa(): string {
  return 'ocr_demo_' + Math.random().toString(36).slice(2, 12) + Math.random().toString(36).slice(2, 12)
}

function filtrarDocumentos(filtros: FiltrosDocumentos): Documento[] {
  return documentos.filter((d) => {
    if (filtros.tipo && d.tipo !== filtros.tipo) return false
    if (filtros.estado && d.estado !== filtros.estado) return false
    if (filtros.desde && d.fecha < filtros.desde) return false
    if (filtros.hasta && d.fecha > filtros.hasta) return false
    return true
  })
}

function generarResultadoParaArchivo(archivo: string, plantillaForzada?: number | null): Resultado {
  const id = `mock-${Date.now()}-${Math.floor(Math.random() * 1000)}`
  const plantilla = plantillaForzada
    ? plantillas.find((p) => p.id === plantillaForzada)
    : plantillas.find((p) => p.activa)

  if (!plantilla) {
    return {
      documento_id: id,
      archivo,
      paginas: 1,
      estado: 'COMPLETADO',
      clasificacion: { tipo: 'desconocido', plantilla_id: null, confianza: 0.2, alternativas: [] },
      campos: {},
      palabras_clave: [],
      texto_completo: 'No se pudo leer el documento de ejemplo.',
      confianza_global: 0.2,
      advertencias: [{ codigo: 'tipo_no_identificado', mensaje: 'Ninguna plantilla superó el umbral de confianza.' }],
      tiempos_ms: { ocr: 900, clasificacion: 10, extraccion: 0, total: 910 },
    }
  }

  const base: Resultado = {
    ...resultadoMockCompleto,
    documento_id: id,
    archivo,
    clasificacion: {
      tipo: plantilla.codigo,
      plantilla_id: plantilla.id,
      plantilla_version: plantilla.version ?? 1,
      confianza: 0.88,
      alternativas: [],
    },
  }
  return base
}

export const apiMock: ClienteApi = {
  salud: () => esperar(saludMock, 150),

  async procesarDocumento(archivo, plantillaId) {
    const resultado = generarResultadoParaArchivo(archivo.name, plantillaId)
    resultados[resultado.documento_id] = resultado
    documentos = [
      {
        id: resultado.documento_id,
        archivo: archivo.name,
        fecha: new Date().toISOString(),
        paginas: resultado.paginas,
        estado: resultado.estado,
        tipo: resultado.clasificacion.tipo,
        plantilla_id: resultado.clasificacion.plantilla_id,
        plantilla_version: resultado.clasificacion.plantilla_version ?? null,
        confianza: resultado.clasificacion.confianza,
      },
      ...documentos,
    ]
    return esperar(resultado, 1200)
  },

  async listarDocumentos(filtros) {
    const items = filtrarDocumentos(filtros)
    const tamano = filtros.tamano ?? 20
    const pagina = filtros.pagina ?? 1
    const inicio = (pagina - 1) * tamano
    const pagina_items = items.slice(inicio, inicio + tamano)
    const resp: ListaPaginada<Documento> = { items: pagina_items, total: items.length, pagina, tamano }
    return esperar(resp, 250)
  },

  async obtenerDocumento(id) {
    const doc = documentos.find((d) => d.id === id)
    if (!doc) throw new Error('Documento no encontrado')
    return esperar(doc, 150)
  },

  async obtenerResultado(id) {
    const resultado = resultados[id]
    if (!resultado) throw new Error('Resultado no encontrado')
    return esperar(resultado, 200)
  },

  async descargarArchivo() {
    return esperar(new Blob(['archivo de ejemplo (mock)'], { type: 'text/plain' }), 150)
  },

  async obtenerImagenPagina() {
    // SVG simple en lugar de una imagen escaneada real, solo para previsualizar.
    const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="850" height="1100">
      <rect width="100%" height="100%" fill="#ffffff" stroke="#cbd5e1" />
      <text x="40" y="60" font-family="monospace" font-size="20">EMPRESA ELÉCTRICA NACIONAL</text>
      <text x="40" y="100" font-family="monospace" font-size="16">Planilla de servicio eléctrico</text>
      <text x="40" y="240" font-family="monospace" font-size="16">N° Cliente 1234567-8</text>
      <text x="40" y="200" font-family="monospace" font-size="14">Dirección: Av. Siempre Viva 742</text>
      <text x="40" y="440" font-family="monospace" font-size="14">Consumo kWh 210</text>
      <text x="520" y="460" font-family="monospace" font-size="16">Total a pagar $45.320</text>
      <text x="520" y="510" font-family="monospace" font-size="14">Vencimiento: 30/11/2026</text>
    </svg>`
    return esperar(new Blob([svg], { type: 'image/svg+xml' }), 150)
  },

  async reprocesarDocumento(id) {
    const resultado = resultados[id]
    if (!resultado) throw new Error('Documento no encontrado')
    return esperar(resultado, 900)
  },

  // --- Cuadrícula de zonas (docs/13 §7): tarjeta ficticia, sin datos de personas reales -----------------
  async obtenerImagenEnderezada(id) {
    const r = recorteMock(id)
    const textos = PALABRAS_TARJETA_MOCK.map(
      (p) =>
        `<text x="${p.x * 856}" y="${(p.y + p.alto * 0.8) * 540}" font-family="Arial" font-size="${p.alto * 540 * 0.8}" fill="${p.confianza < 0.7 ? '#94a3b8' : '#1e293b'}">${p.texto}</text>`,
    ).join('')
    const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="856" height="540">
      <rect width="100%" height="100%" rx="24" fill="#eef2f7" stroke="#cbd5e1" />
      <rect width="100%" height="64" rx="24" fill="#1e3a8a" />
      <rect x="40" y="110" width="200" height="250" rx="12" fill="#cbd5e1" />${textos}
    </svg>`
    return esperar({ blob: new Blob([svg], { type: 'image/svg+xml' }), confiable: r.confiable, origen: r.origen, orientacion: r.orientacion }, 250)
  },

  async obtenerPalabras(id, pagina) {
    if (pagina !== 1) throw new ErrorApi(404, 'Página fuera de rango')
    return esperar({ pagina, recorte: recorteMock(id), palabras: PALABRAS_TARJETA_MOCK }, 200)
  },

  async recortarPagina(id, _pagina, entrada) {
    const anterior = recorteMock(id)
    const esquinas = entrada.esquinas ?? (anterior.origen === 'manual' ? anterior.esquinas : null)
    recortesMock[id] = {
      ...anterior,
      confiable: true,
      aplicado: !!esquinas,
      origen: esquinas ? 'manual' : anterior.origen,
      esquinas,
      orientacion: entrada.orientacion ?? 0,
    }
    const resultado = resultados[id] ?? resultadoMockCompleto
    return esperar(resultado, 1200)
  },

  async quitarRecortePagina(id) {
    delete recortesMock[id]
    return esperar(resultados[id] ?? resultadoMockCompleto, 1000)
  },

  async listarPlantillas(activa) {
    const items = activa === undefined ? plantillas : plantillas.filter((p) => p.activa === activa)
    return esperar(items, 200)
  },

  async obtenerPlantilla(id) {
    const plantilla = plantillas.find((p) => p.id === id)
    if (!plantilla) throw new Error('Plantilla no encontrada')
    return esperar(plantilla, 150)
  },

  async crearPlantilla(entrada: PlantillaEntrada) {
    const nueva: Plantilla = {
      ...entrada,
      id: siguienteIdPlantilla++,
      version: 1,
      creada_en: new Date().toISOString(),
      actualizada_en: new Date().toISOString(),
      total_documentos: 0,
    }
    plantillas = [...plantillas, nueva]
    return esperar(nueva, 500)
  },

  async actualizarPlantilla(id, entrada: PlantillaEntrada) {
    const idx = plantillas.findIndex((p) => p.id === id)
    if (idx === -1) throw new Error('Plantilla no encontrada')
    const actualizada: Plantilla = {
      ...plantillas[idx],
      ...entrada,
      version: (plantillas[idx].version ?? 1) + 1,
      actualizada_en: new Date().toISOString(),
    }
    plantillas = [...plantillas.slice(0, idx), actualizada, ...plantillas.slice(idx + 1)]
    return esperar(actualizada, 500)
  },

  async cambiarEstadoPlantilla(id, activa) {
    const idx = plantillas.findIndex((p) => p.id === id)
    if (idx === -1) throw new Error('Plantilla no encontrada')
    const actualizada = { ...plantillas[idx], activa }
    plantillas = [...plantillas.slice(0, idx), actualizada, ...plantillas.slice(idx + 1)]
    return esperar(actualizada, 250)
  },

  async sugerirPlantilla(documentoIds) {
    // como el servidor: con un solo ejemplo, las sugerencias llegan para revisar
    const revisar = documentoIds.length < 2
    const sugerencia: SugerenciaPlantilla = {
      palabras_clave: [
        { texto: 'número de cliente', peso: 3, revisar },
        { texto: 'total a pagar', peso: 3, revisar },
        { texto: 'fecha de vencimiento', peso: 2, revisar },
        { texto: 'dirección', peso: 1, revisar },
        { texto: 'consumo', peso: 1, revisar },
      ],
      zonas_sugeridas: [
        { x: 0.3, y: 0.03, ancho: 0.4, alto: 0.06, pagina: 1, texto_esperado: 'TARJETA DE EJEMPLO' },
        { x: 0.33, y: 0.2, ancho: 0.15, alto: 0.04, pagina: 1, texto_esperado: 'APELLIDOS' },
      ],
      campos: [
        {
          nombre: 'numero_detectado',
          etiqueta: 'Número detectado',
          tipo_dato: 'numero',
          obligatorio: false,
          regla: { metodo: 'regex', regex: '(\\d{5,})' },
        } as Campo,
        {
          nombre: 'fecha_detectada',
          etiqueta: 'Fecha detectada',
          tipo_dato: 'fecha',
          obligatorio: false,
          regla: { metodo: 'regex', regex: '([\\d]{1,2}[/-][\\d]{1,2}[/-][\\d]{2,4})' },
        } as Campo,
        {
          nombre: 'monto_detectado',
          etiqueta: 'Monto detectado',
          tipo_dato: 'monto',
          obligatorio: false,
          regla: { metodo: 'regex', regex: '\\$\\s*([\\d.,]+)' },
        } as Campo,
      ],
    }
    return esperar(sugerencia, 700)
  },

  async probarPlantilla(id, documentoId) {
    const plantilla = plantillas.find((p) => p.id === id)
    const base = resultados[documentoId] ?? resultadoMockCompleto
    if (!plantilla) throw new Error('Plantilla no encontrada')
    const simulado: Resultado = {
      ...base,
      clasificacion: {
        tipo: plantilla.codigo,
        plantilla_id: plantilla.id,
        plantilla_version: plantilla.version ?? 1,
        confianza: 0.85,
        alternativas: [],
      },
      campos: Object.fromEntries(
        plantilla.campos.map((c) => [
          c.nombre,
          base.campos[c.nombre] ?? { valor: `Valor de prueba (${c.etiqueta})`, confianza: 0.75, pagina: 1 },
        ]),
      ),
    }
    return esperar(simulado, 600)
  },

  async listarVersionesPlantilla(id) {
    const versiones: VersionPlantilla[] = versionesPlantillaMock[id] ?? [
      { version: 1, fecha: new Date().toISOString(), comentario: 'Versión inicial' },
    ]
    return esperar(versiones, 150)
  },

  async reprocesarDocumentosDePlantilla(id) {
    const plantilla = plantillas.find((p) => p.id === id)
    return esperar({ total: plantilla?.total_documentos ?? 0 }, 600)
  },

  // --- Sistema -----------------------------------------------------------------------------------
  async yo() {
    return esperar({ usuario_id: 1, nombre: 'Demostración', rol: rolMock(), publico_habilitado: true }, 100)
  },

  // --- Permisos de plantilla ----------------------------------------------------------------------
  async fijarPermisosPlantilla(id, rol) {
    const p = plantillas.find((x) => x.id === id)
    if (!p) throw new Error('Plantilla no encontrada')
    p.rol_minimo_edicion = rol
    return esperar({ ...p }, 200)
  },

  // --- Flujos de captura ---------------------------------------------------------------------------
  async listarFlujos(todos) {
    return esperar(flujos.filter((f) => todos || f.activo).map((f) => ({ ...f })), 250)
  },

  async obtenerFlujo(codigo) {
    const f = flujos.find((x) => x.codigo === codigo)
    if (!f) throw new Error('Flujo de captura no encontrado')
    return esperar({ ...f }, 200)
  },

  async crearFlujo(entrada: FlujoCapturaEntrada) {
    if (flujos.some((f) => f.codigo === entrada.codigo)) throw new Error(`Ya existe un flujo con el código '${entrada.codigo}'`)
    const nuevo: FlujoCaptura = {
      id: siguienteIdFlujo++,
      codigo: entrada.codigo,
      nombre: entrada.nombre,
      instruccion: entrada.instruccion ?? null,
      acepta_camara: entrada.acepta_camara,
      acepta_pdf: entrada.acepta_pdf,
      activo: entrada.activo,
      rol_minimo_edicion: 'Editor',
      acceso_publico: false,
      plantillas: plantillas.filter((p) => entrada.plantilla_ids.includes(p.id)).map(resumen),
    }
    flujos = [...flujos, nuevo]
    return esperar({ ...nuevo }, 400)
  },

  async actualizarFlujo(id, entrada: FlujoCapturaEntrada) {
    const f = flujos.find((x) => x.id === id)
    if (!f) throw new Error('Flujo de captura no encontrado')
    Object.assign(f, {
      codigo: entrada.codigo,
      nombre: entrada.nombre,
      instruccion: entrada.instruccion ?? null,
      acepta_camara: entrada.acepta_camara,
      acepta_pdf: entrada.acepta_pdf,
      activo: entrada.activo,
      plantillas: plantillas.filter((p) => entrada.plantilla_ids.includes(p.id)).map(resumen),
    })
    return esperar({ ...f }, 400)
  },

  async cambiarEstadoFlujo(id, activo) {
    const f = flujos.find((x) => x.id === id)
    if (!f) throw new Error('Flujo de captura no encontrado')
    f.activo = activo
    return esperar({ ...f }, 200)
  },

  async fijarAccesoPublicoFlujo(id, acceso) {
    const f = flujos.find((x) => x.id === id)
    if (!f) throw new Error('Flujo de captura no encontrado')
    f.acceso_publico = acceso
    return esperar({ ...f }, 250)
  },

  // Acceso público: en la demostración se pueden simular los errores del servidor con el nombre del archivo
  // (429, 503, 413, 400), para ver los mensajes que recibiría una persona externa.
  async obtenerFlujoPublico(codigo): Promise<FlujoPublico> {
    const f = flujos.find((x) => x.codigo === codigo && x.activo && x.acceso_publico)
    if (!f) throw new ErrorApi(404, 'Este punto de captura no está disponible. Revisa el enlace o pide uno nuevo a quien te lo envió.')
    return esperar({ codigo: f.codigo, nombre: f.nombre, instruccion: f.instruccion, acepta_camara: f.acepta_camara, acepta_pdf: f.acepta_pdf, retencion_dias: RETENCION_DIAS_MOCK, aviso_version: '1' }, 300)
  },

  async subirDocumentoPublico(codigo, archivo, _avisoVersion): Promise<ResultadoPublico> {
    const f = flujos.find((x) => x.codigo === codigo && x.activo && x.acceso_publico)
    if (!f) throw new ErrorApi(404, 'Este punto de captura no está disponible. Revisa el enlace o pide uno nuevo a quien te lo envió.')
    const n = archivo.name.toLowerCase()
    if (n.includes('429')) throw new ErrorApi(429, 'Hiciste demasiados intentos en poco tiempo. Espera 42 segundos y vuelve a intentarlo.')
    if (n.includes('503')) throw new ErrorApi(503, 'El servicio está ocupado en este momento. Inténtalo de nuevo en unos segundos.')
    if (n.includes('413')) throw new ErrorApi(413, 'El archivo es demasiado pesado. Prueba con una foto o un archivo más liviano.')
    if (n.includes('400')) throw new ErrorApi(400, 'Imagen demasiado grande (9000x9000 px = 81 MP); el máximo es 50 MP')
    if (!f.acepta_pdf && n.endsWith('.pdf')) throw new ErrorApi(400, 'Este flujo no acepta archivos PDF')
    const permitida = f.plantillas.find((p) => p.activa)
    const base = generarResultadoParaArchivo(archivo.name, permitida?.id ?? null)
    const sinCoincidencia = !permitida || /otro/i.test(n)
    const campos = Object.fromEntries(
      Object.entries(sinCoincidencia ? {} : base.campos).map(([k, v]) => [
        k,
        { valor: v.valor, confianza: v.confianza, etiqueta: plantillas.find((p) => p.id === permitida?.id)?.campos.find((c) => c.nombre === k)?.etiqueta },
      ]),
    )
    return esperar(
      {
        documento_id: base.documento_id,
        archivo: archivo.name,
        estado: sinCoincidencia ? ('NO_COINCIDE' as const) : ('COMPLETADO' as const),
        clasificacion: { tipo: sinCoincidencia ? 'desconocido' : base.clasificacion.tipo, confianza: sinCoincidencia ? 0.18 : base.clasificacion.confianza },
        campos,
        confianza_global: sinCoincidencia ? 0 : base.confianza_global,
        advertencias: sinCoincidencia ? [] : base.advertencias,
        flujo_captura: codigo,
      },
      1200,
    )
  },

  async procesarConFlujo(codigo, archivo) {
    const f = flujos.find((x) => x.codigo === codigo && x.activo)
    if (!f) throw new Error('Flujo de captura no encontrado')
    if (!f.acepta_pdf && archivo.name.toLowerCase().endsWith('.pdf')) throw new Error('Este flujo no acepta archivos PDF')
    const permitida = f.plantillas.find((p) => p.activa)
    // demostración: un archivo cuyo nombre contenga "otro" simula un documento que no es el esperado
    if (!permitida || /otro/i.test(archivo.name)) {
      const base = generarResultadoParaArchivo(archivo.name, null)
      return esperar(
        {
          ...base,
          estado: 'NO_COINCIDE' as const,
          flujo_captura: codigo,
          clasificacion: { tipo: 'desconocido', plantilla_id: null, confianza: 0.18, alternativas: [] },
          campos: {},
        },
        1200,
      )
    }
    const r = generarResultadoParaArchivo(archivo.name, permitida.id)
    return esperar({ ...r, flujo_captura: codigo }, 1200)
  },

  // --- Retención y purga -------------------------------------------------------------------------------
  async vistaPreviaPurga(): Promise<VistaPreviaPurga> {
    return esperar({ retencion_dias: RETENCION_DIAS_MOCK, automatica: true, vencidos: resumenPurga(vencidosMock()), todos: resumenPurga(documentos) }, 250)
  },

  async purgarDocumentos(alcance) {
    const borrar = alcance === 'todos' ? [...documentos] : vencidosMock()
    const ids = new Set(borrar.map((d) => d.id))
    documentos = documentos.filter((d) => !ids.has(d.id))
    return esperar(resumenPurga(borrar), 500)
  },

  // --- Usuarios --------------------------------------------------------------------------------------
  async listarUsuarios() {
    return esperar(usuarios.map((u) => ({ ...u })), 250)
  },

  async crearUsuario(entrada) {
    const u: Usuario = { id: siguienteIdUsuario++, nombre: entrada.nombre, rol: entrada.rol, activo: true, creado_en: new Date().toISOString() }
    usuarios = [...usuarios, u]
    return esperar({ ...u, api_key: claveFalsa() }, 400)
  },

  async actualizarUsuario(id, cambios) {
    const u = usuarios.find((x) => x.id === id)
    if (!u) throw new Error('Usuario no encontrado')
    if (id === 1 && (cambios.activo === false || (cambios.rol && cambios.rol !== 'Administrador'))) {
      throw new Error('No puedes desactivarte ni quitarte el rol de Administrador a ti mismo')
    }
    Object.assign(u, cambios)
    return esperar({ ...u }, 250)
  },

  async regenerarClaveUsuario(id) {
    const u = usuarios.find((x) => x.id === id)
    if (!u) throw new Error('Usuario no encontrado')
    return esperar({ ...u, api_key: claveFalsa() }, 400)
  },
}
