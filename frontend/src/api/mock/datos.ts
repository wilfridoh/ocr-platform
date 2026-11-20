import type { Documento, Plantilla, Resultado, Salud, VersionPlantilla } from '@/tipos'

/**
 * Datos de ejemplo para desarrollar y probar la interfaz sin backend.
 * Activado con VITE_USAR_MOCK=true (ver .env.development).
 */

export const saludMock: Salud = {
  api: 'ok',
  base_datos: 'ok',
  tesseract: 'ok',
  paddleocr: 'instalado',
  motor_ocr_configurado: 'paddle',
  version: 'mock-0.1.0',
}

export const plantillasMock: Plantilla[] = [
  {
    id: 3,
    codigo: 'planilla_servicio_electrico',
    nombre: 'Planilla servicio eléctrico',
    descripcion: 'Boleta mensual de electricidad',
    activa: true,
    umbral_confianza: 0.6,
    version: 2,
    creada_en: '2026-08-01T10:00:00Z',
    actualizada_en: '2026-10-15T09:30:00Z',
    total_documentos: 142,
    palabras_clave: [
      { texto: 'consumo kwh', peso: 3 },
      { texto: 'total a pagar', peso: 2 },
      { texto: 'lectura anterior', peso: 2 },
    ],
    campos: [
      {
        nombre: 'numero_cliente',
        etiqueta: 'Número de cliente',
        tipo_dato: 'texto',
        obligatorio: true,
        regla: { metodo: 'ancla', ancla: 'N° Cliente', regex: '[\\d.-]+' },
      },
      {
        nombre: 'total_pagar',
        etiqueta: 'Total a pagar',
        tipo_dato: 'monto',
        obligatorio: true,
        regla: { metodo: 'regex', regex: 'Total a pagar\\s*\\$?\\s*([\\d.,]+)' },
      },
      {
        nombre: 'direccion',
        etiqueta: 'Dirección',
        tipo_dato: 'texto',
        obligatorio: false,
        regla: { metodo: 'zona', pagina: 1, x: 0.05, y: 0.18, ancho: 0.5, alto: 0.06 },
      },
      {
        nombre: 'fecha_vencimiento',
        etiqueta: 'Fecha de vencimiento',
        tipo_dato: 'fecha',
        obligatorio: true,
        regla: { metodo: 'regex', regex: 'Vencimiento\\s*[:\\-]?\\s*([\\d/\\-]+)' },
      },
      {
        nombre: 'consumo_kwh',
        etiqueta: 'Consumo (kWh)',
        tipo_dato: 'numero',
        obligatorio: false,
        regla: { metodo: 'ancla', ancla: 'Consumo kWh', regex: '[\\d.,]+' },
      },
      {
        nombre: 'periodo',
        etiqueta: 'Período de facturación',
        tipo_dato: 'texto',
        obligatorio: false,
        regla: { metodo: 'zona', pagina: 1, x: 0.6, y: 0.05, ancho: 0.35, alto: 0.05 },
      },
    ],
  },
  {
    id: 7,
    codigo: 'cuenta_contrato',
    nombre: 'Cuenta de contrato',
    descripcion: 'Estado de cuenta de un contrato de servicios',
    activa: true,
    umbral_confianza: 0.55,
    version: 1,
    creada_en: '2026-09-10T08:00:00Z',
    actualizada_en: '2026-09-10T08:00:00Z',
    total_documentos: 87,
    palabras_clave: [
      { texto: 'número de contrato', peso: 3 },
      { texto: 'saldo pendiente', peso: 2 },
    ],
    campos: [
      {
        nombre: 'numero_contrato',
        etiqueta: 'Número de contrato',
        tipo_dato: 'texto',
        obligatorio: true,
        regla: { metodo: 'ancla', ancla: 'N° Contrato', regex: '[\\w.-]+' },
      },
      {
        nombre: 'cliente',
        etiqueta: 'Cliente',
        tipo_dato: 'texto',
        obligatorio: true,
        regla: { metodo: 'zona', pagina: 1, x: 0.05, y: 0.1, ancho: 0.5, alto: 0.05 },
      },
      {
        nombre: 'saldo_pendiente',
        etiqueta: 'Saldo pendiente',
        tipo_dato: 'monto',
        obligatorio: true,
        regla: { metodo: 'regex', regex: 'Saldo pendiente\\s*\\$?\\s*([\\d.,]+)' },
      },
      {
        nombre: 'fecha_emision',
        etiqueta: 'Fecha de emisión',
        tipo_dato: 'fecha',
        obligatorio: false,
        regla: { metodo: 'regex', regex: 'Emisión\\s*[:\\-]?\\s*([\\d/\\-]+)' },
      },
      {
        nombre: 'correo_contacto',
        etiqueta: 'Correo de contacto',
        tipo_dato: 'email',
        obligatorio: false,
        regla: { metodo: 'regex', regex: '([\\w.+-]+@[\\w-]+\\.[\\w.-]+)' },
      },
    ],
  },
  {
    id: 12,
    codigo: 'cedula_identidad',
    nombre: 'Cédula de identidad',
    descripcion: 'Documento nacional de identidad',
    activa: false,
    umbral_confianza: 0.65,
    version: 1,
    creada_en: '2026-10-01T12:00:00Z',
    actualizada_en: '2026-10-01T12:00:00Z',
    total_documentos: 23,
    palabras_clave: [
      { texto: 'cédula de identidad', peso: 3 },
      { texto: 'fecha de nacimiento', peso: 1 },
    ],
    campos: [
      {
        nombre: 'numero_documento',
        etiqueta: 'Número de documento',
        tipo_dato: 'cedula',
        obligatorio: true,
        regla: { metodo: 'ancla', ancla: 'N°', regex: '[\\d.-]+' },
      },
      {
        nombre: 'nombres',
        etiqueta: 'Nombres',
        tipo_dato: 'texto',
        obligatorio: true,
        regla: { metodo: 'zona', pagina: 1, x: 0.3, y: 0.3, ancho: 0.6, alto: 0.08 },
      },
      {
        nombre: 'apellidos',
        etiqueta: 'Apellidos',
        tipo_dato: 'texto',
        obligatorio: true,
        regla: { metodo: 'zona', pagina: 1, x: 0.3, y: 0.2, ancho: 0.6, alto: 0.08 },
      },
      {
        nombre: 'fecha_nacimiento',
        etiqueta: 'Fecha de nacimiento',
        tipo_dato: 'fecha',
        obligatorio: true,
        regla: { metodo: 'regex', regex: 'Nacimiento\\s*[:\\-]?\\s*([\\d/\\-]+)' },
      },
      {
        nombre: 'sexo',
        etiqueta: 'Sexo',
        tipo_dato: 'texto',
        obligatorio: false,
        regla: { metodo: 'ancla', ancla: 'Sexo', regex: '[MF]' },
      },
      {
        nombre: 'nacionalidad',
        etiqueta: 'Nacionalidad',
        tipo_dato: 'texto',
        obligatorio: false,
        regla: { metodo: 'ancla', ancla: 'Nacionalidad' },
      },
      {
        nombre: 'fecha_vencimiento',
        etiqueta: 'Fecha de vencimiento',
        tipo_dato: 'fecha',
        obligatorio: false,
        regla: { metodo: 'regex', regex: 'Vence\\s*[:\\-]?\\s*([\\d/\\-]+)' },
      },
    ],
  },
]

export const versionesPlantillaMock: Record<number, VersionPlantilla[]> = {
  3: [
    { version: 1, fecha: '2026-08-01T10:00:00Z', comentario: 'Versión inicial' },
    { version: 2, fecha: '2026-10-15T09:30:00Z', comentario: 'Se agregó el campo "período de facturación"' },
  ],
  7: [{ version: 1, fecha: '2026-09-10T08:00:00Z', comentario: 'Versión inicial' }],
  12: [{ version: 1, fecha: '2026-10-01T12:00:00Z', comentario: 'Versión inicial' }],
}

// ---------------------------------------------------------------------------
// Resultado completo (contrato de docs/01 sección 5)
// ---------------------------------------------------------------------------

export const resultadoMockCompleto: Resultado = {
  documento_id: '9f3c2a1e-0001-4a2b-8c3d-aaaaaaaaaaaa',
  archivo: 'planilla_luz_noviembre.pdf',
  paginas: 1,
  estado: 'COMPLETADO',
  clasificacion: {
    tipo: 'planilla_servicio_electrico',
    plantilla_id: 3,
    plantilla_version: 2,
    confianza: 0.91,
    alternativas: [
      { tipo: 'cuenta_contrato', confianza: 0.34 },
      { tipo: 'cedula_identidad', confianza: 0.02 },
    ],
  },
  campos: {
    numero_cliente: { valor: '1234567-8', confianza: 0.95, pagina: 1, caja: { x: 0.12, y: 0.22, ancho: 0.2, alto: 0.03 } },
    direccion: { valor: 'Av. Siempre Viva 742', confianza: 0.82, pagina: 1, caja: { x: 0.05, y: 0.18, ancho: 0.5, alto: 0.06 } },
    total_pagar: { valor: 45320, confianza: 0.93, pagina: 1, caja: { x: 0.6, y: 0.4, ancho: 0.25, alto: 0.04 } },
    fecha_vencimiento: { valor: '2026-11-30', confianza: 0.9, pagina: 1, caja: { x: 0.6, y: 0.46, ancho: 0.2, alto: 0.03 } },
    consumo_kwh: { valor: 210, confianza: 0.6, pagina: 1, caja: { x: 0.1, y: 0.55, ancho: 0.15, alto: 0.03 } },
    periodo: { valor: null, confianza: 0, pagina: 1 },
  },
  palabras_clave: ['dirección', 'consumo', 'total a pagar'],
  texto_completo:
    'EMPRESA ELÉCTRICA NACIONAL\nPlanilla de servicio eléctrico\nN° Cliente 1234567-8\n' +
    'Dirección: Av. Siempre Viva 742\nLectura anterior 1500  Lectura actual 1710\n' +
    'Consumo kWh 210\nTotal a pagar $45.320\nVencimiento: 30/11/2026\n',
  confianza_global: 0.87,
  advertencias: [
    { codigo: 'campo_obligatorio_faltante', campo: 'periodo', mensaje: 'No se pudo leer el período de facturación.' },
  ],
  tiempos_ms: { ocr: 1840, clasificacion: 25, extraccion: 40, total: 1950 },
  log: [
    { paso: 'ingesta', mensaje: 'Archivo validado (PDF, 1 página, texto no nativo)', duracion_ms: 15, nivel: 'info' },
    { paso: 'preprocesado', mensaje: 'Escala de grises, deskew 0.4°, binarización Sauvola', duracion_ms: 120, nivel: 'info' },
    { paso: 'ocr', mensaje: 'Tesseract (spa), confianza media 0.89', duracion_ms: 1840, nivel: 'info' },
    { paso: 'clasificacion', mensaje: 'Mejor puntaje: planilla_servicio_electrico (0.91)', duracion_ms: 25, nivel: 'info' },
    { paso: 'extraccion', mensaje: '6 campos evaluados, 1 advertencia', duracion_ms: 40, nivel: 'advertencia' },
    { paso: 'ensamblado', mensaje: 'Resultado persistido', duracion_ms: 5, nivel: 'info' },
  ],
  palabras_ocr: [
    { texto: 'N°', pagina: 1, x: 0.05, y: 0.22, ancho: 0.04, alto: 0.03, confianza: 0.9 },
    { texto: 'Cliente', pagina: 1, x: 0.1, y: 0.22, ancho: 0.08, alto: 0.03, confianza: 0.93 },
    { texto: '1234567-8', pagina: 1, x: 0.12, y: 0.22, ancho: 0.2, alto: 0.03, confianza: 0.95 },
  ],
}

function resultadoBase(id: string, archivo: string, plantilla: Plantilla, confianza: number): Resultado {
  return {
    documento_id: id,
    archivo,
    paginas: 1,
    estado: 'COMPLETADO',
    clasificacion: {
      tipo: plantilla.codigo,
      plantilla_id: plantilla.id,
      plantilla_version: plantilla.version ?? 1,
      confianza,
      alternativas: [],
    },
    campos: Object.fromEntries(
      plantilla.campos.map((c) => [
        c.nombre,
        { valor: `Ejemplo ${c.etiqueta}`, confianza: Math.max(0.5, confianza - 0.05), pagina: 1 },
      ]),
    ),
    palabras_clave: plantilla.palabras_clave.map((p) => p.texto),
    texto_completo: `Texto OCR de ejemplo para ${archivo}`,
    confianza_global: confianza,
    advertencias: [],
    tiempos_ms: { ocr: 1200, clasificacion: 20, extraccion: 30, total: 1250 },
  }
}

export const documentosMock: Documento[] = [
  {
    id: resultadoMockCompleto.documento_id,
    archivo: resultadoMockCompleto.archivo,
    fecha: '2026-11-10T14:05:00Z',
    paginas: 1,
    estado: 'COMPLETADO',
    tipo: 'planilla_servicio_electrico',
    plantilla_id: 3,
    plantilla_version: 2,
    confianza: 0.91,
  },
  {
    id: '9f3c2a1e-0002-4a2b-8c3d-bbbbbbbbbbbb',
    archivo: 'cuenta_contrato_octubre.pdf',
    fecha: '2026-11-09T09:20:00Z',
    paginas: 1,
    estado: 'COMPLETADO',
    tipo: 'cuenta_contrato',
    plantilla_id: 7,
    plantilla_version: 1,
    confianza: 0.78,
  },
  {
    id: '9f3c2a1e-0003-4a2b-8c3d-cccccccccccc',
    archivo: 'cedula_juan_perez.jpg',
    fecha: '2026-11-08T16:45:00Z',
    paginas: 1,
    estado: 'COMPLETADO',
    tipo: 'cedula_identidad',
    plantilla_id: 12,
    plantilla_version: 1,
    confianza: 0.69,
  },
  {
    id: '9f3c2a1e-0004-4a2b-8c3d-dddddddddddd',
    archivo: 'documento_desconocido.pdf',
    fecha: '2026-11-07T11:00:00Z',
    paginas: 2,
    estado: 'COMPLETADO',
    tipo: 'desconocido',
    plantilla_id: null,
    plantilla_version: null,
    confianza: 0.31,
  },
  {
    id: '9f3c2a1e-0005-4a2b-8c3d-eeeeeeeeeeee',
    archivo: 'planilla_escaneada_borrosa.jpg',
    fecha: '2026-11-06T08:30:00Z',
    paginas: 1,
    estado: 'ERROR',
    tipo: null,
    plantilla_id: null,
    plantilla_version: null,
    confianza: null,
    mensaje_error: 'Tesseract no pudo procesar la imagen (resolución insuficiente).',
  },
]

export const resultadosMock: Record<string, Resultado> = {
  [documentosMock[0].id]: resultadoMockCompleto,
  [documentosMock[1].id]: resultadoBase(documentosMock[1].id, documentosMock[1].archivo, plantillasMock[1], 0.78),
  [documentosMock[2].id]: resultadoBase(documentosMock[2].id, documentosMock[2].archivo, plantillasMock[2], 0.69),
  [documentosMock[3].id]: {
    documento_id: documentosMock[3].id,
    archivo: documentosMock[3].archivo,
    paginas: 2,
    estado: 'COMPLETADO',
    clasificacion: {
      tipo: 'desconocido',
      plantilla_id: null,
      confianza: 0.31,
      alternativas: [
        { tipo: 'cuenta_contrato', confianza: 0.31 },
        { tipo: 'planilla_servicio_electrico', confianza: 0.18 },
      ],
    },
    campos: {},
    palabras_clave: ['número', 'fecha'],
    texto_completo: 'Texto OCR sin coincidencias claras con ninguna plantilla registrada...',
    confianza_global: 0.31,
    advertencias: [{ codigo: 'tipo_no_identificado', mensaje: 'Ninguna plantilla superó el umbral de confianza.' }],
    tiempos_ms: { ocr: 2100, clasificacion: 30, extraccion: 0, total: 2130 },
  },
}
