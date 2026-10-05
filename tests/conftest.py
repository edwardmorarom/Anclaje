import socket
from pathlib import Path

import pytest

from anclaje.config import Config


@pytest.fixture(autouse=True)
def sin_red_ni_clave(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Las pruebas no pueden usar la red.")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_MODEL", raising=False)
    monkeypatch.setenv("ALLOW_COUNTERPART_CLOUD", "false")
    monkeypatch.setenv("ANONYMIZED_TELEMETRY", "False")
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    monkeypatch.setenv("TRANSFORMERS_OFFLINE", "1")


@pytest.fixture
def config(tmp_path):
    protocol = Path(__file__).resolve().parents[1] / "protocolo" / "v1.md"
    return Config(
        root=tmp_path, docs_dir=tmp_path / "docs", index_dir=tmp_path / "indice",
        results_dir=tmp_path / "resultados", protocol=protocol,
    )
