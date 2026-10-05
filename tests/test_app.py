from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_app_demo_consulta_y_privacidad(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[1]
    config = tmp_path / "config.yaml"
    config.write_text(f"protocol: {(root / 'protocolo/v1.md').as_posix()}\n", encoding="utf-8")
    monkeypatch.setenv("ANCLAJE_CONFIG", str(config))
    monkeypatch.setenv("ANCLAJE_DEMO", "true")
    app = AppTest.from_file(str(root / "app.py"), default_timeout=30).run()
    assert not app.exception
    assert any("Demostración" in item.value for item in app.warning)
    app.text_input[0].set_value("media aritmética suma valores número observaciones")
    app.button[0].click().run()
    assert not app.exception and not app.error
    assert any("verificada" in item.label for item in app.expander)
    assert any("La media aritmética" in item.value for item in app.markdown)
    app.selectbox[0].select("contraparte")
    app.button[0].click().run()
    assert not app.exception
    assert any("bloqueada" in item.value for item in app.error)
