from types import SimpleNamespace

import pytest

from anclaje.embeddings import EmbedderFalso, EmbeddingsLocales
from anclaje.indice import Indice
from anclaje.modelos import Fragmento


def test_indice_persistente_filtro_y_reconstruccion(tmp_path):
    embedder = EmbedderFalso()
    index = Indice(tmp_path, embedder)
    fragments = [
        Fragmento("uno", "publicos/a.txt", 1, "publicos", "media aritmética suma valores"),
        Fragmento("dos", "contraparte/a.txt", 2, "contraparte", "media aritmética privada"),
    ]
    index.reconstruir(fragments, chunk_size=1000, chunk_overlap=150)
    reopened = Indice(tmp_path, EmbedderFalso())
    assert reopened.estado()["fragmentos"] == 2
    public = reopened.consultar("media aritmética", 4)
    assert len(public) == 1 and public[0].origen == "publicos"
    private = reopened.consultar("media aritmética", 4, ("contraparte",))
    assert len(private) == 1 and private[0].pagina == 2
    reopened.reconstruir(fragments[1:], chunk_size=600, chunk_overlap=100)
    assert reopened.estado()["fragmentos"] == 1
    assert reopened.consultar("media", 4) == []


def test_modelo_distinto_exige_reindexar(tmp_path):
    index = Indice(tmp_path, EmbedderFalso())
    index.reconstruir([], chunk_size=1000, chunk_overlap=150)
    with pytest.raises(ValueError, match="difiere"):
        Indice(tmp_path, SimpleNamespace(nombre="otro")).estado()


def test_fragmentacion_distinta_exige_reindexar(tmp_path):
    index = Indice(tmp_path, EmbedderFalso())
    index.reconstruir([], chunk_size=1000, chunk_overlap=150)
    with pytest.raises(ValueError, match="fragmentación"):
        Indice(tmp_path, EmbedderFalso(), chunk_size=600, chunk_overlap=150).estado()


def test_indice_faltante_y_reconstruccion_vacia(tmp_path):
    index = Indice(tmp_path, EmbedderFalso())
    with pytest.raises(ValueError, match="No hay"):
        index.consultar("Pregunta", 3)
    index.reconstruir([], chunk_size=1000, chunk_overlap=150)
    assert index.consultar("Pregunta", 3) == []


@pytest.mark.parametrize("model,prefix_query,prefix_doc", [
    ("intfloat/multilingual-e5-base", "query: ", "passage: "),
    ("BAAI/bge-m3", "", ""),
])
def test_prefijos_e5_y_bge(model, prefix_query, prefix_doc):
    class Model:
        def __init__(self):
            self.texts = []

        def encode(self, texts, **kwargs):
            self.texts.append(texts)
            assert kwargs["normalize_embeddings"]
            return SimpleNamespace(tolist=lambda: [[1.0, 0.0] for _ in texts])

    embedder = EmbeddingsLocales(model)
    embedder._model = Model()
    assert embedder.consulta("Pregunta") == [1.0, 0.0]
    embedder.documentos(["Fuente"])
    assert embedder._model.texts == [[prefix_query + "Pregunta"], [prefix_doc + "Fuente"]]


def test_carga_perezosa_y_solo_cache(monkeypatch):
    import sys

    calls = []

    def model(*args, **kwargs):
        calls.append(kwargs)
        return object()

    monkeypatch.setitem(sys.modules, "sentence_transformers", SimpleNamespace(SentenceTransformer=model))
    embedder = EmbeddingsLocales("BAAI/bge-m3")
    assert not calls
    embedder._cargar()
    assert calls[0]["local_files_only"] is True
    assert calls[0]["trust_remote_code"] is False
