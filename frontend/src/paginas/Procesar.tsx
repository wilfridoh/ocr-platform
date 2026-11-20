import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQuery } from '@tanstack/react-query'
import { api } from '@/api'
import { ErrorApi } from '@/tipos'
import CargaArchivo from '@/componentes/CargaArchivo'
import VisorPagina, { type CajaResaltada } from '@/componentes/VisorPagina'
import TablaCampos, { filasDesdeResultado } from '@/componentes/TablaCampos'
import VisorJSON from '@/componentes/VisorJSON'
import CargandoIndicador from '@/componentes/CargandoIndicador'
import MensajeError from '@/componentes/MensajeError'
import { Icono } from '@/componentes/Iconos'
import { Link } from 'react-router-dom'
import { formatearPorcentaje } from '@/utilidades/formato'

export default function Procesar() {
  const navigate = useNavigate()
  const [archivo, setArchivo] = useState<File | null>(null)
  const [plantillaId, setPlantillaId] = useState<number | ''>('')
  const [mostrarJson, setMostrarJson] = useState(false)
  const [campoResaltado, setCampoResaltado] = useState<string | null>(null)
  const [urlVistaPrevia, setUrlVistaPrevia] = useState<string | null>(null)

  const { data: plantillas } = useQuery({
    queryKey: ['plantillas', { activa: true }],
    queryFn: () => api.listarPlantillas(true),
  })

  const { data: flujos } = useQuery({ queryKey: ['flujos'], queryFn: () => api.listarFlujos(), retry: false })

  const procesar = useMutation({
    mutationFn: () => {
      if (!archivo) throw new Error('Selecciona un archivo primero')
      return api.procesarDocumento(archivo, plantillaId === '' ? null : plantillaId)
    },
  })

  const resultado = procesar.data

  const plantillaGanadora = useMemo(
    () => plantillas?.find((p) => p.id === resultado?.clasificacion.plantilla_id),
    [plantillas, resultado],
  )

  const filas = useMemo(() => {
    if (!resultado) return []
    if (plantillaGanadora) return filasDesdeResultado(plantillaGanadora.campos, resultado.campos)
    return Object.entries(resultado.campos).map(([nombre, extraido]) => ({ nombre, etiqueta: nombre, extraido }))
  }, [resultado, plantillaGanadora])

  const cajas: CajaResaltada[] = useMemo(() => {
    if (!resultado || !campoResaltado) return []
    const c = resultado.campos[campoResaltado]
    if (!c?.caja) return []
    return [{ id: campoResaltado, ...c.caja, color: '#4f46e5' }]
  }, [resultado, campoResaltado])

  const onArchivoSeleccionado = (f: File) => {
    setArchivo(f)
    procesar.reset()
    if (urlVistaPrevia) URL.revokeObjectURL(urlVistaPrevia)
    setUrlVistaPrevia(f.type.startsWith('image/') ? URL.createObjectURL(f) : null)
  }

  const esDesconocido = resultado?.clasificacion.tipo === 'desconocido'

  const crearPlantillaDesdeDocumento = () => {
    if (!resultado) return
    navigate('/plantillas/nueva', { state: { documentoId: resultado.documento_id } })
  }

  return (
    <div>
      <h2 className="mb-4 text-[22px] font-bold tracking-[-0.01em] text-ink">Procesar documento</h2>

      <div className="tarjeta p-4">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start">
          <div className="flex-1">
            <CargaArchivo onArchivoSeleccionado={onArchivoSeleccionado} archivoActual={archivo} deshabilitado={procesar.isPending} />
          </div>
          <div className="w-full shrink-0 sm:w-56">
            <label className="etiqueta-campo" htmlFor="tipo-forzado">
              Tipo
            </label>
            <select
              id="tipo-forzado"
              className="campo-entrada"
              value={plantillaId}
              onChange={(e) => setPlantillaId(e.target.value ? Number(e.target.value) : '')}
            >
              <option value="">Detectar automático</option>
              {plantillas?.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.nombre}
                </option>
              ))}
            </select>
            <button
              type="button"
              className="boton-primario mt-3 w-full"
              disabled={!archivo || procesar.isPending}
              onClick={() => procesar.mutate()}
            >
              Procesar
            </button>
          </div>
        </div>
      </div>

      {flujos && flujos.length > 0 && !resultado && (
        <div className="tarjeta mt-4">
          <div className="border-b border-line px-4 py-3 text-[13px] font-semibold">Flujos de captura</div>
          <ul className="grid gap-2 p-4 sm:grid-cols-2">
            {flujos.map((f) => (
              <li key={f.id}>
                <Link
                  to={`/procesar/${f.codigo}`}
                  className="flex items-center gap-3 rounded-lg border border-line px-3 py-2.5 hover:border-brand-line hover:bg-brand-soft"
                >
                  <span className="grid h-8 w-8 flex-none place-items-center rounded-lg bg-brand-soft text-brand">
                    <Icono nombre="flujos" />
                  </span>
                  <span className="min-w-0">
                    <span className="block truncate text-[13px] font-semibold text-ink">{f.nombre}</span>
                    <span className="block truncate text-xs text-ink-3">{f.instruccion || f.codigo}</span>
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}

      {procesar.isPending && (
        <div className="tarjeta mt-4">
          <CargandoIndicador etiqueta={`Leyendo documento... ${archivo?.name ?? ''}`} />
        </div>
      )}

      {procesar.isError && (
        <div className="mt-4">
          <MensajeError
            mensaje={procesar.error instanceof ErrorApi ? procesar.error.message : 'No se pudo procesar el documento.'}
            onReintentar={() => procesar.mutate()}
          />
        </div>
      )}

      {resultado && !procesar.isPending && (
        <div className="mt-6">
          <hr className="mb-4 border-slate-200" />
          <h3 className="mb-3 text-lg font-semibold text-slate-800">Resultado</h3>

          <div className="mb-4 flex flex-wrap items-center gap-3 text-sm">
            <span className="text-slate-500">Tipo detectado:</span>
            <span className="font-medium text-slate-800">
              {plantillaGanadora?.nombre ?? (esDesconocido ? 'Desconocido' : resultado.clasificacion.tipo)}
            </span>
            <span className="text-slate-500">Confianza</span>
            <span className="font-medium text-slate-800">{formatearPorcentaje(resultado.clasificacion.confianza)}</span>
          </div>

          {esDesconocido && (
            <div className="mb-4 rounded-md bg-amber-50 px-4 py-3 text-sm text-amber-800">
              <p className="mb-2">
                No se identificó una plantilla para este documento. Puedes crear una nueva a partir de él.
              </p>
              <button type="button" className="boton-primario" onClick={crearPlantillaDesdeDocumento}>
                Crear plantilla desde este documento
              </button>
            </div>
          )}

          <div className="grid gap-4 lg:grid-cols-2">
            <div>
              <h4 className="mb-2 text-sm font-semibold text-slate-600">Vista previa</h4>
              <VisorPagina src={urlVistaPrevia} cajas={cajas} />
            </div>
            <div>
              <h4 className="mb-2 text-sm font-semibold text-slate-600">Campos extraídos</h4>
              <TablaCampos filas={filas} campoResaltado={campoResaltado} onResaltar={setCampoResaltado} />
            </div>
          </div>

          {resultado.palabras_clave.length > 0 && (
            <div className="mt-4">
              <h4 className="mb-2 text-sm font-semibold text-slate-600">Palabras clave</h4>
              <div className="flex flex-wrap gap-2">
                {resultado.palabras_clave.map((p) => (
                  <span key={p} className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-600">
                    {p}
                  </span>
                ))}
              </div>
            </div>
          )}

          <div className="mt-5 flex flex-wrap gap-2">
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
            <button
              type="button"
              className="boton-secundario"
              onClick={() => {
                const blob = new Blob([JSON.stringify(resultado, null, 2)], { type: 'application/json' })
                const url = URL.createObjectURL(blob)
                const a = document.createElement('a')
                a.href = url
                a.download = `${resultado.documento_id}.json`
                a.click()
                URL.revokeObjectURL(url)
              }}
            >
              Descargar
            </button>
            <button type="button" className="boton-secundario" onClick={() => procesar.mutate()}>
              Reprocesar
            </button>
          </div>

          {mostrarJson && (
            <div className="mt-4">
              <VisorJSON datos={resultado} nombreArchivo={`${resultado.documento_id}.json`} />
            </div>
          )}
        </div>
      )}
    </div>
  )
}
