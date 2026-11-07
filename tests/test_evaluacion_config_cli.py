import csv
import json
from dataclasses import replace
from pathlib import Path

import pytest

from anclaje.cli import main
from anclaje.config import cargar_config
from anclaje.embeddings import EmbedderFalso
from anclaje.evaluar import barrido, evaluar, guardar_csv, leer_banco, wilson
from anclaje.llm import ClienteFalso, ErrorLLM
from anclaje.modelos import Fragmento


@pytest.mark.parametrize("successes,n,low,high", [
    (0, 10, 0.0, 0.2775327999),
    (10, 10, 0.7224672001, 1.0),
    (5, 10, 0.2365930905, 0.7634069095),
    (50, 100, 0.4038315304, 0.5961684696),
])
def test_wilson_valores_conocidos(successes, n, low, high):
    result = wilson(successes, n)
    assert result["n"] == n and result["proporcion"] == successes / n
    assert result["ic95_inferior"] == pytest.approx(low, abs=1e-9)
    assert result["ic95_superior"] == pytest.approx(high, abs=1e-9)


def test_wilson_sin_datos_e_invalido():
    assert wilson(0, 0)["proporcion"] is None
    with pytest.raises(ValueError):
        wilson(11, 10)


def banco(path, *, counterpart=False):
    prefix = "contraparte" if counterpart else "publicos"
    folder = path.parent / 'docs' / prefix
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'a.txt').write_text('media suma entre n\fmediana valor central', encoding='utf-8')
    rows = [
        {"pregunta": "media", "respuesta_conocida": "suma entre n", "documento": f"{prefix}/a.txt", "pagina": 1, "tipo": "en_corpus"},
        {"pregunta": "mediana", "respuesta_conocida": "valor central", "documento": f"{prefix}/a.txt", "pagina": 2, "tipo": "en_corpus"},
        {"pregunta": "Marte", "respuesta_conocida": "No está en las fuentes.", "documento": "", "pagina": "", "tipo": "fuera_de_corpus"},
    ]
    guardar_csv(path, rows)
    return path


class IndiceFalso:
    def consultar(self, question, top_k, origins):
        if question == "Marte":
            return []
        page = 1 if question == "media" else 2
        return [Fragmento(str(page), "publicos/a.txt", page, "publicos", "media suma entre n; mediana valor central", 0.9)]


def test_evaluacion_ac_control_sin_degradar_y_metricas(config):
    path = banco(config.root / "banco.csv")
    client = ClienteFalso()
    output, metrics = evaluar(path, config, IndiceFalso(), client)
    with output.open(encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file, delimiter=';'))
    assert len(rows) == 6
    assert all(row["revision_manual"] == "" for row in rows)
    assert all("protocolo_sha256" in row for row in rows)
    summary = {(r["tratamiento"], r["metrica"]): r for r in metrics}
    assert summary["C", "hit@k"]["aciertos"] == 2
    assert summary["C", "hit@k"]["n"] == 2
    assert summary["C", "citas_textuales_validas"]["proporcion"] == pytest.approx(2 / 3)
    assert summary["C", "fidelidad_revisada"]["n"] == 0
    assert summary["C", "abstencion_correcta_fuera"]["proporcion"] == 1
    assert summary["C", "respuesta_fuera_sin_abstencion"]["proporcion"] == 0
    assert summary["A", "hit@k"]["n"] == 0


def test_control_respuesta_sin_citas_cuenta_invencion(config):
    path = banco(config.root / "banco.csv")
    client = ClienteFalso({"respuesta": "Respuesta sin soporte", "abstencion": False, "citas": []})
    _, metrics = evaluar(path, config, IndiceFalso(), client)
    summary = {(r["tratamiento"], r["metrica"]): r for r in metrics}
    assert summary["A", "respuesta_fuera_sin_abstencion"]["proporcion"] == 1
    assert summary["C", "respuesta_fuera_sin_abstencion"]["proporcion"] == 0


def test_errores_api_no_cuentan_como_abstencion_correcta(config):
    class Client:
        def generar(self, messages):
            raise ErrorLLM("fallo sintético")

    path = banco(config.root / "banco.csv")
    output, metrics = evaluar(path, config, IndiceFalso(), Client())
    a = next(r for r in metrics if r["tratamiento"] == "A" and r["metrica"] == "abstencion_correcta_fuera")
    assert a["n"] == 0 and a["errores"] == 3
    assert "fallo sintético" not in output.read_text(encoding="utf-8-sig")


def test_evaluacion_privada_bloqueada_antes_del_control(config):
    client = ClienteFalso()
    with pytest.raises(ValueError, match="contraparte"):
        evaluar(banco(config.root / "banco.csv", counterpart=True), config, IndiceFalso(), client)
    assert client.llamadas == []


def test_banco_invalido(tmp_path):
    path = tmp_path / "banco.csv"
    path.write_text("pregunta,tipo\nx,en_corpus", encoding="utf-8")
    with pytest.raises(ValueError, match="necesita"):
        leer_banco(path)


def test_barrido_local_no_reemplaza_indice_principal(config):
    docs = config.docs_dir / "publicos"
    docs.mkdir(parents=True)
    (docs / "a.txt").write_text("media suma entre n\fmediana valor central", encoding="utf-8")
    (config.docs_dir / "PROCEDENCIA.md").write_text("| publicos/a.txt | publicos |", encoding="utf-8")
    bank = banco(config.root / "banco.csv")
    sweep = {"chunk_sizes": [20, 30], "top_ks": [1, 2], "embedding_models": ["falso-a", "falso-b"]}
    cfg = replace(config, chunk_overlap=3, sweep=sweep)
    output, rows = barrido(bank, cfg, embedder_factory=lambda name: EmbedderFalso())
    assert len(rows) == 8
    assert all(r["n"] == 2 and r["proporcion"] == 1.0 for r in rows)
    assert output.exists()
    assert not (config.index_dir / "chroma.sqlite3").exists()


def test_config_rutas_env_y_clave_oculta(tmp_path, monkeypatch, capsys):
    path = tmp_path / "config.yaml"
    path.write_text("top_k: 3\n", encoding="utf-8")
    monkeypatch.setenv("ALLOW_COUNTERPART_CLOUD", "true")
    cfg = cargar_config(path)
    assert cfg.allow_counterpart_cloud and cfg.top_k == 3
    assert cfg.docs_dir == tmp_path / "docs"
    assert "ADVERTENCIA DE PRIVACIDAD" in capsys.readouterr().err
    assert "api_key" not in repr(cfg)
    path.write_text("allow_counterpart_cloud: true\n", encoding="utf-8")
    with pytest.raises(ValueError, match="desconocidos"):
        cargar_config(path)


def test_humo_cli_sin_red(tmp_path, capsys):
    protocol = Path(__file__).resolve().parents[1] / "protocolo" / "v1.md"
    path = tmp_path / "config.yaml"
    path.write_text(f"protocol: {protocol.as_posix()}\n", encoding="utf-8")
    assert main(["--config", str(path), "humo"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["estado"].startswith("OK")
    assert output["respuesta"]["abstencion"] is False
    assert output["respuesta"]["citas"][0]["estado"] == "verificada"


@pytest.mark.parametrize("parameter", ["top_k: true", "chunk_size: texto", "temperature: alta"])
def test_config_rechaza_tipos_invalidos(tmp_path, parameter):
    path = tmp_path / "config.yaml"
    path.write_text(parameter, encoding="utf-8")
    with pytest.raises(ValueError):
        cargar_config(path)


def test_cli_recorrido_completo_con_documentos_sinteticos(tmp_path, monkeypatch, capsys):
    import anclaje.cli as cli

    monkeypatch.setattr(cli, "EmbeddingsLocales", lambda *args, **kwargs: EmbedderFalso())
    protocol = Path(__file__).resolve().parents[1] / "protocolo" / "v1.md"
    config = tmp_path / "config.yaml"
    config.write_text(f"embedding_model: falso-local-v1\nprotocol: {protocol.as_posix()}\n", encoding="utf-8")
    for origin in ("publicos", "contraparte"):
        (tmp_path / "docs" / origin).mkdir(parents=True)
    (tmp_path / "docs/publicos/a.txt").write_text("media suma entre n\fmediana valor central", encoding="utf-8")
    (tmp_path / "docs/contraparte/a.txt").write_text("PRIVADO LOCAL", encoding="utf-8")
    (tmp_path / "docs/PROCEDENCIA.md").write_text("| publicos/a.txt |\n| contraparte/a.txt |", encoding="utf-8")
    prefix = ["--config", str(config)]
    assert main([*prefix, "reindexar"]) == 0
    capsys.readouterr()
    assert main([*prefix, "buscar", "PRIVADO LOCAL"]) == 0
    assert "contraparte/a.txt" in capsys.readouterr().out
    assert main([*prefix, "preguntar", "media suma entre n", "--falso", "--json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["citas"][0]["estado"] == "verificada"
    assert all(f["origen"] == "publicos" for f in result["fragmentos"])
    assert main([*prefix, "preguntar", "PRIVADO LOCAL", "--origen", "contraparte", "--falso"]) == 2
    assert "bloqueada" in capsys.readouterr().err
    bank = banco(tmp_path / "banco.csv")
    assert main([*prefix, "evaluar", str(bank), "--falso"]) == 0
    capsys.readouterr()
    output = next((tmp_path / "resultados").glob("evaluacion_*.csv"))
    with output.open(encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file, delimiter=';'))
    assert len(rows) == 6 and all(r["modelo_llm"] == "cliente-falso" for r in rows)
