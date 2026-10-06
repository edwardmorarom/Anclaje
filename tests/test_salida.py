from dataclasses import replace
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from anclaje.salida import cargar_destino, guardar_destino, validar_destino


def test_destino_explicito_persistente_y_demo_separado(config):
    assert cargar_destino(config) is None
    chosen = config.results_dir / "mis_resultados"
    assert guardar_destino(config, str(chosen)) == chosen
    assert cargar_destino(config) == chosen
    assert cargar_destino(config, demo=True) is None
    assert list(chosen.iterdir()) == []


def test_destino_fuera_del_repositorio_es_posible(config):
    original = config
    config = replace(config, root=config.root / "repo", results_dir=config.root / "repo/resultados")
    chosen = original.root / "carpeta_usuario"
    assert guardar_destino(config, str(chosen)) == chosen
    assert cargar_destino(config) == chosen


def test_no_escribe_sobre_archivos_o_codigo(config):
    for invalid in ("", "relativa", str(config.root), str(config.docs_dir), str(config.root / ".git")):
        with pytest.raises(ValueError):
            validar_destino(config, invalid)
    file = config.results_dir / "archivo.csv"
    file.parent.mkdir(parents=True)
    file.write_text("original", encoding="utf-8")
    with pytest.raises(ValueError, match="archivo"):
        guardar_destino(config, str(file))
    assert file.read_text(encoding="utf-8") == "original"


def test_interfaz_pide_destino_antes_de_procesar_y_lo_recuerda(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[1]
    project = tmp_path / "repo"
    project.mkdir()
    conf = project / "config.yaml"
    conf.write_text(f"protocol: {(root / 'protocolo/v1.md').as_posix()}\n", encoding="utf-8")
    monkeypatch.setenv("ANCLAJE_CONFIG", str(conf))
    monkeypatch.setenv("ANCLAJE_DEMO", "true")
    app = AppTest.from_file(str(root / "app.py"), default_timeout=30).run()
    assert not app.exception and app.button(key="paso_siguiente").disabled
    app.radio(key="paso_activo").set_value("Consultar").run()
    assert not any(button.key == "consultar" for button in app.button)
    chosen = tmp_path / "salida_elegida"
    app.text_input(key="ruta_salida").set_value(str(chosen))
    app.button(key="confirmar_salida").click().run()
    assert not app.exception and not app.error
    app.radio(key="paso_activo").set_value("Consultar").run()
    app.text_input(key="pregunta_consulta").set_value("media aritmética suma valores número observaciones")
    app.button(key="consultar").click().run()
    assert not app.exception and not app.error
    assert len(list(chosen.glob("humo/consultas/*.json"))) == 1
    assert not list((project / "resultados").glob("**/consulta_*.json"))
    fresh = AppTest.from_file(str(root / "app.py"), default_timeout=30).run()
    assert fresh.text_input(key="ruta_salida").value == str(chosen)
    assert not fresh.button(key="paso_siguiente").disabled
    fresh.radio(key="paso_activo").set_value("Evaluar").run()
    fresh.text_input(key="banco_pregunta").set_value("media aritmética suma valores número observaciones")
    fresh.text_area(key="banco_respuesta").set_value("Suma dividida entre n")
    fresh.text_input(key="banco_documento").set_value("publicos/demo.txt")
    fresh.button(key="agregar_pregunta").click().run()
    assert (chosen / "humo/banco.csv").is_file()
    fresh.button(key="ejecutar_evaluacion").click().run()
    assert not fresh.exception and not fresh.error
    assert list(chosen.glob("evaluacion_*.csv")) and list(chosen.glob("metricas_*.csv"))
    fresh.radio(key="paso_activo").set_value("Memoria").run()
    fresh.text_area(key="memoria_diagnostico").set_value("Borrador en salida seleccionada")
    fresh.button(key="guardar_memoria").click().run()
    assert (chosen / "memoria/borrador.md").is_file()
    other = tmp_path / "otra_salida"
    fresh.text_input(key="ruta_salida").set_value(str(other))
    fresh.button(key="confirmar_salida").click().run()
    fresh.radio(key="paso_activo").set_value("Memoria").run()
    assert fresh.radio(key="paso_activo").value != "Memoria"
    assert (chosen / "memoria/borrador.md").is_file()
    assert not (other / "memoria/borrador.md").exists()
