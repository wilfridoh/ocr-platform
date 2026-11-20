import { useEffect, useState } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import BarraLateral from './BarraLateral'

export default function Layout() {
  const [menuAbierto, setMenuAbierto] = useState(false)
  const { pathname } = useLocation()

  // En pantalla angosta el menú es un cajón: se cierra al navegar
  useEffect(() => setMenuAbierto(false), [pathname])

  return (
    <div className="flex min-h-screen">
      {/* Barra superior solo en pantalla angosta (<768px) */}
      <header className="fixed inset-x-0 top-0 z-30 flex h-12 items-center gap-3 bg-side px-3 md:hidden">
        <button
          type="button"
          onClick={() => setMenuAbierto(true)}
          aria-label="Abrir menú"
          aria-expanded={menuAbierto}
          className="grid h-9 w-9 place-items-center rounded-lg text-white hover:bg-[#1E293B]"
        >
          <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden>
            <path d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>
        <span className="text-sm font-bold text-white">OCR Platform</span>
      </header>

      <BarraLateral abierto={menuAbierto} onCerrar={() => setMenuAbierto(false)} />

      <main className="min-w-0 flex-1 px-4 pb-6 pt-16 sm:px-6 md:px-8 md:py-7">
        <div className="mx-auto max-w-[1280px]">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
