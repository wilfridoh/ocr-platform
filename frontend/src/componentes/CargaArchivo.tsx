import { useCallback, useRef, useState } from 'react'

const EXTENSIONES_ACEPTADAS = ['.pdf', '.jpg', '.jpeg', '.png', '.tiff', '.tif']

interface Props {
  onArchivoSeleccionado: (archivo: File) => void
  archivoActual?: File | null
  deshabilitado?: boolean
}

export default function CargaArchivo({ onArchivoSeleccionado, archivoActual, deshabilitado }: Props) {
  const [arrastrando, setArrastrando] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const manejarArchivos = useCallback(
    (lista: FileList | null) => {
      const archivo = lista?.[0]
      if (archivo) onArchivoSeleccionado(archivo)
    },
    [onArchivoSeleccionado],
  )

  return (
    <div>
      <div
        role="button"
        tabIndex={0}
        aria-label="Arrastra aquí tu PDF o imagen, o haz clic para seleccionar"
        onClick={() => !deshabilitado && inputRef.current?.click()}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') inputRef.current?.click()
        }}
        onDragOver={(e) => {
          e.preventDefault()
          if (!deshabilitado) setArrastrando(true)
        }}
        onDragLeave={() => setArrastrando(false)}
        onDrop={(e) => {
          e.preventDefault()
          setArrastrando(false)
          if (!deshabilitado) manejarArchivos(e.dataTransfer.files)
        }}
        className={`flex min-h-[160px] cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed p-6 text-center transition-colors ${
          arrastrando ? 'border-indigo-500 bg-indigo-50' : 'border-slate-300 bg-white hover:border-indigo-400'
        } ${deshabilitado ? 'pointer-events-none opacity-60' : ''}`}
      >
        <svg className="mb-2 h-8 w-8 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"
          />
        </svg>
        {archivoActual ? (
          <p className="text-sm font-medium text-slate-700">{archivoActual.name}</p>
        ) : (
          <>
            <p className="text-sm font-medium text-slate-700">Arrastra aquí tu PDF o imagen, o haz clic</p>
            <p className="mt-1 text-xs text-slate-400">PDF, JPG, PNG o TIFF, máx. 20 MB</p>
          </>
        )}
        <input
          ref={inputRef}
          type="file"
          className="hidden"
          accept={EXTENSIONES_ACEPTADAS.join(',')}
          disabled={deshabilitado}
          onChange={(e) => manejarArchivos(e.target.files)}
        />
      </div>
    </div>
  )
}
