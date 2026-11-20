import type {
  Documento,
  EstadoDocumento,
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

  // Plantillas
  listarPlantillas(activa?: boolean): Promise<Plantilla[]>
  obtenerPlantilla(id: number): Promise<Plantilla>
  crearPlantilla(entrada: PlantillaEntrada): Promise<Plantilla>
  actualizarPlantilla(id: number, entrada: PlantillaEntrada): Promise<Plantilla>
  cambiarEstadoPlantilla(id: number, activa: boolean): Promise<Plantilla>
  sugerirPlantilla(documentoId: string): Promise<SugerenciaPlantilla>
  probarPlantilla(id: number, documentoId: string): Promise<Resultado>
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
