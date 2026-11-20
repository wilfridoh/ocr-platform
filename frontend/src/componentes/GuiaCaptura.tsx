/**
 * Consejos para fotografiar el documento. La lectura automática depende sobre todo de la foto: de frente, completa,
 * con luz y nítida. Se muestra antes de los botones de cámara/archivo en las pantallas de captura.
 */
export default function GuiaCaptura() {
  return (
    <section className="rounded-card border border-line bg-white px-4 py-3" aria-labelledby="guia-captura-titulo">
      <h2 id="guia-captura-titulo" className="mb-2 text-[13px] font-semibold text-ink">
        Para que la foto se lea bien
      </h2>
      <div className="flex flex-col items-start gap-2.5 sm:flex-row sm:gap-4">
        <div className="flex flex-none gap-2" aria-hidden>
          <figure className="text-center">
            <svg viewBox="0 0 56 44" width="56" height="44" className="rounded-md bg-slate-100">
              <rect x="6" y="7" width="44" height="30" rx="3" fill="#fff" stroke="#10B981" strokeWidth="2" />
              <path d="M12 16h18M12 22h26M12 28h14" stroke="#94A3B8" strokeWidth="2" strokeLinecap="round" />
            </svg>
            <figcaption className="mt-0.5 text-[10.5px] font-semibold text-ok">Así sí</figcaption>
          </figure>
          <figure className="text-center">
            <svg viewBox="0 0 56 44" width="56" height="44" className="rounded-md bg-slate-100">
              <path d="M16 12l30 5-5 20-31-9z" fill="#fff" stroke="#F87171" strokeWidth="2" strokeLinejoin="round" />
              <path d="M20 18l14 3M18 24l18 4" stroke="#94A3B8" strokeWidth="2" strokeLinecap="round" />
            </svg>
            <figcaption className="mt-0.5 text-[10.5px] font-semibold text-[#DC2626]">Así no</figcaption>
          </figure>
        </div>
        <ul className="min-w-0 list-disc space-y-0.5 pl-4 text-[12.5px] leading-snug text-ink-2">
          <li>Apoya el documento en una superficie plana y de color distinto.</li>
          <li>Toma la foto de frente, sin inclinar el celular.</li>
          <li>Que se vea completo y ocupe casi toda la pantalla.</li>
          <li>Buena luz, sin reflejos ni sombras, y que el texto se vea nítido.</li>
        </ul>
      </div>
    </section>
  )
}
