import os
from pathlib import Path

from .embeddings import Embedder
from .modelos import Fragmento

COLECCION = "anclaje"
VERSION_INDICE = 1


class Indice:
    def __init__(self, directorio: Path, embedder: Embedder):
        self.directorio = Path(directorio)
        self.embedder = embedder
        self._client = None

    def _abrir(self):
        if self._client is None:
            os.environ["ANONYMIZED_TELEMETRY"] = "False"
            from chromadb import PersistentClient
            from chromadb.config import Settings

            self._client = PersistentClient(
                path=str(self.directorio), settings=Settings(anonymized_telemetry=False),
            )
        return self._client

    def _coleccion(self):
        try:
            collection = self._abrir().get_collection(COLECCION, embedding_function=None)
        except Exception:
            raise ValueError("No hay un índice legible. Ejecuta python -m anclaje reindexar.") from None
        meta = collection.metadata or {}
        if not meta.get("listo") or meta.get("version") != VERSION_INDICE:
            raise ValueError("El índice está incompleto o desactualizado. Ejecuta reindexar.")
        if meta.get("embedding_model") != self.embedder.nombre:
            raise ValueError("El modelo configurado difiere del índice. Ejecuta reindexar.")
        return collection

    def reconstruir(self, fragments: list[Fragmento], *, chunk_size: int, chunk_overlap: int):
        vectors = self.embedder.documentos([f.texto for f in fragments])
        client = self._abrir()
        if COLECCION in {c.name for c in client.list_collections()}:
            client.delete_collection(COLECCION)
        meta = {
            "hnsw:space": "cosine", "embedding_model": self.embedder.nombre,
            "chunk_size": chunk_size, "chunk_overlap": chunk_overlap,
            "version": VERSION_INDICE, "listo": False,
        }
        collection = client.create_collection(COLECCION, metadata=meta, embedding_function=None)
        for start in range(0, len(fragments), 128):
            batch = fragments[start:start + 128]
            collection.add(
                ids=[f.id for f in batch], documents=[f.texto for f in batch],
                metadatas=[f.metadata() for f in batch], embeddings=vectors[start:start + 128],
            )
        collection.modify(metadata={**meta, "listo": True})

    def estado(self) -> dict:
        collection = self._coleccion()
        return {"fragmentos": collection.count(), **collection.metadata}

    def consultar(self, pregunta: str, top_k: int, origenes: tuple[str, ...] = ("publicos",)) -> list[Fragmento]:
        if top_k < 1:
            raise ValueError("top_k debe ser positivo.")
        if not origenes or set(origenes) - {"publicos", "contraparte"}:
            raise ValueError("Selecciona publicos, contraparte o ambos.")
        collection = self._coleccion()
        count = collection.count()
        if not count:
            return []
        where = {"origen": origenes[0]} if len(origenes) == 1 else {"origen": {"$in": list(origenes)}}
        result = collection.query(
            query_embeddings=[self.embedder.consulta(pregunta)],
            n_results=min(count, top_k), where=where, include=["documents", "metadatas", "distances"],
        )
        fragments = []
        for identity, text, meta, distance in zip(
            result["ids"][0], result["documents"][0], result["metadatas"][0], result["distances"][0],
        ):
            fragments.append(Fragmento(
                identity, meta["documento"], int(meta["pagina"]), meta["origen"], text,
                max(-1.0, min(1.0, 1.0 - distance)),
            ))
        return fragments
