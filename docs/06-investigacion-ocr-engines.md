# 06 — Investigación: motores OCR open source (comparativa de fiabilidad)

> Objetivo: validar con evidencia de mercado si Tesseract (motor por defecto actual, ver [`02-backend.md`](02-backend.md)) y PaddleOCR (alternativa actual) son la elección correcta para este proyecto, priorizando **precisión de reconocimiento** sobre velocidad o facilidad de uso.

La evidencia cuantitativa pública en este espacio es escasa. La fuente más citada en esta investigación es un benchmark de un solo proveedor comercial ([imagetotable.ai](https://imagetotable.ai/references/receipt-ocr-benchmark-results), que vende servicios de parsing de documentos) corriendo varios motores sobre SROIE 2019 (recibos en inglés). Se trata como un dato, no como verdad asentada, y se señala explícitamente dónde aplica.

## 1. Tesseract 5 (LSTM)
- **Arquitectura:** motor clásico, red LSTM por línea de texto (sin paso de detección de layout deep-learning separado; depende de segmentación heurística de Leptonica).
- **Evidencia de precisión:** CER ≈ 33.6% en el benchmark de recibos citado — el peor de los 5 motores comparados (docTR 19.7%, PaddleOCR 20.5%, EasyOCR 28.3%, Tesseract 33.6%). Consistente con la percepción general: Tesseract es sensible a ruido, inclinación e iluminación irregular, justo los casos "difíciles" que preocupan a este proyecto. Mantenimiento activo (Google/comunidad), pero la arquitectura LSTM no ha cambiado sustancialmente desde 2018.
- **Español:** soporte maduro vía `tesseract-ocr-spa` (traineddata dedicado), buena cobertura de acentos y ñ.
- **Licencia:** Apache 2.0.
- **Integración:** la más simple — `pytesseract` + binario apt, cero dependencias de deep learning. Ya está en el Dockerfile actual.
- **CPU:** el más rápido y liviano de todos (~670 ms/página en el benchmark), sin frameworks pesados.

## 2. PaddleOCR (PP-OCRv4/v5)
- **Arquitectura:** pipeline de detección + reconocimiento deep learning (DBNet/PP-OCR detector + CRNN/SVTR reconocedor).
- **Evidencia de precisión:** CER ≈ 20.5% en el mismo benchmark, muy por delante de Tesseract. PP-OCRv5 (2025) reporta mejora de +30% en precisión multilingüe sobre PP-OCRv3 ([paddleocr.ai](https://www.paddleocr.ai/latest/en/version3.x/algorithm/PP-OCRv5/PP-OCRv5_multi_languages.html)), activamente mantenido por Baidu/PaddlePaddle con lanzamientos frecuentes.
- **Español:** soporte vía el modelo `latin_PP-OCRv5_mobile_rec`, que cubre español junto a ~15 idiomas latinos más (no es un modelo dedicado solo a español). La cifra de 84.7% reportada es agregada para todo el grupo latino, no específica de español — no hay cifra aislada confiable.
- **Licencia:** Apache 2.0.
- **Integración:** requiere instalar primero el framework `paddlepaddle` (wheel CPU separado) y luego `paddleocr`; más pesado que Tesseract pero bien documentado para Docker CPU-only. Riesgo conocido: errores de import si se instala en el orden equivocado; builds que intentan acceder a CUDA pueden fallar en Docker si no se fija explícitamente la variante CPU.
- **CPU:** razonable (~297 ms/página en el benchmark, aunque esa corrida específica usó GPU — tratar con cautela).

## 3. docTR (Mindee)
- **Arquitectura:** pipeline de detección + reconocimiento deep learning (DBNet/LinkNet + CRNN/ViTSTR/master), con backends PyTorch o TensorFlow.
- **Evidencia de precisión:** el mejor resultado del benchmark de recibos (CER 19.7%, el más bajo de los 5). Un paper independiente (arXiv:2605.29476, traducción de texto en imágenes) confirma la tendencia: docTR superó a EasyOCR en todos los idiomas probados, con CER en inglés de 3.1 vs 15.6 de EasyOCR. Es la señal más sólida de las encontradas, aunque sigue siendo evidencia limitada (dos fuentes, ninguna un benchmark académico tipo ICDAR dedicado).
- **Español:** no se encontraron modelos específicos de español documentados; usa vocabularios latinos genéricos que deberían cubrir acentos/ñ, pero sin confirmación explícita — requiere validación con muestra real.
- **Licencia:** Apache 2.0, mantenido activamente por Mindee desde 2021.
- **Integración:** API Python limpia, pensada para integrarse en backends (a diferencia de PaddleOCR, más orientado a línea de comandos en su diseño original). Existe `OnnxTR`, backend ONNX sin necesidad de PyTorch/TensorFlow, optimizado para CPU — reduce el peso de la imagen Docker.
- **CPU:** el proyecto afirma estar optimizado para CPU; comparativas de terceros la describen como competitiva frente a PaddleOCR en CPU.

## 4. EasyOCR
- **Arquitectura:** detección CRAFT + reconocimiento CRNN, ambos PyTorch.
- **Evidencia de precisión:** CER 28.3% en el benchmark — claramente peor que PaddleOCR y docTR, mejor que Tesseract.
- **Español:** soporte explícito y bien documentado (uno de los puntos fuertes de EasyOCR, con +80 idiomas listados).
- **Licencia:** Apache 2.0.
- **Integración:** la más sencilla de los motores deep learning (`pip install easyocr`, API de dos líneas), pero carga PyTorch completo.
- **CPU:** funcional pero más lento que Tesseract/PaddleOCR por imagen, debido al overhead de PyTorch sin batching optimizado para CPU.

## 5. Surya
- **Arquitectura:** transformer para detección + reconocimiento + layout, proyecto relativamente nuevo (2024-2025).
- **Evidencia de precisión:** en el mismo benchmark, "Surya2" obtiene el menor CER de todos los motores probados — pero es una sola fuente comercial. Otro blog (sin metodología clara) lo ubica por encima de PaddleOCR en F1 general.
- **⚠️ Licencia:** fuentes contradictorias — una dice que el código es Apache 2.0 pero los **pesos del modelo** usan una licencia OpenRAIL-M modificada con restricciones de uso comercial; otra fuente dice GPL-3.0. Bandera roja para un proyecto comercial — requiere verificación directa en el repo antes de considerarlo en producción.
- **CPU:** el más lento con diferencia (~2.7 s/página vs 300-700 ms de los demás) — problema serio de rendimiento en un entorno sin GPU garantizada si el volumen de documentos es alto.
- **Conclusión:** prometedor en precisión pero descartado para este proyecto por la combinación de licencia ambigua + lentitud en CPU.

## 6. TrOCR (Microsoft)
- **Arquitectura:** transformer encoder-decoder (ViT + decodificador de texto). Importante: **no incluye paso de detección de layout** — espera recortes de línea/palabra ya segmentados, por lo que requiere combinarse con otro detector (p. ej. docTR solo para detección).
- **Español:** los checkpoints oficiales de Microsoft son solo inglés. Existe un modelo de español de terceros (Qantev, arXiv:2407.06950, 2024) pero no es oficial ni tiene garantía de mantenimiento a largo plazo — riesgo de integración.
- **Licencia:** MIT (la de Microsoft). La licencia del modelo de español de terceros no está clara.
- **CPU:** la decodificación autoregresiva transformer por línea es costosa en CPU sin GPU; no es viable para documentos completos de alto volumen sin aceleración.
- **Conclusión:** descartado como motor principal — exige arquitectura adicional (detector separado) y no tiene soporte de español oficial ni maduro.

## 7. Kraken
- **Arquitectura:** segmentación + reconocimiento, optimizado para manuscritos históricos y escrituras no latinas.
- **Licencia:** Apache 2.0.
- **Conclusión:** descartado — el caso de uso (planillas de servicios, cédulas) no es el nicho de Kraken (textos históricos/paleografía); no hay evidencia de que rinda bien en documentos administrativos modernos.

## 8. MMOCR
- **Arquitectura:** toolbox de OpenMMLab con múltiples modelos de detección/reconocimiento/comprensión.
- **Licencia:** Apache 2.0.
- **⚠️ Mantenimiento:** no se encontró confirmación de actividad en 2025; su stack de dependencias (`mmcv`, `mmdet`, `mmengine`) es históricamente frágil entre versiones y pesado para Docker.
- **Conclusión:** descartado para este proyecto — el riesgo de mantenimiento y la complejidad de dependencias no se justifican frente a alternativas más simples con mejor evidencia de precisión.

---

## Ranking final (por fiabilidad de precisión, con los filtros de licencia/Docker/CPU/español aplicados)

| # | Motor | Por qué |
|---|---|---|
| **1** | **PaddleOCR (PP-OCRv5)** | Segundo mejor CER en la evidencia disponible (~20.5%), muy por delante de Tesseract, activamente mantenido, Apache 2.0, soporte de español (modelo latino), instalación CPU-only documentada y usada en producción por muchos proyectos. Mejor balance precisión/madurez/mantenimiento. |
| **2** | **docTR (Mindee)** | Mejor CER de la evidencia encontrada (~19.7%, confirmado por un paper independiente frente a EasyOCR), Apache 2.0, API más limpia para integrar en FastAPI, backend ONNX (`OnnxTR`) ideal para CPU-only. El punto débil es que no hay confirmación explícita de soporte dedicado a español — a validar con una muestra real antes de confiar en él para producción. |
| **3** | **EasyOCR** | Tercer mejor CER (~28.3%), claramente por detrás de los dos anteriores pero con soporte de español más documentado que docTR y licencia Apache 2.0. Sirve como alternativa fácil de integrar o motor de respaldo con buen soporte multilingüe explícito. |

**Tesseract queda fuera del top 3** por tener el CER más alto de los motores DL-based comparados (33.6%), pese a ser el más liviano y fácil de desplegar.

## Recomendación concreta para el proyecto

El diseño actual (`docs/02-backend.md`) usa **Tesseract como motor por defecto** y PaddleOCR solo como alternativa para fotos de celular. La evidencia encontrada apunta en la dirección contraria a esa jerarquía:

1. **Motor principal: PaddleOCR (PP-OCRv5)** — tanto para documentos escaneados limpios como para fotos de celular con mala iluminación. La evidencia de benchmark (que viene justamente de un dataset de recibos fotografiados, el escenario "difícil") muestra que PaddleOCR ya es sustancialmente más preciso que Tesseract incluso en ese caso, así que no hay razón basada en evidencia para reservar Tesseract como motor por defecto en el caso "fácil".
2. **Motor alternativo / segunda opinión: docTR** — para casos donde PaddleOCR dé baja confianza, o como validación cruzada (si ambos motores coinciden en un campo, sube la confianza del resultado; si difieren, se marca para revisión manual). Dado que su CER reportado es el más bajo de todos, vale la pena pilotarlo con documentos reales en español antes de decidir si reemplaza a PaddleOCR como principal.
3. **Tesseract como fallback ligero**, no como motor principal — mantenerlo disponible por su bajo costo computacional y cero dependencias pesadas, útil si PaddleOCR/docTR fallan o para entornos con restricciones de recursos muy estrictas, pero no como la primera pasada para precisión.
4. **Descartar** Surya (licencia de pesos ambigua + lentitud en CPU), TrOCR (sin detección integrada, sin español oficial), Kraken (nicho equivocado) y MMOCR (riesgo de mantenimiento/dependencias) para este proyecto.

**Limitación importante:** casi toda la evidencia cuantitativa viene de un solo proveedor comercial evaluando un dataset de recibos en inglés (SROIE), no de documentos administrativos en español como cédulas o planillas de servicios chilenas/latinoamericanas. Antes de cambiar el motor por defecto en producción, se recomienda correr el script `scripts/evaluar.py` ya previsto en el diseño (sección 9 de `02-backend.md`) sobre una muestra etiquetada de documentos reales del proyecto, comparando Tesseract vs PaddleOCR vs docTR en CER/exactitud por campo — esa prueba interna pesará más que cualquier benchmark externo.

## Impacto en el diseño (cambios ya aplicados)

Esta investigación **reemplazó** la jerarquía de motores asumida en la v1 de `docs/02-backend.md` (Tesseract por defecto, PaddleOCR como alternativa) por:

- **`OCR_MOTOR` por defecto: `paddle`** (antes `tesseract`).
- Se agregó **docTR** (vía `OnnxTR`) como motor de segunda opinión, activable para validación cruzada en campos de baja confianza (`OCR_SEGUNDA_OPINION`, `OCR_UMBRAL_SEGUNDA_OPINION`).
- Tesseract se mantiene en el código y el Dockerfile como **fallback**, no como ruta principal.
- El backend ya implementa y verificó esta jerarquía (PaddleOCR funcionando end-to-end con una planilla sintética, docTR importado y disponible aunque aún no consumido automáticamente por campo — pendiente para una iteración siguiente).
- Pendiente antes de producción: correr `scripts/evaluar.py` sobre una muestra real en español y confirmar o ajustar esta decisión con esa evidencia interna.

Ver los cambios reflejados en `docs/01-diseno-general.md` §8 (tabla de decisiones) y `docs/02-backend.md` §4.3 y §7.
