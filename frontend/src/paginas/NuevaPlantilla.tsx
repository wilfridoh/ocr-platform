import { useEffect, useMemo, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useMutation, useQuery } from '@tanstack/react-query'
import { api } from '@/api'
import type { Campo, PalabraClave, Resultado, ZonaEtiqueta } from '@/tipos'
import { MAX_EJEMPLOS_PLANTILLA } from '@/tipos'
import CargaArchivo from '@/componentes/CargaArchivo'
import VisorPagina from '@/componentes/VisorPagina'
import EditorPalabrasClave from '@/componentes/EditorPalabrasClave'
import EditorCampos from '@/componentes/EditorCampos'
import TablaCampos, { filasDesdeResultado } from '@/componentes/TablaCampos'
import CargandoIndicador from '@/componentes/CargandoIndicador'
import { probarEnMemoria } from '@/utilidades/probarEnMemoria'

const PASOS = ['Documentos de ejemplo', 'Identificación', 'Campos'] as const

/** Un documento de ejemplo del asistente: un archivo aún sin procesar o un documento ya procesado. */
interface EjemploLocal {
  clave: string
  archivo?: File
  url?: string | null
  resultado?: Resultado
}

export default function NuevaPlantilla() {
  const navigate = useNavigate()
  const location = useLocation() as { state?: { documentoId?: string } }
  const documentoIdPrevio = location.state?.documentoId

  const [paso, setPaso] = useState(0)
  const [ejemplos, setEjemplos] = useState<EjemploLocal[]>([])
  const [activo, setActivo] = useState(0)
  const [sugeridoPara, setSugeridoPara] = useState('')
  const [zonasSugeridas, setZonasSugeridas] = useState<ZonaEtiqueta[]>([])
  const resultadoEjemplo = ejemplos[0]?.resultado ?? null
  const urlVistaPrevia = ejemplos[activo]?.url ?? ejemplos[0]?.url ?? null

  const [codigo, setCodigo] = useState('')
  const [nombre, setNombre] = useState('')
  const [descripcion, setDescripcion] = useState('')
  const [umbral, setUmbral] = useState(0.6)
  const [palabrasClave, setPalabrasClave] = useState<PalabraClave[]>([])
  const [campos, setCampos] = useState<Campo[]>([])

  const resultadoPrevioQuery = useQuery({
    queryKey: ['resultado', documentoIdPrevio],
    queryFn: () => api.obtenerResultado(documentoIdPrevio!),
    enabled: Boolean(documentoIdPrevio) && ejemplos.length === 0,
  })

  useEffect(() => {
    if (resultadoPrevioQuery.data && ejemplos.length === 0) {
      setEjemplos([{ clave: resultadoPrevioQuery.data.documento_id, resultado: resultadoPrevioQuery.data }])
    }
  }, [resultadoPrevioQuery.data, ejemplos.length])

  const procesarEjemplo = useMutation({ mutationFn: (f: File) => api.procesarDocumento(f) })

  const sugerir = useMutation({
    mutationFn: (documentoIds: string[]) => api.sugerirPlantilla(documentoIds),
    onSuccess: (sugerencia, documentoIds) => {
      setPalabrasClave(sugerencia.palabras_clave)
      setCampos(sugerencia.campos)
      setZonasSugeridas(sugerencia.zonas_sugeridas ?? [])
      setSugeridoPara(documentoIds.join(','))
    },
  })

  const crear = useMutation({
    mutationFn: () =>
      api.crearPlantilla({
        codigo,
        nombre,
        descripcion,
        activa: true,
        umbral_confianza: umbral,
        // "revisar" es solo una marca de la sugerencia: no se guarda
        palabras_clave: palabrasClave.map(({ texto, peso }) => ({ texto, peso })),
        campos,
      }),
    onSuccess: (plantilla) => {
      const primero = ejemplos[0]?.resultado?.documento_id
      if (zonasSugeridas.length && primero) {
        // las etiquetas sugeridas se precargan en la cuadrícula para revisarlas (no se guardan solas)
        navigate(`/plantillas/${plantilla.id}/zonas?documento=${primero}`, { state: { zonasSugeridas } })
      } else {
        navigate(`/plantillas/${plantilla.id}`)
      }
    },
  })

  const agregarEjemplo = (f: File) => {
    if (ejemplos.length >= MAX_EJEMPLOS_PLANTILLA) return
    const url = f.type.startsWith('image/') ? URL.createObjectURL(f) : null
    setEjemplos((es) => [...es, { clave: `${f.name}-${Date.now()}`, archivo: f, url }])
    setActivo(ejemplos.length)
  }

  const quitarEjemplo = (clave: string) => {
    setEjemplos((es) => {
      const e = es.find((x) => x.clave === clave)
      if (e?.url) URL.revokeObjectURL(e.url)
      return es.filter((x) => x.clave !== clave)
    })
    setActivo(0)
  }

  const avanzarDesdePaso1 = async () => {
    // procesa los ejemplos que aún son solo archivos (uno tras otro: el OCR es pesado)
    const listos: EjemploLocal[] = []
    for (const e of ejemplos) {
      if (e.resultado) listos.push(e)
      else if (e.archivo) listos.push({ ...e, resultado: await procesarEjemplo.mutateAsync(e.archivo) })
    }
    setEjemplos(listos)
    const ids = listos.map((e) => e.resultado!.documento_id)
    // se vuelve a sugerir solo si cambió el conjunto de ejemplos (no pisa ajustes hechos con los mismos)
    if (ids.join(',') !== sugeridoPara) await sugerir.mutateAsync(ids)
    setPaso(1)
  }

  const vistaPrevia = useMemo(() => {
    if (!resultadoEjemplo) return null
    return probarEnMemoria({ codigo, campos }, resultadoEjemplo)
  }, [resultadoEjemplo, codigo, campos])

  const puedeGuardar = codigo.trim() !== '' && nombre.trim() !== '' && campos.length > 0

  return (
    <div>
      <h2 className="mb-1 text-[22px] font-bold tracking-[-0.01em] text-ink">Nueva plantilla</h2>
      <ol className="mb-6 flex gap-4 text-sm">
        {PASOS.map((p, i) => (
          <li key={p} className={`flex items-center gap-2 ${i === paso ? 'font-semibold text-indigo-700' : 'text-slate-400'}`}>
            <span
              className={`flex h-6 w-6 items-center justify-center rounded-full text-xs ${
                i === paso ? 'bg-indigo-600 text-white' : i < paso ? 'bg-indigo-100 text-indigo-700' : 'bg-slate-100'
              }`}
            >
              {i + 1}
            </span>
            {p}
          </li>
        ))}
      </ol>

      <div className="grid gap-6 lg:grid-cols-[1fr_380px]">
        <div>
          {paso === 0 && (
            <div className="tarjeta space-y-4 p-4">
              <div className="flex items-center justify-between gap-3">
                <p className="text-sm text-slate-600">
                  Sube de 1 a {MAX_EJEMPLOS_PLANTILLA} documentos del <b>mismo tipo</b>. Lo que se repite en todos pasa a ser
                  palabra clave o etiqueta fija; los datos de cada titular quedan fuera.
                </p>
                <span className="whitespace-nowrap rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600">
                  {ejemplos.length} de {MAX_EJEMPLOS_PLANTILLA}
                </span>
              </div>

              {ejemplos.length > 0 && (
                <ol className="divide-y divide-slate-100 rounded-md border border-slate-200">
                  {ejemplos.map((e, i) => (
                    <li key={e.clave} className={`flex items-center gap-3 px-3 py-2 text-sm ${i === activo ? 'bg-indigo-50' : ''}`}>
                      <span className="flex h-6 w-6 items-center justify-center rounded-full bg-slate-100 text-xs font-semibold">{i + 1}</span>
                      <button type="button" className="flex-1 truncate text-left text-slate-700" onClick={() => setActivo(i)}>
                        {e.resultado?.archivo ?? e.archivo?.name}
                        <span className="ml-2 text-xs text-slate-400">{e.resultado ? 'procesado' : 'por procesar'}</span>
                      </button>
                      <button
                        type="button"
                        aria-label={`Quitar el ejemplo ${i + 1}`}
                        className="text-slate-400 hover:text-red-600"
                        disabled={procesarEjemplo.isPending || sugerir.isPending}
                        onClick={() => quitarEjemplo(e.clave)}
                      >
                        ✕
                      </button>
                    </li>
                  ))}
                </ol>
              )}

              {ejemplos.length === 1 && (
                <p className="rounded-md bg-amber-50 px-3 py-2 text-xs text-amber-800">
                  Con un solo ejemplo las sugerencias llegan <b>para revisar</b>: no hay con qué comparar para separar los textos
                  impresos de los datos del titular. Agrega otro documento del mismo tipo si puedes.
                </p>
              )}
              {ejemplos.length >= 2 && (
                <p className="rounded-md bg-emerald-50 px-3 py-2 text-xs text-emerald-800">
                  Con {ejemplos.length} ejemplos, lo que se repite en todos pasa a ser palabra clave o etiqueta fija; los datos del
                  titular quedan fuera.
                </p>
              )}

              {ejemplos.length < MAX_EJEMPLOS_PLANTILLA ? (
                <CargaArchivo onArchivoSeleccionado={agregarEjemplo} archivoActual={null} />
              ) : (
                <p className="text-center text-xs text-slate-400">Máximo {MAX_EJEMPLOS_PLANTILLA} ejemplos: quita uno para agregar otro.</p>
              )}

              {ejemplos[activo] && (
                <div>
                  {ejemplos.length > 1 && (
                    <div className="mb-2 flex gap-1 text-xs">
                      {ejemplos.map((e, i) => (
                        <button
                          key={e.clave}
                          type="button"
                          onClick={() => setActivo(i)}
                          className={`rounded px-2 py-1 ${i === activo ? 'bg-indigo-600 text-white' : 'bg-slate-100 text-slate-600'}`}
                        >
                          Ejemplo {i + 1}
                        </button>
                      ))}
                    </div>
                  )}
                  <VisorPagina src={ejemplos[activo].url ?? null} />
                  {ejemplos[activo].resultado && (
                    <details className="mt-3">
                      <summary className="cursor-pointer text-sm text-indigo-600">Ver texto OCR</summary>
                      <pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap rounded bg-slate-50 p-3 text-xs text-slate-600">
                        {ejemplos[activo].resultado!.texto_completo}
                      </pre>
                    </details>
                  )}
                </div>
              )}

              {(procesarEjemplo.isPending || sugerir.isPending) && (
                <CargandoIndicador
                  etiqueta={procesarEjemplo.isPending ? 'Procesando los documentos de ejemplo...' : 'Buscando lo que tienen en común...'}
                />
              )}
              {(procesarEjemplo.isError || sugerir.isError) && (
                <p className="text-sm text-red-600">{((procesarEjemplo.error ?? sugerir.error) as Error).message}</p>
              )}

              <div className="flex justify-end">
                <button
                  type="button"
                  className="boton-primario"
                  disabled={ejemplos.length === 0 || procesarEjemplo.isPending || sugerir.isPending}
                  onClick={avanzarDesdePaso1}
                >
                  Siguiente
                </button>
              </div>
            </div>
          )}

          {paso === 1 && (
            <div className="tarjeta space-y-4 p-4">
              <div className="grid gap-3 sm:grid-cols-2">
                <div>
                  <label className="etiqueta-campo">Código del tipo (snake_case)</label>
                  <input
                    className="campo-entrada font-mono"
                    value={codigo}
                    onChange={(e) => setCodigo(e.target.value)}
                    placeholder="planilla_servicio_electrico"
                  />
                </div>
                <div>
                  <label className="etiqueta-campo">Nombre</label>
                  <input className="campo-entrada" value={nombre} onChange={(e) => setNombre(e.target.value)} placeholder="Planilla servicio eléctrico" />
                </div>
              </div>
              <div>
                <label className="etiqueta-campo">Descripción</label>
                <input className="campo-entrada" value={descripcion} onChange={(e) => setDescripcion(e.target.value)} />
              </div>
              <div className="w-48">
                <label className="etiqueta-campo">Umbral de confianza</label>
                <input
                  type="number"
                  min={0}
                  max={1}
                  step={0.05}
                  className="campo-entrada"
                  value={umbral}
                  onChange={(e) => setUmbral(Number(e.target.value))}
                />
              </div>
              <div>
                <label className="etiqueta-campo">Palabras clave (sugeridas automáticamente, ajústalas)</label>
                <EditorPalabrasClave valor={palabrasClave} onCambiar={setPalabrasClave} />
              </div>

              <div className="flex justify-between">
                <button type="button" className="boton-secundario" onClick={() => setPaso(0)}>
                  Atrás
                </button>
                <button type="button" className="boton-primario" disabled={!codigo || !nombre} onClick={() => setPaso(2)}>
                  Siguiente
                </button>
              </div>
            </div>
          )}

          {paso === 2 && (
            <div className="space-y-4">
              <div className="tarjeta p-4">
                <p className="mb-3 text-sm text-slate-500">
                  Campos sugeridos a partir del documento de ejemplo. Ajusta nombre, tipo, obligatoriedad y la regla de
                  extracción de cada uno.
                </p>
                <EditorCampos campos={campos} onCambiar={setCampos} imagenSrc={urlVistaPrevia} />
              </div>
              <div className="flex justify-between">
                <button type="button" className="boton-secundario" onClick={() => setPaso(1)}>
                  Atrás
                </button>
                <button type="button" className="boton-primario" disabled={!puedeGuardar || crear.isPending} onClick={() => crear.mutate()}>
                  {crear.isPending ? 'Guardando...' : 'Guardar y activar'}
                </button>
              </div>
              {crear.isError && <p className="text-sm text-red-600">{(crear.error as Error).message}</p>}
            </div>
          )}
        </div>

        <div>
          <h3 className="mb-2 text-sm font-semibold text-slate-600">Resultado con esta plantilla</h3>
          {vistaPrevia ? (
            <TablaCampos filas={filasDesdeResultado(campos, vistaPrevia.campos)} />
          ) : (
            <p className="tarjeta p-4 text-sm text-slate-400">
              Sube o elige un documento de ejemplo para ver la vista previa en vivo.
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
