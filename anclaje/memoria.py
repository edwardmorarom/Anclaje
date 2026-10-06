import json
from pathlib import Path

TRATAMIENTOS = {
    "A": ("Harold", "Chat sin fuentes ni navegación"),
    "B": ("Natalia", "Buscador conectado a bases bibliográficas reales"),
    "C": ("Edward", "Contexto cerrado con sus propios documentos"),
}
APARTADOS = (
    ("diagnostico", "Diagnóstico", "Qué les inventó la IA, cómo lo detectaron y qué les costó."),
    ("experimento", "Experimento y decisión", "Conteos por tratamiento, proporciones con intervalo, acuerdo de clasificación y herramienta elegida frente a las descartadas."),
    ("sistema", "El sistema", "Cómo quedó montado y por qué: embeddings, tamaño de fragmento y número recuperado, cada decisión comparada con su alternativa."),
    ("evaluacion", "Evaluación", "Medición por tratamiento, caso de fallo y su causa, y hallazgos de la auditoría cruzada."),
    ("correcciones", "Qué corrigieron de su propio anteproyecto", "Afirmación concreta que no tenía soporte, ubicación en el anteproyecto y corrección realizada."),
    ("uso_ia", "Declaración de uso de IA", "Herramientas y versiones, para qué se usaron, alternativas descartadas, qué no delegaron y qué corrigieron de lo generado."),
)


def reconocer_tratamiento(carpeta: str | Path, relativo: str) -> str | None:
    components = [Path(carpeta).name, *Path(relativo).parts[:-1]]
    names = {person.casefold(): treatment for treatment, (person, _) in TRATAMIENTOS.items()}
    for component in reversed(components):
        if component.casefold() in names:
            return names[component.casefold()]
    return None


def destino_tratamiento(config, tratamiento: str) -> Path:
    if tratamiento not in TRATAMIENTOS:
        raise ValueError("Tratamiento inválido.")
    return config.docs_dir if tratamiento == "C" else config.results_dir / "evidencias" / tratamiento


def cargar_memoria(path: Path) -> dict:
    if not path.exists():
        return {key: "" for key, _, _ in APARTADOS}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or any(not isinstance(data.get(key, ""), str) for key, _, _ in APARTADOS):
        raise ValueError("El borrador de memoria no tiene el formato esperado.")
    return {key: data.get(key, "") for key, _, _ in APARTADOS}


def guardar_memoria(path: Path, contenido: dict):
    data = {key: contenido.get(key, "") for key, _, _ in APARTADOS}
    if any(not isinstance(value, str) for value in data.values()):
        raise ValueError("Cada apartado de la memoria debe ser texto.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def exportar_memoria(contenido: dict) -> str:
    blocks = ["# Memoria — Nada sin fuente", "Borrador de trabajo. Extensión final requerida: 2 a 4 páginas."]
    for key, title, _ in APARTADOS:
        blocks.append(f"## {title}\n\n{contenido.get(key, '').strip() or '[Pendiente de completar con evidencia real]'}")
    return "\n\n".join(blocks) + "\n"
