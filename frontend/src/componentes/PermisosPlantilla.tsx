import { useEffect, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/api'
import { ROLES, type Plantilla, type Rol } from '@/tipos'
import { Icono } from './Iconos'

const AYUDA: Record<Rol, string> = {
  Operador: 'Cualquier usuario con rol Editor o Administrador puede editarla (el mínimo de la ruta sigue siendo Editor).',
  Editor: 'La pueden editar Editores y Administradores (valor por defecto).',
  Administrador: 'Solo un Administrador puede editarla o activarla. Útil para plantillas sensibles, como la cédula.',
}

/** Sección «Permisos» de /plantillas/:id (docs/07 §6.3). Solo se muestra a un Administrador. */
export default function PermisosPlantilla({ plantilla }: { plantilla: Plantilla }) {
  const queryClient = useQueryClient()
  const actual: Rol = plantilla.rol_minimo_edicion ?? 'Editor'
  const [rol, setRol] = useState<Rol>(actual)
  useEffect(() => setRol(actual), [actual])

  const guardar = useMutation({
    mutationFn: () => api.fijarPermisosPlantilla(plantilla.id, rol),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['plantilla', plantilla.id] })
      void queryClient.invalidateQueries({ queryKey: ['plantillas'] })
    },
  })

  return (
    <div className="tarjeta mb-4">
      <div className="flex items-center gap-2 border-b border-line px-4 py-3 text-[13px] font-semibold">
        <Icono nombre="candado" tamano={14} /> Permisos
      </div>
      <div className="p-4">
        <label className="etiqueta-campo" htmlFor="rol-minimo-edicion">
          Rol mínimo para editarla
        </label>
        <select id="rol-minimo-edicion" className="campo-entrada" value={rol} onChange={(e) => setRol(e.target.value as Rol)}>
          {ROLES.map((r) => (
            <option key={r} value={r}>
              {r}
            </option>
          ))}
        </select>
        <p className="mt-1.5 text-xs text-ink-3">{AYUDA[rol]}</p>
        <div className="mt-3 flex items-center gap-3">
          <button type="button" className="boton-secundario" disabled={rol === actual || guardar.isPending} onClick={() => guardar.mutate()}>
            {guardar.isPending ? 'Guardando...' : 'Guardar permisos'}
          </button>
          {guardar.isSuccess && rol === actual && <span className="text-xs text-ok">Guardado ✓</span>}
        </div>
        {guardar.isError && <p className="mt-2 text-xs text-err">{(guardar.error as Error).message}</p>}
      </div>
    </div>
  )
}
