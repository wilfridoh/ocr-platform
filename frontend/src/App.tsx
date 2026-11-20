import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import Layout from '@/componentes/Layout'
import Procesar from '@/paginas/Procesar'
import Documentos from '@/paginas/Documentos'
import DetalleDocumento from '@/paginas/DetalleDocumento'
import Plantillas from '@/paginas/Plantillas'
import NuevaPlantilla from '@/paginas/NuevaPlantilla'
import EditarPlantilla from '@/paginas/EditarPlantilla'
import ZonasPlantilla from '@/paginas/ZonasPlantilla'
import ConfigurarAcceso from '@/paginas/ConfigurarAcceso'
import Flujos from '@/paginas/Flujos'
import EditarFlujo from '@/paginas/EditarFlujo'
import ProcesarConFlujo from '@/paginas/ProcesarConFlujo'
import Usuarios from '@/paginas/Usuarios'
import CapturaPublica from '@/paginas/CapturaPublica'
import RequiereRol from '@/componentes/RequiereRol'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, refetchOnWindowFocus: false },
  },
})

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          {/* Pantalla pública (sin sesión): fuera del Layout para que no cargue el menú ni llame a la API con clave */}
          <Route path="captura/:codigo" element={<CapturaPublica />} />
          <Route element={<Layout />}>
            <Route index element={<Procesar />} />
            <Route path="documentos" element={<Documentos />} />
            <Route path="documentos/:id" element={<DetalleDocumento />} />
            <Route path="plantillas" element={<Plantillas />} />
            <Route path="plantillas/nueva" element={<RequiereRol minimo="Editor"><NuevaPlantilla /></RequiereRol>} />
            <Route path="plantillas/:id" element={<RequiereRol minimo="Editor"><EditarPlantilla /></RequiereRol>} />
            <Route path="plantillas/:id/zonas" element={<RequiereRol minimo="Editor"><ZonasPlantilla /></RequiereRol>} />
            <Route path="flujos-captura" element={<Flujos />} />
            <Route path="flujos-captura/nuevo" element={<EditarFlujo />} />
            <Route path="flujos-captura/:id" element={<EditarFlujo />} />
            <Route path="procesar/:codigo" element={<ProcesarConFlujo />} />
            <Route path="usuarios" element={<Usuarios />} />
            <Route path="configurar-acceso" element={<ConfigurarAcceso />} />
            <Route path="*" element={<Procesar />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}

export default App
