#!/usr/bin/env python
"""Evalúa los motores OCR (PaddleOCR / docTR / Tesseract) sobre documentos reales etiquetados.

Calcula, por motor: CER (tasa de error de caracteres, si hay texto de referencia), exactitud
por campo (si hay plantilla + valores esperados) y acierto de clasificación (tipo detectado vs
`tipo` esperado, si hay plantillas), además del tiempo medio por documento.
Es la validación de docs/02 §9 y docs/08 §6.2.

Uso (desde la raíz del repo, con el venv del backend):

    backend\\.venv\\Scripts\\python.exe scripts\\evaluar.py CARPETA --esperado esperado.json \\
        --plantilla plantilla1.json [plantilla2.json ...] --motores paddle,doctr,tesseract --salida resultados.json

Formato de `esperado.json` (clave = nombre de archivo dentro de CARPETA):

    {
      "planilla_01.png": {
        "tipo":   "codigo de la plantilla esperada (opcional, habilita acierto de clasificación)",
        "texto":  "texto completo de referencia (opcional, habilita CER)",
        "campos": {"numero_cliente": "1234567-8", "total_pagar": 45320, "fecha_vencimiento": "2026-11-30"}
      }
    }

Cada `--plantilla` es una definición de plantilla (mismo JSON que POST /api/plantillas, con
`codigo`, `palabras_clave` y `campos`). Se clasifica entre todas las dadas; los campos se extraen
con la plantilla del `tipo` esperado (o la única, si solo hay una). Sin plantillas solo se mide CER. Los PDF con texto nativo se
evalúan una vez con el pseudo-motor "pdf-nativo" (no pasan por OCR).
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
import unicodedata
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

from rapidfuzz.distance import Levenshtein  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.dominio.modelos import PaginaOCR, PlantillaCrear  # noqa: E402
from app.pipeline.clasificador import PlantillaCandidata, clasificar  # noqa: E402
from app.pipeline.extractor import extraer_campos  # noqa: E402
from app.pipeline.ingesta import ErrorIngesta, ingerir  # noqa: E402
from app.pipeline.ocr import MotorNoDisponible, obtener_motor  # noqa: E402
from app.pipeline.preprocesado import OpcionesPreprocesado, preprocesar  # noqa: E402

EXTENSIONES = {".pdf", ".jpg", ".jpeg", ".png", ".tif", ".tiff"}


# ------------------------------------------------------------------ métricas
def _norm_texto(s: str) -> str:
    s = unicodedata.normalize("NFD", str(s))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return " ".join(s.casefold().split())


def cer(referencia: str, hipotesis: str) -> float:
    """Character Error Rate = distancia de Levenshtein / largo de la referencia (espacios normalizados)."""
    ref = " ".join(referencia.split())
    hip = " ".join(hipotesis.split())
    if not ref:
        return 0.0 if not hip else 1.0
    return Levenshtein.distance(ref, hip) / len(ref)


def campo_correcto(esperado, obtenido) -> bool:
    """Compara valor esperado vs extraído: numérico con tolerancia, texto sin acentos/mayúsculas/espacios."""
    if obtenido is None:
        return False
    if isinstance(esperado, (int, float)) and not isinstance(esperado, bool):
        try:
            return abs(float(obtenido) - float(esperado)) < 1e-6
        except (TypeError, ValueError):
            return False
    return _norm_texto(esperado) == _norm_texto(obtenido)


# ------------------------------------------------------------------ evaluación
def _leer_con_motor(motor, imagenes, idioma: str) -> list[PaginaOCR]:
    paginas = []
    for i, img in enumerate(imagenes):
        p = motor.leer(img, idioma)
        p.numero = i + 1
        for palabra in p.palabras:
            palabra.pagina = i + 1
        paginas.append(p)
    return paginas


def evaluar_documento(ruta: Path, esperado: dict, plantillas: list[PlantillaCrear], motores: list[str], args, settings):
    """Devuelve {motor: {cer, campos_ok, campos_total, ms, error, detalle}} para un documento."""
    datos = ruta.read_bytes()
    try:
        doc = ingerir(ruta.name, datos, max_mb=settings.MAX_TAMANO_MB, dpi=settings.OCR_DPI)
    except ErrorIngesta as e:
        return {"-": {"error": f"ingesta: {e}"}}

    salida: dict[str, dict] = {}
    if doc.es_pdf_nativo:
        lecturas = {"pdf-nativo": (lambda: doc.paginas_nativas)}
    else:
        op = OpcionesPreprocesado(
            deskew=not args.sin_preprocesado and settings.PRE_DESKEW,
            denoise=not args.sin_preprocesado and settings.PRE_DENOISE,
            binarizar=not args.sin_preprocesado and settings.PRE_BINARIZAR,
            reescalar=not args.sin_preprocesado and settings.PRE_REESCALAR,
        )
        imagenes = [preprocesar(img, op)[0] for img in doc.imagenes]
        lecturas = {}
        for nombre in motores:
            def _leer(nombre=nombre):
                return _leer_con_motor(obtener_motor(nombre, settings), imagenes, args.idioma)

            lecturas[nombre] = _leer

    for nombre, leer in lecturas.items():
        t0 = time.perf_counter()
        try:
            paginas = leer()
        except (MotorNoDisponible, ImportError) as e:  # motor no instalado o sin modelos
            salida[nombre] = {"error": str(e)}
            continue
        ms = int((time.perf_counter() - t0) * 1000)
        res: dict = {"ms": ms, "error": None, "cer": None, "campos_ok": 0, "campos_total": 0, "detalle": {}, "tipo_ok": None, "tipo_detectado": None}
        texto = "\n".join(p.texto for p in paginas)
        if esperado.get("texto"):
            res["cer"] = cer(esperado["texto"], texto)
        if plantillas:
            candidatas = [
                PlantillaCandidata(i, i, pl.codigo, pl.umbral_confianza, pl.palabras_clave)
                for i, pl in enumerate(plantillas, 1)
            ]
            clasif, _ = clasificar(texto, candidatas, settings.UMBRAL_DESCONOCIDO)
            res["tipo_detectado"] = clasif.tipo
            if esperado.get("tipo"):
                res["tipo_ok"] = clasif.tipo == esperado["tipo"]
        plantilla = next((pl for pl in plantillas if pl.codigo == esperado.get("tipo")), None)
        if plantilla is None and len(plantillas) == 1:
            plantilla = plantillas[0]
        if plantilla and esperado.get("campos"):
            extraidos = {c.nombre: c for c in extraer_campos(plantilla.campos, paginas)}
            for nombre_campo, valor_esp in esperado["campos"].items():
                c = extraidos.get(nombre_campo)
                obtenido = c.valor if c else None
                ok = campo_correcto(valor_esp, obtenido)
                res["campos_total"] += 1
                res["campos_ok"] += int(ok)
                res["detalle"][nombre_campo] = {"esperado": valor_esp, "obtenido": obtenido, "ok": ok}
        salida[nombre] = res
    return salida


def resumir(por_documento: dict[str, dict[str, dict]]) -> dict[str, dict]:
    """Agrega por motor: CER medio, exactitud de campos (micro), ms medio y errores."""
    acum: dict[str, dict] = {}
    for resultados in por_documento.values():
        for motor, r in resultados.items():
            a = acum.setdefault(motor, {"cers": [], "ok": 0, "total": 0, "ms": [], "errores": 0, "docs": 0, "tipos_ok": 0, "tipos_total": 0})
            a["docs"] += 1
            if r.get("error"):
                a["errores"] += 1
                continue
            if r["cer"] is not None:
                a["cers"].append(r["cer"])
            if r.get("tipo_ok") is not None:
                a["tipos_total"] += 1
                a["tipos_ok"] += int(r["tipo_ok"])
            a["ok"] += r["campos_ok"]
            a["total"] += r["campos_total"]
            a["ms"].append(r["ms"])
    return {
        m: {
            "documentos": a["docs"],
            "errores": a["errores"],
            "cer_medio": statistics.mean(a["cers"]) if a["cers"] else None,
            "exactitud_campos": a["ok"] / a["total"] if a["total"] else None,
            "acierto_clasificacion": a["tipos_ok"] / a["tipos_total"] if a["tipos_total"] else None,
            "campos_ok": a["ok"],
            "campos_total": a["total"],
            "ms_medio": int(statistics.mean(a["ms"])) if a["ms"] else None,
        }
        for m, a in acum.items()
    }


def _fmt_pct(x) -> str:
    return "   -  " if x is None else f"{x * 100:5.1f}%"


def imprimir_tabla(resumen: dict[str, dict]) -> None:
    print(f"\n{'Motor':<12} {'Docs':>4} {'Err':>4} {'CER':>7} {'Campos OK':>14} {'Exactitud':>10} {'Clasif.':>8} {'ms/doc':>8}")
    print("-" * 75)
    for motor, r in sorted(resumen.items(), key=lambda kv: -(kv[1]["exactitud_campos"] or 0)):
        campos = f"{r['campos_ok']}/{r['campos_total']}" if r["campos_total"] else "-"
        ms = r["ms_medio"] if r["ms_medio"] is not None else "-"
        print(
            f"{motor:<12} {r['documentos']:>4} {r['errores']:>4} {_fmt_pct(r['cer_medio']):>7} "
            f"{campos:>14} {_fmt_pct(r['exactitud_campos']):>10} {_fmt_pct(r['acierto_clasificacion']):>8} {ms:>8}"
        )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Evalúa motores OCR (CER y exactitud por campo).")
    ap.add_argument("carpeta", type=Path, help="Carpeta con los documentos (pdf/jpg/png/tiff)")
    ap.add_argument("--esperado", type=Path, help="JSON con lo esperado (default: CARPETA/esperado.json)")
    ap.add_argument("--plantilla", type=Path, nargs="+", default=[], help="JSON(s) de plantilla: clasificación y reglas de campos")
    ap.add_argument("--motores", default="paddle,doctr,tesseract", help="Lista separada por comas")
    ap.add_argument("--idioma", default=None, help="Idioma OCR (default: OCR_IDIOMA de la config)")
    ap.add_argument("--sin-preprocesado", action="store_true", help="Desactiva el preprocesado de imagen")
    ap.add_argument("--salida", type=Path, help="Guarda el detalle completo en este JSON")
    ap.add_argument("--verbose", "-v", action="store_true", help="Muestra el detalle por campo fallado")
    args = ap.parse_args(argv)

    settings = get_settings()
    args.idioma = args.idioma or settings.OCR_IDIOMA
    carpeta: Path = args.carpeta
    if not carpeta.is_dir():
        print(f"No existe la carpeta: {carpeta}", file=sys.stderr)
        return 2
    ruta_esp = args.esperado or carpeta / "esperado.json"
    if not ruta_esp.is_file():
        print(f"No se encontró el JSON de esperados: {ruta_esp}", file=sys.stderr)
        return 2
    esperados: dict = json.loads(ruta_esp.read_text(encoding="utf-8"))
    plantillas = [PlantillaCrear.model_validate_json(p.read_text(encoding="utf-8")) for p in args.plantilla]
    motores = [m.strip() for m in args.motores.split(",") if m.strip()]

    archivos = sorted(p for p in carpeta.iterdir() if p.suffix.lower() in EXTENSIONES)
    sin_etiqueta = [p.name for p in archivos if p.name not in esperados]
    if sin_etiqueta:
        print(f"Aviso: {len(sin_etiqueta)} archivo(s) sin entrada en esperado.json, se omiten: {', '.join(sin_etiqueta)}")
    archivos = [p for p in archivos if p.name in esperados]
    if not archivos:
        print("No hay documentos etiquetados para evaluar.", file=sys.stderr)
        return 2

    por_documento: dict[str, dict] = {}
    for p in archivos:
        print(f"Evaluando {p.name} ...", flush=True)
        por_documento[p.name] = evaluar_documento(p, esperados[p.name], plantillas, motores, args, settings)
        if args.verbose:
            for motor, r in por_documento[p.name].items():
                if r.get("error"):
                    print(f"   [{motor}] ERROR: {r['error']}")
                if r.get("tipo_ok") is False:
                    print(f"   [{motor}] tipo: esperado={esperados[p.name].get('tipo')!r} detectado={r['tipo_detectado']!r}")
                for campo, d in r.get("detalle", {}).items():
                    if not d["ok"]:
                        print(f"   [{motor}] {campo}: esperado={d['esperado']!r} obtenido={d['obtenido']!r}")

    resumen = resumir(por_documento)
    imprimir_tabla(resumen)
    if args.salida:
        args.salida.write_text(
            json.dumps({"resumen": resumen, "documentos": por_documento}, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        print(f"\nDetalle guardado en {args.salida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
