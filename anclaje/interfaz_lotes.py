from pathlib import Path

import pandas as pd
from .operaciones import controles as st

from .embeddings import EmbeddingsLocales, EmbedderFalso
from .evaluar import sello
from .llm import ClienteDeepSeek, ClienteFalso, ErrorLLM
from .lotes import analizar_fila, cargar_memoria_agente, exportar_csv, guardar_memoria_agente
from .recorrido import estado_proyecto
from .responder import origenes_permitidos
from .operaciones import programar
from .flujo import marcar_avance, invalidar_avance


def mostrar_lotes(config, indice, demo):
    folder = config.results_dir / ("humo/agente" if demo else "agente")
    memory_path = folder / "memoria.json"
    if "lote_memoria" not in st.session_state:
        st.session_state["lote_memoria"] = cargar_memoria_agente(memory_path)
    memory = st.session_state["lote_memoria"]
    st.subheader("Mesa de preguntas")
    st.write("Agrega tantas filas como necesites. Escribe la respuesta conocida para comparar el significado al terminar.")
    with st.expander("Informe base: localizar dónde se trata cada pregunta"):
        st.write("Carga el informe de tu anteproyecto. Se guarda separado de las fuentes de C y se busca localmente. Las páginas sugeridas requieren confirmación.")
        report = st.file_uploader("Seleccionar informe base", type=["pdf", "docx", "txt", "md"], key="informe_base_archivo")
        if st.button("Guardar informe base", key="guardar_informe", disabled=not report):
            folder.mkdir(parents=True, exist_ok=True)
            target = folder / ("informe_base" + Path(report.name).suffix.lower())
            target.write_bytes(report.getvalue())
            memory["informe"] = target.name
            memory["informe_nombre"] = Path(report.name).name
            guardar_memoria_agente(memory_path, memory)
            st.success("Informe guardado localmente. No se incorpora al corpus de fuentes.")
        if memory.get("informe"):
            st.caption(f"Informe activo: {memory.get('informe_nombre', memory['informe'])}. Para páginas estables, usa PDF; en DOCX son estimadas.")
    columns = ["Pregunta", "Respuesta conocida", "Página informe confirmada"]
    if "tabla_preguntas" not in st.session_state:
        st.session_state["lote_tabla_inicial"] = memory.get("preguntas") or [{column: "" for column in columns}]
    initial = st.session_state["lote_tabla_inicial"]
    rows = st.data_editor(pd.DataFrame(initial, columns=columns).fillna(""), num_rows="dynamic", hide_index=True,
                          width="stretch", key="tabla_preguntas", column_config={
                              "Pregunta": st.column_config.TextColumn("Pregunta", width="large"),
                              "Respuesta conocida": st.column_config.TextColumn("Respuesta conocida", width="large"),
                              "Página informe confirmada": st.column_config.TextColumn("Página del informe (opcional)", help="Solo escribe la página que hayas comprobado tú.")})
    questions = rows.fillna("").to_dict("records")
    memory["preguntas"] = questions
    mode = st.selectbox("Cómo responder este lote", ["C", "A"], key="lote_tratamiento",
                        format_func=lambda value: "C · Con mis fuentes" if value == "C" else "A · Sin fuentes")
    origin = st.selectbox("Privacidad de las preguntas y fuentes", ["publicos", "contraparte", "ambos"], key="lote_origen",
                          format_func=lambda value: {"publicos": "Públicas", "contraparte": "De contraparte", "ambos": "Ambos orígenes"}[value])
    st.caption("En modo real, DeepSeek recibe la pregunta y las fuentes permitidas; una segunda llamada compara la respuesta obtenida con la conocida. No se envía el informe base. La clasificación es automática y puede requerir revisión.")
    active = [row for row in questions if str(row["Pregunta"]).strip()]
    left, right = st.columns(2)
    if st.button_in(left, "Guardar mesa de trabajo", key="guardar_mesa", width="stretch"):
        memory["preguntas"] = questions
        guardar_memoria_agente(memory_path, memory)
        st.success("Preguntas guardadas en la memoria local del agente.")
    state = estado_proyecto(config, indice, demo)
    ready = bool(active) and (demo or state["clave_configurada"]) and (mode == "A" or state["indice_listo"])
    if st.button_in(right, f"Analizar {len(active)} preguntas", key="analizar_lote", type="primary", disabled=not ready, width="stretch"):
        def analizar():
            if mode == "C":
                invalidar_avance(config, "consulta", demo)
            # El mismo permiso cubre preguntas/respuestas conocidas sensibles, incluso en A.
            origenes_permitidos(config, origin)
            client = ClienteFalso() if demo else ClienteDeepSeek(config)
            report_name = memory.get("informe", "")
            if report_name and (Path(report_name).name != report_name or not report_name.startswith("informe_base.") or Path(report_name).suffix not in {".pdf", ".docx", ".txt", ".md"}):
                raise ValueError("La referencia al informe en la memoria no es válida. Vuelve a cargar el informe.")
            report_path = folder / report_name if report_name else None
            if report_path and not report_path.is_file():
                raise ValueError("El informe guardado no está disponible. Vuelve a cargarlo antes de analizar.")
            memory.update({"preguntas": questions, "resultados": [], "tratamiento": mode, "origen": origin})
            memory["archivo_csv"] = f"consultas_{sello()}.csv"
            guardar_memoria_agente(memory_path, memory)
            embedder = (EmbedderFalso() if demo else EmbeddingsLocales(config.embedding_model)) if report_path else None
            progress = st.progress(0, text="Preparando el lote…")
            report_cache = {}
            for position, row in enumerate(active):
                try:
                    result = analizar_fila(row, config, indice, client, tratamiento=mode, origen=origin,
                                           informe=report_path, embedder=embedder, demo=demo, cache_informe=report_cache)
                    if report_path:
                        result["informe_base"] = memory.get("informe_nombre", report_path.name)
                except (ValueError, ErrorLLM, OSError) as error:
                    result = {"pregunta": row["Pregunta"], "respuesta_conocida": row["Respuesta conocida"],
                              "respuesta": "", "coincidencia": "Revisar", "explicacion": "Consulta no completada.",
                              "error": str(error), "tratamiento": mode, "origen": origin}
                memory["resultados"].append(result)
                guardar_memoria_agente(memory_path, memory)
                (folder / memory["archivo_csv"]).write_bytes(exportar_csv(memory["resultados"]))
                progress.progress((position + 1) / len(active), text=f"Analizadas {position + 1} de {len(active)} preguntas")
            st.success("Lote guardado. Revisa la comparación y las ubicaciones antes de usarlo como evidencia.")
            st.caption(f"CSV guardado en: {folder / memory['archivo_csv']}")
            if mode == "C" and memory["resultados"] and not any(row.get("error") or row.get("motivo_respuesta") in {"salida_json_invalida", "sin_citas_verificadas"} for row in memory["resultados"]):
                marcar_avance(config, "consulta", demo)
        programar("Analizando las preguntas del lote...", analizar)
    if not ready:
        st.info("Agrega al menos una pregunta. En modo real necesitas la clave; para C, prepara primero el índice.")
    results = memory.get("resultados", [])
    if results:
        st.subheader("Resultados del último lote guardado")
        st.caption(f"Memoria local: {memory_path.name}. Los resultados conservados corresponden al lote ejecutado, aunque después cambies las preguntas o las fuentes.")
        if demo:
            st.warning("Demostración: la coincidencia semántica no se mide con el cliente falso.")
        table = pd.DataFrame(results).reindex(columns=["pregunta", "respuesta_conocida", "respuesta", "coincidencia", "explicacion", "documento_fuente", "pagina_fuente", "paginas_informe_sugeridas", "pagina_informe_confirmada", "error"])
        table = table.rename(columns={"pregunta": "Pregunta", "respuesta_conocida": "Respuesta conocida", "respuesta": "Respuesta obtenida", "coincidencia": "Coincidencia semántica", "explicacion": "Explicación", "documento_fuente": "Fuente", "pagina_fuente": "Página de la fuente", "paginas_informe_sugeridas": "Páginas sugeridas del informe", "pagina_informe_confirmada": "Página confirmada del informe", "error": "Error"})
        st.dataframe(table, hide_index=True, width="stretch")
        st.download_button("Descargar resultados CSV · separado por ;", data=exportar_csv(results),
                           file_name="consultas_anclaje.csv", mime="text/csv", key="descargar_lote")
        for position, result in enumerate(results, 1):
            if result.get("ubicaciones_informe"):
                with st.expander(f"{position}. Ubicaciones sugeridas en el informe base"):
                    for item in result["ubicaciones_informe"]:
                        st.caption(f"Página {item['pagina']} · sugerida, pendiente de confirmar")
                        st.text(item["fragmento"])
    st.caption("La memoria JSON conserva preguntas, resultados y referencia al informe entre sesiones; no guarda claves ni cambia el protocolo de respuesta. Puedes descargar los resultados y completar revision_manual en Excel.")
