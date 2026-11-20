import type { ClienteApi } from './contrato'
import { ErrorApi } from '@/tipos'
import { adaptarAdvertencia, adaptarDocumento, adaptarPlantilla, adaptarResultado, type DocumentoApi } from './adaptadores'
import { aQuery, solicitar, solicitarBlob, solicitarBlobConCabeceras, solicitarPublico } from './http'
import type {
  Documento,
  FiltrosDocumentos,
  OrigenRecorte,
  Orientacion,
  PalabrasPagina,
  ListaPaginada,
  Plantilla,
  FlujoCaptura,
  FlujoCapturaEntrada,
  FlujoPublico,
  PlantillaEntrada,
  Resultado,
  ResultadoPublico,
  ResumenPurga,
  Salud,
  SugerenciaPlantilla,
  Usuario,
  UsuarioConClave,
  VersionPlantilla,
  VistaPreviaPurga,
  Yo,
} from '@/tipos'

export const apiHttp: ClienteApi = {
  salud: () => solicitar<Salud>('/salud'),
  // Un backend anterior a docs/07 no tiene /yo y solo conoce la clave única del sistema (Administrador).
  yo: () =>
    solicitar<Yo>('/yo').catch((e: unknown): Yo => {
      if (e instanceof ErrorApi && e.status === 404) return { usuario_id: null, nombre: 'Sistema', rol: 'Administrador' }
      throw e
    }),

  procesarDocumento(archivo, plantillaId) {
    const fd = new FormData()
    fd.append('archivo', archivo)
    if (plantillaId) fd.append('plantilla_id', String(plantillaId))
    fd.append('sincrono', 'true')
    return solicitar<Resultado>('/documentos', { method: 'POST', body: fd, crudo: true }).then(adaptarResultado)
  },

  async listarDocumentos(filtros: FiltrosDocumentos) {
    const lista = await solicitar<ListaPaginada<DocumentoApi>>(
      `/documentos${aQuery({
        tipo: filtros.tipo,
        estado: filtros.estado,
        desde: filtros.desde,
        hasta: filtros.hasta,
        pagina: filtros.pagina ?? 1,
        tamano: filtros.tamano ?? 20,
      })}`,
    )
    return { ...lista, items: lista.items.map(adaptarDocumento) } as ListaPaginada<Documento>
  },

  obtenerDocumento: (id) => solicitar<DocumentoApi>(`/documentos/${id}`).then(adaptarDocumento),
  obtenerResultado: (id) => solicitar<Resultado>(`/documentos/${id}/resultado`).then(adaptarResultado),
  descargarArchivo: (id) => solicitarBlob(`/documentos/${id}/archivo`),
  obtenerImagenPagina: (id, pagina) => solicitarBlob(`/documentos/${id}/paginas/${pagina}`),
  reprocesarDocumento: (id) =>
    solicitar<Resultado>(`/documentos/${id}/reprocesar`, { method: 'POST' }).then(adaptarResultado),

  async obtenerImagenEnderezada(id, pagina, opciones = {}) {
    const { blob, cabeceras } = await solicitarBlobConCabeceras(
      `/documentos/${id}/paginas/${pagina}/enderezada${aQuery({ relacion: opciones.relacion, formato: opciones.formato })}`,
    )
    return {
      blob,
      confiable: cabeceras.get('X-Recorte-Confiable') === 'true',
      origen: (cabeceras.get('X-Recorte-Origen') ?? 'desconocido') as OrigenRecorte,
      orientacion: Number(cabeceras.get('X-Orientacion') ?? 0) as Orientacion,
    }
  },
  obtenerPalabras: (id, pagina, relacion) =>
    solicitar<PalabrasPagina>(`/documentos/${id}/paginas/${pagina}/palabras${aQuery({ relacion })}`),
  recortarPagina: (id, pagina, entrada) =>
    solicitar<Resultado>(`/documentos/${id}/paginas/${pagina}/recorte`, { method: 'POST', body: entrada }).then(
      adaptarResultado,
    ),
  quitarRecortePagina: (id, pagina) =>
    solicitar<Resultado>(`/documentos/${id}/paginas/${pagina}/recorte`, { method: 'DELETE' }).then(adaptarResultado),

  listarPlantillas: (activa) =>
    solicitar<Plantilla[]>(`/plantillas${aQuery({ activa })}`).then((l) => l.map(adaptarPlantilla)),
  obtenerPlantilla: (id) => solicitar<Plantilla>(`/plantillas/${id}`).then(adaptarPlantilla),
  crearPlantilla: (entrada: PlantillaEntrada) => solicitar<Plantilla>('/plantillas', { method: 'POST', body: entrada }),
  actualizarPlantilla: (id, entrada) => solicitar<Plantilla>(`/plantillas/${id}`, { method: 'PUT', body: entrada }),
  cambiarEstadoPlantilla: (id, activa) =>
    solicitar<Plantilla>(`/plantillas/${id}/estado`, { method: 'PATCH', body: { activa } }),
  // El backend recibe `documento_id` como parámetro de consulta (no en el cuerpo JSON).
  sugerirPlantilla: (documentoId) =>
    solicitar<SugerenciaPlantilla>(`/plantillas/sugerir${aQuery({ documento_id: documentoId })}`, { method: 'POST' }),
  probarPlantilla: (id, documentoId) =>
    solicitar<Resultado>(`/plantillas/${id}/probar${aQuery({ documento_id: documentoId })}`, { method: 'POST' }).then(
      adaptarResultado,
    ),
  listarVersionesPlantilla: (id) => solicitar<VersionPlantilla[]>(`/plantillas/${id}/versiones`),
  reprocesarDocumentosDePlantilla: (id) =>
    solicitar<{ total: number }>(`/plantillas/${id}/reprocesar`, { method: 'POST' }),

  fijarPermisosPlantilla: (id, rol) =>
    solicitar<Plantilla>(`/plantillas/${id}/permisos`, { method: 'PATCH', body: { rol_minimo_edicion: rol } }).then(
      adaptarPlantilla,
    ),

  // Flujos de captura
  listarFlujos: (todos) => solicitar<FlujoCaptura[]>(`/flujos-captura${aQuery({ todos: todos ? true : undefined })}`),
  obtenerFlujo: (codigo) => solicitar<FlujoCaptura>(`/flujos-captura/${encodeURIComponent(codigo)}`),
  crearFlujo: (entrada: FlujoCapturaEntrada) =>
    solicitar<FlujoCaptura>('/flujos-captura', { method: 'POST', body: entrada }),
  actualizarFlujo: (id, entrada) => solicitar<FlujoCaptura>(`/flujos-captura/${id}`, { method: 'PUT', body: entrada }),
  cambiarEstadoFlujo: (id, activo) =>
    solicitar<FlujoCaptura>(`/flujos-captura/${id}/estado`, { method: 'PATCH', body: { activo } }),
  fijarAccesoPublicoFlujo: (id, acceso) =>
    solicitar<FlujoCaptura>(`/flujos-captura/${id}/acceso-publico`, { method: 'PATCH', body: { acceso_publico: acceso } }),
  procesarConFlujo(codigo, archivo) {
    const fd = new FormData()
    fd.append('archivo', archivo)
    return solicitar<Resultado>(`/flujos-captura/${encodeURIComponent(codigo)}/documentos`, {
      method: 'POST',
      body: fd,
      crudo: true,
    }).then(adaptarResultado)
  },

  // Acceso público (sin clave)
  obtenerFlujoPublico: (codigo) => solicitarPublico<FlujoPublico>(`/flujos-captura/${encodeURIComponent(codigo)}/publico`),
  subirDocumentoPublico(codigo, archivo, avisoVersion) {
    const fd = new FormData()
    fd.append('archivo', archivo)
    fd.append('consentimiento', 'true') // la pantalla solo permite subir tras marcar la casilla del aviso
    fd.append('aviso_version', avisoVersion)
    return solicitarPublico<ResultadoPublico>(`/flujos-captura/${encodeURIComponent(codigo)}/documentos`, {
      method: 'POST',
      body: fd,
    }).then((r) => ({ ...r, advertencias: (r.advertencias ?? []).map((a) => adaptarAdvertencia(a)) }))
  },

  // Retención y purga
  vistaPreviaPurga: () => solicitar<VistaPreviaPurga>('/purga'),
  purgarDocumentos: (alcance) => solicitar<ResumenPurga>('/purga', { method: 'POST', body: { alcance, confirmar: true } }),

  // Usuarios
  listarUsuarios: () => solicitar<Usuario[]>('/usuarios'),
  crearUsuario: (entrada) => solicitar<UsuarioConClave>('/usuarios', { method: 'POST', body: entrada }),
  actualizarUsuario: (id, cambios) => solicitar<Usuario>(`/usuarios/${id}`, { method: 'PATCH', body: cambios }),
  regenerarClaveUsuario: (id) => solicitar<UsuarioConClave>(`/usuarios/${id}/clave`, { method: 'POST' }),
}
