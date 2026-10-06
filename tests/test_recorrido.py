from dataclasses import asdict

import pytest

from anclaje.embeddings import EmbedderFalso
from anclaje.indice import Indice
from anclaje.recorrido import agregar_pregunta, guardar_banco, importar_banco, resumen_banco, ruta_banco, estado_proyecto


def test_estado_inicial_no_confunde_clave_con_conexion(config):
    index = Indice(config.index_dir, EmbedderFalso())
    status = estado_proyecto(config, index)
    assert status["documentos"] == [] and not status["indice_listo"]
    assert not status["clave_configurada"] and not status["banco_existe"]


def test_preguntas_persisten_y_validacion_no_destruye_banco(config):
    first = {"pregunta": "¿Qué es la media?", "respuesta_conocida": "Suma entre n.",
             "documento": "publicos/a.pdf", "pagina": 1, "tipo": "en_corpus"}
    questions = agregar_pregunta(config, first)
    assert len(questions) == 1
    original = ruta_banco(config).read_bytes()
    with pytest.raises(ValueError):
        agregar_pregunta(config, {**first, "pagina": 0})
    assert ruta_banco(config).read_bytes() == original
    with pytest.raises(ValueError):
        importar_banco(config, b"archivo,incorrecto\na,b")
    assert ruta_banco(config).read_bytes() == original
    outside = {"pregunta": "¿Cuántas personas viven en Marte?", "respuesta_conocida": "No está en las fuentes.",
               "documento": "", "pagina": None, "tipo": "fuera_de_corpus"}
    questions = agregar_pregunta(config, outside)
    assert resumen_banco(questions) == {"total": 2, "fuera": 1, "completo_para_actividad": False}


def test_banco_demo_no_sobreescribe_banco_real(config):
    row = {"pregunta": "Prueba", "respuesta_conocida": "No está en las fuentes.", "documento": "", "pagina": None, "tipo": "fuera_de_corpus"}
    guardar_banco(config, [row])
    original = ruta_banco(config).read_bytes()
    guardar_banco(config, [{**row, "pregunta": "Otra prueba"}], demo=True)
    assert ruta_banco(config).read_bytes() == original
    assert ruta_banco(config, True) != ruta_banco(config)


def test_banco_completo_exige_preguntas_fuera(config):
    row = {"pregunta": "Media", "respuesta_conocida": "Suma entre n", "documento": "publicos/a.txt", "pagina": 1, "tipo": "en_corpus"}
    inside = guardar_banco(config, [{**row, "pregunta": f"Pregunta {n}"} for n in range(15)])
    assert not resumen_banco(inside)["completo_para_actividad"]
    outside = [{"pregunta": f"Fuera {n}", "respuesta_conocida": "No está en las fuentes.", "documento": "", "pagina": None, "tipo": "fuera_de_corpus"} for n in range(3)]
    questions = guardar_banco(config, [*[asdict(q) for q in inside], *outside])
    assert resumen_banco(questions)["completo_para_actividad"]
