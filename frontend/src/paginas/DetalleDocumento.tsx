import { useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/api'
import VisorPagina, { type CajaResaltada } from '@/componentes/VisorPagina'
import TablaCampos from '@/componentes/TablaCampos'
import VisorJSON from '@/componentes/VisorJSON'
import CargandoIndicador from '@/componentes/CargandoIndicador'
import MensajeError from '@/componentes/MensajeError'
import InsigniaEstado from '@/componentes/InsigniaEstado'
import { formatearFecha, formatearPorcentaje } from '@/utilidades/formato'

type Pestana = 'resultado' | 'texto' | 'tiempos' | 'log'

export default function DetalleDocumento() {
  const { id = '' } = useParams()
  const queryClient = useQueryClient()
  const [pestana, setPestana] = useState<Pestana>('resultado')
  const [campoResaltado, setCampoResaltado] = useState<string | null>(null)
  const [mostrarJson, setMostrarJson] = useState(false)

  const documentoQuery = useQuery({ queryKey: ['documento', id], queryFn: () => api.obtenerDocumento(id) })
  const resultadoQuery = useQuery({ queryKey: ['resultado', id], queryFn: () => api.obtenerResultado(id) })
  const plantillaQuery = useQuery({
    queryKey: ['plantilla', resultadoQuery.data?.clasificacion.plantilla_id],
    queryFn: () => api.obtenerPlantilla(resultadoQuery.data!.clasificacion.plantilla_id!),
    enabled: Boolean(resultadoQuery.data?.clasificacion.plantilla_id),
  })
  const imagenQuery = useQuery({
    queryKey: ['pagina', id, 1],
    queryFn: async () => URL.createObjectURL(await api.obtenerImagenPagina(id, 1)),
    enabled: Boolean(resultadoQuery.data),
  })

  const reprocesar = useMutation({
    mutationFn: () => api.reprocesarDocumento(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['resultado', id] })
      queryClient.invalidateQueries({ queryKey: ['documento', id] })
    },
  })

  const resultado = resultadoQuery.data
  const documento = documentoQuery.data

  const filas = useMemo(() => {
    if (!resultado) return []
    if (plantillaQuery.data) {
      return plantillaQuery.data.campos.map((c) => ({
        nombre: c.nombre,
        etiqueta: c.etiqueta,
        obligatorio: c.obligatorio,
        extraido: resultado.campos[c.nombre],
      }))
    }
    return Object.entries(resultado.campos).map(([nombre, extraido]) => ({ nombre, etiqueta: nombre, extraido }))
  }, [resultado, plantillaQuery.data])

  const cajas: CajaResaltada[] = useMemo(() => {
    if (!resultado || !campoResaltado) return []
    const c = resultado.campos[campoResaltado]
    if (!c?.caja) return []
    return [{ id: campoResaltado, ...c.caja, color: '#4f46e5' }]
  }, [resultado, campoResaltado])

  if (documentoQuery.isLoading || resultadoQuery.isLoading) return <CargandoIndicador etiqueta="Cargando documento..." />
  if (documentoQuery.isError) return <MensajeError mensaje={(documentoQuery.error as Error).message} onReintentar={() => documentoQuery.refetch()} />
  if (resultadoQuery.isError) return <MensajeError mensaje={(resultadoQuery.error as Error).message} onReintentar={() => resultadoQuery.refetch()} />
  if (!resultado || !documento) return null

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <div>
          <Link to="/documentos" className="text-sm text-indigo-600 hover:underline">
            ← Volver al historial
          </Link>
          <h2 className="mt-1 text-[22px] font-bold tracking-[-0.01em] text-ink">{documento.archivo}</h2>
          <p className="text-sm text-slate-500">
            {formatearFecha(documento.fecha)} · Plantilla v{resultado.clasificacion.plantilla_version ?? '—'}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <InsigniaEstado estado={documento.estado} />
          <button type="button" className="boton-secundario" onClick={() => reprocesar.mutate()} disabled={reprocesar.isPending}>
            {reprocesar.isPending ? 'Reprocesando...' : 'Reprocesar'}
          </button>
        </div>
      </div>

      <div className="mb-4 flex flex-wrap items-center gap-3 text-sm">
        <span className="text-slate-500">Tipo:</span>
        <span className="font-medium text-slate-800">{plantillaQuery.data?.nombre ?? resultado.clasificacion.tipo}</span>
        <span className="text-slate-500">Confianza global</span>
        <span className="font-medium text-slate-800">{formatearPorcentaje(resultado.confianza_global)}</span>
      </div>

      <div className="mb-4 flex gap-1 rounded-md bg-slate-100 p-1 text-sm">
        {([
          ['resultado', 'Resultado'],
          ['texto', 'Texto OCR'],
          ['tiempos', 'Tiempos'],
          ['log', 'Log de procesamiento'],
        ] as [Pestana, string][]).map(([id_, etiqueta]) => (
          <button
            key={id_}
            type="button"
            onClick={() => setPestana(id_)}
            className={`rounded-md px-3 py-1.5 font-medium transition-colors ${
              pestana === id_ ? 'bg-white text-indigo-700 shadow-sm' : 'text-slate-500 hover:text-slate-700'
            }`}
          >
            {etiqueta}
          </button>
        ))}
      </div>

      {pestana === 'resultado' && (
        <div>
          <div className="grid gap-4 lg:grid-cols-2">
            <VisorPagina src={imagenQuery.data ?? null} cajas={cajas} />
            <TablaCampos filas={filas} campoResaltado={campoResaltado} onResaltar={setCampoResaltado} />
          </div>

          {resultado.advertencias.length > 0 && (
            <ul className="mt-4 space-y-1 text-sm text-amber-700">
              {resultado.advertencias.map((a, i) => (
                <li key={i} className="rounded bg-amber-50 px-3 py-2">
                  {a.mensaje}
                </li>
              ))}
            </ul>
          )}

          <div className="mt-4 flex flex-wrap gap-2">
            <button type="button" className="boton-secundario" onClick={() => setMostrarJson((v) => !v)}>
              {mostrarJson ? 'Ocultar JSON' : 'Ver JSON'}
            </button>
            <button
              type="button"
              className="boton-secundario"
              onClick={() => navigator.clipboard.writeText(JSON.stringify(resultado, null, 2))}
            >
              Copiar JSON
            </button>
          </div>
          {mostrarJson && (
            <div className="mt-4">
              <VisorJSON datos={resultado} nombreArchivo={`${resultado.documento_id}.json`} />
            </div>
          )}
        </div>
      )}

      {pestana === 'texto' && (
        <pre className="tarjeta max-h-[560px] overflow-auto whitespace-pre-wrap p-4 text-sm text-slate-700">
          {resultado.texto_completo}
        </pre>
      )}

      {pestana === 'tiempos' && (
        <div className="tarjeta p-4">
          <table className="w-full text-sm">
            <tbody className="divide-y divide-slate-100">
              {Object.entries(resultado.tiempos_ms).map(([etapa, ms]) => (
                <tr key={etapa}>
                  <td className="py-2 capitalize text-slate-600">{etapa}</td>
                  <td className="py-2 text-right font-medium text-slate-800">{ms} ms</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {pestana === 'log' && (
        <div className="tarjeta divide-y divide-slate-100 p-4">
          {(resultado.log ?? []).map((entrada, i) => (
            <div key={i} className="flex items-center justify-between py-2 text-sm">
              <div>
                <span className="font-medium text-slate-700">{entrada.paso}</span>
                <span className="ml-2 text-slate-500">{entrada.mensaje}</span>
              </div>
              <span className="text-slate-400">{entrada.duracion_ms} ms</span>
            </div>
          ))}
          {(!resultado.log || resultado.log.length === 0) && <p className="text-sm text-slate-400">Sin registros.</p>}
        </div>
      )}
    </div>
  )
}
