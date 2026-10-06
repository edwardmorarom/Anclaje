import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from anclaje.biblioteca import actualizar_indice, explorar_carpeta, importar_archivos, importar_carpeta, seleccionar_carpeta
from anclaje.embeddings import EmbedderFalso
from anclaje.indice import Indice
from anclaje.memoria import APARTADOS, cargar_memoria, destino_tratamiento, exportar_memoria, guardar_memoria, reconocer_tratamiento


def archivo(nombre, texto):
    return SimpleNamespace(name=nombre, getvalue=lambda: texto.encode())


def test_explorar_omite_temporales_y_respeta_subcarpetas(tmp_path):
    folder = tmp_path / "edward"
    folder.mkdir()
    for name in ("articulo.pdf", "~$estado.docx", "trazabilidad.xlsx", ".oculto.md", "datos.csv"):
        (folder / name).write_bytes(b"sintetico")
    (folder / "complemento").mkdir()
    (folder / "complemento/otro.md").write_text("Texto", encoding="utf-8")
    assert [f.relativo for f in explorar_carpeta(folder)] == ["articulo.pdf"]
    assert [f.relativo for f in explorar_carpeta(folder, True)] == ["articulo.pdf", "complemento/otro.md"]


def test_importar_carpeta_conserva_originales_y_procedencia(config):
    source = config.root / "edward"
    source.mkdir()
    original = source / "fuente.txt"
    original.write_text("Texto original", encoding="utf-8")
    results = importar_carpeta(source, config.docs_dir, "publicos", ["fuente.txt"],
                              grupo="edward", permiso="Licencia verificada", verificado_por="Edward")
    assert results[0].nuevo
    assert (config.docs_dir / "publicos/edward/fuente.txt").read_text(encoding="utf-8") == "Texto original"
    assert original.read_text(encoding="utf-8") == "Texto original"
    provenance = (config.docs_dir / "PROCEDENCIA.md").read_text(encoding="utf-8")
    assert "publicos/edward/fuente.txt" in provenance and "Licencia verificada" in provenance
    again = importar_carpeta(source, config.docs_dir, "publicos", ["fuente.txt"], grupo="edward")
    assert not again[0].nuevo
    assert (config.docs_dir / "PROCEDENCIA.md").read_text(encoding="utf-8").count("publicos/edward/fuente.txt") == 1


def test_colision_conserva_los_dos_contenidos(config):
    first = importar_archivos([archivo("a.txt", "primero")], config.docs_dir, "publicos")
    second = importar_archivos([archivo("a.txt", "segundo")], config.docs_dir, "publicos")
    assert first[0].documento == "publicos/a.txt" and second[0].documento == "publicos/a_2.txt"
    assert (config.docs_dir / "publicos/a.txt").read_text() == "primero"
    assert (config.docs_dir / "publicos/a_2.txt").read_text() == "segundo"


@pytest.mark.parametrize("nombre", ["../escape.txt", "..\\escape.txt", "/escape.txt", "C:\\escape.txt", "~$temporal.docx", "datos.csv"])
def test_upload_no_puede_escribir_fuera_del_origen(config, nombre):
    with pytest.raises(ValueError):
        importar_archivos([archivo(nombre, "Texto")], config.docs_dir, "publicos")
    assert not (config.root / "escape.txt").exists()


def test_no_importa_archivos_que_no_estan_en_vista_previa(config):
    source = config.root / "edward"
    source.mkdir()
    with pytest.raises(ValueError, match="vista previa"):
        importar_carpeta(source, config.docs_dir, "publicos", ["fuera.pdf"])


@pytest.mark.parametrize("folder,relative,expected", [
    ("edward", "articulo.pdf", "C"), ("Harold", "articulo.pdf", "A"), ("NATALIA", "articulo.pdf", "B"),
    ("II", "edward/articulo.pdf", "C"), ("II", "Harold/articulo.pdf", "A"), ("II", "natalia/articulo.pdf", "B"),
    ("otros", "articulo.pdf", None),
])
def test_reconoce_carpetas_del_experimento(folder, relative, expected):
    assert reconocer_tratamiento(Path(folder), relative) == expected


def test_evidencias_ab_quedan_fuera_del_corpus(config):
    for treatment, person in (("A", "Harold"), ("B", "Natalia"), ("C", "Edward")):
        importar_archivos([archivo("a.txt", f"Texto de {person}")], destino_tratamiento(config, treatment), "publicos", grupo=person)
    index = Indice(config.index_dir, EmbedderFalso())
    summary = actualizar_indice(config, index)
    assert summary["documentos"] == 1
    retrieved = index.consultar("Texto", 5)
    assert all("Edward" in f.documento for f in retrieved)
    assert not (config.docs_dir / "publicos/Harold").exists()
    assert (config.results_dir / "evidencias/A/publicos/Harold/a.txt").exists()


def test_actualizar_sin_texto_conserva_indice_anterior(config):
    importar_archivos([archivo("a.txt", "Media aritmética")], config.docs_dir, "publicos")
    index = Indice(config.index_dir, EmbedderFalso())
    actualizar_indice(config, index)
    (config.docs_dir / "publicos/a.txt").write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="No hay texto legible"):
        actualizar_indice(config, index)
    assert index.estado()["fragmentos"] == 1


def test_selector_nativo_se_ejecuta_en_proceso_separado(monkeypatch):
    import anclaje.biblioteca as library

    monkeypatch.setattr(library.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=json.dumps("C:/fuentes/edward")))
    assert seleccionar_carpeta() == "C:/fuentes/edward"


def test_memoria_conserva_los_seis_apartados_sin_inventar(config):
    path = config.results_dir / "memoria/borrador.json"
    contents = cargar_memoria(path)
    assert len(contents) == 6 and all(value == "" for value in contents.values())
    contents["diagnostico"] = "Referencia que no abrió; detectada al revisar el DOI."
    guardar_memoria(path, contents)
    assert cargar_memoria(path) == contents
    markdown = exportar_memoria(contents)
    assert all(f"## {title}" in markdown for _, title, _ in APARTADOS)
    assert markdown.count("[Pendiente de completar con evidencia real]") == 5
