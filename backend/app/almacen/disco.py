"""Almacén de archivos en disco. Guarda por hash para deduplicar y evitar colisiones."""
from __future__ import annotations

import os
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
        else:
            # mismo contenido que ya estaba: se renueva su fecha para que la limpieza de huérfanos de la purga
            # no lo tome por un resto viejo mientras se crea el registro de esta subida
            try:
                os.utime(ruta, None)
            except OSError:
                pass
        return f"{subcarpeta}/{nombre}"

    def listar(self, modificados_antes_de: float | None = None) -> list[tuple[str, int]]:
        """(ruta relativa, bytes) de cada archivo del almacén; con límite, solo los modificados antes (epoch)."""
        archivos: list[tuple[str, int]] = []
        for ruta in self.raiz.glob("*/*"):
            try:
                if not ruta.is_file():
                    continue
                info = ruta.stat()
            except OSError:
                continue  # lo borraron mientras se listaba
            if modificados_antes_de is None or info.st_mtime < modificados_antes_de:
                archivos.append((ruta.relative_to(self.raiz).as_posix(), info.st_size))
        return archivos

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
