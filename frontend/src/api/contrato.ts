import type {
  Campo,
  DisenoPlantilla,
  Documento,
  EstadoDocumento,
  ImagenEnderezada,
  Orientacion,
  PalabrasPagina,
  FiltrosDocumentos,
  ListaPaginada,
  Plantilla,
  FlujoCaptura,
  FlujoCapturaEntrada,
  FlujoPublico,
  PlantillaEntrada,
  Resultado,
  ResultadoPublico,
  ResumenPurga,
  Rol,
  Salud,
  SugerenciaPlantilla,
  Usuario,
  UsuarioConClave,
  VersionPlantilla,
  VistaPreviaPurga,
  Yo,
} from '@/tipos'

/**
 * Contrato del cliente de API. Hay dos implementaciones intercambiables:
 * - `apiHttp` (src/api/apiHttp.ts): llama al backend real en /api.
 * - `apiMock` (src/api/mock/): datos en memoria, activo con VITE_USAR_MOCK=true.
 */
export interface ClienteApi {
  // Sistema
  salud(): Promise<Salud>
  /** Identidad y rol de la API key en uso */
  yo(): Promise<Yo>

  // Documentos
  procesarDocumento(archivo: File, plantillaId?: number | null): Promise<Resultado>
  listarDocumentos(filtros: FiltrosDocumentos): Promise<ListaPaginada<Documento>>
  obtenerDocumento(id: string): Promise<Documento>
  obtenerResultado(id: string): Promise<Resultado>
  descargarArchivo(id: string): Promise<Blob>
  obtenerImagenPagina(id: string, pagina: number): Promise<Blob>
  reprocesarDocumento(id: string): Promise<Resultado>

  // Cuadrícula de zonas (docs/13 §7)
  /** Página recortada y enderezada en color: el marco de las coordenadas de `obtenerPalabras` */
  obtenerImagenEnderezada(
    id: string,
    pagina: number,
    opciones?: { relacion?: number | null; formato?: 'png' | 'jpeg' },
  ): Promise<ImagenEnderezada>
  /** Palabras del OCR con posición relativa. Error 404 si el documento es anterior a la función (hay que reprocesarlo). */
  obtenerPalabras(id: string, pagina: number, relacion?: number | null): Promise<PalabrasPagina>
  /** Recorte y/o giro manual: reprocesa el documento con esas esquinas (relativas a la imagen original) */
  recortarPagina(
    id: string,
    pagina: number,
    entrada: { esquinas?: [number, number][] | null; orientacion?: Orientacion },
  ): Promise<Resultado>
  /** Quita el recorte manual y vuelve a la detección automática (reprocesa) */
  quitarRecortePagina(id: string, pagina: number): Promise<Resultado>

  // Plantillas
  listarPlantillas(activa?: boolean): Promise<Plantilla[]>
  obtenerPlantilla(id: number): Promise<Plantilla>
  crearPlantilla(entrada: PlantillaEntrada): Promise<Plantilla>
  actualizarPlantilla(id: number, entrada: PlantillaEntrada): Promise<Plantilla>
  cambiarEstadoPlantilla(id: number, activa: boolean): Promise<Plantilla>
  /** De 1 a 3 documentos de ejemplo del mismo tipo: con 2 o más, lo común es palabra clave y los datos del titular quedan fuera */
  sugerirPlantilla(documentoIds: string[]): Promise<SugerenciaPlantilla>
  /**
   * Aplica la plantilla a un documento ya procesado, sin guardar nada. `cambios` prueba campos o un diseño aún sin
   * guardar (vista previa del editor de cuadrícula); `diseno: null` explícito prueba sin cuadrícula.
   */
  probarPlantilla(
    id: number,
    documentoId: string,
    cambios?: { campos?: Campo[]; diseno?: DisenoPlantilla | null },
  ): Promise<Resultado>
  /** Versiones de una plantilla (opcional en el backend; el mock la implementa) */
  listarVersionesPlantilla(id: number): Promise<VersionPlantilla[]>
  /** Reprocesa todos los documentos que usaron esta plantilla; devuelve cuántos encoló */
  reprocesarDocumentosDePlantilla(id: number): Promise<{ total: number }>
  /** Rol mínimo para editar la plantilla (solo Administrador) */
  fijarPermisosPlantilla(id: number, rol: Rol): Promise<Plantilla>

  // Flujos de captura
  /** `todos` incluye los inactivos (Editor o superior) */
  listarFlujos(todos?: boolean): Promise<FlujoCaptura[]>
  obtenerFlujo(codigo: string): Promise<FlujoCaptura>
  crearFlujo(entrada: FlujoCapturaEntrada): Promise<FlujoCaptura>
  actualizarFlujo(id: number, entrada: FlujoCapturaEntrada): Promise<FlujoCaptura>
  cambiarEstadoFlujo(id: number, activo: boolean): Promise<FlujoCaptura>
  /** Abre o cierra el acceso SIN clave a un flujo (solo Administrador y solo si el servidor lo habilita) */
  fijarAccesoPublicoFlujo(id: number, acceso: boolean): Promise<FlujoCaptura>
  /** Procesa un documento clasificando solo entre las plantillas del flujo (estado NO_COINCIDE si ninguna aplica) */
  procesarConFlujo(codigo: string, archivo: File): Promise<Resultado>

  // Acceso PÚBLICO (sin API key): nunca envían la clave
  obtenerFlujoPublico(codigo: string): Promise<FlujoPublico>
  /** `avisoVersion`: versión del aviso de privacidad que la persona aceptó (el servidor la registra con la fecha) */
  subirDocumentoPublico(codigo: string, archivo: File, avisoVersion: string): Promise<ResultadoPublico>

  // Retención y purga de documentos (solo Administrador)
  vistaPreviaPurga(): Promise<VistaPreviaPurga>
  purgarDocumentos(alcance: 'vencidos' | 'todos'): Promise<ResumenPurga>

  // Usuarios (solo Administrador)
  listarUsuarios(): Promise<Usuario[]>
  crearUsuario(entrada: { nombre: string; rol: Rol }): Promise<UsuarioConClave>
  actualizarUsuario(id: number, cambios: { nombre?: string; rol?: Rol; activo?: boolean }): Promise<Usuario>
  /** Genera una API key nueva (la anterior deja de valer); se muestra una sola vez */
  regenerarClaveUsuario(id: number): Promise<UsuarioConClave>
}

export type { EstadoDocumento }
