import { useMemo, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useMutation, useQuery } from '@tanstack/react-query'
import { api } from '@/api'
import { ErrorApi } from '@/tipos'
import CargandoIndicador from '@/componentes/CargandoIndicador'
import MensajeError from '@/componentes/MensajeError'
import TablaCampos, { filasDesdeResultado } from '@/componentes/TablaCampos'
import { Icono } from '@/componentes/Iconos'
import { formatearPorcentaje } from '@/utilidades/formato'

const IMAGENES = ['.jpg', '.jpeg', '.png', '.tif', '.tiff']

/**
 * Captura dirigida (docs/07 §6.1): `/procesar/:codigo`. La persona ve solo la instrucción del flujo, sin selector de
 * tipo ni plantillas. Requiere una API key (acceso interno); el acceso sin clave es una fase aparte.
 */
export default function ProcesarConFlujo() {
  const { codigo = '' } = useParams()
  const [archivo, setArchivo] = useState<File | null>(null)
  const entradaArchivo = useRef<HTMLInputElement>(null)
  const entradaCamara = useRef<HTMLInputElement>(null)

  const flujoQuery = useQuery({ queryKey: ['flujo', codigo], queryFn: () => api.obtenerFlujo(codigo), retry: false })
  const flujo = flujoQuery.data

  const procesar = useMutation({ mutationFn: (f: File) => api.procesarConFlujo(codigo, f) })
  const resultado = procesar.data

  const plantillaId = resultado?.clasificacion.plantilla_id ?? null
  const plantillaQuery = useQuery({
    queryKey: ['plantilla', plantillaId],
    queryFn: () => api.obtenerPlantilla(plantillaId!),
    enabled: plantillaId !== null && resultado?.estado === 'COMPLETADO',
  })

  const filas = useMemo(() => {
    if (!resultado) return []
    if (plantillaQuery.data) return filasDesdeResultado(plantillaQuery.data.campos, resultado.campos)
    return Object.entries(resultado.campos).map(([nombre, extraido]) => ({ nombre, etiqueta: nombre.replace(/_/g, ' '), extraido }))
  }, [resultado, plantillaQuery.data])

  const elegir = (lista: FileList | null) => {
    const f = lista?.[0]
    if (!f) return
    setArchivo(f)
    procesar.mutate(f)
  }

  const reiniciar = () => {
    setArchivo(null)
    procesar.reset()
    if (entradaArchivo.current) entradaArchivo.current.value = ''
    if (entradaCamara.current) entradaCamara.current.value = ''
  }

  if (flujoQuery.isLoading) return <CargandoIndicador etiqueta="Cargando..." />
  if (flujoQuery.isError || !flujo) {
    return (
      <div className="mx-auto max-w-[560px]">
        <MensajeError mensaje={flujoQuery.error instanceof ErrorApi && flujoQuery.error.status === 404 ? 'Este punto de captura no existe o no está disponible.' : (flujoQuery.error as Error)?.message ?? 'No se pudo cargar el flujo.'} onReintentar={() => flujoQuery.refetch()} />
      </div>
    )
  }

  const extensiones = flujo.acepta_pdf ? [...IMAGENES, '.pdf'] : IMAGENES
  const formatos = flujo.acepta_pdf ? 'JPG, PNG, TIFF o PDF' : 'JPG, PNG o TIFF'
  const procesando = procesar.isPending
  const noCoincide = resultado?.estado === 'NO_COINCIDE'

  return (
    <div className="mx-auto max-w-[560px]">
      <div className="tarjeta p-[30px]">
        <div className="text-center">
          <div className="mx-auto mb-4 grid h-16 w-16 place-items-center rounded-[18px] bg-brand-soft text-brand">
            <Icono nombre="archivo" tamano={30} />
          </div>
          <h2 className="mb-1.5 text-lg font-semibold text-ink">{flujo.instruccion || flujo.nombre}</h2>
          <p className="text-ink-3">Formatos aceptados: {formatos}. Máximo 20 MB.</p>
        </div>

        {!resultado && (
          <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:justify-center">
            {flujo.acepta_camara && (
              <button type="button" className="boton-primario" disabled={procesando} onClick={() => entradaCamara.current?.click()}>
                <Icono nombre="camara" /> Usar cámara
              </button>
            )}
            <button
              type="button"
              className={flujo.acepta_camara ? 'boton-secundario' : 'boton-primario'}
              disabled={procesando}
              onClick={() => entradaArchivo.current?.click()}
            >
              <Icono nombre="archivo" /> Elegir archivo
            </button>
          </div>
        )}
        <input ref={entradaArchivo} type="file" className="hidden" accept={extensiones.join(',')} onChange={(e) => elegir(e.target.files)} aria-label="Elegir archivo" />
        <input ref={entradaCamara} type="file" className="hidden" accept="image/*" capture="environment" onChange={(e) => elegir(e.target.files)} aria-label="Tomar foto con la cámara" />

        {procesando && (
          <div className="mt-6">
            <CargandoIndicador etiqueta={`Leyendo ${archivo?.name ?? 'el documento'}...`} />
          </div>
        )}

        {procesar.isError && (
          <div className="mt-5">
            <MensajeError mensaje={(procesar.error as Error).message} onReintentar={archivo ? () => procesar.mutate(archivo) : undefined} />
          </div>
        )}

        {resultado && noCoincide && (
          <div className="mt-6" role="alert">
            <div className="rounded-card border border-[#FCD34D] bg-warn-soft px-4 py-3 text-warn">
              <p className="font-semibold">Este documento no es el que se esperaba</p>
              <p className="mt-1 text-[13px]">{flujo.instruccion || 'Revisa que sea el documento correcto y que se vea completo y nítido.'}</p>
            </div>
            <div className="mt-4 flex justify-center">
              <button type="button" className="boton-primario" onClick={reiniciar}>
                Subir otro documento
              </button>
            </div>
          </div>
        )}

        {resultado && !noCoincide && (
          <div className="mt-6">
            <div className="mb-3 flex items-center justify-between gap-3">
              <h3 className="text-[13px] font-semibold text-ink">Datos leídos</h3>
              <span className="chip chip-ok">
                <Icono nombre="check" tamano={12} /> Confianza {formatearPorcentaje(resultado.confianza_global)}
              </span>
            </div>
            {plantillaQuery.isLoading ? <CargandoIndicador /> : <TablaCampos filas={filas} />}
            {resultado.advertencias.length > 0 && (
              <ul className="mt-3 space-y-1 text-[13px]">
                {resultado.advertencias.map((a, i) => (
                  <li key={i} className="rounded-lg bg-warn-soft px-3 py-2 text-warn">
                    {a.mensaje}
                  </li>
                ))}
              </ul>
            )}
            <div className="mt-5 flex items-center justify-between gap-3">
              <Link to={`/documentos/${resultado.documento_id}`} className="text-[13px] text-brand hover:underline">
                Ver el detalle del documento
              </Link>
              <button type="button" className="boton-secundario" onClick={reiniciar}>
                Subir otro documento
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
