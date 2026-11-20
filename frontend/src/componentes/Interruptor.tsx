/** Interruptor (docs/09 §4): 34×20 px; apagado #CBD5E1, encendido `ok`; perilla blanca de 16 px. */
export default function Interruptor({
  activo,
  onCambio,
  etiqueta,
  deshabilitado,
  titulo,
}: {
  activo: boolean
  onCambio: (nuevo: boolean) => void
  /** Texto accesible: qué enciende o apaga este interruptor */
  etiqueta: string
  deshabilitado?: boolean
  titulo?: string
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={activo}
      aria-label={etiqueta}
      title={titulo ?? etiqueta}
      disabled={deshabilitado}
      onClick={() => onCambio(!activo)}
      className={`relative h-5 w-[34px] flex-none rounded-full transition-colors disabled:cursor-not-allowed disabled:opacity-[.45] ${
        activo ? 'bg-ok' : 'bg-[#CBD5E1]'
      }`}
    >
      <span
        className={`absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition-all ${activo ? 'left-[16px]' : 'left-0.5'}`}
      />
    </button>
  )
}
