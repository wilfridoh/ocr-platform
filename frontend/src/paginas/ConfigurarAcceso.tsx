import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { guardarClaveApi, obtenerClaveApi } from '@/api/claveApi'
import { BASE_URL } from '@/api/http'
import { USAR_MOCK } from '@/api'
import { verificarConexion, type ResultadoConexion } from '@/api/verificarConexion'
import { fijarRolMock, rolMock } from '@/api/mock'
import { ROLES, type Rol } from '@/tipos'

type Estado = { fase: 'inactivo' } | { fase: 'verificando' } | { fase: 'resultado'; r: ResultadoConexion }

/** Íconos de la maqueta (trazo 2, 24x24). */
function IconoLlave() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <circle cx="7.5" cy="15.5" r="5.5" />
      <path d="m21 2-9.6 9.6M15.5 7.5l3 3L22 7l-3-3" />
    </svg>
  )
}

function Insignia({ estado }: { estado: Estado }) {
  if (estado.fase === 'inactivo') return null
  let clase = 'ui-estado-neutro'
  let icono = <circle cx="12" cy="12" r="9" />
  let texto = ''
  if (estado.fase === 'verificando') {
    texto = 'Verificando conexión…'
  } else {
    const r = estado.r
    if (r.estado === 'ok') {
      clase = 'ui-estado-ok'
      icono = <path d="M20 6 9 17l-5-5" />
      texto = USAR_MOCK
        ? 'Modo demostración · datos de ejemplo'
        : r.version
          ? `Conexión verificada · API ${r.version}`
          : 'Conexión verificada'
    } else if (r.estado === 'sin_clave') {
      texto = 'Servidor disponible. Falta ingresar la clave de API.'
    } else if (r.estado === 'clave_invalida') {
      clase = 'ui-estado-error'
      icono = <path d="M18 6 6 18M6 6l12 12" />
      texto = 'El servidor rechazó la clave de API. Revísala con el administrador.'
    } else {
      clase = 'ui-estado-error'
      icono = <path d="M18 6 6 18M6 6l12 12" />
      texto = `No se pudo conectar con el servidor${r.detalle ? ` (${r.detalle})` : ''}.`
    }
  }
  return (
    <div className={`ui-estado ${clase}`} role="status" aria-live="polite">
      <svg viewBox="0 0 24 24" aria-hidden>
        {icono}
      </svg>
      <span>{texto}</span>
    </div>
  )
}

export default function ConfigurarAcceso() {
  const navegar = useNavigate()
  const queryClient = useQueryClient()
  const [clave, setClave] = useState(obtenerClaveApi())
  const [rolDemo, setRolDemo] = useState<Rol>(rolMock())
  const [estado, setEstado] = useState<Estado>({ fase: 'inactivo' })
  const consulta = useRef(0) // descarta respuestas de verificaciones viejas

  const verificar = async (valor: string): Promise<ResultadoConexion> => {
    const id = ++consulta.current
    setEstado({ fase: 'verificando' })
    const r = await verificarConexion(valor)
    if (id === consulta.current) setEstado({ fase: 'resultado', r })
    return r
  }

  // Al cargar: comprobar la clave que ya estuviera guardada.
  useEffect(() => {
    void verificar(obtenerClaveApi())
    return () => {
      consulta.current++
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const guardarYEntrar = async (e: React.FormEvent) => {
    e.preventDefault()
    const valor = clave.trim()
    const r = await verificar(valor)
    // Solo se guarda una clave que el servidor aceptó: una clave mala no reemplaza a la que ya funcionaba.
    if (r.estado === 'ok') {
      guardarClaveApi(valor)
      void queryClient.invalidateQueries() // refresca el indicador del menú y los listados con la clave nueva
      navegar('/')
    }
  }

  const verificando = estado.fase === 'verificando'

  return (
    <div style={{ maxWidth: 520, margin: '40px auto 0' }}>
      <form onSubmit={guardarYEntrar} className="ui-tarjeta" style={{ padding: 30 }} noValidate>
        <div style={{ textAlign: 'center', paddingBottom: 18 }}>
          <div className="ui-vacio-icono">
            <IconoLlave />
          </div>
          <h2 style={{ fontSize: 18, fontWeight: 700, marginBottom: 6 }}>Configurar acceso</h2>
          <p style={{ color: 'var(--ink3)', maxWidth: 420, margin: '0 auto' }}>
            Ingresa la clave de API que te entregó el administrador. Se guarda solo en este navegador.
          </p>
        </div>

        <label className="ui-etiqueta" htmlFor="clave-api">
          Clave de API
        </label>
        <input
          id="clave-api"
          type="password"
          className="ui-campo"
          value={clave}
          onChange={(e) => setClave(e.target.value)}
          placeholder="••••••••••••••••"
          autoComplete="off"
          aria-describedby="ayuda-clave"
        />
        <div id="ayuda-clave" className="ui-ayuda">
          Se envía en cada petición como <span style={{ fontFamily: 'var(--mono)' }}>X-API-Key</span>.
        </div>

        <label className="ui-etiqueta" htmlFor="servidor" style={{ marginTop: 14 }}>
          Servidor
        </label>
        <input id="servidor" className="ui-campo" value={BASE_URL} disabled readOnly />

        {USAR_MOCK && (
          <div style={{ marginTop: 14 }}>
            <label className="ui-etiqueta" htmlFor="rol-demo">
              Rol de la demostración
            </label>
            <select
              id="rol-demo"
              className="ui-campo"
              value={rolDemo}
              onChange={(e) => {
                const r = e.target.value as Rol
                setRolDemo(r)
                fijarRolMock(r)
                void queryClient.invalidateQueries({ queryKey: ['yo'] })
              }}
            >
              {ROLES.map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </select>
            <div className="ui-ayuda">Solo en modo demostración: cambia lo que ve el menú y las pantallas según el rol.</div>
          </div>
        )}

        <Insignia estado={estado} />

        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 20 }}>
          <Link to="/" className="ui-btn ui-btn-fantasma">
            Cancelar
          </Link>
          <button type="submit" className="ui-btn ui-btn-pri" disabled={verificando}>
            {verificando ? 'Verificando…' : 'Guardar y entrar'}
          </button>
        </div>
      </form>
    </div>
  )
}
