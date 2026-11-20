import { useEffect, useMemo, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useMutation, useQuery } from '@tanstack/react-query'
import { api } from '@/api'
import type { Campo, PalabraClave, Resultado } from '@/tipos'
import CargaArchivo from '@/componentes/CargaArchivo'
import VisorPagina from '@/componentes/VisorPagina'
import EditorPalabrasClave from '@/componentes/EditorPalabrasClave'
import EditorCampos from '@/componentes/EditorCampos'
import TablaCampos, { filasDesdeResultado } from '@/componentes/TablaCampos'
import CargandoIndicador from '@/componentes/CargandoIndicador'
import { probarEnMemoria } from '@/utilidades/probarEnMemoria'

const PASOS = ['Documento de ejemplo', 'Identificación', 'Campos'] as const

export default function NuevaPlantilla() {
  const navigate = useNavigate()
  const location = useLocation() as { state?: { documentoId?: string } }
  const documentoIdPrevio = location.state?.documentoId

  const [paso, setPaso] = useState(0)
  const [archivo, setArchivo] = useState<File | null>(null)
  const [urlVistaPrevia, setUrlVistaPrevia] = useState<string | null>(null)
  const [resultadoEjemplo, setResultadoEjemplo] = useState<Resultado | null>(null)

  const [codigo, setCodigo] = useState('')
  const [nombre, setNombre] = useState('')
  const [descripcion, setDescripcion] = useState('')
  const [umbral, setUmbral] = useState(0.6)
  const [palabrasClave, setPalabrasClave] = useState<PalabraClave[]>([])
  const [campos, setCampos] = useState<Campo[]>([])

  const resultadoPrevioQuery = useQuery({
    queryKey: ['resultado', documentoIdPrevio],
    queryFn: () => api.obtenerResultado(documentoIdPrevio!),
    enabled: Boolean(documentoIdPrevio) && !resultadoEjemplo,
  })

  useEffect(() => {
    if (resultadoPrevioQuery.data && !resultadoEjemplo) {
      setResultadoEjemplo(resultadoPrevioQuery.data)
    }
  }, [resultadoPrevioQuery.data, resultadoEjemplo])

  const procesarEjemplo = useMutation({
    mutationFn: (f: File) => api.procesarDocumento(f),
    onSuccess: (resultado) => setResultadoEjemplo(resultado),
  })

  const sugerir = useMutation({
    mutationFn: (documentoId: string) => api.sugerirPlantilla(documentoId),
    onSuccess: (sugerencia) => {
      setPalabrasClave(sugerencia.palabras_clave)
      setCampos(sugerencia.campos)
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
        palabras_clave: palabrasClave,
        campos,
      }),
    onSuccess: (plantilla) => navigate(`/plantillas/${plantilla.id}`),
  })

  const onArchivoSeleccionado = (f: File) => {
    setArchivo(f)
    if (urlVistaPrevia) URL.revokeObjectURL(urlVistaPrevia)
    setUrlVistaPrevia(f.type.startsWith('image/') ? URL.createObjectURL(f) : null)
  }

  const avanzarDesdePaso1 = async () => {
    if (!resultadoEjemplo && archivo) {
      const resultado = await procesarEjemplo.mutateAsync(archivo)
      await sugerir.mutateAsync(resultado.documento_id)
    } else if (resultadoEjemplo && palabrasClave.length === 0 && campos.length === 0) {
      await sugerir.mutateAsync(resultadoEjemplo.documento_id)
    }
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
            <div className="tarjeta p-4">
              {resultadoEjemplo ? (
                <div>
                  <p className="mb-3 text-sm text-slate-600">
                    Documento de ejemplo: <span className="font-medium">{resultadoEjemplo.archivo}</span>
                  </p>
                  <VisorPagina src={urlVistaPrevia} />
                  <details className="mt-3">
                    <summary className="cursor-pointer text-sm text-indigo-600">Ver texto OCR</summary>
                    <pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap rounded bg-slate-50 p-3 text-xs text-slate-600">
                      {resultadoEjemplo.texto_completo}
                    </pre>
                  </details>
                  <button type="button" className="boton-secundario mt-3" onClick={() => setResultadoEjemplo(null)}>
                    Elegir otro documento
                  </button>
                </div>
              ) : (
                <CargaArchivo onArchivoSeleccionado={onArchivoSeleccionado} archivoActual={archivo} />
              )}

              {(procesarEjemplo.isPending || sugerir.isPending) && (
                <CargandoIndicador etiqueta="Analizando el documento de ejemplo..." />
              )}

              <div className="mt-4 flex justify-end">
                <button
                  type="button"
                  className="boton-primario"
                  disabled={!resultadoEjemplo && !archivo}
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
