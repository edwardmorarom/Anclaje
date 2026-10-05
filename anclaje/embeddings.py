import hashlib
import math
import re
from typing import Protocol

from .fragmentos import normalizar


class Embedder(Protocol):
    nombre: str

    def documentos(self, textos: list[str]) -> list[list[float]]: ...

    def consulta(self, texto: str) -> list[float]: ...


class EmbeddingsLocales:
    def __init__(self, nombre: str, *, permitir_descarga: bool = False):
        self.nombre = nombre
        self.permitir_descarga = permitir_descarga
        self._model = None

    def _cargar(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            try:
                self._model = SentenceTransformer(
                    self.nombre, local_files_only=not self.permitir_descarga,
                    trust_remote_code=False,
                )
            except Exception:
                raise ValueError(
                    "No se pudo cargar el modelo local. Ejecuta reindexar con conexión "
                    "para descargar sus pesos, o revisa la caché del modelo configurado."
                ) from None
        return self._model

    def _codificar(self, textos: list[str], tipo: str) -> list[list[float]]:
        if not textos:
            return []
        if "multilingual-e5" in self.nombre.lower():
            prefix = "query: " if tipo == "query" else "passage: "
            textos = [prefix + text for text in textos]
        return self._cargar().encode(
            textos, normalize_embeddings=True, batch_size=16, show_progress_bar=False,
        ).tolist()

    def documentos(self, textos: list[str]) -> list[list[float]]:
        return self._codificar(textos, "passage")

    def consulta(self, texto: str) -> list[float]:
        return self._codificar([texto], "query")[0]


class EmbedderFalso:
    """Vectores léxicos deterministas; no representan calidad semántica real."""

    nombre = "falso-local-v1"

    def consulta(self, texto: str) -> list[float]:
        vector = [0.0] * 128
        for token in re.findall(r"\w+", normalizar(texto)):
            digest = hashlib.sha256(token.encode()).digest()
            vector[int.from_bytes(digest[:4], "big") % len(vector)] += 1.0
        norm = math.sqrt(sum(x * x for x in vector)) or 1.0
        return [x / norm for x in vector]

    def documentos(self, textos: list[str]) -> list[list[float]]:
        return [self.consulta(text) for text in textos]
