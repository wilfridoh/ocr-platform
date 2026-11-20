import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery } from '@tanstack/react-query'
import { api } from '@/api'
import type { Campo, PalabraClave } from '@/tipos'
import EditorPalabrasClave from '@/componentes/EditorPalabrasClave'
import EditorCampos from '@/componentes/EditorCampos'
import CargandoIndicador from '@/componentes/CargandoIndicador'
import MensajeError from '@/componentes/MensajeError'
import PermisosPlantilla from '@/componentes/PermisosPlantilla'
import SinPermiso from '@/componentes/SinPermiso'
import { rolMayor } from '@/utilidades/roles'
import { useYo } from '@/utilidades/useYo'
import { formatearFecha } from '@/utilidades/formato'

export default function EditarPlantilla() {
  const { id } = useParams()
  const plantillaId = Number(id)
  const navigate = useNavigate()
  const { rol, puede } = useYo()

  const plantillaQuery = useQuery({ queryKey: ['plantilla', plantillaId], queryFn: () => api.obtenerPlantilla(plantillaId) })
  const versionesQuery = useQuery({
    queryKey: ['plantilla', plantillaId, 'versiones'],
    queryFn: () => api.listarVersionesPlantilla(plantillaId),
  })

  const [codigo, setCodigo] = useState('')
  const [nombre, setNombre] = useState('')
  const [descripcion, setDescripcion] = useState('')
  const [umbral, setUmbral] = useState(0.6)
  const [palabrasClave, setPalabrasClave] = useState<PalabraClave[]>([])
  const [campos, setCampos] = useState<Campo[]>([])
  const [cargado, setCargado] = useState(false)

  useEffect(() => {
    if (plantillaQuery.data && !cargado) {
      const p = plantillaQuery.data
      setCodigo(p.codigo)
      setNombre(p.nombre)
      setDescripcion(p.descripcion ?? '')
      setUmbral(p.umbral_confianza)
      setPalabrasClave(p.palabras_clave)
      setCampos(p.campos)
      setCargado(true)
    }
  }, [plantillaQuery.data, cargado])

  const guardar = useMutation({
    mutationFn: () =>
      api.actualizarPlantilla(plantillaId, {
        codigo,
        nombre,
        descripcion,
        activa: plantillaQuery.data?.activa ?? true,
        umbral_confianza: umbral,
        palabras_clave: palabrasClave,
        campos,
        // la cuadrícula se edita en su propia pantalla; aquí se reenvía tal cual para que la versión nueva no la pierda
        diseno: plantillaQuery.data?.diseno ?? null,
      }),
  })

  const reprocesarTodos = useMutation({
    mutationFn: () => api.reprocesarDocumentosDePlantilla(plantillaId),
  })

  const puedeGuardar = useMemo(() => codigo.trim() !== '' && nombre.trim() !== '' && campos.length > 0, [codigo, nombre, campos])

  if (plantillaQuery.isLoading) return <CargandoIndicador etiqueta="Cargando plantilla..." />
  if (plantillaQuery.isError) return <MensajeError mensaje={(plantillaQuery.error as Error).message} onReintentar={() => plantillaQuery.refetch()} />

  const rolNecesario = rolMayor('Editor', plantillaQuery.data?.rol_minimo_edicion ?? 'Editor')
  if (plantillaQuery.data && !puede(rolNecesario)) {
    return <SinPermiso requiere={rolNecesario} rolActual={rol} detalle={`Esta plantilla solo la puede editar el rol ${rolNecesario} o superior.`} />
  }

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <div>
          <button type="button" onClick={() => navigate('/plantillas')} className="text-sm text-indigo-600 hover:underline">
            ← Volver a plantillas
          </button>
          <h2 className="mt-1 text-[22px] font-bold tracking-[-0.01em] text-ink">Editar plantilla: {plantillaQuery.data?.codigo}</h2>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            className="boton-secundario"
            title="Marcar en qué zonas de la página está cada dato y qué textos impresos deben aparecer"
            onClick={() => navigate(`/plantillas/${plantillaId}/zonas`)}
          >
            ▦ Cuadrícula{plantillaQuery.data?.diseno ? ' ✓' : ''}
          </button>
          <button type="button" className="boton-secundario" disabled={reprocesarTodos.isPending} onClick={() => reprocesarTodos.mutate()}>
            {reprocesarTodos.isPending ? 'Reprocesando...' : 'Reprocesar documentos de esta plantilla'}
          </button>
        </div>
      </div>
      {cargado && plantillaQuery.data?.diseno && (
        <p className="mb-4 rounded-md bg-indigo-50 px-3 py-2 text-xs text-indigo-700">
          Esta plantilla tiene cuadrícula. Si guardas aquí, se conserva; para cambiar zonas usa «Cuadrícula» (guarda las
          zonas por separado, así que guarda antes los cambios de esta pantalla).
        </p>
      )}

      {reprocesarTodos.isSuccess && (
        <p className="mb-4 rounded-md bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
          Se encolaron {reprocesarTodos.data.total} documentos para reprocesar.
        </p>
      )}

      <div className="grid gap-6 lg:grid-cols-[1fr_300px]">
        <div className="space-y-4">
          <div className="tarjeta space-y-4 p-4">
            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <label className="etiqueta-campo">Código del tipo</label>
                <input className="campo-entrada font-mono" value={codigo} onChange={(e) => setCodigo(e.target.value)} />
              </div>
              <div>
                <label className="etiqueta-campo">Nombre</label>
                <input className="campo-entrada" value={nombre} onChange={(e) => setNombre(e.target.value)} />
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
              <label className="etiqueta-campo">Palabras clave</label>
              <EditorPalabrasClave valor={palabrasClave} onCambiar={setPalabrasClave} />
            </div>
          </div>

          <div className="tarjeta p-4">
            <h3 className="mb-3 text-sm font-semibold text-slate-600">Campos</h3>
            <EditorCampos campos={campos} onCambiar={setCampos} />
          </div>

          <div className="flex items-center gap-3">
            <button type="button" className="boton-primario" disabled={!puedeGuardar || guardar.isPending} onClick={() => guardar.mutate()}>
              {guardar.isPending ? 'Guardando...' : 'Guardar cambios'}
            </button>
            {guardar.isSuccess && <span className="text-sm text-emerald-600">Guardado ✓ (nueva versión)</span>}
            {guardar.isError && <span className="text-sm text-red-600">{(guardar.error as Error).message}</span>}
          </div>
        </div>

        <div>
          {puede('Administrador') && plantillaQuery.data && <PermisosPlantilla plantilla={plantillaQuery.data} />}
          <h3 className="mb-2 text-sm font-semibold text-slate-600">Historial de versiones</h3>
          <ul className="tarjeta divide-y divide-slate-100">
            {versionesQuery.data?.map((v) => (
              <li key={v.version} className="px-3 py-2 text-sm">
                <div className="font-medium text-slate-700">Versión {v.version}</div>
                <div className="text-xs text-slate-400">{formatearFecha(v.fecha)}</div>
                {v.comentario && <div className="text-xs text-slate-500">{v.comentario}</div>}
              </li>
            ))}
            {!versionesQuery.data?.length && <li className="px-3 py-4 text-sm text-slate-400">Sin versiones registradas.</li>}
          </ul>
        </div>
      </div>
    </div>
  )
}
