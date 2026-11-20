import importlib.util
from pathlib import Path

_ruta = Path(__file__).resolve().parents[2] / "scripts" / "evaluar.py"
_spec = importlib.util.spec_from_file_location("evaluar", _ruta)
evaluar = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(evaluar)


def test_cer():
    assert evaluar.cer("hola mundo", "hola mundo") == 0.0
    assert evaluar.cer("abcd", "abxd") == 0.25
    assert evaluar.cer("", "x") == 1.0


def test_campo_correcto():
    assert evaluar.campo_correcto(45320, 45320.0)
    assert not evaluar.campo_correcto(45320, None)
    assert evaluar.campo_correcto("Dirección  Central", "direccion central")
    assert not evaluar.campo_correcto("a", "b")


def test_resumir():
    docs = {
        "a.png": {"paddle": {"cer": 0.1, "campos_ok": 2, "campos_total": 3, "ms": 100, "error": None, "tipo_ok": True}},
        "b.png": {"paddle": {"cer": 0.3, "campos_ok": 1, "campos_total": 1, "ms": 200, "error": None, "tipo_ok": False}},
        "c.png": {"paddle": {"error": "boom"}},
    }
    r = evaluar.resumir(docs)["paddle"]
    assert r["documentos"] == 3 and r["errores"] == 1
    assert abs(r["cer_medio"] - 0.2) < 1e-9
    assert r["acierto_clasificacion"] == 0.5
    assert r["campos_ok"] == 3 and r["campos_total"] == 4 and r["ms_medio"] == 150
