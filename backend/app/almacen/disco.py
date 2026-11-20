"""Almacén de archivos en disco. Guarda por hash para deduplicar y evitar colisiones."""
from __future__ import annotations

from pathlib import Path


class AlmacenDisco:
    def __init__(self, raiz: str) -> None:
        self.raiz = Path(raiz)
        self.raiz.mkdir(parents=True, exist_ok=True)

    def guardar(self, hash_sha256: str, extension: str, datos: bytes) -> str:
        """Guarda el archivo y devuelve la ruta relativa al almacén."""
        subcarpeta = hash_sha256[:2]
        carpeta = self.raiz / subcarpeta
        carpeta.mkdir(parents=True, exist_ok=True)
        nombre = f"{hash_sha256}.{extension}"
        ruta = carpeta / nombre
        if not ruta.exists():
            ruta.write_bytes(datos)
        return f"{subcarpeta}/{nombre}"

    def leer(self, ruta_relativa: str) -> bytes:
        return (self.raiz / ruta_relativa).read_bytes()

    def ruta_absoluta(self, ruta_relativa: str) -> Path:
        return self.raiz / ruta_relativa

    def tamano(self, ruta_relativa: str) -> int:
        """Bytes del archivo (0 si ya no existe)."""
        try:
            return (self.raiz / ruta_relativa).stat().st_size
        except OSError:
            return 0

    def eliminar(self, ruta_relativa: str) -> bool:
        """Borra el archivo; True si existía. Nunca sale de la raíz del almacén."""
        destino = (self.raiz / ruta_relativa).resolve()
        if self.raiz.resolve() not in destino.parents:
            raise ValueError("Ruta fuera del almacén")
        try:
            destino.unlink()
            return True
        except FileNotFoundError:
            return False
