import type { Campo, CampoExtraido, PlantillaEntrada, Resultado } from '@/tipos'

/**
 * Evalúa las reglas de una plantilla todavía no guardada contra el texto OCR
 * de un documento de ejemplo, para la vista previa "Resultado con esta
 * plantilla" del asistente. Es una aproximación simple en el navegador;
 * el backend real hace la extracción definitiva (anclas tolerantes a OCR,
 * recorte de zonas, normalización por tipo de dato, etc.).
 */
export function probarEnMemoria(entrada: Pick<PlantillaEntrada, 'codigo' | 'campos'>, base: Resultado): Resultado {
  const texto = base.texto_completo
  const campos: Record<string, CampoExtraido> = {}

  for (const campo of entrada.campos) {
    campos[campo.nombre] = evaluarCampo(campo, texto)
  }

  return {
    ...base,
    clasificacion: {
      ...base.clasificacion,
      tipo: entrada.codigo || base.clasificacion.tipo,
      confianza: 0.85,
    },
    campos,
  }
}

function evaluarCampo(campo: Campo, texto: string): CampoExtraido {
  try {
    if (campo.regla.metodo === 'regex') {
      const re = new RegExp(campo.regla.regex, 'i')
      const m = texto.match(re)
      const valor = m ? (m[1] ?? m[0]) : null
      return { valor, confianza: valor ? 0.8 : 0, pagina: 1 }
    }
    if (campo.regla.metodo === 'ancla') {
      const idx = texto.toLowerCase().indexOf(campo.regla.ancla.toLowerCase())
      if (idx === -1) return { valor: null, confianza: 0, pagina: 1 }
      const resto = texto.slice(idx + campo.regla.ancla.length)
      const linea = resto.split('\n')[0]?.trim() ?? ''
      if (campo.regla.regex) {
        const re = new RegExp(campo.regla.regex, 'i')
        const m = linea.match(re)
        const valor = m ? (m[1] ?? m[0]) : null
        return { valor, confianza: valor ? 0.78 : 0, pagina: 1 }
      }
      return { valor: linea || null, confianza: linea ? 0.7 : 0, pagina: 1 }
    }
    // zona: no se puede recortar la imagen en el navegador sin backend; se marca como pendiente.
    return { valor: '(valor desde la zona dibujada)', confianza: 0.5, pagina: campo.regla.pagina }
  } catch {
    return { valor: null, confianza: 0, pagina: 1 }
  }
}
