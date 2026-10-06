import json
from dataclasses import replace

import pytest

from anclaje.llm import ClienteDeepSeek, ClienteFalso, ErrorLLM
from anclaje.modelos import Fragmento
from anclaje.responder import ABSTENCION, control, interpretar, responder, verificar_citas


def fragmento(origen="publicos", similitud=0.9):
    text = "La estadística descriptiva resume los datos." if origen == "publicos" else "SECRETO SINTÉTICO CONTRAPARTE"
    return Fragmento(origen, f"{origen}/a.pdf", 3, origen, text, similitud)


class IndiceFalso:
    def __init__(self, fragments):
        self.fragments = fragments
        self.origenes = None

    def consultar(self, pregunta, top_k, origenes):
        self.origenes = origenes
        return self.fragments[:top_k]


def test_citas_normalizadas_reales_e_inventadas():
    sources = [fragmento()]
    raw = [
        {"documento": "publicos/a.pdf", "pagina": 3, "cita_textual": "ESTADISTICA  descriptiva"},
        {"documento": "publicos/a.pdf", "pagina": 3, "cita_textual": "La luna es de queso."},
        {"documento": "publicos/a.pdf", "pagina": 4, "cita_textual": "resume los datos"},
        {"documento": "publicos/a.pdf", "pagina": 3, "cita_textual": "  "},
        {"documento": "publicos/otro.pdf", "pagina": 3, "cita_textual": "resume los datos"},
    ]
    cites = verificar_citas(raw, sources)
    assert [c.estado for c in cites] == ["verificada"] + ["no_verificada"] * 4
    assert cites[0].fragmento == sources[0].texto


@pytest.mark.parametrize("fragments", [[], [fragmento(similitud=0.1)]])
def test_sin_umbral_no_llama_llm(config, fragments):
    client = ClienteFalso()
    result = responder("¿Qué es estadística?", config, IndiceFalso(fragments), client)
    assert result.abstencion and result.respuesta == ABSTENCION
    assert client.llamadas == []


def test_sin_citas_verificadas_se_abstiene(config):
    client = ClienteFalso({
        "respuesta": "Respuesta inventada.", "abstencion": False,
        "citas": [{"documento": "publicos/a.pdf", "pagina": 3, "cita_textual": "Dato inventado"}],
    })
    result = responder("Pregunta", config, IndiceFalso([fragmento()]), client)
    assert result.respuesta == ABSTENCION
    assert result.citas[0].estado == "no_verificada"
    assert not result.sostenida_por_fragmento


def test_cita_bajo_umbral_no_se_verifica(config):
    sources = [fragmento(), Fragmento("b", "publicos/b.pdf", 2, "publicos", "dato excluido", 0.1)]
    client = ClienteFalso({"respuesta": "dato excluido", "abstencion": False, "citas": [
        {"documento": "publicos/b.pdf", "pagina": 2, "cita_textual": "dato excluido"},
    ]})
    result = responder("Pregunta", config, IndiceFalso(sources), client)
    assert result.abstencion and result.citas[0].estado == "no_verificada"
    assert len(result.fragmentos) == 2


def test_privacidad_filtro_antes_de_enviar_a_llm(config):
    index = IndiceFalso([fragmento("contraparte"), fragmento()])
    client = ClienteFalso()
    result = responder("Pregunta", config, index, client)
    assert index.origenes == ("publicos",)
    assert result.sostenida_por_fragmento
    assert all(f.origen == "publicos" for f in result.fragmentos)
    assert "SECRETO" not in json.dumps(client.llamadas)
    assert "contraparte" not in client.llamadas[0][-1]["content"]


@pytest.mark.parametrize("origen", ["ambos", "contraparte"])
def test_selector_no_habilita_contraparte(config, origen):
    client = ClienteFalso()
    with pytest.raises(ValueError, match="bloqueada"):
        responder("Pregunta", config, IndiceFalso([fragmento("contraparte")]), client, origen=origen)
    assert not client.llamadas


def test_contraparte_con_flag_explicito(config):
    client = ClienteFalso()
    result = responder("Pregunta", replace(config, allow_counterpart_cloud=True), IndiceFalso([fragmento("contraparte")]), client, origen="contraparte")
    assert result.sostenida_por_fragmento
    assert "SECRETO" in json.dumps(client.llamadas, ensure_ascii=False)


@pytest.mark.parametrize("raw", ["", "no json", [], {}, {"respuesta": "x", "abstencion": "false", "citas": []},
    {"respuesta": "x", "abstencion": False, "citas": [{"documento": "a", "pagina": True, "cita_textual": "x"}]}])
def test_json_invalido_abstencion(raw):
    result = interpretar(raw, [fragmento()])
    assert result.abstencion and result.motivo == "salida_json_invalida"


def test_abstencion_del_modelo_usa_frase_fija():
    result = interpretar({"respuesta": "No sé.", "abstencion": True, "citas": []}, [])
    assert result.respuesta == ABSTENCION


def test_deepseek_no_inicia_cliente_sin_clave(config):
    client = ClienteDeepSeek(config)
    with pytest.raises(ErrorLLM, match="Falta"):
        client.generar([])
    assert client._client is None


def test_control_conserva_citas_para_revision_sin_verificarlas():
    client = ClienteFalso({
        "respuesta": "Respuesta del control.", "abstencion": False,
        "citas": [{"documento": "inventado.pdf", "pagina": 1, "cita_textual": "Referencia del control"}],
    })
    result = control("Pregunta", client)
    assert not result.abstencion and not result.sostenida_por_fragmento
    assert result.citas[0].estado == "no_verificada"


def test_cliente_deepseek_json_y_temperatura_con_transporte_falso(config):
    from types import SimpleNamespace

    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content='{"respuesta":"No está en las fuentes.","abstencion":true,"citas":[]}'))])

    client = ClienteDeepSeek(replace(config, api_key=object()))
    client._client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    client.generar([{"role": "system", "content": "Devuelve json."}])
    assert calls[0]["response_format"] == {"type": "json_object"}
    assert calls[0]["temperature"] == 0.0
    assert calls[0]["extra_body"] == {"thinking": {"type": "disabled"}}
