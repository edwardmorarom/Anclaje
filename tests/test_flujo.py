from dataclasses import replace
from pathlib import Path

from streamlit.testing.v1 import AppTest

from anclaje.flujo import estado_flujo, marcar_avance, invalidar_avance
from anclaje.recorrido import guardar_banco


def state(docs=True, ready=True):
    return {"documentos": ["publicos/a.txt"] if docs else [], "indice_listo": ready}


def test_requisitos_impiden_saltar_por_el_menu(config):
    flow = estado_flujo(config, state(), False)
    assert [key for key, value in flow["habilitados"].items() if value] == ["Inicio"]
    flow = estado_flujo(config, state(docs=False, ready=False), True)
    assert flow["habilitados"]["Fuentes"] and not flow["habilitados"]["Preparar"]
    flow = estado_flujo(config, state(ready=False), True)
    assert flow["habilitados"]["Preparar"] and not flow["habilitados"]["Consultar"]
    flow = estado_flujo(config, state(), True)
    assert flow["habilitados"]["Consultar"] and not flow["habilitados"]["Evaluar"]
    marcar_avance(config, "consulta")
    assert estado_flujo(config, state(), True)["habilitados"]["Evaluar"]
    marcar_avance(config, "evaluacion")
    assert estado_flujo(config, state(), True)["habilitados"]["Memoria"]
    invalidar_avance(config, "evaluacion")
    assert not estado_flujo(config, state(), True)["habilitados"]["Memoria"]
    assert estado_flujo(config, state(), True)["habilitados"]["Evaluar"]


def test_corpus_parametros_y_banco_nuevos_invalidan_checks(config):
    folder = config.docs_dir / "publicos"
    folder.mkdir(parents=True)
    source = folder / "a.txt"
    source.write_text("Antes", encoding="utf-8")
    marcar_avance(config, "consulta")
    marcar_avance(config, "evaluacion")
    assert estado_flujo(config, state(), True)["completados"]["Evaluar"]
    assert not estado_flujo(replace(config, top_k=8), state(), True)["completados"]["Consultar"]
    source.write_text("Después del cambio", encoding="utf-8")
    assert not estado_flujo(config, state(), True)["completados"]["Consultar"]
    marcar_avance(config, "consulta")
    marcar_avance(config, "evaluacion")
    guardar_banco(config, [{"pregunta": "Una nueva", "respuesta_conocida": "No está en las fuentes.", "tipo": "fuera_de_corpus", "documento": "", "pagina": None}])
    assert not estado_flujo(config, state(), True)["completados"]["Evaluar"]


def test_check_memoria_exige_seis_apartados_guardados(config):
    from anclaje.memoria import guardar_memoria, APARTADOS

    marcar_avance(config, "consulta")
    marcar_avance(config, "evaluacion")
    path = config.results_dir / "memoria/borrador.json"
    guardar_memoria(path, {"diagnostico": "Texto"})
    assert not estado_flujo(config, state(), True)["completados"]["Memoria"]
    guardar_memoria(path, {key: "Texto" for key, _, _ in APARTADOS})
    assert estado_flujo(config, state(), True)["completados"]["Memoria"]


def test_operacion_fallida_libera_controles_y_no_admite_otra():
    source = '''
from anclaje.operaciones import controles as st, programar, ejecutar_pendiente, ocupado
from anclaje.llm import ErrorLLM
def fallo():
    st.session_state["ocupado_durante"] = ocupado()
    st.session_state["duplicado"] = programar("otra", lambda: None)
    raise ErrorLLM("Fallo simulado")
if st.button("Ejecutar", key="run"):
    programar("Procesando", fallo)
ejecutar_pendiente()
'''
    app = AppTest.from_string(source).run()
    app.button(key="run").click().run()
    assert not app.exception
    assert app.session_state["ocupado_durante"] and app.session_state["duplicado"] is False
    assert "operacion_pendiente" not in app.session_state
    assert app.session_state["aviso_operacion"] == ("error", "Fallo simulado")
    assert not app.button(key="run").disabled


def test_app_bloquea_controles_mientras_procesa(tmp_path, monkeypatch):
    import anclaje.operaciones as operations

    root = Path(__file__).resolve().parents[1]
    conf = tmp_path / "config.yaml"
    conf.write_text(f"protocol: {(root / 'protocolo/v1.md').as_posix()}\n", encoding="utf-8")
    monkeypatch.setenv("ANCLAJE_CONFIG", str(conf))
    monkeypatch.setenv("ANCLAJE_DEMO", "true")
    app = AppTest.from_file(str(root / "app.py"), default_timeout=30).run()
    app.button(key="confirmar_salida").click().run()
    app.radio(key="paso_activo").set_value("Memoria").run()
    assert app.radio(key="paso_activo").value == "Inicio"
    assert any("consulta C" in item.value for item in app.warning)
    app.radio(key="paso_activo").set_value("Consultar").run()
    monkeypatch.setattr(operations, "ejecutar_pendiente", lambda: None)
    app.session_state["operacion_pendiente"] = ("Simulación", lambda: None)
    app.run()
    assert not app.exception
    assert all(button.disabled for button in app.button)
    assert all(radio.disabled for radio in app.radio)
    assert all(field.disabled for field in app.text_input)
    assert all(select.disabled for select in app.selectbox)
    del app.session_state["operacion_pendiente"]
    app.run()
    assert not app.button(key="confirmar_salida").disabled
