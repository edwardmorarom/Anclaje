import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dotenv import load_dotenv

ADVERTENCIA = (
    "ADVERTENCIA DE PRIVACIDAD: ALLOW_COUNTERPART_CLOUD=true. Los fragmentos y "
    "metadatos de contraparte seleccionados pueden enviarse a DeepSeek. "
    "Debe existir autorización escrita de la contraparte."
)


@dataclass(frozen=True)
class Config:
    root: Path
    docs_dir: Path
    index_dir: Path
    results_dir: Path
    protocol: Path
    embedding_model: str = "BAAI/bge-m3"
    chunk_size: int = 1000
    chunk_overlap: int = 150
    top_k: int = 4
    similarity_threshold: float = 0.45
    llm_model: str = "deepseek-chat"
    temperature: float = 0.0
    max_tokens: int = 1800
    timeout: float = 60.0
    allow_counterpart_cloud: bool = False
    api_key: str = field(default="", repr=False)
    sweep: dict = field(default_factory=dict)

    def __post_init__(self):
        if any(type(value) is not int for value in (self.chunk_size, self.chunk_overlap, self.top_k, self.max_tokens)):
            raise ValueError("Tamaño, solapamiento, top_k y max_tokens deben ser enteros.")
        if any(type(value) not in (int, float) for value in (self.similarity_threshold, self.temperature, self.timeout)):
            raise ValueError("Umbral, temperatura y tiempo de espera deben ser numéricos.")
        if not self.embedding_model or not isinstance(self.embedding_model, str) or not isinstance(self.llm_model, str) or not self.llm_model:
            raise ValueError("Los nombres de modelos deben ser textos no vacíos.")
        if not 0 <= self.chunk_overlap < self.chunk_size:
            raise ValueError("Se requiere 0 <= chunk_overlap < chunk_size.")
        if self.top_k < 1 or not -1 <= self.similarity_threshold <= 1:
            raise ValueError("top_k debe ser positivo y el umbral debe estar entre -1 y 1.")
        if not 0 <= self.temperature <= 2 or self.max_tokens < 1 or self.timeout <= 0:
            raise ValueError("Temperatura, límite de tokens o tiempo de espera inválidos.")


def cargar_config(path: str | Path = "config.yaml", *, advertir: bool = True) -> Config:
    path = Path(path).resolve()
    if not path.is_file():
        raise ValueError(f"No existe la configuración: {path}")
    root = path.parent
    load_dotenv(root / ".env", override=False)
    values = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(values, dict):
        raise ValueError("config.yaml debe contener un mapa de parámetros.")
    allowed = set(Config.__dataclass_fields__) - {"root", "api_key", "allow_counterpart_cloud"}
    unknown = set(values) - allowed
    if unknown:
        raise ValueError(f"Parámetros desconocidos: {', '.join(sorted(unknown))}")
    for name, default in (
        ("docs_dir", "docs"), ("index_dir", "indice"),
        ("results_dir", "resultados"), ("protocol", "protocolo/v1.md"),
    ):
        values[name] = (root / values.get(name, default)).resolve()
    values["llm_model"] = os.getenv("DEEPSEEK_MODEL") or values.get("llm_model", "deepseek-chat")
    values["api_key"] = os.getenv("DEEPSEEK_API_KEY", "")
    values["allow_counterpart_cloud"] = os.getenv("ALLOW_COUNTERPART_CLOUD", "false").lower() == "true"
    cfg = Config(root=root, **values)
    if cfg.allow_counterpart_cloud and advertir:
        print(ADVERTENCIA, file=sys.stderr)
    return cfg
