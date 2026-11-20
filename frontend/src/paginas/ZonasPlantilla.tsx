import { useEffect, useMemo, useState } from 'react'
import { useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/api'
import type { Campo, DisenoPlantilla, Orientacion, PalabraPosicion, Regla, ZonaEtiqueta, ZonaRelativa } from '@/tipos'
import { ErrorApi } from '@/tipos'
import CargandoIndicador from '@/componentes/CargandoIndicador'
import MensajeError from '@/componentes/MensajeError'
import SinPermiso from '@/componentes/SinPermiso'
import LienzoCuadricula, { type ZonaDibujo } from '@/componentes/cuadricula/LienzoCuadricula'
import PanelValidacion from '@/componentes/cuadricula/PanelValidacion'
import AjusteEsquinas from '@/componentes/cuadricula/AjusteEsquinas'
import { rolMayor } from '@/utilidades/roles'
import { useYo } from '@/utilidades/useYo'
import {
  CONFIANZA_BAJA,
  colorCampo,
  densidad as obtenerDensidad,
  DENSIDADES,
  DISENO_POR_DEFECTO,
  FORMATOS,
  rangoCeldas,
  textoEnZona,
  tieneZonaValor,
} from '@/utilidades/cuadricula'

type Objetivo = { tipo: 'campo'; nombre: string } | { tipo: 'fijo' }
type TipoZona = 'valor' | 'etiqueta'
interface Estado {
  campos: Campo[]
  fijos: ZonaEtiqueta[]
}

const ORIGEN_LEGIBLE: Record<string, string> = {
  automatico: 'automático',
  manual: 'manual',
  ninguno: 'no detectado',
  pdf: 'PDF (sin recorte)',
  desconocido: 'desconocido',
}

/** "#/plantillas/zonas" de la maqueta (docs/12): marcar en qué celdas está cada dato y qué textos impresos se esperan. */
export default function ZonasPlantilla() {
  const { id } = useParams()
  const plantillaId = Number(id)
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const documentoId = params.get('documento') ?? ''
  const qc = useQueryClient()
  const { rol, puede } = useYo()

  const plantillaQuery = useQuery({ queryKey: ['plantilla', plantillaId], queryFn: () => api.obtenerPlantilla(plantillaId) })
  const plantilla = plantillaQuery.data

  // ---------------------------------------------------------------- estado editable (con deshacer)
  const [estado, setEstado] = useState<Estado | null>(null)
  const [historial, setHistorial] = useState<Estado[]>([])
  const [diseno, setDiseno] = useState<DisenoPlantilla>(DISENO_POR_DEFECTO)
  const [objetivo, setObjetivo] = useState<Objetivo | null>(null)
  const [tipoZona, setTipoZona] = useState<TipoZona>('valor')
  const [herramienta, setHerramienta] = useState<'dibujar' | 'borrar'>('dibujar')
  const [mostrarRejilla, setMostrarRejilla] = useState(true)
  const [pestana, setPestana] = useState<'mapear' | 'validar'>('mapear')
  const [usarDeTodosModos, setUsarDeTodosModos] = useState(false)
  const [ajustandoEsquinas, setAjustandoEsquinas] = useState(false)
  const [resaltado, setResaltado] = useState<string | null>(null)
  const [aviso, setAviso] = useState<string | null>(null)

  // etiquetas fijas sugeridas por el asistente de nueva plantilla (docs/13 §5): se precargan para revisarlas
  const zonasSugeridas = (useLocation().state as { zonasSugeridas?: ZonaEtiqueta[] } | null)?.zonasSugeridas ?? []

  useEffect(() => {
    if (plantilla && !estado) {
      const precargar = !plantilla.diseno && zonasSugeridas.length > 0
      setEstado({ campos: plantilla.campos, fijos: precargar ? zonasSugeridas : plantilla.diseno?.elementos_fijos ?? [] })
      if (precargar)
        setAviso(
          `Precargamos ${zonasSugeridas.length} etiquetas fijas sugeridas (rayadas). Revísalas: borra las que no sean texto impreso del formato y pulsa «Guardar zonas».`,
        )
      setDiseno(plantilla.diseno ?? DISENO_POR_DEFECTO)
      const primero = plantilla.campos[0]
      if (primero) setObjetivo({ tipo: 'campo', nombre: primero.nombre })
    }
  }, [plantilla, estado])

  const cambiar = (f: (e: Estado) => Estado) => {
    if (!estado) return
    setHistorial((h) => [...h.slice(-49), estado])
    setEstado(f(estado))
  }
  const deshacer = () => {
    setHistorial((h) => {
      if (!h.length) return h
      setEstado(h[h.length - 1])
      return h.slice(0, -1)
    })
  }
  useEffect(() => {
    const alTeclado = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z' && !(e.target instanceof HTMLInputElement)) {
        e.preventDefault()
        deshacer()
      }
    }
    window.addEventListener('keydown', alTeclado)
    return () => window.removeEventListener('keydown', alTeclado)
  })

  const dens = obtenerDensidad(diseno.densidad_rejilla)
  const relacionEsperada = diseno.formato === 'libre' ? null : diseno.relacion ?? null

  // ---------------------------------------------------------------- documento de ejemplo
  const documentosQuery = useQuery({
    queryKey: ['documentos', 'ejemplos', plantilla?.codigo],
    queryFn: () => api.listarDocumentos({ tipo: plantilla!.codigo, tamano: 20, pagina: 1 }),
    enabled: !!plantilla,
  })
  const imagenQuery = useQuery({
    queryKey: ['enderezada', documentoId, relacionEsperada],
    queryFn: () => api.obtenerImagenEnderezada(documentoId, 1, { relacion: relacionEsperada }),
    enabled: !!documentoId,
  })
  const palabrasQuery = useQuery({
    queryKey: ['palabras', documentoId, relacionEsperada],
    queryFn: () => api.obtenerPalabras(documentoId, 1, relacionEsperada),
    enabled: !!documentoId,
    retry: false,
  })
  const originalQuery = useQuery({
    queryKey: ['pagina-original', documentoId],
    queryFn: () => api.obtenerImagenPagina(documentoId, 1),
    enabled: !!documentoId && ajustandoEsquinas,
  })
  const urlImagen = useObjectUrl(imagenQuery.data?.blob)
  const urlOriginal = useObjectUrl(originalQuery.data)
  const palabras = palabrasQuery.data?.palabras ?? []
  const recorte = palabrasQuery.data?.recorte
  // el diseño tal como quedaría al guardar (lo usan Guardar y la vista previa de Validar)
  const disenoActual: DisenoPlantilla = useMemo(
    () => ({
      ...diseno,
      relacion: diseno.formato === 'libre' ? recorte?.relacion ?? diseno.relacion ?? null : diseno.relacion,
      elementos_fijos: estado?.fijos ?? [],
    }),
    [diseno, recorte?.relacion, estado?.fijos],
  )
  const sinPosiciones = palabrasQuery.error instanceof ErrorApi && palabrasQuery.error.status === 404
  const origen = recorte?.origen ?? imagenQuery.data?.origen ?? (sinPosiciones ? 'desconocido' : undefined)
  const confiable = recorte?.confiable ?? imagenQuery.data?.confiable ?? false
  const bloqueado = !!documentoId && !sinPosiciones && !!imagenQuery.data && !confiable && !usarDeTodosModos

  const invalidarDocumento = () => {
    qc.invalidateQueries({ queryKey: ['enderezada', documentoId] })
    qc.invalidateQueries({ queryKey: ['palabras', documentoId] })
  }
  const recortar = useMutation({
    mutationFn: (entrada: { esquinas?: [number, number][] | null; orientacion?: Orientacion }) =>
      api.recortarPagina(documentoId, 1, entrada),
    onSuccess: () => {
      setAjustandoEsquinas(false)
      invalidarDocumento()
    },
  })
  const quitarRecorte = useMutation({ mutationFn: () => api.quitarRecortePagina(documentoId, 1), onSuccess: invalidarDocumento })
  const reprocesar = useMutation({ mutationFn: () => api.reprocesarDocumento(documentoId), onSuccess: invalidarDocumento })

  // ---------------------------------------------------------------- guardar
  const guardar = useMutation({
    mutationFn: () =>
      api.actualizarPlantilla(plantillaId, {
        codigo: plantilla!.codigo,
        nombre: plantilla!.nombre,
        descripcion: plantilla!.descripcion,
        activa: plantilla!.activa,
        umbral_confianza: plantilla!.umbral_confianza,
        palabras_clave: plantilla!.palabras_clave,
        campos: estado!.campos,
        diseno: disenoActual,
      }),
    onSuccess: () => {
      setHistorial([])
      qc.invalidateQueries({ queryKey: ['plantilla', plantillaId] })
    },
  })

  // ---------------------------------------------------------------- zonas a dibujar
  const zonasDibujo: ZonaDibujo[] = useMemo(() => {
    if (!estado) return []
    const salida: ZonaDibujo[] = []
    estado.campos.forEach((c, i) => {
      const color = colorCampo(i)
      const atenuada = !!resaltado && resaltado !== c.nombre
      if (tieneZonaValor(c.regla))
        salida.push({ id: `v:${c.nombre}`, zona: zonaDe(c.regla), tipo: 'valor', color, etiqueta: c.etiqueta, atenuada })
      if (c.regla.zona_etiqueta)
        salida.push({ id: `e:${c.nombre}`, zona: c.regla.zona_etiqueta, tipo: 'etiqueta', color, etiqueta: `${c.etiqueta} · etiqueta`, atenuada })
    })
    estado.fijos.forEach((f, i) =>
      salida.push({ id: `f:${i}`, zona: f, tipo: 'etiqueta', color: '#334155', etiqueta: `${f.texto_esperado.slice(0, 24)} · fijo`, atenuada: !!resaltado && resaltado !== `f:${i}` }),
    )
    return salida
  }, [estado, resaltado])

  const alDibujar = (zona: ZonaRelativa, palabra?: PalabraPosicion) => {
    // texto esperado de una etiqueta: la palabra elegida con clic; si se arrastró, lo que hay en la zona. Ojo: las celdas
    // pueden abarcar también el valor de al lado (un dato del titular), por eso el clic en la palabra es más preciso.
    const leido = palabra?.texto ?? textoEnZona(palabras, zona)
    if (!objetivo || !estado) return
    const z = { ...zona, pagina: 1 }
    if (objetivo.tipo === 'fijo') {
      cambiar((e) => ({ ...e, fijos: [...e.fijos, { ...z, texto_esperado: leido || 'TEXTO FIJO' }] }))
      return
    }
    const campo = estado.campos.find((c) => c.nombre === objetivo.nombre)
    if (!campo) return
    if (tipoZona === 'valor') {
      cambiar((e) => ({ ...e, campos: e.campos.map((c) => (c.nombre === campo.nombre ? { ...c, regla: { ...c.regla, ...z } as Regla } : c)) }))
      // como en la maqueta: el foco pasa al siguiente campo sin zona de valor
      const siguiente = estado.campos.find((c) => c.nombre !== campo.nombre && !tieneZonaValor(c.regla))
      if (siguiente) setObjetivo({ tipo: 'campo', nombre: siguiente.nombre })
    } else {
      const texto = leido || campo.etiqueta.toUpperCase()
      cambiar((e) => ({
        ...e,
        campos: e.campos.map((c) => (c.nombre === campo.nombre ? { ...c, regla: { ...c.regla, zona_etiqueta: { ...z, texto_esperado: texto } } as Regla } : c)),
      }))
    }
  }

  const borrarZona = (idZona: string) => {
    const [tipo, clave] = [idZona.slice(0, 1), idZona.slice(2)]
    if (tipo === 'f') {
      cambiar((e) => ({ ...e, fijos: e.fijos.filter((_, i) => String(i) !== clave) }))
      return
    }
    const campo = estado?.campos.find((c) => c.nombre === clave)
    if (!campo) return
    if (tipo === 'v' && campo.regla.metodo === 'zona') {
      setAviso(`«${campo.etiqueta}» se extrae solo por zona: su zona no se puede quitar, solo volver a dibujar.`)
      return
    }
    cambiar((e) => ({
      ...e,
      campos: e.campos.map((c) => {
        if (c.nombre !== clave) return c
        if (tipo === 'v') return { ...c, regla: { ...c.regla, x: null, y: null, ancho: null, alto: null } as Regla }
        return { ...c, regla: { ...c.regla, zona_etiqueta: null } as Regla }
      }),
    }))
  }

  const cambiarTextoEsperado = (clave: string, texto: string) => {
    cambiar((e) =>
      clave.startsWith('f:')
        ? { ...e, fijos: e.fijos.map((f, i) => (`f:${i}` === clave ? { ...f, texto_esperado: texto } : f)) }
        : {
            ...e,
            campos: e.campos.map((c) =>
              c.nombre === clave && c.regla.zona_etiqueta ? { ...c, regla: { ...c.regla, zona_etiqueta: { ...c.regla.zona_etiqueta, texto_esperado: texto } } as Regla } : c,
            ),
          },
    )
  }

  // ---------------------------------------------------------------- render
  if (plantillaQuery.isLoading || (plantilla && !estado)) return <CargandoIndicador etiqueta="Cargando plantilla..." />
  if (plantillaQuery.isError || !plantilla || !estado)
    return <MensajeError mensaje={(plantillaQuery.error as Error)?.message ?? 'Plantilla no encontrada'} onReintentar={() => plantillaQuery.refetch()} />
  const rolNecesario = rolMayor('Editor', plantilla.rol_minimo_edicion ?? 'Editor')
  if (!puede(rolNecesario)) return <SinPermiso requiere={rolNecesario} rolActual={rol} />

  const cambiosSinGuardar = historial.length > 0
  const nombreObjetivo =
    objetivo?.tipo === 'fijo' ? 'un elemento fijo (sin campo)' : estado.campos.find((c) => c.nombre === objetivo?.nombre)?.etiqueta ?? '—'

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <button type="button" onClick={() => navigate(`/plantillas/${plantillaId}`)} className="text-sm text-indigo-600 hover:underline">
            ← Volver a la plantilla
          </button>
          <h2 className="mt-1 text-[22px] font-bold tracking-[-0.01em] text-ink">Mapear campos por posición · {plantilla.nombre}</h2>
          <p className="text-sm text-slate-500">
            Marca qué celdas ocupa cada dato y qué textos impresos deben aparecer. Sirve para leer valores por posición y para
            comprobar que un documento coincide con el diseño de la plantilla (no su autenticidad).
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {origen && (
            <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${confiable ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-800'}`}>
              Recorte: {ORIGEN_LEGIBLE[origen] ?? origen}
              {usarDeTodosModos && !confiable ? ' · sin verificar' : ''}
            </span>
          )}
          <button type="button" className="boton-primario" disabled={guardar.isPending || !cambiosSinGuardar && !!plantilla.diseno} onClick={() => guardar.mutate()}>
            {guardar.isPending ? 'Guardando...' : 'Guardar zonas'}
          </button>
        </div>
      </div>
      {guardar.isSuccess && !cambiosSinGuardar && (
        <p className="mb-3 rounded-md bg-emerald-50 px-3 py-2 text-sm text-emerald-700">Zonas guardadas ✓ (nueva versión de la plantilla).</p>
      )}
      {guardar.isError && <p className="mb-3 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{(guardar.error as Error).message}</p>}
      {aviso && (
        <p className="mb-3 flex items-start justify-between gap-2 rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-800">
          {aviso}
          <button type="button" className="text-xs underline" onClick={() => setAviso(null)}>
            cerrar
          </button>
        </p>
      )}

      <div className="mb-3 flex gap-4 border-b border-slate-200 text-sm">
        {(['mapear', 'validar'] as const).map((p) => (
          <button
            key={p}
            type="button"
            onClick={() => setPestana(p)}
            className={`-mb-px border-b-2 px-1 pb-2 font-medium ${pestana === p ? 'border-indigo-600 text-indigo-700' : 'border-transparent text-slate-500 hover:text-slate-700'}`}
          >
            {p === 'mapear' ? 'Mapear' : 'Validar un documento'}
          </button>
        ))}
      </div>

      <div className={`mb-3 flex flex-wrap items-end gap-3 ${pestana === 'validar' ? 'hidden' : ''}`}>
        <div className="min-w-[260px] flex-1">
          <label className="etiqueta-campo">Documento de ejemplo</label>
          <select
            className="campo-entrada"
            value={documentoId}
            onChange={(e) => {
              setUsarDeTodosModos(false)
              setAjustandoEsquinas(false)
              setParams(e.target.value ? { documento: e.target.value } : {})
            }}
          >
            <option value="">— Elige un documento procesado con esta plantilla —</option>
            {documentoId && !documentosQuery.data?.items.some((d) => d.id === documentoId) && <option value={documentoId}>{documentoId}</option>}
            {documentosQuery.data?.items.map((d) => (
              <option key={d.id} value={d.id}>
                {d.archivo} · {d.id.slice(0, 8)}
              </option>
            ))}
          </select>
        </div>
        <div className="w-40">
          <label className="etiqueta-campo">O pega su ID</label>
          <input
            className="campo-entrada font-mono text-xs"
            placeholder="ID del documento"
            onKeyDown={(e) => {
              if (e.key === 'Enter') setParams({ documento: (e.target as HTMLInputElement).value.trim() })
            }}
          />
        </div>
      </div>

      {pestana === 'validar' ? (
        <PanelValidacion
          plantillaId={plantillaId}
          campos={estado.campos}
          diseno={disenoActual}
          documentos={documentosQuery.data?.items ?? []}
          documentoInicial={documentoId}
          densidad={dens}
        />
      ) : (
        <div className="grid gap-4 lg:grid-cols-[1fr_330px]">
          <div className="space-y-3">
            {/* avisos del documento */}
            {sinPosiciones && (
              <div className="flex flex-wrap items-center gap-3 rounded-md border border-sky-200 bg-sky-50 px-3 py-2 text-sm text-sky-800">
                <div className="flex-1">
                  <b>Este documento no tiene posiciones guardadas.</b> Se procesó antes de esta función: puedes marcar celdas igual,
                  pero no se proponen palabras.
                </div>
                <button type="button" className="boton-secundario" disabled={reprocesar.isPending} onClick={() => reprocesar.mutate()}>
                  {reprocesar.isPending ? 'Reprocesando…' : 'Reprocesar para ver posiciones'}
                </button>
              </div>
            )}
            {bloqueado && !ajustandoEsquinas && (
              <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
                <b>No pudimos detectar los bordes del documento con fiabilidad.</b> La cuadrícula podría no alinearse. Ajusta las
                cuatro esquinas o vuelve a subir la foto sobre un fondo oscuro.
                <div className="mt-2 flex flex-wrap gap-2">
                  <button type="button" className="boton-primario" onClick={() => setAjustandoEsquinas(true)}>
                    Ajustar esquinas
                  </button>
                  <button
                    type="button"
                    className="boton-secundario"
                    disabled={recortar.isPending}
                    onClick={() => recortar.mutate({ orientacion: (((recorte?.orientacion ?? 0) + 90) % 360) as Orientacion })}
                  >
                    {recortar.isPending ? 'Girando…' : `Girar 90°${recorte?.orientacion ? ` · ahora ${recorte.orientacion}°` : ''}`}
                  </button>
                  <button type="button" className="boton-secundario" onClick={() => setUsarDeTodosModos(true)}>
                    Usar de todos modos
                  </button>
                </div>
                {recortar.isError && !ajustandoEsquinas && <p className="mt-2 text-red-700">{(recortar.error as Error).message}</p>}
              </div>
            )}

            {ajustandoEsquinas ? (
              <AjusteEsquinas
                src={urlOriginal}
                inicial={recorte?.esquinas ?? null}
                enCurso={recortar.isPending}
                error={recortar.isError ? (recortar.error as Error).message : null}
                onConfirmar={(esquinas) => recortar.mutate({ esquinas, orientacion: recorte?.orientacion ?? 0 })}
                onCancelar={() => {
                  recortar.reset()
                  setAjustandoEsquinas(false)
                }}
              />
            ) : (
              <>
                <div className="tarjeta flex flex-wrap items-center gap-3 px-3 py-2 text-sm">
                  <label className="flex items-center gap-2">
                    <input type="checkbox" checked={mostrarRejilla} onChange={(e) => setMostrarRejilla(e.target.checked)} />
                    Cuadrícula
                  </label>
                  <select
                    className="rounded-md border border-slate-300 bg-white px-2 py-1 text-sm"
                    value={dens.id}
                    onChange={(e) => setDiseno((d) => ({ ...d, densidad_rejilla: e.target.value }))}
                    aria-label="Densidad de la rejilla"
                  >
                    {DENSIDADES.map((d) => (
                      <option key={d.id} value={d.id}>
                        {d.etiqueta}
                      </option>
                    ))}
                  </select>
                  <div className="flex rounded-md bg-slate-100 p-0.5">
                    {(['dibujar', 'borrar'] as const).map((h) => (
                      <button
                        key={h}
                        type="button"
                        onClick={() => setHerramienta(h)}
                        className={`rounded px-2.5 py-1 text-xs font-medium ${herramienta === h ? 'bg-white text-indigo-700 shadow-sm' : 'text-slate-500'}`}
                      >
                        {h === 'dibujar' ? '✎ Dibujar' : '⌫ Borrar'}
                      </button>
                    ))}
                  </div>
                  <button type="button" className="text-xs text-slate-600 hover:text-slate-900 disabled:opacity-40" disabled={!historial.length} onClick={deshacer}>
                    ↶ Deshacer
                  </button>
                  {origen === 'manual' && (
                    <button type="button" className="text-xs text-slate-600 underline" disabled={quitarRecorte.isPending} onClick={() => quitarRecorte.mutate()}>
                      {quitarRecorte.isPending ? 'Quitando…' : 'Quitar recorte manual'}
                    </button>
                  )}
                  {origen && !bloqueado && (
                    <button type="button" className="text-xs text-slate-600 underline" onClick={() => setAjustandoEsquinas(true)}>
                      Ajustar esquinas
                    </button>
                  )}
                  <span className="ml-auto text-xs text-slate-400">
                    {dens.columnas} × {dens.filas} celdas
                  </span>
                </div>

                {objetivo && (
                  <div className="flex flex-wrap items-center gap-2 rounded-md bg-orange-50 px-3 py-2 text-sm text-slate-700">
                    <span className="h-2 w-2 rounded-full bg-orange-500" />
                    Marcando <b>{nombreObjetivo}</b>
                    {objetivo.tipo === 'campo' && (
                      <>
                        como
                        {(['valor', 'etiqueta'] as const).map((t) => (
                          <button
                            key={t}
                            type="button"
                            onClick={() => setTipoZona(t)}
                            className={`rounded px-2 py-0.5 text-xs font-medium ${tipoZona === t ? 'bg-white text-indigo-700 shadow-sm' : 'text-slate-500'}`}
                          >
                            {t === 'valor' ? 'Valor' : 'Etiqueta fija'}
                          </button>
                        ))}
                      </>
                    )}
                    <span className="text-xs text-slate-500">
                      {objetivo.tipo === 'campo' && tipoZona === 'valor'
                        ? '— arrastra sobre las celdas, o haz clic en una palabra'
                        : '— haz clic sobre la palabra impresa; arrastrar puede incluir el dato de abajo'}
                    </span>
                  </div>
                )}

                {imagenQuery.isLoading && documentoId ? (
                  <div className="tarjeta flex h-72 animate-pulse items-center justify-center text-sm text-slate-400">Cargando imagen…</div>
                ) : imagenQuery.isError ? (
                  <MensajeError mensaje={(imagenQuery.error as Error).message} onReintentar={() => imagenQuery.refetch()} />
                ) : (
                  <LienzoCuadricula
                    src={urlImagen}
                    densidad={dens}
                    mostrarRejilla={mostrarRejilla}
                    zonas={zonasDibujo}
                    palabras={palabras}
                    herramienta={herramienta}
                    bloqueado={bloqueado}
                    onZona={alDibujar}
                    onBorrar={borrarZona}
                  />
                )}
                <p className="flex flex-wrap gap-4 text-xs text-slate-500">
                  <span>▮ Valor: dato a extraer</span>
                  <span>▨ Etiqueta fija: texto impreso que valida el diseño</span>
                  <span className="text-slate-400">▮ Texto gris: lectura poco confiable (&lt; {Math.round(CONFIANZA_BAJA * 100)} %)</span>
                </p>
              </>
            )}
          </div>

          {/* panel de campos y zonas */}
          <div className="space-y-3">
            <div className="tarjeta divide-y divide-slate-100">
              <div className="flex items-center justify-between px-3 py-2">
                <h3 className="text-sm font-semibold text-slate-700">Campos y zonas</h3>
                <span className="rounded-full bg-indigo-50 px-2 py-0.5 text-xs text-indigo-700">{zonasDibujo.length} zonas</span>
              </div>
              {estado.campos.map((c, i) => {
                const activo = objetivo?.tipo === 'campo' && objetivo.nombre === c.nombre
                const zv = tieneZonaValor(c.regla) ? zonaDe(c.regla) : null
                const ze = c.regla.zona_etiqueta
                return (
                  <div
                    key={c.nombre}
                    className={`px-3 py-2 text-sm ${activo ? 'bg-orange-50' : ''}`}
                    onMouseEnter={() => setResaltado(c.nombre)}
                    onMouseLeave={() => setResaltado(null)}
                  >
                    <button type="button" className="flex w-full items-center gap-2 text-left" onClick={() => setObjetivo({ tipo: 'campo', nombre: c.nombre })}>
                      <span className="h-2.5 w-2.5 rounded-sm" style={{ background: colorCampo(i) }} />
                      <span className="font-medium text-slate-800">{c.etiqueta}</span>
                      {!zv && !ze && <span className="ml-auto text-xs text-slate-400">Sin zona</span>}
                    </button>
                    <div className="mt-1 flex flex-wrap gap-1.5">
                      {zv ? (
                        <ChipZona tipo="valor" texto={rangoCeldas(zv, dens)} onQuitar={() => borrarZona(`v:${c.nombre}`)} />
                      ) : (
                        <BotonAgregar texto="+ Valor" onClick={() => (setObjetivo({ tipo: 'campo', nombre: c.nombre }), setTipoZona('valor'))} />
                      )}
                      {ze ? (
                        <ChipZona tipo="etiqueta" texto={rangoCeldas(ze, dens)} onQuitar={() => borrarZona(`e:${c.nombre}`)} />
                      ) : (
                        <BotonAgregar texto="+ Etiqueta fija" onClick={() => (setObjetivo({ tipo: 'campo', nombre: c.nombre }), setTipoZona('etiqueta'))} />
                      )}
                    </div>
                    {zv && palabras.length > 0 && <p className="mt-1 text-xs text-slate-500">Lee: {textoEnZona(palabras, zv) || <i>(vacía)</i>}</p>}
                    {ze && <TextoEsperado valor={ze.texto_esperado} onCambiar={(t) => cambiarTextoEsperado(c.nombre, t)} />}
                  </div>
                )
              })}
              <div className="px-3 py-2 text-sm">
                <div className="flex items-center justify-between">
                  <span className="font-medium text-slate-800">Elementos fijos</span>
                  <span className="text-xs text-slate-400">solo validación</span>
                </div>
                <p className="text-xs text-slate-500">Textos impresos sin campo (encabezado, título…).</p>
                {estado.fijos.map((f, i) => (
                  <div key={i} className="mt-1.5" onMouseEnter={() => setResaltado(`f:${i}`)} onMouseLeave={() => setResaltado(null)}>
                    <ChipZona tipo="etiqueta" texto={rangoCeldas(f, dens)} onQuitar={() => borrarZona(`f:${i}`)} />
                    <TextoEsperado valor={f.texto_esperado} onCambiar={(t) => cambiarTextoEsperado(`f:${i}`, t)} />
                  </div>
                ))}
                <div className="mt-1.5">
                  <BotonAgregar texto="+ Elemento fijo" onClick={() => setObjetivo({ tipo: 'fijo' })} />
                </div>
              </div>
            </div>

            <div className="tarjeta space-y-3 p-3 text-sm">
              <h3 className="font-semibold text-slate-700">Diseño</h3>
              <div>
                <label className="etiqueta-campo">Formato (proporción esperada)</label>
                <select
                  className="campo-entrada"
                  value={diseno.formato}
                  onChange={(e) => {
                    const f = FORMATOS.find((x) => x.id === e.target.value)!
                    setDiseno((d) => ({ ...d, formato: f.id, relacion: f.relacion ?? recorte?.relacion ?? null }))
                  }}
                >
                  {FORMATOS.map((f) => (
                    <option key={f.id} value={f.id}>
                      {f.etiqueta}
                    </option>
                  ))}
                </select>
                <p className="mt-1 text-xs text-slate-400">
                  Relación {(diseno.formato === 'libre' ? recorte?.relacion ?? diseno.relacion : diseno.relacion)?.toFixed(3) ?? '—'}: se usa para
                  saber si el recorte de cada documento es fiable.
                </p>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="etiqueta-campo">Umbral de coincidencia</label>
                  <input
                    type="number"
                    min={0}
                    max={100}
                    step={5}
                    className="campo-entrada"
                    value={Math.round(diseno.umbral_coincidencia * 100)}
                    onChange={(e) => setDiseno((d) => ({ ...d, umbral_coincidencia: Math.min(1, Math.max(0, Number(e.target.value) / 100)) }))}
                  />
                </div>
                <div>
                  <label className="etiqueta-campo">Tolerancia (%)</label>
                  <input
                    type="number"
                    min={0}
                    max={20}
                    step={1}
                    className="campo-entrada"
                    value={Math.round(diseno.tolerancia * 100)}
                    onChange={(e) => setDiseno((d) => ({ ...d, tolerancia: Math.min(0.2, Math.max(0, Number(e.target.value) / 100)) }))}
                  />
                </div>
              </div>
              <p className="text-xs text-slate-400">Guardar crea una nueva versión de la plantilla (como al editarla).</p>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function zonaDe(r: Regla): ZonaRelativa {
  return { x: r.x ?? 0, y: r.y ?? 0, ancho: r.ancho ?? 0, alto: r.alto ?? 0, pagina: r.pagina ?? 1 }
}

function ChipZona({ tipo, texto, onQuitar }: { tipo: 'valor' | 'etiqueta'; texto: string; onQuitar: () => void }) {
  return (
    <span className={`inline-flex items-center gap-1 rounded border px-1.5 py-0.5 font-mono text-[11px] ${tipo === 'valor' ? 'border-indigo-200 bg-indigo-50 text-indigo-700' : 'border-dashed border-fuchsia-300 bg-fuchsia-50 text-fuchsia-700'}`}>
      <span className="font-sans text-[10px] font-semibold uppercase">{tipo}</span>
      {texto}
      <button type="button" aria-label="Quitar zona" title="Quitar esta zona" onClick={onQuitar} className="ml-0.5 text-slate-400 hover:text-red-600">
        ×
      </button>
    </span>
  )
}

function BotonAgregar({ texto, onClick }: { texto: string; onClick: () => void }) {
  return (
    <button type="button" onClick={onClick} className="rounded border border-slate-200 px-1.5 py-0.5 text-[11px] text-slate-600 hover:border-indigo-300 hover:text-indigo-700">
      {texto}
    </button>
  )
}

function TextoEsperado({ valor, onCambiar }: { valor: string; onCambiar: (v: string) => void }) {
  const [texto, setTexto] = useState(valor)
  useEffect(() => setTexto(valor), [valor])
  return (
    <label className="mt-1 flex items-center gap-1 text-xs text-slate-500">
      Debe decir:
      <input
        className="flex-1 rounded border border-slate-200 px-1.5 py-0.5 text-xs text-slate-800"
        value={texto}
        maxLength={200}
        onChange={(e) => setTexto(e.target.value)}
        onBlur={() => texto.trim() && texto !== valor && onCambiar(texto.trim())}
      />
    </label>
  )
}

/** objectURL de un Blob que se libera al cambiar o desmontar. */
function useObjectUrl(blob: Blob | undefined): string | null {
  const [url, setUrl] = useState<string | null>(null)
  useEffect(() => {
    if (!blob) {
      setUrl(null)
      return
    }
    const u = URL.createObjectURL(blob)
    setUrl(u)
    return () => URL.revokeObjectURL(u)
  }, [blob])
  return url
}
