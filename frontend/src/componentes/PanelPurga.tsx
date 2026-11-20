import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/api'
import MensajeError from './MensajeError'
import { Icono } from './Iconos'
import { formatearTamano } from '@/utilidades/formato'

/**
 * Retención y purga de documentos (datos personales). Solo se monta para un Administrador.
 * Muestra la política vigente y permite eliminar a mano los vencidos o, para limpiar tras una tanda de pruebas, todos.
 */
export default function PanelPurga({ onCerrar }: { onCerrar: () => void }) {
  const queryClient = useQueryClient()
  const [resultado, setResultado] = useState<string | null>(null)

  const vista = useQuery({ queryKey: ['purga'], queryFn: () => api.vistaPreviaPurga(), retry: false })
  const v = vista.data

  const purgar = useMutation({
    mutationFn: (alcance: 'vencidos' | 'todos') => api.purgarDocumentos(alcance),
    onSuccess: (r) => {
      setResultado(`Se eliminaron ${r.documentos} documento(s): ${r.archivos} archivo(s) liberados (${formatearTamano(r.bytes)}).`)
      void queryClient.invalidateQueries({ queryKey: ['documentos'] })
      void queryClient.invalidateQueries({ queryKey: ['purga'] })
    },
  })

  const eliminarVencidos = () => {
    if (!v) return
    if (window.confirm(`¿Eliminar ${v.vencidos.documentos} documento(s) con más de ${v.retencion_dias} días? No se puede deshacer.`)) {
      setResultado(null)
      purgar.mutate('vencidos')
    }
  }

  const eliminarTodos = () => {
    if (!v) return
    const respuesta = window.prompt(
      `Vas a eliminar TODOS los documentos (${v.todos.documentos}) con sus datos extraídos y archivos originales. No se puede deshacer.\n\nEscribe ELIMINAR para confirmar:`,
    )
    if (respuesta?.trim() === 'ELIMINAR') {
      setResultado(null)
      purgar.mutate('todos')
    }
  }

  return (
    <div className="tarjeta mb-4" role="region" aria-label="Retención y purga de documentos">
      <div className="flex items-center justify-between border-b border-line px-4 py-3 text-[13px] font-semibold">
        <span className="flex items-center gap-2">
          <Icono nombre="candado" tamano={14} /> Retención y purga de documentos
        </span>
        <button type="button" className="text-xs font-normal text-ink-3 hover:underline" onClick={onCerrar}>
          Cerrar
        </button>
      </div>
      <div className="space-y-3 p-4">
        {vista.isLoading && <p className="text-sm text-ink-3">Calculando…</p>}
        {vista.isError && <MensajeError mensaje={(vista.error as Error).message} onReintentar={() => vista.refetch()} />}

        {v && (
          <>
            <p className="text-[13px] text-ink-2">
              {v.retencion_dias > 0 ? (
                <>
                  Los documentos se conservan <b>{v.retencion_dias} días</b>
                  {v.automatica ? ' y se eliminan automáticamente cada día.' : '. La purga automática está APAGADA en este servidor: solo se elimina a mano.'}
                </>
              ) : (
                <>Este servidor <b>no caduca documentos automáticamente</b>: solo se eliminan a mano.</>
              )}{' '}
              Al eliminar se borran el registro, los datos extraídos, el registro de procesamiento y el archivo original.
            </p>

            <div className="flex flex-wrap items-center gap-3">
              <button type="button" className="boton-secundario" disabled={purgar.isPending || v.retencion_dias <= 0 || v.vencidos.documentos === 0} onClick={eliminarVencidos}>
                Eliminar vencidos ({v.vencidos.documentos}
                {v.vencidos.bytes > 0 ? ` · ${formatearTamano(v.vencidos.bytes)}` : ''})
              </button>
              <button type="button" className="boton-peligro" disabled={purgar.isPending || v.todos.documentos === 0} onClick={eliminarTodos}>
                Eliminar TODOS ({v.todos.documentos}
                {v.todos.bytes > 0 ? ` · ${formatearTamano(v.todos.bytes)}` : ''})
              </button>
            </div>
            <p className="text-xs text-ink-3">«Eliminar TODOS» sirve para limpiar después de una tanda de pruebas. Las plantillas y flujos no se tocan.</p>
          </>
        )}

        {purgar.isError && <MensajeError mensaje={(purgar.error as Error).message} />}
        {resultado && (
          <p className="flex items-center gap-2 rounded-lg bg-ok-soft px-3 py-2 text-[13px] text-ok" role="status">
            <Icono nombre="check" tamano={14} /> {resultado}
          </p>
        )}
      </div>
    </div>
  )
}
