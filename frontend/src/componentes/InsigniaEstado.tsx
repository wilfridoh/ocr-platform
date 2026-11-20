import type { EstadoDocumento } from '@/tipos'

// Guía visual (docs/09 §4): COMPLETADO = ok, ERROR = err, PROCESANDO = marca, todos con punto de estado.
const ESTILOS: Record<EstadoDocumento, string> = {
  RECIBIDO: 'chip',
  PROCESANDO: 'chip chip-marca',
  COMPLETADO: 'chip chip-ok',
  ERROR: 'chip chip-err',
  NO_COINCIDE: 'chip chip-warn', // flujo de captura: se esperaba otro tipo de documento
}

const ETIQUETAS: Record<EstadoDocumento, string> = {
  RECIBIDO: 'Recibido',
  PROCESANDO: 'Procesando',
  COMPLETADO: 'Completado',
  ERROR: 'Error',
  NO_COINCIDE: 'No coincide',
}

export default function InsigniaEstado({ estado }: { estado: EstadoDocumento }) {
  return (
    <span className={ESTILOS[estado]}>
      <span className="chip-punto" aria-hidden />
      {ETIQUETAS[estado]}
    </span>
  )
}
