import argparse
import importlib.metadata
import json
import sys
from dataclasses import replace
from pathlib import Path
from time import perf_counter

from .biblioteca import actualizar_indice
from .config import cargar_config
from .embeddings import EmbedderFalso, EmbeddingsLocales
from .evaluar import barrido, evaluar
from .fragmentos import fragmentar
from .indice import Indice
from .llm import ClienteDeepSeek, ClienteFalso, ErrorLLM
from .modelos import Pagina
from .responder import responder


def preparar_humo(config):
    demo = replace(config, embedding_model=EmbedderFalso.nombre, index_dir=config.index_dir / "humo")
    index = Indice(demo.index_dir, EmbedderFalso())
    pages = [
        Pagina("publicos/demo.txt", 1, "publicos", "La media aritmética es la suma de los valores dividida por el número de observaciones."),
        Pagina("contraparte/demo.txt", 1, "contraparte", "CONTENIDO PRIVADO SINTÉTICO que nunca debe enviarse por defecto."),
    ]
    fragments = fragmentar(pages, demo.chunk_size, demo.chunk_overlap)
    index.reconstruir(fragments, chunk_size=demo.chunk_size, chunk_overlap=demo.chunk_overlap)
    return demo, index


def humo(config) -> dict:
    start = perf_counter()
    if not (3, 11) <= sys.version_info[:2] < (3, 14):
        raise ValueError("Usa Python 3.11, 3.12 o 3.13; se recomienda 3.12.")
    versions = {name: importlib.metadata.version(name) for name in (
        "chromadb", "sentence-transformers", "PyMuPDF", "python-docx", "openai", "streamlit",
    )}
    config.protocol.read_text(encoding="utf-8")
    demo, index = preparar_humo(config)
    client = ClienteFalso()
    result = responder("media aritmética suma valores número observaciones", demo, index, client)
    if not result.sostenida_por_fragmento:
        raise ValueError("Falló la consulta de humo con citas verificadas.")
    if "CONTENIDO PRIVADO" in json.dumps(client.llamadas):
        raise ValueError("Falló el aislamiento de privacidad en humo.")
    try:
        real_state = Indice(config.index_dir, EmbeddingsLocales(config.embedding_model),
                            chunk_size=config.chunk_size, chunk_overlap=config.chunk_overlap).estado()
    except ValueError:
        real_state = "Pendiente: ejecuta reindexar con tu corpus."
    return {
        "estado": "OK: prueba sintética sin API ni descargas",
        "python": sys.version.split()[0], "dependencias": versions,
        "indice_configurado": real_state, "indice_sintetico": index.estado(),
        "respuesta": result.como_dict(), "segundos": round(perf_counter() - start, 3),
    }


def mostrar(result):
    print(result.respuesta)
    for cite in result.citas:
        print(f"[{cite.documento}, p. {cite.pagina}] {cite.estado}: {cite.cita_textual}")
        if cite.fragmento:
            print(f"Soporte: {cite.fragmento}")
    if any(c.estado == "no_verificada" for c in result.citas):
        print("ADVERTENCIA: hay citas no verificadas; revisa la respuesta manualmente.")


def mostrar_metricas(rows):
    for row in rows:
        value = row["proporcion"]
        interval = "sin observaciones" if value is None else (
            f"{value:.3f}, IC95% Wilson [{row['ic95_inferior']:.3f}, {row['ic95_superior']:.3f}]"
        )
        prefix = row.get("tratamiento", row.get("embedding_model", ""))
        print(f"{prefix} {row['metrica']}: {interval}; n={row['n']}")
        if row.get("errores"):
            print(f"Errores excluidos: {row['errores']} de {row['preguntas_programadas']} consultas.")


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Anclaje: nada sin fuente.")
    parser.add_argument("--config", default="config.yaml", help="Ruta a la configuración YAML.")
    subs = parser.add_subparsers(dest="comando", required=True)
    subs.add_parser("reindexar", help="Reconstruye la colección local; puede descargar pesos.")
    for name in ("buscar", "preguntar"):
        sub = subs.add_parser(name)
        sub.add_argument("texto")
        sub.add_argument("--origen", choices=["publicos", "contraparte", "ambos"], default="ambos" if name == "buscar" else "publicos")
        if name == "preguntar":
            sub.add_argument("--falso", action="store_true", help="Cliente LLM falso; no llama a DeepSeek.")
        sub.add_argument("--json", action="store_true", help="Salida estructurada.")
    sub = subs.add_parser("evaluar")
    sub.add_argument("banco", type=Path)
    sub.add_argument("--origen", choices=["publicos", "contraparte", "ambos"], default="publicos")
    sub.add_argument("--falso", action="store_true")
    sub = subs.add_parser("barrido")
    sub.add_argument("banco", nargs="?", type=Path, default=Path("eval/banco.csv"))
    subs.add_parser("humo", help="Verifica entorno, índice y consulta sintética sin red.")
    args = parser.parse_args(argv)
    try:
        config = cargar_config(args.config)
        if args.comando == "humo":
            print(json.dumps(humo(config), ensure_ascii=False, indent=2))
            return 0
        if args.comando == "barrido":
            path, rows = barrido(args.banco, config)
            mostrar_metricas(rows)
            print(f"Tabla comparativa: {path}")
            return 0
        embedder = EmbeddingsLocales(config.embedding_model, permitir_descarga=args.comando == "reindexar")
        index = Indice(config.index_dir, embedder, chunk_size=config.chunk_size, chunk_overlap=config.chunk_overlap)
        if args.comando == "reindexar":
            summary = actualizar_indice(config, index)
            for notice in summary["avisos"]:
                print(f"ADVERTENCIA: {notice}", file=sys.stderr)
            print(f"Índice reconstruido: {summary['fragmentos']} fragmentos, {summary['paginas']} páginas.")
        elif args.comando == "buscar":
            if not args.texto.strip():
                raise ValueError("La búsqueda no puede estar vacía.")
            origins = ("publicos", "contraparte") if args.origen == "ambos" else (args.origen,)
            fragments = index.consultar(args.texto, config.top_k, origins)
            if args.json:
                from dataclasses import asdict

                print(json.dumps([asdict(f) for f in fragments], ensure_ascii=False, indent=2))
            else:
                for f in fragments:
                    print(f"[{f.documento}, p. {f.pagina}] origen={f.origen}, similitud={f.similitud:.3f}\n{f.texto}\n")
                if not fragments:
                    print("No se encontraron fragmentos.")
        else:
            client = ClienteFalso() if args.falso else ClienteDeepSeek(config)
            if args.falso:
                config = replace(config, llm_model="cliente-falso")
                print("MODO FALSO: valida el circuito; no mide calidad del modelo.", file=sys.stderr)
            if args.comando == "preguntar":
                result = responder(args.texto, config, index, client, origen=args.origen)
                if args.json:
                    print(json.dumps(result.como_dict(), ensure_ascii=False, indent=2))
                else:
                    mostrar(result)
            else:
                index.estado()
                path, rows = evaluar(args.banco, config, index, client, origen=args.origen)
                mostrar_metricas(rows)
                print(f"Respuestas para revisión manual: {path}")
                if any(r["errores"] for r in rows):
                    return 2
        return 0
    except (ValueError, ErrorLLM, OSError, importlib.metadata.PackageNotFoundError) as error:
        if isinstance(error, (ValueError, ErrorLLM)):
            print(f"Error: {error}", file=sys.stderr)
        else:
            print("Error: no se pudo acceder a un archivo o falta una dependencia. Revisa la instalación y las rutas.", file=sys.stderr)
        return 2
