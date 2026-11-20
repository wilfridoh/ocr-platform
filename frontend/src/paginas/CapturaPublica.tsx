import { useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import { useMutation, useQuery } from '@tanstack/react-query'
import { api } from '@/api'
import { Icono } from '@/componentes/Iconos'
import { formatearValorCampo } from '@/utilidades/formato'

const IMAGENES = ['.jpg', '.jpeg', '.png', '.tif', '.tiff']

/**
 * Captura dirigida PÚBLICA (docs/07 §5.2, docs/09 §6): `/captura/:codigo`. Pensada para una persona externa que
 * llega desde un enlace, sin cuenta: no hay menú, no se piden ni se envían API keys (el cliente `solicitarPublico`
 * nunca la adjunta) y solo se muestra el resultado reducido que devuelve el servidor.
 */
export default function CapturaPublica() {
  const { codigo = '' } = useParams()
  const [archivo, setArchivo] = useState<File | null>(null)
  const [acepto, setAcepto] = useState(false) // consentimiento al aviso de privacidad (obligatorio para subir)
  const entradaArchivo = useRef<HTMLInputElement>(null)
  const entradaCamara = useRef<HTMLInputElement>(null)

  const flujoQuery = useQuery({
    queryKey: ['captura-publica', codigo],
    queryFn: () => api.obtenerFlujoPublico(codigo),
    retry: false,
  })
  const flujo = flujoQuery.data

  const subir = useMutation({
    // se envía la versión del aviso que se mostró: el servidor la registra junto con la fecha del consentimiento
    mutationFn: (f: File) => api.subirDocumentoPublico(codigo, f, flujo?.aviso_version ?? ''),
    retry: false,
  })
  const resultado = subir.data

  const elegir = (lista: FileList | null) => {
    const f = lista?.[0]
    if (!f || !acepto) return // sin consentimiento no se sube nada
    setArchivo(f)
    subir.mutate(f)
  }

  const reiniciar = () => {
    setArchivo(null)
    subir.reset()
    if (entradaArchivo.current) entradaArchivo.current.value = ''
    if (entradaCamara.current) entradaCamara.current.value = ''
  }

  const fondo = { background: 'linear-gradient(180deg,#EEF0FF 0%,#F5F6FA 60%)' }

  if (flujoQuery.isLoading) {
    return (
      <main className="grid min-h-screen place-items-center" style={fondo}>
        <p className="flex items-center gap-3 text-sm text-ink-3" role="status">
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-line border-t-brand" aria-hidden /> Cargando…
        </p>
      </main>
    )
  }

  if (flujoQuery.isError || !flujo) {
    return (
      <main className="min-h-screen px-4 py-[8vh]" style={fondo}>
        <div className="mx-auto w-full max-w-[460px] rounded-2xl border border-line bg-surface p-[30px] text-center shadow-card">
          <div className="mx-auto mb-4 grid h-16 w-16 place-items-center rounded-[18px] bg-warn-soft text-warn">
            <Icono nombre="alerta" tamano={30} />
          </div>
          <h1 className="mb-1.5 text-lg font-semibold text-ink">No podemos abrir este enlace</h1>
          <p className="text-ink-3" role="alert">
            {(flujoQuery.error as Error | null)?.message ?? 'Este punto de captura no está disponible.'}
          </p>
          <button type="button" className="boton-secundario mt-5" onClick={() => flujoQuery.refetch()}>
            Reintentar
          </button>
        </div>
      </main>
    )
  }

  const extensiones = flujo.acepta_pdf ? [...IMAGENES, '.pdf'] : IMAGENES
  const formatos = flujo.acepta_pdf ? 'JPG, PNG, TIFF o PDF' : 'JPG, PNG o TIFF'
  const procesando = subir.isPending
  const noCoincide = resultado?.estado === 'NO_COINCIDE'
  const campos = resultado ? Object.entries(resultado.campos) : []

  return (
    <main className="min-h-screen px-4 py-[6vh]" style={fondo}>
      <div className="mx-auto w-full max-w-[460px] rounded-2xl border border-line bg-surface p-[30px] shadow-card">
        <div className="text-center">
          <div className="mx-auto mb-4 grid h-16 w-16 place-items-center rounded-[18px] bg-brand-soft text-brand">
            <Icono nombre="archivo" tamano={30} />
          </div>
          <h1 className="mb-1.5 text-lg font-semibold text-ink">{flujo.instruccion || flujo.nombre}</h1>
          <p className="text-ink-3">Formatos aceptados: {formatos}.</p>
        </div>

        {!resultado && !procesando && (
          <section className="mt-6 rounded-card border border-brand-line bg-brand-soft px-4 py-3" aria-labelledby="aviso-titulo">
            <h2 id="aviso-titulo" className="mb-1 text-[13px] font-semibold text-ink">
              Antes de subir tu documento
            </h2>
            <p id="aviso-texto" className="text-[13px] leading-relaxed text-ink-2">
              Este documento se procesa para leer sus datos automáticamente. Se usa solo para esta prueba y{' '}
              {flujo.retencion_dias > 0 ? (
                <>
                  se elimina pasados <b>{flujo.retencion_dias} {flujo.retencion_dias === 1 ? 'día' : 'días'}</b>
                </>
              ) : (
                <>se conserva hasta que el administrador lo elimine</>
              )}
              . No se comparte con terceros.
            </p>
            <label className="mt-2.5 flex cursor-pointer items-start gap-2.5 text-[13px] font-medium text-ink">
              <input
                type="checkbox"
                className="mt-0.5 h-4 w-4 flex-none accent-[#4338CA]"
                checked={acepto}
                onChange={(e) => setAcepto(e.target.checked)}
                aria-describedby="aviso-texto"
              />
              <span>Entiendo y autorizo el uso de mi documento para esta prueba.</span>
            </label>
          </section>
        )}

        {!resultado && !procesando && (
          <div className="mt-4 flex flex-col gap-3">
            {!acepto && (
              <p id="aviso-ayuda" className="text-center text-xs text-ink-3">
                Marca la casilla para poder subir tu documento.
              </p>
            )}
            {flujo.acepta_camara && (
              <button type="button" className="boton-primario w-full" disabled={!acepto} aria-describedby={acepto ? undefined : 'aviso-ayuda'} onClick={() => entradaCamara.current?.click()}>
                <Icono nombre="camara" /> Usar cámara
              </button>
            )}
            <button
              type="button"
              className={`${flujo.acepta_camara ? 'boton-secundario' : 'boton-primario'} w-full`}
              disabled={!acepto}
              aria-describedby={acepto ? undefined : 'aviso-ayuda'}
              onClick={() => entradaArchivo.current?.click()}
            >
              <Icono nombre="archivo" /> Elegir archivo
            </button>
          </div>
        )}
        <input ref={entradaArchivo} type="file" className="hidden" accept={extensiones.join(',')} onChange={(e) => elegir(e.target.files)} aria-label="Elegir archivo" />
        <input ref={entradaCamara} type="file" className="hidden" accept="image/*" capture="environment" onChange={(e) => elegir(e.target.files)} aria-label="Tomar foto con la cámara" />

        {procesando && (
          <p className="mt-6 flex items-center justify-center gap-3 text-sm text-ink-3" role="status">
            <span className="h-4 w-4 animate-spin rounded-full border-2 border-line border-t-brand" aria-hidden />
            Leyendo tu documento…
          </p>
        )}

        {subir.isError && (
          <div className="mt-6" role="alert">
            <div className="rounded-card border border-[#FCA5A5] bg-err-soft px-4 py-3 text-err">
              <p className="font-semibold">No pudimos procesar el archivo</p>
              <p className="mt-1 text-[13px]">{(subir.error as Error).message}</p>
            </div>
            <div className="mt-4 flex justify-center gap-2">
              <button type="button" className="boton-primario" onClick={reiniciar}>
                Probar con otro archivo
              </button>
              {archivo && (
                <button type="button" className="boton-secundario" onClick={() => subir.mutate(archivo)}>
                  Reintentar
                </button>
              )}
            </div>
          </div>
        )}

        {resultado && noCoincide && (
          <div className="mt-6" role="alert">
            <div className="rounded-card border border-[#FCD34D] bg-warn-soft px-4 py-3 text-warn">
              <p className="font-semibold">Este documento no es el que se esperaba</p>
              <p className="mt-1 text-[13px]">Revisa que sea el documento correcto y que se vea completo y nítido.</p>
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
            <div className="mb-3 flex items-center gap-2 text-[13px] font-semibold text-ok">
              <Icono nombre="check" tamano={16} /> Recibimos tu documento
            </div>
            {campos.length > 0 && (
              <>
                <p className="mb-2 text-[13px] text-ink-3">Esto es lo que leímos. Revisa que sea correcto.</p>
                <dl className="divide-y divide-line-2 rounded-card border border-line">
                  {campos.map(([nombre, c]) => {
                    const dudoso = c.valor === null || c.valor === '' || c.confianza < 0.7
                    return (
                      <div key={nombre} className="flex items-start justify-between gap-3 px-3 py-2.5">
                        <dt className="text-[13px] text-ink-3">{c.etiqueta ?? nombre.replace(/_/g, ' ')}</dt>
                        <dd className="text-right text-[13px] font-semibold text-ink">
                          {c.valor === null || c.valor === '' ? <span className="font-normal text-ink-3">No se pudo leer</span> : formatearValorCampo(c.valor)}
                          {dudoso && <span className="chip chip-warn ml-2">Revísalo</span>}
                        </dd>
                      </div>
                    )
                  })}
                </dl>
              </>
            )}
            {resultado.advertencias.length > 0 && (
              <ul className="mt-3 space-y-1 text-[13px]">
                {resultado.advertencias.map((a, i) => (
                  <li key={i} className="rounded-lg bg-warn-soft px-3 py-2 text-warn">
                    {a.mensaje}
                  </li>
                ))}
              </ul>
            )}
            <div className="mt-5 flex justify-center">
              <button type="button" className="boton-secundario" onClick={reiniciar}>
                Subir otro documento
              </button>
            </div>
          </div>
        )}
      </div>
    </main>
  )
}
