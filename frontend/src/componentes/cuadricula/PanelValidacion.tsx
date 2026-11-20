import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/api'
import type { Campo, Coincidencia, DisenoPlantilla, Documento, EstadoZona } from '@/tipos'
import { ErrorApi } from '@/tipos'
import MensajeError from '@/componentes/MensajeError'
import { rangoCeldas, type Densidad } from '@/utilidades/cuadricula'

interface Props {
  plantillaId: number
  /** Campos y diseño tal como están en el editor (aunque no se hayan guardado) */
  campos: Campo[]
  diseno: DisenoPlantilla
  documentos: Documento[]
  documentoInicial: string
  densidad: Densidad
}

const COLOR: Record<EstadoZona, string> = { coincide: '#15803d', parcial: '#b45309', no_coincide: '#b91c1c' }
const ICONO: Record<EstadoZona, string> = { coincide: '✓', parcial: '≈', no_coincide: '✕' }
const TEXTO: Record<EstadoZona, string> = { coincide: 'Coincide', parcial: 'Coincidencia parcial', no_coincide: 'No coincide' }

/** Espera `ms` sin cambios antes de devolver el valor (para no llamar al servidor en cada clic). */
function useRetardado<T>(valor: T, ms: number): T {
  const [v, setV] = useState(valor)
  useEffect(() => {
    const t = setTimeout(() => setV(valor), ms)
    return () => clearTimeout(t)
  }, [valor, ms])
  return v
}

/**
 * Pestaña «Validar un documento» (docs/12 §2 y docs/13 §3): coincidencia de DISEÑO de un documento ya procesado con
 * la plantilla, usando las zonas del editor aunque no estén guardadas (POST /plantillas/{id}/probar no guarda nada).
 */
export default function PanelValidacion({ plantillaId, campos, diseno, documentos, documentoInicial, densidad }: Props) {
  const [documentoId, setDocumentoId] = useState(documentoInicial)
  const [soloDiferencias, setSoloDiferencias] = useState(false)
  const [resaltada, setResaltada] = useState<number | null>(null)
  useEffect(() => {
    if (!documentoId && documentoInicial) setDocumentoId(documentoInicial)
  }, [documentoInicial, documentoId])

  const cambios = useRetardado(useMemo(() => JSON.stringify({ campos, diseno }), [campos, diseno]), 500)
  const probarQuery = useQuery({
    queryKey: ['probar', plantillaId, documentoId, cambios],
    queryFn: () => api.probarPlantilla(plantillaId, documentoId, JSON.parse(cambios)),
    enabled: !!documentoId,
    placeholderData: (anterior) => anterior,
  })
  const imagenQuery = useQuery({
    queryKey: ['enderezada', documentoId, diseno.relacion ?? null],
    queryFn: () => api.obtenerImagenEnderezada(documentoId, 1, { relacion: diseno.relacion }),
    enabled: !!documentoId,
  })
  const [url, setUrl] = useState<string | null>(null)
  useEffect(() => {
    if (!imagenQuery.data?.blob) return setUrl(null)
    const u = URL.createObjectURL(imagenQuery.data.blob)
    setUrl(u)
    return () => URL.revokeObjectURL(u)
  }, [imagenQuery.data])

  const resultado = probarQuery.data
  const c: Coincidencia | null | undefined = resultado?.coincidencia
  const zonas = c?.zonas ?? []
  const filas = zonas.map((z, i) => ({ z, i })).filter(({ z }) => !soloDiferencias || z.estado !== 'coincide')
  const nombreCampo = (n: string | null) => (n ? campos.find((x) => x.nombre === n)?.etiqueta ?? n : 'Elemento fijo')
  const celdasPorDesplazamiento =
    c?.desplazamiento_medio != null ? c.desplazamiento_medio / ((1 / densidad.columnas + 1 / densidad.filas) / 2) : null

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-end gap-3">
        <div className="min-w-[260px] flex-1">
          <label className="etiqueta-campo">Documento a validar</label>
          <select className="campo-entrada" value={documentoId} onChange={(e) => setDocumentoId(e.target.value)}>
            <option value="">— Elige un documento ya procesado —</option>
            {documentoId && !documentos.some((d) => d.id === documentoId) && <option value={documentoId}>{documentoId}</option>}
            {documentos.map((d) => (
              <option key={d.id} value={d.id}>
                {d.archivo} · {d.id.slice(0, 8)}
              </option>
            ))}
          </select>
        </div>
        <p className="max-w-sm text-xs text-slate-500">
          Usa las zonas tal como están en el editor, aunque no estén guardadas. No guarda nada. Mide la coincidencia de
          <b> diseño</b> con la plantilla, no la autenticidad del documento.
        </p>
      </div>

      {!documentoId ? (
        <div className="tarjeta p-6 text-center text-sm text-slate-500">Elige un documento para validarlo con esta plantilla.</div>
      ) : probarQuery.isError ? (
        <MensajeError
          mensaje={(probarQuery.error as Error).message}
          onReintentar={() => probarQuery.refetch()}
        />
      ) : !resultado ? (
        <div className="tarjeta flex h-48 animate-pulse items-center justify-center text-sm text-slate-400">Calculando…</div>
      ) : !c ? (
        <div className="tarjeta p-6 text-center text-sm text-slate-600">
          Aún no hay cuadrícula: marca al menos una <b>etiqueta fija</b> en «Mapear» para poder validar el diseño.
        </div>
      ) : (
        <div className="grid gap-4 lg:grid-cols-[1fr_320px]">
          <div className="space-y-3">
            {/* documento con las zonas coloreadas por estado */}
            <div className="tarjeta relative overflow-hidden bg-slate-100">
              {url ? <img src={url} alt="Documento a validar" className="block w-full" /> : <div className="h-64" />}
              {zonas.map((z, i) => (
                <div
                  key={i}
                  className="pointer-events-none absolute rounded-sm border-2"
                  style={{
                    left: `${z.x * 100}%`,
                    top: `${z.y * 100}%`,
                    width: `${z.ancho * 100}%`,
                    height: `${z.alto * 100}%`,
                    borderColor: COLOR[z.estado],
                    borderStyle: z.tipo === 'etiqueta' ? 'dashed' : 'solid',
                    background: `${COLOR[z.estado]}${resaltada === i ? '44' : '1a'}`,
                    opacity: resaltada !== null && resaltada !== i ? 0.35 : 1,
                  }}
                >
                  <span className="absolute -top-[16px] left-0 rounded px-1 text-[10px] font-bold text-white" style={{ background: COLOR[z.estado] }}>
                    {ICONO[z.estado]}
                  </span>
                </div>
              ))}
              {probarQuery.isFetching && (
                <span className="absolute right-2 top-2 rounded bg-white/90 px-2 py-0.5 text-xs text-slate-500">Calculando…</span>
              )}
            </div>

            {/* detalle por zona */}
            <div className="tarjeta overflow-x-auto">
              <div className="flex items-center justify-between px-3 py-2">
                <h3 className="text-sm font-semibold text-slate-700">Detalle por zona</h3>
                <label className="flex items-center gap-2 text-xs text-slate-600">
                  <input type="checkbox" checked={soloDiferencias} onChange={(e) => setSoloDiferencias(e.target.checked)} />
                  Solo diferencias
                </label>
              </div>
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 text-slate-500">
                  <tr>
                    <th className="px-3 py-1.5">Zona</th>
                    <th className="px-3 py-1.5">Celdas</th>
                    <th className="px-3 py-1.5">Esperado</th>
                    <th className="px-3 py-1.5">Leído</th>
                    <th className="px-3 py-1.5">Estado</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {filas.map(({ z, i }) => {
                    const valor = z.tipo === 'valor' && z.campo ? resultado.campos[z.campo]?.valor : undefined
                    return (
                      <tr key={i} onMouseEnter={() => setResaltada(i)} onMouseLeave={() => setResaltada(null)} className={resaltada === i ? 'bg-slate-50' : ''}>
                        <td className="px-3 py-1.5 text-slate-700">
                          {nombreCampo(z.campo)} <span className="text-slate-400">· {z.tipo === 'valor' ? 'valor' : 'etiqueta'}</span>
                        </td>
                        <td className="px-3 py-1.5 font-mono text-slate-500">{rangoCeldas(z, densidad)}</td>
                        <td className="px-3 py-1.5 text-slate-600">{z.esperado ?? '—'}</td>
                        <td className="px-3 py-1.5 text-slate-600">
                          {z.tipo === 'etiqueta'
                            ? z.leido ?? <i className="text-slate-400">no aparece</i>
                            : valor != null && valor !== ''
                              ? String(valor)
                              : <i className="text-slate-400">sin valor</i>}
                          {z.similitud != null && z.tipo === 'etiqueta' && z.similitud < 1 && z.leido && (
                            <span className="ml-1 text-slate-400">({Math.round(z.similitud * 100)} %)</span>
                          )}
                        </td>
                        <td className="px-3 py-1.5 font-medium" style={{ color: COLOR[z.estado] }}>
                          {ICONO[z.estado]} {TEXTO[z.estado]}
                        </td>
                      </tr>
                    )
                  })}
                  {!filas.length && (
                    <tr>
                      <td colSpan={5} className="px-3 py-4 text-center text-slate-400">
                        {soloDiferencias ? 'Sin diferencias.' : 'Sin zonas.'}
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* puntaje y desglose */}
          <div className="space-y-3">
            <div className="tarjeta flex flex-col items-center gap-2 p-4 text-center">
              {c.verificable && c.puntaje != null && c.veredicto ? (
                <>
                  <Anillo valor={c.puntaje} color={COLOR[c.veredicto]} />
                  <b style={{ color: COLOR[c.veredicto] }}>{TEXTO[c.veredicto]}</b>
                  <span className="text-xs text-slate-500">Umbral de la plantilla: {Math.round(c.umbral * 100)} %</span>
                </>
              ) : (
                <>
                  <span className="flex h-16 w-16 items-center justify-center rounded-full bg-slate-100 text-2xl text-slate-400">?</span>
                  <b className="text-slate-700">No verificable</b>
                  <span className="text-xs text-slate-500">
                    {!c.recorte_confiable
                      ? 'No se detectó el documento con fiabilidad: ajusta las esquinas en «Mapear».'
                      : c.etiquetas_total === 0
                        ? 'Marca al menos una etiqueta fija para poder validar el diseño.'
                        : 'Menos de la mitad de las etiquetas fijas se pudo leer: imagen borrosa o de otro tipo.'}
                  </span>
                </>
              )}
            </div>
            <dl className="tarjeta divide-y divide-slate-100 text-sm">
              <Dato titulo="Etiquetas fijas en su sitio" valor={`${c.etiquetas_ok} de ${c.etiquetas_total}`} />
              <Dato
                titulo="Desplazamiento medio"
                valor={celdasPorDesplazamiento == null ? '—' : `${celdasPorDesplazamiento.toFixed(1)} celdas`}
              />
              <Dato titulo="Valores legibles" valor={`${c.valores_legibles} de ${c.valores_total}`} />
              <Dato titulo="Recorte" valor={c.recorte_confiable ? `fiable (${c.recorte_origen})` : 'no fiable'} />
              {c.orientacion ? <Dato titulo="Orientación corregida" valor={`${c.orientacion}°`} /> : null}
            </dl>
            {c.sugerencia && (
              <div className="rounded-md border border-sky-200 bg-sky-50 px-3 py-2 text-sm text-sky-900">
                ¿Otro tipo de documento? Coincide un {Math.round(c.sugerencia.puntaje * 100)} % con la plantilla{' '}
                <Link className="font-medium underline" to={`/plantillas/${c.sugerencia.plantilla_id}`}>
                  {c.sugerencia.codigo}
                </Link>
                .
              </div>
            )}
          </div>
        </div>
      )}
      {probarQuery.error instanceof ErrorApi && probarQuery.error.status === 400 && (
        <p className="text-xs text-slate-500">Ese documento todavía no tiene un resultado de OCR: procésalo primero.</p>
      )}
    </div>
  )
}

function Dato({ titulo, valor }: { titulo: string; valor: string }) {
  return (
    <div className="flex items-center justify-between px-3 py-2">
      <dt className="text-slate-500">{titulo}</dt>
      <dd className="font-medium text-slate-800">{valor}</dd>
    </div>
  )
}

function Anillo({ valor, color }: { valor: number; color: string }) {
  const r = 34
  const circ = 2 * Math.PI * r
  return (
    <svg width="96" height="96" viewBox="0 0 96 96" role="img" aria-label={`Puntaje de coincidencia ${Math.round(valor * 100)} %`}>
      <circle cx="48" cy="48" r={r} fill="none" stroke="#e2e8f0" strokeWidth="9" />
      <circle
        cx="48"
        cy="48"
        r={r}
        fill="none"
        stroke={color}
        strokeWidth="9"
        strokeLinecap="round"
        strokeDasharray={`${circ * Math.max(0, Math.min(1, valor))} ${circ}`}
        transform="rotate(-90 48 48)"
      />
      <text x="48" y="54" textAnchor="middle" fontSize="20" fontWeight="700" fill="#0f172a">
        {Math.round(valor * 100)} %
      </text>
    </svg>
  )
}
