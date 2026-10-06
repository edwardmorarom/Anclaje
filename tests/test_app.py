from pathlib import Path

from streamlit.testing.v1 import AppTest

from anclaje.embeddings import EmbedderFalso
from anclaje.llm import ClienteFalso


def ir_a(app, paso):
    app.radio(key="paso_activo").set_value(paso).run()
    return app


def test_app_demo_consulta_y_privacidad(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[1]
    config = tmp_path / "config.yaml"
    config.write_text(f"protocol: {(root / 'protocolo/v1.md').as_posix()}\n", encoding="utf-8")
    monkeypatch.setenv("ANCLAJE_CONFIG", str(config))
    monkeypatch.setenv("ANCLAJE_DEMO", "true")
    app = AppTest.from_file(str(root / "app.py"), default_timeout=30).run()
    assert not app.exception
    assert any("Demostración" in item.value for item in app.warning)
    ir_a(app, "Consultar")
    app.text_input(key="pregunta_consulta").set_value("media aritmética suma valores número observaciones")
    app.button(key="consultar").click().run()
    assert not app.exception and not app.error
    assert any("verificada" in item.label for item in app.expander)
    assert any("La media aritmética" in item.value for item in app.markdown)
    app.selectbox(key="origen_consulta").select("contraparte")
    app.button(key="consultar").click().run()
    assert not app.exception
    assert any("bloqueada" in item.value for item in app.error)


def app_real_falsa(tmp_path, monkeypatch):
    import anclaje.embeddings as embeddings
    import anclaje.llm as llm

    class ModeloFalso(EmbedderFalso):
        def __init__(self, nombre, **kwargs):
            self.nombre = nombre
            self.permitir_descarga = False

    monkeypatch.setattr(embeddings, "EmbeddingsLocales", ModeloFalso)
    client = ClienteFalso()
    monkeypatch.setattr(llm, "ClienteDeepSeek", lambda config: client)
    root = Path(__file__).resolve().parents[1]
    config = tmp_path / "config.yaml"
    config.write_text(f"embedding_model: falso-local-v1\nprotocol: {(root / 'protocolo/v1.md').as_posix()}\n", encoding="utf-8")
    monkeypatch.setenv("ANCLAJE_CONFIG", str(config))
    monkeypatch.setenv("ANCLAJE_DEMO", "false")
    app = AppTest.from_file(str(root / "app.py"), default_timeout=30).run()
    return ir_a(app, "Fuentes"), client


def test_app_importa_carpeta_y_actualiza_desde_la_interfaz(tmp_path, monkeypatch):
    source = tmp_path / "edward"
    source.mkdir()
    (source / "media.txt").write_text("media aritmética suma valores número observaciones", encoding="utf-8")
    (source / "~$temporal.docx").write_bytes(b"temporal")
    app, client = app_real_falsa(tmp_path, monkeypatch)
    app.text_input(key="carpeta_fuentes").set_value(str(source))
    app.button(key="revisar_carpeta").click().run()
    assert not app.exception
    treatment = app.selectbox(key=f"tratamiento_importacion:{source}:False")
    assert treatment.value == "C"
    choices = app.multiselect(key=f"seleccion_fuentes:{source}:False:C")
    assert choices.value == ["media.txt"]
    app.button(key="importar_carpeta").click().run()
    assert not app.exception and not app.error
    assert (tmp_path / "docs/publicos/edward/media.txt").exists()
    ir_a(app, "Consultar")
    assert app.button(key="consultar").disabled
    assert not client.llamadas
    assert (tmp_path / "docs/.indice_pendiente").exists()
    root = Path(__file__).resolve().parents[1]
    fresh = AppTest.from_file(str(root / "app.py"), default_timeout=30).run()
    ir_a(fresh, "Consultar")
    assert fresh.button(key="consultar").disabled
    ir_a(app, "Preparar")
    app.button(key="actualizar_indice").click().run()
    assert not app.exception and not app.error
    assert not (tmp_path / "docs/.indice_pendiente").exists()
    ir_a(app, "Consultar")
    assert not app.button(key="consultar").disabled
    app.text_input(key="pregunta_consulta").set_value("media aritmética suma valores número observaciones")
    app.button(key="consultar").click().run()
    assert not app.exception and not app.error
    assert any("publicos/edward/media.txt" in item.label for item in app.expander)
    assert len(client.llamadas) == 1


def test_app_reconoce_padre_con_tres_tratamientos_y_no_mezcla(tmp_path, monkeypatch):
    source = tmp_path / "II"
    for person in ("edward", "Harold", "natalia"):
        folder = source / person
        folder.mkdir(parents=True)
        (folder / "a.txt").write_text(person, encoding="utf-8")
    app, _ = app_real_falsa(tmp_path, monkeypatch)
    app.text_input(key="carpeta_fuentes").set_value(str(source))
    app.checkbox(key="subcarpetas_fuentes").check()
    app.button(key="revisar_carpeta").click().run()
    assert not app.exception
    assert app.multiselect(key=f"seleccion_fuentes:{source}:True:C").value == ["edward/a.txt"]
    app.multiselect(key=f"seleccion_fuentes:{source}:True:C").select("Harold/a.txt")
    app.button(key="importar_carpeta").click().run()
    assert any("mezcla" in item.value for item in app.error)
    assert not (tmp_path / "docs/publicos/II/Harold/a.txt").exists()
    app.selectbox(key=f"tratamiento_importacion:{source}:True").select("A").run()
    assert app.multiselect(key=f"seleccion_fuentes:{source}:True:A").value == ["Harold/a.txt"]
    app.button(key="importar_carpeta").click().run()
    assert not app.exception and not app.error
    assert (tmp_path / "resultados/evidencias/A/publicos/II/Harold/a.txt").exists()
    assert not (tmp_path / "docs/publicos/II/Harold/a.txt").exists()


def test_app_memoria_guarda_y_restaurar_seis_apartados(tmp_path, monkeypatch):
    app, _ = app_real_falsa(tmp_path, monkeypatch)
    ir_a(app, "Memoria")
    assert len(app.text_area) == 6
    app.text_area(key="memoria_diagnostico").set_value("El DOI no abría; revisamos la referencia.")
    app.button(key="guardar_memoria").click().run()
    assert not app.exception and not app.error
    markdown = (tmp_path / "resultados/memoria/borrador.md").read_text(encoding="utf-8")
    assert "El DOI no abría" in markdown and markdown.count("## ") == 6
    root = Path(__file__).resolve().parents[1]
    restored = AppTest.from_file(str(root / "app.py"), default_timeout=30).run()
    ir_a(restored, "Memoria")
    assert restored.text_area(key="memoria_diagnostico").value == "El DOI no abría; revisamos la referencia."


def test_app_control_a_no_usa_indice_ni_fuentes(tmp_path, monkeypatch):
    app, client = app_real_falsa(tmp_path, monkeypatch)
    ir_a(app, "Consultar")
    app.selectbox(key="tratamiento_consulta").select("A").run()
    app.text_input(key="pregunta_consulta").set_value("Pregunta de control")
    app.button(key="consultar").click().run()
    assert not app.exception and not app.error
    assert len(client.llamadas) == 1
    assert '"fuentes"' not in client.llamadas[0][-1]["content"]


def test_carpeta_invalida_no_oculta_las_otras_pestanas(tmp_path, monkeypatch):
    app, _ = app_real_falsa(tmp_path, monkeypatch)
    app.text_input(key="carpeta_fuentes").set_value(str(tmp_path / "inexistente"))
    app.button(key="revisar_carpeta").click().run()
    assert not app.exception and any("no existe" in item.value for item in app.error)
    ir_a(app, "Consultar")
    assert app.text_input(key="pregunta_consulta")
    ir_a(app, "Memoria")
    assert len(app.text_area) == 6


def test_botones_guiados_y_borradores_se_conservan(tmp_path, monkeypatch):
    app, _ = app_real_falsa(tmp_path, monkeypatch)
    ir_a(app, "Inicio")
    assert not app.exception and app.radio(key="paso_activo").value == "Inicio"
    app.button(key="paso_siguiente").click().run()
    assert app.radio(key="paso_activo").value == "Fuentes"
    assert app.button(key="paso_siguiente").disabled
    app.text_input(key="carpeta_fuentes").set_value(str(tmp_path / "edward")).run()
    app.text_input(key="verificador_importacion").set_value("Edward").run()
    ir_a(app, "Memoria")
    app.text_area(key="memoria_diagnostico").set_value("Mi borrador sin guardar.").run()
    ir_a(app, "Inicio")
    ir_a(app, "Memoria")
    assert app.text_area(key="memoria_diagnostico").value == "Mi borrador sin guardar."
    ir_a(app, "Fuentes")
    assert app.text_input(key="carpeta_fuentes").value == str(tmp_path / "edward")
    assert app.text_input(key="verificador_importacion").value == "Edward"
    assert not any("Session State API" in w.value for w in app.warning)
    app.button(key="paso_anterior").click().run()
    assert app.radio(key="paso_activo").value == "Inicio"


def test_evaluacion_desde_el_recorrido_sin_clave(tmp_path, monkeypatch):
    from anclaje.evaluar import guardar_csv

    source = tmp_path / "docs/publicos/edward"
    source.mkdir(parents=True)
    (source / "media.txt").write_text("media aritmética suma valores número observaciones", encoding="utf-8")
    (tmp_path / "docs/PROCEDENCIA.md").write_text("| publicos/edward/media.txt | publicos |", encoding="utf-8")
    app, client = app_real_falsa(tmp_path, monkeypatch)
    ir_a(app, "Preparar")
    assert app.button(key="paso_siguiente").disabled
    app.button(key="actualizar_indice").click().run()
    assert not app.exception and not app.error
    app.button(key="paso_siguiente").click().run()
    assert app.radio(key="paso_activo").value == "Consultar"
    app.text_input(key="pregunta_consulta").set_value("media aritmética suma valores número observaciones")
    app.button(key="consultar").click().run()
    assert len(client.llamadas) == 1
    app.button(key="paso_siguiente").click().run()
    assert app.radio(key="paso_activo").value == "Evaluar"
    app.text_input(key="banco_pregunta").set_value("media aritmética suma valores número observaciones")
    app.text_area(key="banco_respuesta").set_value("Suma entre n.")
    app.text_input(key="banco_documento").set_value("publicos/edward/media.txt")
    app.button(key="agregar_pregunta").click().run()
    assert not app.exception and not app.error
    assert (tmp_path / "eval/banco.csv").exists()
    assert app.metric[0].value == "1"
    assert app.button(key="ejecutar_evaluacion").disabled
    app.checkbox(key="evaluacion_falsa").check().run()
    assert not app.button(key="ejecutar_evaluacion").disabled
    app.button(key="ejecutar_evaluacion").click().run()
    assert not app.exception and not app.error
    assert list((tmp_path / "resultados").glob("evaluacion_*.csv"))
    assert any("cliente falso" in w.value for w in app.warning)
    assert len(client.llamadas) == 1
    ir_a(app, "Consultar")
    assert any("La media" in m.value or "media aritmética" in m.value for m in app.markdown)
    assert len(client.llamadas) == 1
