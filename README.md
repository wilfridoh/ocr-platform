# OCR Platform — Lectura inteligente de documentos

> Plataforma que recibe un documento (imagen o PDF), lo lee con OCR, identifica **qué tipo de documento es**, extrae sus datos según una **plantilla** y devuelve un **JSON** estructurado. Se administra desde una interfaz web y se puede consumir desde agentes de IA mediante un **servidor MCP**.

## ¿Qué problema resuelve?

Las empresas reciben documentos en papel o escaneados (cuentas de contrato, planillas de servicios, cédulas, facturas). Alguien tiene que leerlos y transcribir los datos a un sistema. Esta plataforma automatiza ese trabajo:

1. Se sube el documento.
2. El sistema lo lee (OCR), lo clasifica y extrae los campos definidos para ese tipo.
3. Devuelve un JSON listo para integrar en cualquier otro sistema.

Si llega un documento nuevo que no conoce, se crea una **plantilla** desde la interfaz y, a partir de ahí, el sistema sabe cómo leerlo.

## Vista rápida

```
 Usuario / Agente IA
        │
        ├─── Interfaz web (React) ──────┐
        └─── Servidor MCP ──────────────┤
                                        ▼
                               API Backend (FastAPI)
                        ┌───────────────┼────────────────┐
                        ▼               ▼                ▼
                  Motor OCR      Clasificador       Extractor
                 (Tesseract /    (plantillas +     (campos del
                  PaddleOCR)      palabras clave)    JSON final)
                                        │
                                        ▼
                                   SQL Server
```

Todo corre en contenedores Docker (`docker compose up`), primero local y luego en la nube sin cambios.

## Documentación

| Documento | Para quién | Qué contiene |
|---|---|---|
| [docs/01-diseno-general.md](docs/01-diseno-general.md) | Cualquier persona | Objetivo, alcance, arquitectura, flujo completo, decisiones y glosario |
| [docs/02-backend.md](docs/02-backend.md) | Desarrolladores | API REST, pipeline OCR, plantillas, servidor MCP, estructura de código |
| [docs/03-frontend.md](docs/03-frontend.md) | Desarrolladores / UX | Pantallas, flujos de usuario, componentes, stack |
| [docs/04-base-de-datos.md](docs/04-base-de-datos.md) | Desarrolladores / DBA | Modelo de datos SQL Server, tablas, relaciones, índices, scripts |
| [docs/06-investigacion-ocr-engines.md](docs/06-investigacion-ocr-engines.md) | Cualquier persona | Comparativa de motores OCR open source y por qué el motor principal es PaddleOCR (no Tesseract) |
| [docs/07-flujos-captura-y-permisos.md](docs/07-flujos-captura-y-permisos.md) | Cualquier persona | Flujos de captura dirigidos (ej. "solo pedir cédula") y permisos por rol sobre plantillas — siguiente iteración |
| [docs/08-checklist-levantamiento-y-poc.md](docs/08-checklist-levantamiento-y-poc.md) | Cualquier persona | Checklist mínimo para levantar cada parte y qué falta para una prueba de concepto demostrable |
| [qa/informe-qa-backend-ocr.md](qa/informe-qa-backend-ocr.md) | Cualquier persona | Informe de QA del backend: cobertura de tests, bugs reales encontrados (motor OCR, fechas, montos) |
| [qa/informe-qa-poc-e2e.md](qa/informe-qa-poc-e2e.md) | Cualquier persona | PoC end-to-end validada sobre el stack real: UI, MCP, SQL Server, documentos reales de tipo desconocido |
| [docs/09-guia-visual-frontend.md](docs/09-guia-visual-frontend.md) | Frontend / UX | Paleta, tipografía y patrones de componentes de la maqueta, para que el frontend real los adopte |

## Estado del proyecto

| Fase | Estado |
|---|---|
| Diseño y documentación | En curso |
| Backend: API + OCR + clasificación | Pendiente |
| Servidor MCP | Pendiente |
| Frontend: carga y administrador de plantillas | Pendiente |
| Base de datos SQL Server + Docker Compose | Pendiente |
| Reconocimiento facial (fase 2) | Planificado para la siguiente semana |

## Glosario mínimo

- **OCR**: Reconocimiento óptico de caracteres. Convierte imagen en texto.
- **Plantilla**: Definición de un tipo de documento: cómo reconocerlo y qué campos extraer.
- **Clasificación**: Decidir a qué plantilla pertenece un documento.
- **Extracción**: Sacar los valores de los campos (número de contrato, dirección, monto, fecha...).
- **MCP** (Model Context Protocol): Estándar para que agentes de IA (Claude, etc.) usen herramientas externas. Aquí expone la plataforma como herramientas.
