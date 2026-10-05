import csv
import hashlib
import itertools
import json
import math
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path

from .config import Config
from .embeddings import EmbeddingsLocales
from .fragmentos import fragmentar
from .indice import Indice
from .ingesta import leer_corpus
from .llm import ErrorLLM
from .responder import control, origenes_permitidos, responder


@dataclass(frozen=True)
class Pregunta:
    pregunta: str
    respuesta_conocida: str
    documento: str
    pagina: int | None
    tipo: str


def leer_banco(path: Path) -> list[Pregunta]:
    questions = []
    with Path(path).open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        required = {"pregunta", "respuesta_conocida", "documento", "pagina", "tipo"}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError("El banco necesita pregunta, respuesta_conocida, documento, pagina y tipo.")
        for number, row in enumerate(reader, 2):
            if None in row or any(row[key] is None for key in required):
                raise ValueError(f"Fila {number}: cantidad de columnas inválida.")
            row = {key: (value or "").strip() for key, value in row.items()}
            if not row["pregunta"] or row["tipo"] not in {"en_corpus", "fuera_de_corpus"}:
                raise ValueError(f"Fila {number}: pregunta vacía o tipo inválido.")
            try:
                page = int(row["pagina"]) if row["pagina"] else None
            except ValueError:
                raise ValueError(f"Fila {number}: pagina debe ser un entero.") from None
            if row["tipo"] == "en_corpus" and (
                not row["respuesta_conocida"] or not row["documento"] or not page or page < 1
            ):
                raise ValueError(f"Fila {number}: falta respuesta conocida o ubicación válida.")
            questions.append(Pregunta(
                row["pregunta"], row["respuesta_conocida"], row["documento"], page, row["tipo"],
            ))
    if not questions:
        raise ValueError("El banco está vacío.")
    return questions


def wilson(aciertos: int, n: int) -> dict:
    if n < 0 or not 0 <= aciertos <= n:
        raise ValueError("Se requiere 0 <= aciertos <= n.")
    if not n:
        return {"aciertos": 0, "n": 0, "proporcion": None, "ic95_inferior": None, "ic95_superior": None}
    z = 1.959963984540054
    p = aciertos / n
    denominator = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denominator
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denominator
    return {
        "aciertos": aciertos, "n": n, "proporcion": p,
        "ic95_inferior": max(0.0, center - margin), "ic95_superior": min(1.0, center + margin),
    }


def hit(pregunta: Pregunta, fragments) -> bool:
    return any(f.documento == pregunta.documento and f.pagina == pregunta.pagina for f in fragments)


def resumir(rows: list[dict]) -> list[dict]:
    summaries = []
    for treatment in ("A", "C"):
        planned = [r for r in rows if r["tratamiento"] == treatment]
        valid = [r for r in planned if not r["error"]]
        inside = [r for r in valid if r["tipo"] == "en_corpus"]
        outside = [r for r in valid if r["tipo"] == "fuera_de_corpus"]
        values = {
            "hit@k": [r["hit"] for r in inside] if treatment == "C" else [],
            "cita_verificada": [r["sostenida_por_fragmento"] for r in valid],
            "abstencion_correcta_fuera": [r["abstencion"] for r in outside],
            "invencion_fuera": [not r["abstencion"] for r in outside],
        }
        for metric, observations in values.items():
            summaries.append({
                "tratamiento": treatment, "metrica": metric,
                **wilson(sum(observations), len(observations)),
                "preguntas_programadas": len(planned), "errores": len(planned) - len(valid),
            })
    return summaries


def guardar_csv(path: Path, rows: list[dict]):
    if not rows:
        raise ValueError("No hay filas para guardar.")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def sello() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def evaluar(banco: Path, config: Config, indice, cliente, *, origen: str = "publicos") -> tuple[Path, list[dict]]:
    origins = origenes_permitidos(config, origen)
    questions = leer_banco(banco)
    if not config.allow_counterpart_cloud and any(q.documento.startswith("contraparte/") for q in questions):
        raise ValueError("El banco contiene preguntas de contraparte; evaluación en nube bloqueada.")
    if any(q.tipo == "en_corpus" and q.documento.split("/", 1)[0] not in origins for q in questions):
        raise ValueError("El banco incluye documentos fuera del origen elegido. Usa rutas relativas a docs.")
    rows = []
    for question in questions:
        for treatment in ("A", "C"):
            error = ""
            result = None
            try:
                result = control(question.pregunta, cliente) if treatment == "A" else responder(
                    question.pregunta, config, indice, cliente, origen=origen,
                )
                if result.motivo == "salida_json_invalida":
                    error = "Salida JSON inválida; excluida de métricas, requiere revisión."
            except (ErrorLLM, ValueError):
                error = "No se completó la consulta; revisa entorno, configuración o API."
            rows.append({
                "pregunta": question.pregunta, "respuesta_conocida": question.respuesta_conocida,
                "documento": question.documento, "pagina": question.pagina, "tipo": question.tipo,
                "tratamiento": treatment, "respuesta_obtenida": result.respuesta if result else "",
                "citas": json.dumps([asdict(c) for c in result.citas], ensure_ascii=False) if result else "[]",
                "sostenida_por_fragmento": result.sostenida_por_fragmento if result else False,
                "abstencion": result.abstencion if result else "",
                "hit": hit(question, result.fragmentos) if result else False,
                "revision_manual": "", "error": error,
                "cliente_llm": type(cliente).__name__, "origen_consulta": origen,
                "modelo_llm": config.llm_model, "modelo_embeddings": config.embedding_model,
                "chunk_size": config.chunk_size, "chunk_overlap": config.chunk_overlap,
                "top_k": config.top_k, "umbral": config.similarity_threshold,
                "temperatura": config.temperature, "protocolo": config.protocol.name,
                "protocolo_sha256": hashlib.sha256(config.protocol.read_bytes()).hexdigest(),
            })
    tag = sello()
    output = config.results_dir / f"evaluacion_{tag}.csv"
    summaries = resumir(rows)
    guardar_csv(output, rows)
    guardar_csv(config.results_dir / f"metricas_{tag}.csv", summaries)
    return output, summaries


def barrido(banco: Path, config: Config, *, embedder_factory=None) -> tuple[Path, list[dict]]:
    questions = [q for q in leer_banco(banco) if q.tipo == "en_corpus"]
    if not questions:
        raise ValueError("El barrido necesita preguntas en_corpus para medir hit@k.")
    sweep = config.sweep
    sizes = sweep.get("chunk_sizes", [600, 1000])
    ks = sweep.get("top_ks", [1, 4])
    models = sweep.get("embedding_models", ["BAAI/bge-m3", "intfloat/multilingual-e5-base"])
    if not sizes or not ks or not models:
        raise ValueError("El barrido necesita listas no vacías de tamaños, top_k y modelos.")
    for size, k in itertools.product(sizes, ks):
        replace(config, chunk_size=size, top_k=k)
    pages = leer_corpus(config.docs_dir)
    if not pages:
        raise ValueError("No hay páginas en el corpus.")
    factory = embedder_factory or (lambda name: EmbeddingsLocales(name, permitir_descarga=True))
    rows = []
    for model in models:
        embedder = factory(model)
        for size in sizes:
            digest = hashlib.sha256(f"{model}:{size}:{config.chunk_overlap}".encode()).hexdigest()[:16]
            index = Indice(config.index_dir / "barridos" / digest, embedder)
            fragments = fragmentar(pages, size, config.chunk_overlap)
            index.reconstruir(fragments, chunk_size=size, chunk_overlap=config.chunk_overlap)
            for k in ks:
                successes = sum(hit(q, index.consultar(q.pregunta, k, ("publicos", "contraparte"))) for q in questions)
                rows.append({
                    "chunk_size": size, "chunk_overlap": config.chunk_overlap,
                    "top_k": k, "embedding_model": model, "fragmentos": len(fragments),
                    "metrica": "hit@k", **wilson(successes, len(questions)),
                })
    output = config.results_dir / f"barrido_{sello()}.csv"
    guardar_csv(output, rows)
    return output, rows
