import csv
import hashlib
import itertools
import json
import math
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone, date
from pathlib import Path

from .config import Config
from .embeddings import EmbeddingsLocales
from .fragmentos import fragmentar
from .indice import Indice
from .ingesta import leer_corpus
from .llm import ErrorLLM, ClienteFalso
from .responder import control, origenes_permitidos, responder
from .responder import texto_literal
from .exportaciones import guardar_tabla, csv_bytes, avisos_unicode
from .ingesta import leer_archivo


@dataclass(frozen=True)
class Pregunta:
    pregunta: str
    respuesta_conocida: str
    documento: str
    pagina: int | None
    tipo: str
    cita_conocida: str = ""
    clave_gestor: str = ""
    verificado_por: str = ""
    fecha_verificacion: str = ""
    afirmacion_informe: str = ""
    pagina_informe_confirmada: str = ""


def leer_banco(path: Path) -> list[Pregunta]:
    questions = []
    with Path(path).open(encoding="utf-8-sig", newline="") as file:
        header = file.readline()
        file.seek(0)
        reader = csv.DictReader(file, delimiter=";" if header.count(";") > header.count(",") else ",")
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
                *(row.get(key, "") for key in ("cita_conocida", "clave_gestor", "verificado_por", "fecha_verificacion",
                                               "afirmacion_informe", "pagina_informe_confirmada")),
            ))
    if not questions:
        raise ValueError("El banco está vacío.")
    return questions


def validar_banco(questions, docs_dir, *, entrega=False):
    """Comprueba ubicación real antes de consultar; una cita literal no valida la respuesta conocida."""
    root = Path(docs_dir).resolve()
    if entrega and not (15 <= len(questions) <= 20 and sum(q.tipo == "fuera_de_corpus" for q in questions) >= 3):
        raise ValueError("La entrega requiere 15–20 preguntas y al menos tres fuera del corpus.")
    if len({texto_literal(q.pregunta) for q in questions}) != len(questions):
        raise ValueError("El banco contiene preguntas repetidas.")
    if entrega:
        cantidad = len({hashlib.sha256(p.read_bytes()).digest() for origin in ("publicos", "contraparte")
                        for p in (root / origin).rglob("*") if p.is_file() and not p.is_symlink()
                        and p.suffix.lower() in {".pdf", ".docx", ".txt", ".md"}})
        if not 10 <= cantidad <= 40:
            raise ValueError("La entrega requiere un corpus de 10–40 documentos; no agregues duplicados para completar el número.")
    cache = {}
    for q in questions:
        if q.tipo == "fuera_de_corpus":
            if q.documento or q.pagina:
                raise ValueError("Las preguntas fuera del corpus deben tener ubicación vacía.")
            if not q.respuesta_conocida.strip():
                raise ValueError("Las preguntas fuera del corpus requieren una respuesta conocida de abstención.")
            continue
        archivo = (root / q.documento).resolve()
        if not archivo.is_relative_to(root) or not archivo.is_file():
            raise ValueError(f"Documento del banco inexistente o fuera del corpus: {q.documento}")
        if q.documento not in cache:
            cache[q.documento] = {p.pagina: p.texto for p in leer_archivo(archivo, q.documento, q.documento.split('/')[0])}
        texto = cache[q.documento].get(q.pagina, "")
        if not texto:
            raise ValueError(f"Página inexistente o sin texto: {q.documento}, p. {q.pagina}")
        if q.cita_conocida and texto_literal(q.cita_conocida) not in texto_literal(texto):
            raise ValueError(f"La cita conocida no aparece en {q.documento}, p. {q.pagina}")
        if entrega:
            if not all([q.cita_conocida, q.clave_gestor, q.verificado_por, q.fecha_verificacion]):
                raise ValueError("La entrega necesita cita conocida, clave del gestor, verificador y fecha por pregunta en corpus.")
            try:
                date.fromisoformat(q.fecha_verificacion)
            except ValueError:
                raise ValueError("La fecha de verificación debe tener formato AAAA-MM-DD.") from None


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
            "citas_textuales_validas": [r.get("citas_textuales_validas", False) for r in valid] if treatment == "C" else [],
            "abstencion_correcta_fuera": [r["abstencion"] for r in outside],
            "respuesta_fuera_sin_abstencion": [not r["abstencion"] for r in outside],
            "fidelidad_revisada": [r["sostenida_por_fragmento"] == "Sí" for r in inside
                                   if r.get("sostenida_por_fragmento") in {"Sí", "No"}
                                   and r.get('verificado_por') and r.get('fecha_verificacion') and r.get('observaciones_revision')],
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
    path.write_bytes(csv_bytes(rows))


def sello() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def evaluar(banco: Path, config: Config, indice, cliente, *, origen: str = "publicos", entrega=False, sintetico=False) -> tuple[Path, list[dict]]:
    sintetico = sintetico or isinstance(cliente, ClienteFalso) or config.llm_model == 'cliente-falso'
    origins = origenes_permitidos(config, origen)
    questions = leer_banco(banco)
    if not config.allow_counterpart_cloud and any(q.documento.startswith("contraparte/") for q in questions):
        raise ValueError("El banco contiene preguntas de contraparte; evaluación en nube bloqueada.")
    if any(q.tipo == "en_corpus" and q.documento.split("/", 1)[0] not in origins for q in questions):
        raise ValueError("El banco incluye documentos fuera del origen elegido. Usa rutas relativas a docs.")
    if entrega and sintetico:
        raise ValueError("El cliente falso no permite generar una evaluación de entrega.")
    if not sintetico:
        validar_banco(questions, config.docs_dir, entrega=entrega)
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
                "respuesta_propuesta_rechazada": result.respuesta_propuesta if result else "",
                "cita_conocida": question.cita_conocida, "clave_gestor": question.clave_gestor,
                "conocida_verificada_por": question.verificado_por, "conocida_fecha_verificacion": question.fecha_verificacion,
                "afirmacion_informe": question.afirmacion_informe,
                "pagina_informe_confirmada": question.pagina_informe_confirmada,
                "citas": json.dumps([asdict(c) for c in result.citas], ensure_ascii=False) if result else "[]",
                "citas_textuales_validas": result.citas_verificadas if result else False,
                "sostenida_por_fragmento": "Pendiente" if question.tipo == "en_corpus" else "No aplica",
                "verificado_por": "", "fecha_verificacion": "", "observaciones_revision": "",
                "caso_fallo": "", "causa_tecnica": "", "evidencia_fallo": "",
                "abstencion": result.abstencion if result else "",
                "hit": hit(question, result.fragmentos) if result else False,
                "revision_manual": "", "error": error,
                "motivo_respuesta": result.motivo if result else "error_consulta",
                "modalidad": "sintetica" if sintetico else "entrega_pendiente_revision" if entrega else "ensayo",
                "cliente_llm": type(cliente).__name__, "origen_consulta": origen,
                "modelo_llm": config.llm_model, "modelo_embeddings": config.embedding_model,
                "chunk_size": config.chunk_size, "chunk_overlap": config.chunk_overlap,
                "top_k": config.top_k, "umbral": config.similarity_threshold,
                "temperatura": config.temperature, "protocolo": config.protocol.name,
                "protocolo_sha256": hashlib.sha256(config.protocol.read_bytes()).hexdigest(),
            })
            rows[-1]["aviso_codificacion"] = avisos_unicode(rows[-1])
    tag = sello()
    output = config.results_dir / f"evaluacion_{tag}.csv"
    summaries = resumir(rows)
    guardar_tabla(output, rows)
    guardar_tabla(config.results_dir / f"metricas_{tag}.csv", summaries)
    guardar_guia(output, rows, questions, entrega=entrega, sintetico=sintetico)
    return output, summaries


def guardar_guia(output, rows, questions, *, entrega=False, sintetico=False):
    pendientes = sum(r.get("sostenida_por_fragmento") == "Pendiente" for r in rows)
    fallos = sum(r.get("caso_fallo") == "Sí" and bool(r.get("causa_tecnica")) and bool(r.get("evidencia_fallo")) for r in rows)
    text = f"""# Evaluación de anclaje — {output.stem}

Modalidad: {'sintética; no mide calidad real' if sintetico else 'entrega, pendiente de revisión' if entrega else 'ensayo; no acredita entrega'}.
Banco: {len(questions)} preguntas; {sum(q.tipo == 'fuera_de_corpus' for q in questions)} fuera del corpus.
Filas pendientes de revisión de respaldo: {pendientes}. Casos de fallo documentados: {fallos}.

## Campos del enunciado

Pregunta → pregunta. Respuesta conocida → respuesta_conocida.
Dónde está → documento y pagina (ubicación conocida; distinta de las citas recuperadas).
Tratamiento → tratamiento. Respuesta obtenida → respuesta_obtenida.
¿Sostenida por un fragmento real? → sostenida_por_fragmento: completar Sí/No tras abrir la fuente.
Las preguntas fuera del corpus se evalúan por abstención; el respaldo se registra como No aplica.

## Revisión necesaria

Completa verificado_por, fecha_verificacion (AAAA-MM-DD) y observaciones_revision.
Las citas textuales válidas solo certifican existencia de texto, documento y página.
No certifican que todas las afirmaciones sean fieles. Las métricas de fidelidad usan únicamente revisiones Sí/No completas.
Una respuesta fuera del corpus sin abstención no se etiqueta automáticamente como invención.
Documenta al menos un fallo real con caso_fallo=Sí, causa_tecnica y evidencia_fallo.
Los rechazos preventivos del validador no sustituyen un fallo real de la respuesta final.

## Entregables externos pendientes

Esta salida no firma la auditoría cruzada, no acredita el experimento bibliográfico A/B/C,
no reemplaza el gestor de referencias, ni completa la memoria de 2–4 páginas o la defensa.
La trazabilidad del estado del arte requiere cada afirmación textual, clave del gestor,
ubicación de fuente, verificador y fecha. No confundir página sugerida con página confirmada.

## Abrir sin perder caracteres

CSV: UTF-8 con BOM, separador punto y coma. En Excel: Datos → Desde texto/CSV,
origen UTF-8 y delimitador punto y coma. El XLSX adjunto evita la selección de codificación.
No edites ni sobrescribas los originales al reparar una exportación anterior.
"""
    output.with_suffix('.md').write_text(text, encoding='utf-8')
    trazabilidad = [{
        'afirmacion': r.get('afirmacion_informe', ''), 'fuente_clave_gestor': r.get('clave_gestor', ''),
        'documento_fuente': r.get('documento', ''), 'pagina_fuente': r.get('pagina', ''),
        'cita_textual_fuente': r.get('cita_conocida', ''), 'pagina_informe_confirmada': r.get('pagina_informe_confirmada', ''),
        'verificado_por': '', 'fecha': '', 'estado': 'Pendiente de verificar la afirmación del informe',
    } for r in rows if r.get('tratamiento') == 'C' and r.get('tipo') == 'en_corpus']
    # Es una plantilla: verificar una respuesta no acredita automáticamente la afirmación del informe.
    trace = output.with_name(output.stem + '_trazabilidad_pendiente.csv')
    if trazabilidad and not trace.exists():
        guardar_tabla(trace, trazabilidad)


def guardar_revision(output, rows):
    """Guarda revisión humana explícita y recalcula métricas sin repetir la API."""
    output = Path(output)
    for r in rows:
        for key in ('abstencion', 'hit', 'citas_textuales_validas'):
            if r.get(key) in ('True', 'False'):
                r[key] = r[key] == 'True'
        estado = r.get("sostenida_por_fragmento", "Pendiente")
        if estado not in {"Sí", "No", "Pendiente", "No aplica"}:
            raise ValueError("La revisión debe indicar Sí, No, Pendiente o No aplica.")
        if estado in {"Sí", "No"}:
            if not r.get("verificado_por", "").strip() or not r.get("observaciones_revision", "").strip():
                raise ValueError("Cada revisión Sí/No requiere verificador y observación documental.")
            try:
                date.fromisoformat(r.get("fecha_verificacion", ""))
            except ValueError:
                raise ValueError("Cada revisión Sí/No requiere fecha AAAA-MM-DD.") from None
        if r.get("tipo") == "en_corpus" and estado == "No aplica":
            raise ValueError("Una pregunta en corpus necesita revisión Sí/No, no No aplica.")
        if r.get("tipo") == "fuera_de_corpus" and estado != "No aplica":
            raise ValueError("Para fuera de corpus revisa abstención; respaldo debe ser No aplica.")
        if estado == "Sí" and (r.get("error") or (r.get("tratamiento") == "C" and not r.get("citas_textuales_validas"))):
            raise ValueError("No se puede aprobar como sostenida una respuesta C sin citas válidas o una consulta fallida.")
        if estado == "Sí" and r.get("abstencion"):
            raise ValueError("Una abstención en una pregunta en corpus no cuenta como respuesta sostenida.")
        if r.get("caso_fallo") == "Sí" and not (r.get("causa_tecnica", "").strip() and r.get("evidencia_fallo", "").strip()):
            raise ValueError("El caso de fallo requiere causa técnica y evidencia.")
    guardar_tabla(output, rows)
    tag = output.stem.removeprefix('evaluacion_')
    metrics = resumir(rows)
    guardar_tabla(output.parent / f'metricas_{tag}.csv', metrics)
    questions = list({r['pregunta']: Pregunta(r['pregunta'], r['respuesta_conocida'], r['documento'], r['pagina'], r['tipo']) for r in rows}.values())
    guardar_guia(output, rows, questions, entrega=any(r.get('modalidad') == 'entrega_pendiente_revision' for r in rows),
                 sintetico=any(r.get('modalidad') == 'sintetica' for r in rows))
    return metrics


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
