import { useEffect, useState } from 'react'

interface Props {
  abierto: boolean
  titulo: string
  mensaje: string
  /** Texto del botón que confirma */
  confirmar?: string
  /** Estilo rojo para acciones destructivas o que abren datos al público */
  peligro?: boolean
  /** Si se indica, hay que escribir esta palabra para habilitar el botón (acciones irreversibles) */
  palabraClave?: string
  onConfirmar: () => void
  onCancelar: () => void
}

/** Diálogo de confirmación propio (sustituye a window.confirm/prompt, que algunos navegadores bloquean). */
export default function DialogoConfirmar({
  abierto,
  titulo,
  mensaje,
  confirmar = 'Continuar',
  peligro = false,
  palabraClave,
  onConfirmar,
  onCancelar,
}: Props) {
  const [escrito, setEscrito] = useState('')

  useEffect(() => {
    if (!abierto) return
    setEscrito('')
    const alTeclear = (e: KeyboardEvent) => e.key === 'Escape' && onCancelar()
    window.addEventListener('keydown', alTeclear)
    return () => window.removeEventListener('keydown', alTeclear)
  }, [abierto, onCancelar])

  if (!abierto) return null
  const habilitado = !palabraClave || escrito.trim() === palabraClave

  return (
    <div className="fixed inset-0 z-[60] grid place-items-center bg-black/50 p-4" onClick={onCancelar}>
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="dialogo-titulo"
        className="w-full max-w-[440px] rounded-2xl border border-line bg-surface p-5 shadow-card"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 id="dialogo-titulo" className="mb-2 text-base font-bold text-ink">
          {titulo}
        </h2>
        <p className="mb-4 text-[13px] leading-relaxed text-ink-2">{mensaje}</p>
        {palabraClave && (
          <label className="mb-4 block text-[13px] text-ink-2">
            Escribe <b>{palabraClave}</b> para confirmar
            <input
              className="mt-1 w-full rounded-lg border border-line bg-white px-3 py-2 text-sm"
              value={escrito}
              onChange={(e) => setEscrito(e.target.value)}
              autoFocus
              autoComplete="off"
              data-testid="dialogo-palabra"
            />
          </label>
        )}
        <div className="flex justify-end gap-2">
          <button type="button" className="boton-secundario" onClick={onCancelar} autoFocus={!palabraClave}>
            Cancelar
          </button>
          <button
            type="button"
            className={peligro ? 'boton-peligro' : 'boton-primario'}
            disabled={!habilitado}
            onClick={onConfirmar}
            data-testid="dialogo-confirmar"
          >
            {confirmar}
          </button>
        </div>
      </div>
    </div>
  )
}
