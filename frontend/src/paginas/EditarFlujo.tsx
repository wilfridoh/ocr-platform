import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/api'
import type { FlujoCapturaEntrada } from '@/tipos'
import CargandoIndicador from '@/componentes/CargandoIndicador'
import MensajeError from '@/componentes/MensajeError'
import SinPermiso from '@/componentes/SinPermiso'
import Interruptor from '@/componentes/Interruptor'
import { rolMayor } from '@/utilidades/roles'
import { useYo } from '@/utilidades/useYo'

const CODIGO_VALIDO = /^[a-z0-9_]+$/

/** Alta (`/flujos-captura/nuevo`) y edición (`/flujos-captura/:id`) de un flujo de captura. */
export default function EditarFlujo() {
  const { id } = useParams()
  const esNuevo = id === undefined
  const flujoId = Number(id)
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { yo, rol, cargando: cargandoRol, puede } = useYo()
  const [urlCopiada, setUrlCopiada] = useState(false)

  const flujosQuery = useQuery({ queryKey: ['flujos', 'todos'], queryFn: () => api.listarFlujos(true), enabled: !esNuevo && puede('Editor') })
  const plantillasQuery = useQuery({ queryKey: ['plantillas'], queryFn: () => api.listarPlantillas(), enabled: puede('Editor') })
  const flujo = esNuevo ? undefined : flujosQuery.data?.find((f) => f.id === flujoId)

  const [codigo, setCodigo] = useState('')
  const [nombre, setNombre] = useState('')
  const [instruccion, setInstruccion] = useState('')
  const [aceptaCamara, setAceptaCamara] = useState(true)
  const [aceptaPdf, setAceptaPdf] = useState(true)
  const [activo, setActivo] = useState(true)
  const [plantillaIds, setPlantillaIds] = useState<number[]>([])
  const [cargado, setCargado] = useState(esNuevo)
  const [intentoGuardar, setIntentoGuardar] = useState(false)

  useEffect(() => {
    if (flujo && !cargado) {
      setCodigo(flujo.codigo)
      setNombre(flujo.nombre)
      setInstruccion(flujo.instruccion ?? '')
      setAceptaCamara(flujo.acepta_camara)
      setAceptaPdf(flujo.acepta_pdf)
      setActivo(flujo.activo)
      setPlantillaIds(flujo.plantillas.map((p) => p.id))
      setCargado(true)
    }
  }, [flujo, cargado])

  const guardar = useMutation({
    mutationFn: (entrada: FlujoCapturaEntrada) => (esNuevo ? api.crearFlujo(entrada) : api.actualizarFlujo(flujoId, entrada)),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['flujos'] })
      navigate('/flujos-captura')
    },
  })

  const accesoPublico = useMutation({
    mutationFn: (acceso: boolean) => api.fijarAccesoPublicoFlujo(flujoId, acceso),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['flujos'] }),
  })

  if (cargandoRol) return <CargandoIndicador />
  if (!puede('Editor')) return <SinPermiso requiere="Editor" rolActual={rol} />
  if (!esNuevo && flujosQuery.isLoading) return <CargandoIndicador etiqueta="Cargando flujo..." />
  if (!esNuevo && flujosQuery.data && !flujo) return <MensajeError mensaje="No se encontró el flujo de captura." />
  if (flujo && !puede(rolMayor('Editor', flujo.rol_minimo_edicion))) {
    return <SinPermiso requiere={flujo.rol_minimo_edicion} rolActual={rol} detalle={`Este flujo solo lo puede editar el rol ${flujo.rol_minimo_edicion} o superior.`} />
  }

  const errorCodigo = !codigo.trim()
    ? 'El código es obligatorio'
    : !CODIGO_VALIDO.test(codigo)
      ? 'Usa solo minúsculas, números y guion bajo (p. ej. alta_cliente_cedula)'
      : null
  const errorNombre = nombre.trim() ? null : 'El nombre es obligatorio'
  const errorPlantillas = plantillaIds.length === 0 ? 'Elige al menos una plantilla permitida' : null
  const hayErrores = Boolean(errorCodigo || errorNombre || errorPlantillas)

  const alternar = (pid: number) =>
    setPlantillaIds((ids) => (ids.includes(pid) ? ids.filter((x) => x !== pid) : [...ids, pid]))

  const enviar = (e: React.FormEvent) => {
    e.preventDefault()
    setIntentoGuardar(true)
    if (hayErrores) return
    guardar.mutate({
      codigo: codigo.trim(),
      nombre: nombre.trim(),
      instruccion: instruccion.trim() || null,
      acepta_camara: aceptaCamara,
      acepta_pdf: aceptaPdf,
      activo,
      plantilla_ids: plantillaIds,
    })
  }

  const mostrarError = (e: string | null) => intentoGuardar && e && <p className="mt-1 text-xs text-err">{e}</p>

  return (
    <form onSubmit={enviar} noValidate>
      <div className="mb-4">
        <Link to="/flujos-captura" className="text-sm text-brand hover:underline">
          ← Volver a flujos de captura
        </Link>
        <h2 className="mt-1 text-[22px] font-bold tracking-[-0.01em] text-ink">{esNuevo ? 'Nuevo flujo de captura' : `Editar flujo: ${flujo?.nombre ?? ''}`}</h2>
      </div>

      {guardar.isError && (
        <div className="mb-4">
          <MensajeError mensaje={(guardar.error as Error).message} />
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-[1fr_340px]">
        <div className="space-y-4">
          <div className="tarjeta">
            <div className="border-b border-line px-4 py-3 text-[13px] font-semibold">Datos del flujo</div>
            <div className="space-y-4 p-4">
              <div className="grid gap-3 sm:grid-cols-2">
                <div>
                  <label className="etiqueta-campo" htmlFor="flujo-nombre">
                    Nombre
                  </label>
                  <input id="flujo-nombre" className="campo-entrada" value={nombre} onChange={(e) => setNombre(e.target.value)} placeholder="Alta de cliente — cédula" />
                  {mostrarError(errorNombre)}
                </div>
                <div>
                  <label className="etiqueta-campo" htmlFor="flujo-codigo">
                    Código
                  </label>
                  <input
                    id="flujo-codigo"
                    className="campo-entrada font-mono text-[12.5px]"
                    value={codigo}
                    onChange={(e) => setCodigo(e.target.value)}
                    placeholder="alta_cliente_cedula"
                    autoComplete="off"
                  />
                  <p className="mt-1 text-xs text-ink-3">Enlace interno (con clave): /procesar/{codigo || 'codigo'}</p>
                  {mostrarError(errorCodigo)}
                </div>
              </div>
              <div>
                <label className="etiqueta-campo" htmlFor="flujo-instruccion">
                  Instrucción para quien sube el documento
                </label>
                <textarea
                  id="flujo-instruccion"
                  className="campo-entrada"
                  rows={2}
                  maxLength={500}
                  value={instruccion}
                  onChange={(e) => setInstruccion(e.target.value)}
                  placeholder="Sube o escanea tu cédula de identidad"
                />
                <p className="mt-1 text-xs text-ink-3">Es lo primero que ve la persona; no necesita saber qué es una plantilla.</p>
              </div>
            </div>
          </div>

          <div className="tarjeta">
            <div className="border-b border-line px-4 py-3 text-[13px] font-semibold">Plantillas permitidas</div>
            <div className="p-4">
              <p className="mb-3 text-xs text-ink-3">
                El sistema solo reconocerá estos tipos de documento en este flujo. Si el archivo no coincide con ninguno, queda como «No coincide».
              </p>
              {plantillasQuery.isLoading && <CargandoIndicador etiqueta="Cargando plantillas..." />}
              {plantillasQuery.isError && <MensajeError mensaje={(plantillasQuery.error as Error).message} />}
              <ul className="space-y-1.5">
                {plantillasQuery.data?.map((p) => (
                  <li key={p.id}>
                    <label className="flex cursor-pointer items-center gap-3 rounded-lg border border-line px-3 py-2 hover:bg-line-2">
                      <input
                        type="checkbox"
                        className="h-4 w-4 accent-[#4338CA]"
                        checked={plantillaIds.includes(p.id)}
                        onChange={() => alternar(p.id)}
                      />
                      <span className="flex-1">
                        <span className="block text-[13px] font-semibold text-ink">{p.nombre}</span>
                        <span className="font-mono text-[12px] text-ink-3">{p.codigo}</span>
                      </span>
                      {!p.activa && <span className="chip chip-warn">Inactiva</span>}
                    </label>
                  </li>
                ))}
              </ul>
              {mostrarError(errorPlantillas)}
            </div>
          </div>
        </div>

        <div className="space-y-4">
          <div className="tarjeta">
            <div className="border-b border-line px-4 py-3 text-[13px] font-semibold">Qué acepta</div>
            <div className="space-y-3 p-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="text-[13px] font-semibold text-ink">Foto desde la cámara</div>
                  <div className="text-xs text-ink-3">Muestra el botón «Usar cámara» en móviles.</div>
                </div>
                <Interruptor activo={aceptaCamara} onCambio={setAceptaCamara} etiqueta="Aceptar foto desde la cámara" />
              </div>
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="text-[13px] font-semibold text-ink">Archivos PDF</div>
                  <div className="text-xs text-ink-3">Si se apaga, solo imágenes (JPG, PNG, TIFF).</div>
                </div>
                <Interruptor activo={aceptaPdf} onCambio={setAceptaPdf} etiqueta="Aceptar archivos PDF" />
              </div>
              <div className="flex items-center justify-between gap-3 border-t border-line-2 pt-3">
                <div>
                  <div className="text-[13px] font-semibold text-ink">Flujo activo</div>
                  <div className="text-xs text-ink-3">Un flujo inactivo no se puede usar.</div>
                </div>
                <Interruptor activo={activo} onCambio={setActivo} etiqueta="Flujo activo" />
              </div>
            </div>
          </div>

          {!esNuevo && flujo && puede('Administrador') && yo?.publico_habilitado && (
            <div className="tarjeta">
              <div className="border-b border-line px-4 py-3 text-[13px] font-semibold">Acceso público</div>
              <div className="space-y-3 p-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="text-[13px] font-semibold text-ink">Permitir subir sin clave</div>
                    <div className="text-xs text-ink-3">Cualquier persona con el enlace podrá subir documentos a este flujo, sin cuenta.</div>
                  </div>
                  <Interruptor
                    activo={flujo.acceso_publico}
                    etiqueta="Permitir subir documentos sin clave"
                    deshabilitado={accesoPublico.isPending}
                    onCambio={(nuevo) => {
                      if (
                        !nuevo ||
                        window.confirm(
                          'Vas a abrir este flujo al público: cualquier persona con el enlace podrá subir documentos SIN clave y los datos personales que contengan se guardarán. ¿Continuar?',
                        )
                      )
                        accesoPublico.mutate(nuevo)
                    }}
                  />
                </div>
                {flujo.acceso_publico && (
                  <div>
                    <div className="mb-1 text-xs text-ink-3">Enlace para compartir</div>
                    <div className="flex items-center gap-2">
                      <code className="min-w-0 flex-1 break-all rounded-lg border border-line bg-white px-3 py-2 font-mono text-[12px] text-ink">
                        {`${window.location.origin}/captura/${flujo.codigo}`}
                      </code>
                      <button
                        type="button"
                        className="boton-secundario"
                        onClick={async () => {
                          try {
                            await navigator.clipboard.writeText(`${window.location.origin}/captura/${flujo.codigo}`)
                            setUrlCopiada(true)
                          } catch {
                            setUrlCopiada(false)
                          }
                        }}
                      >
                        {urlCopiada ? 'Copiado' : 'Copiar'}
                      </button>
                    </div>
                    {!flujo.activo && <p className="mt-1.5 text-xs text-warn">El flujo está inactivo: el enlace no funcionará hasta activarlo.</p>}
                  </div>
                )}
                {accesoPublico.isError && <p className="text-xs text-err">{(accesoPublico.error as Error).message}</p>}
              </div>
            </div>
          )}

          <div className="flex justify-end gap-2">
            <Link to="/flujos-captura" className="boton-secundario">
              Cancelar
            </Link>
            <button type="submit" className="boton-primario" disabled={guardar.isPending}>
              {guardar.isPending ? 'Guardando...' : esNuevo ? 'Crear flujo' : 'Guardar cambios'}
            </button>
          </div>
        </div>
      </div>
    </form>
  )
}
