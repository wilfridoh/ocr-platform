import { useState } from 'react'
import { JsonView, allExpanded, defaultStyles } from 'react-json-view-lite'
import 'react-json-view-lite/dist/index.css'

interface Props {
  datos: unknown
  nombreArchivo?: string
}

export default function VisorJSON({ datos, nombreArchivo = 'resultado.json' }: Props) {
  const [copiado, setCopiado] = useState(false)
  const texto = JSON.stringify(datos, null, 2)

  const copiar = async () => {
    try {
      await navigator.clipboard.writeText(texto)
      setCopiado(true)
      setTimeout(() => setCopiado(false), 1500)
    } catch {
      /* portapapeles no disponible */
    }
  }

  const descargar = () => {
    const blob = new Blob([texto], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = nombreArchivo
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="tarjeta p-3">
      <div className="mb-2 flex items-center justify-end gap-2">
        <button type="button" onClick={copiar} className="boton-secundario">
          {copiado ? 'Copiado ✓' : 'Copiar JSON'}
        </button>
        <button type="button" onClick={descargar} className="boton-secundario">
          Descargar
        </button>
      </div>
      <div className="max-h-[480px] overflow-auto text-xs">
        <JsonView data={datos as object} shouldExpandNode={allExpanded} style={defaultStyles} />
      </div>
    </div>
  )
}
