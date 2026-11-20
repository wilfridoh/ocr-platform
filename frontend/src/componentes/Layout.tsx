import { Outlet } from 'react-router-dom'
import BarraLateral from './BarraLateral'

export default function Layout() {
  return (
    <div className="flex min-h-screen">
      <BarraLateral />
      <main className="min-w-0 flex-1 overflow-y-auto px-8 py-7">
        <div className="mx-auto max-w-[1280px]">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
