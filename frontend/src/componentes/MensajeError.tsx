export default function MensajeError({
  mensaje,
  onReintentar,
}: {
  mensaje: string
  onReintentar?: () => void
}) {
  return (
    <div className="tarjeta border-[#FCA5A5] bg-err-soft p-4 text-sm text-err">
      <p className="font-medium">Ocurrió un error</p>
      <p className="mt-1">{mensaje}</p>
      {onReintentar && (
        <button type="button" onClick={onReintentar} className="boton-secundario mt-3">
          Reintentar
        </button>
      )}
    </div>
  )
}
