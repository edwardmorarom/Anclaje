"""Requisitos del recorrido y comprobantes vinculados al corpus actual."""
import hashlib
import json
from pathlib import Path

from .memoria import APARTADOS, cargar_memoria
from .recorrido import PASOS


def firma_corpus(config, demo=False):
    if demo:
        return "demo-v1"
    rows = [f"{p.relative_to(config.docs_dir)}:{p.stat().st_size}:{p.stat().st_mtime_ns}"
            for origin in ("publicos", "contraparte") for p in sorted((config.docs_dir / origin).rglob("*"))
            if p.is_file() and p.suffix.lower() in {".pdf", ".docx", ".md", ".txt"}]
    rows += [config.embedding_model, str(config.chunk_size), str(config.chunk_overlap)]
    rows += [str(config.top_k), str(config.similarity_threshold), config.llm_model,
             config.protocol.read_text(encoding="utf-8")]
    return hashlib.sha256("\n".join(rows).encode()).hexdigest()


def ruta_flujo(config, demo=False):
    return config.results_dir / ("humo/recorrido.json" if demo else "recorrido.json")


def cargar_avance(config, demo=False):
    path = ruta_flujo(config, demo)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) and data.get("firma") == firma_corpus(config, demo) else {}
    except (ValueError, OSError):
        return {}


def marcar_avance(config, etapa, demo=False):
    data = cargar_avance(config, demo)
    data.update(firma=firma_corpus(config, demo))
    data[etapa] = True
    if etapa == "evaluacion":
        from .recorrido import ruta_banco
        bank = ruta_banco(config, demo)
        data["banco_firma"] = hashlib.sha256(bank.read_bytes()).hexdigest() if bank.exists() else ""
    if etapa == "consulta":
        data.pop("evaluacion", None)
    path = ruta_flujo(config, demo)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp.json")
    temporary.write_text(json.dumps(data, indent=2), encoding="utf-8")
    temporary.replace(path)


def invalidar_avance(config, etapa, demo=False):
    data = cargar_avance(config, demo)
    data.pop("evaluacion", None)
    if etapa == "consulta":
        data.pop("consulta", None)
    path = ruta_flujo(config, demo)
    if path.exists():
        temporary = path.with_suffix(".tmp.json")
        temporary.write_text(json.dumps(data, indent=2), encoding="utf-8")
        temporary.replace(path)


def estado_flujo(config, estado, salida_lista, demo=False):
    advance = cargar_avance(config, demo)
    sources = bool(estado["documentos"]) or demo
    ready = estado["indice_listo"]
    query = ready and bool(advance.get("consulta"))
    from .recorrido import ruta_banco
    bank = ruta_banco(config, demo)
    bank_hash = hashlib.sha256(bank.read_bytes()).hexdigest() if bank.exists() else ""
    evaluation = query and bool(advance.get("evaluacion")) and advance.get("banco_firma") == bank_hash
    try:
        memory = cargar_memoria(config.results_dir / "memoria/borrador.json")
        written = all(memory.get(key, "").strip() for key, _, _ in APARTADOS)
    except (ValueError, OSError):
        written = False
    complete = dict(zip(PASOS, [salida_lista, salida_lista and sources, salida_lista and sources and ready,
                               salida_lista and query, salida_lista and evaluation, salida_lista and evaluation and written]))
    enabled, reasons = {}, {}
    prerequisites = [True, salida_lista, salida_lista and sources, salida_lista and sources and ready,
                     salida_lista and sources and query, salida_lista and sources and evaluation]
    for step, allowed in zip(PASOS, prerequisites):
        enabled[step] = allowed
        if not salida_lista:
            reasons[step] = "Confirma la carpeta de salida en Inicio."
        elif not sources:
            reasons[step] = "Importa al menos un documento de Edward/C en Fuentes."
        elif not ready:
            reasons[step] = "Prepara el índice de las fuentes actuales en Preparar."
        elif not query:
            reasons[step] = "Ejecuta una consulta C antes de pasar a Evaluar."
        elif not evaluation:
            reasons[step] = "Ejecuta una evaluación sin errores antes de pasar a Memoria."
        else:
            reasons[step] = ""
    return {"completados": complete, "habilitados": enabled, "motivos": reasons}


def primer_pendiente(flujo):
    return next((p for p in PASOS if flujo["habilitados"][p] and not flujo["completados"][p]), "Memoria")
