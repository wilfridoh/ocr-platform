"""Errores de dominio compartidos por los comandos de documentos."""


class DocumentoPurgado(RuntimeError):
    """El documento dejó de existir mientras se procesaba (lo eliminó una purga). La API responde 409/404 limpio."""
