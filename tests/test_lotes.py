import csv
import io
import json
from pathlib import Path

import pytest

from anclaje.embeddings import EmbedderFalso
from anclaje.llm import ClienteFalso, ErrorLLM
from anclaje.lotes import analizar_fila, cargar_memoria_agente, candidatos_informe, comparar_significado, exportar_csv, guardar_memoria_agente


def test_comparacion_semantica_envia_significado_y_conserva_motivo():
    client = ClienteFalso({"coincidencia": "Coincide", "explicacion": "Ambas expresan la suma dividida por el número de datos."})
    result = comparar_significado("¿Cómo se calcula la media?", "Suma dividida por n", "Sumar los valores y dividir por la cantidad de observaciones", client)
    assert result["coincidencia"] == "Coincide"
    payload = json.loads(client.llamadas[0][1]["content"])
    assert payload["respuesta_conocida"] != payload["respuesta_obtenida"]
    assert "negaciones" in client.llamadas[0][0]["content"]
    assert result["explicacion"]


@pytest.mark.parametrize("output", ["no json", {}, {"coincidencia": "Coincide", "explicacion": ""}, {"coincidencia": True}])
def test_comparacion_invalida_no_se_cuenta_como_coincidencia(output):
    assert comparar_significado("q", "esperada", "obtenida", ClienteFalso(output))["coincidencia"] == "Revisar"


def test_sin_conocida_no_llama_comparador():
    client = ClienteFalso()
    assert comparar_significado("q", " ", "a", client)["coincidencia"] == "Sin respuesta conocida"
    assert not client.llamadas


def test_csv_punto_y_coma_textos_multilinea_y_formulas():
    data = exportar_csv([{"pregunta": "¿Cuál; cómo?", "respuesta": "Una línea\notra; más", "respuesta_conocida": "=1+1", "coincidencia": "Revisar"}])
    assert data.startswith(b"\xef\xbb\xbf")
    row = next(csv.DictReader(io.StringIO(data.decode("utf-8-sig")), delimiter=";"))
    assert row["pregunta"] == "¿Cuál; cómo?" and row["respuesta"] == "Una línea\notra; más"
    assert row["respuesta_conocida"] == "'=1+1"


def test_memoria_json_persiste_entre_sesiones_y_rechaza_corrupcion(tmp_path):
    path = tmp_path / "agente/memoria.json"
    guardar_memoria_agente(path, {"preguntas": [{"Pregunta": "¿Dónde?"}], "resultados": [{"coincidencia": "Revisar"}]})
    memory = cargar_memoria_agente(path)
    assert memory["preguntas"][0]["Pregunta"] == "¿Dónde?" and memory["version"] == 1
    assert not path.with_suffix(".tmp.json").exists()
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="memoria"):
        cargar_memoria_agente(path)


def test_ubicacion_informe_conserva_pagina_y_reutiliza_vectores(tmp_path):
    report = tmp_path / "informe.txt"
    report.write_text("Introducción general\fmedia aritmética suma número observaciones", encoding="utf-8")
    cache = {}
    embedder = EmbedderFalso()
    first = candidatos_informe(report, "media aritmética", "suma número observaciones", embedder, cache)
    assert first[0]["pagina"] == 2
    report.unlink()
    assert candidatos_informe(report, "media aritmética", "suma número observaciones", embedder, cache) == first


def test_fallo_comparador_conserva_respuesta_y_se_marca_revisar(config):
    class Client:
        def __init__(self):
            self.calls = 0

        def generar(self, messages):
            self.calls += 1
            if self.calls == 1:
                return {"respuesta": "Sumar y dividir entre n", "abstencion": False, "citas": []}
            raise ErrorLLM("Sin conexión")

    result = analizar_fila({"Pregunta": "¿Cómo calcular la media?", "Respuesta conocida": "Suma dividida entre n"}, config, None, Client(), tratamiento="A")
    assert result["respuesta"] == "Sumar y dividir entre n"
    assert result["coincidencia"] == "Revisar" and result["explicacion"] == "Sin conexión"


def test_informe_ilegible_no_bloquea_consultas_y_cache_permite_reintentar(tmp_path):
    cache = {}
    with pytest.raises(ValueError, match="informe"):
        candidatos_informe(tmp_path / "ausente.pdf", "q", "a", EmbedderFalso(), cache)
    assert not cache
    report = tmp_path / "informe.txt"
    report.write_text("dato", encoding="utf-8")
    assert candidatos_informe(report, "dato", "dato", EmbedderFalso(), cache)[0]["pagina"] == 1


def test_tabla_demo_analiza_guarda_y_reabre_memoria(tmp_path, monkeypatch):
    from streamlit.testing.v1 import AppTest

    root = Path(__file__).resolve().parents[1]
    config = tmp_path / "config.yaml"
    config.write_text(f"protocol: {(root / 'protocolo/v1.md').as_posix()}\n", encoding="utf-8")
    monkeypatch.setenv("ANCLAJE_CONFIG", str(config))
    monkeypatch.setenv("ANCLAJE_DEMO", "true")
    guardar_memoria_agente(tmp_path / "resultados/humo/agente/memoria.json", {"preguntas": [
        {"Pregunta": "media aritmética suma valores número observaciones", "Respuesta conocida": "Suma dividida por n", "Página informe confirmada": ""},
        {"Pregunta": "Otra pregunta", "Respuesta conocida": "Sin datos", "Página informe confirmada": ""},
    ]})
    app = AppTest.from_file(str(root / "app.py"), default_timeout=30).run()
    app.radio(key="paso_activo").set_value("Consultar").run()
    app.radio(key="espacio_consulta").set_value("Tabla de preguntas").run()
    assert not app.exception and not app.error
    assert not app.button(key="analizar_lote").disabled
    app.button(key="analizar_lote").click().run()
    assert not app.exception and not app.error
    paths = list(tmp_path.rglob("agente/memoria.json"))
    assert len(paths) == 1
    saved = cargar_memoria_agente(paths[0])
    assert len(saved["resultados"]) == 2 and saved["resultados"][0]["coincidencia"] == "Revisar"
    app.radio(key="paso_activo").set_value("Inicio").run()
    app.radio(key="paso_activo").set_value("Consultar").run()
    assert app.radio(key="espacio_consulta").value == "Tabla de preguntas"
    assert not app.exception
    fresh = AppTest.from_file(str(root / "app.py"), default_timeout=30).run()
    fresh.radio(key="paso_activo").set_value("Consultar").run()
    fresh.radio(key="espacio_consulta").set_value("Tabla de preguntas").run()
    assert fresh.session_state["lote_memoria"]["resultados"] == saved["resultados"]
