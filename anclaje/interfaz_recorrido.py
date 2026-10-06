from dataclasses import asdict, replace

from .operaciones import controles as st

from .biblioteca import actualizar_indice
from .diseno import mostrar_portada
from .evaluar import evaluar, leer_banco
from .llm import ClienteDeepSeek, ClienteFalso
from .recorrido import PASOS, agregar_pregunta, importar_banco, resumen_banco, ruta_banco
from .responder import control
from .operaciones import ocupado, programar
from .flujo import marcar_avance, invalidar_avance

CAMPOS = {
    "espacio_consulta", "lote_tratamiento", "lote_origen",
    "carpeta_fuentes", "subcarpetas_fuentes", "metodo_importacion", "origen_importacion",
    "permiso_importacion", "verificador_importacion", "tratamiento_archivos",
    "tratamiento_consulta", "origen_consulta", "pregunta_consulta", "evaluacion_falsa", "origen_evaluacion",
    "banco_pregunta", "banco_respuesta", "banco_tipo", "banco_documento", "banco_pagina",
}
PREFIJOS = ("memoria_", "tratamiento_importacion:", "seleccion_fuentes:", "grupo_fuentes:", "grupo_archivos:")


def conservar_campos():
    saved = st.session_state.setdefault("campos_recorrido", {})
    for key in list(st.session_state):
        if key in CAMPOS or key.startswith(PREFIJOS):
            saved[key] = st.session_state[key]


def restaurar_campos():
    for key, value in st.session_state.get("campos_recorrido", {}).items():
        if key not in st.session_state:
            st.session_state[key] = value


def ir_a(paso):
    if ocupado():
        return
    if not st.session_state.get("pasos_habilitados", {}).get(paso, True):
        st.session_state["aviso_navegacion"] = st.session_state.get("motivos_pasos", {}).get(paso, "Completa el paso anterior.")
        return
    conservar_campos()
    st.session_state["paso_activo"] = paso


def seleccionar_paso():
    target = st.session_state["paso_activo"]
    if ocupado() or not st.session_state.get("pasos_habilitados", {}).get(target, True):
        st.session_state["paso_activo"] = st.session_state.get("ultimo_paso_valido", "Inicio")
        st.session_state["aviso_navegacion"] = st.session_state.get("motivos_pasos", {}).get(target, "Espera a que termine el proceso.")
    conservar_campos()


def botones_paso(paso, *, puede_continuar=True, motivo=""):
    position = PASOS.index(paso)
    st.divider()
    left, right = st.columns(2)
    if position:
        with left:
            st.button("← Anterior", key="paso_anterior", on_click=ir_a, args=(PASOS[position - 1],), width="stretch")
    if position < len(PASOS) - 1:
        with right:
            st.button(f"Continuar a {PASOS[position + 1].lower()} →", key="paso_siguiente", type="primary",
                      on_click=ir_a, args=(PASOS[position + 1],), disabled=not puede_continuar, width="stretch")
        if not puede_continuar and motivo:
            st.info(motivo)
    else:
        with right:
            st.button("Revisar estado del proyecto", on_click=ir_a, args=("Inicio",), width="stretch")


def mostrar_inicio(config, estado, demo):
    mostrar_portada()
    st.write("Sigue los pasos de la izquierda. En cada pantalla encontrarás qué hacer y un botón para continuar.")
    rows = [
        {"Requisito": "Clave de DeepSeek", "Estado": "Configurada; conexión por comprobar" if estado["clave_configurada"] else "Pendiente",
         "Qué hacer": "Prueba la conexión con el botón de abajo." if estado["clave_configurada"] else "Completa DEEPSEEK_API_KEY en .env y reinicia la app."},
        {"Requisito": "Documentos de Edward / C", "Estado": f"{len(estado['documentos'])} incorporados",
         "Qué hacer": "Revisa la procedencia de cada archivo." if estado["documentos"] else "Paso 2: elige la carpeta edward e importa sus documentos."},
        {"Requisito": "Índice local", "Estado": f"Listo: {estado['fragmentos']} fragmentos" if estado["indice_listo"] else "Pendiente",
         "Qué hacer": "Paso 4: prueba una respuesta con cita." if estado["indice_listo"] else "Paso 3: pulsa Preparar documentos."},
        {"Requisito": "Banco de preguntas", "Estado": "Archivo disponible; revisa su contenido" if estado["banco_existe"] else "Pendiente",
         "Qué hacer": "Paso 5: prepara 15–20 preguntas, al menos tres fuera del corpus."},
    ]
    st.dataframe(rows, hide_index=True, width="stretch")
    if demo:
        st.info("Estás practicando con fuentes sintéticas. Los resultados de esta demostración no validan tu corpus real.")
    else:
        st.caption(f"Modelo configurado: {config.llm_model}. Tener una clave configurada no confirma saldo, permisos ni conexión.")
        if st.button("Probar conexión con DeepSeek", key="probar_api", disabled=not estado["clave_configurada"]):
            def probar():
                control("Prueba de conexión: responde brevemente que el servicio está disponible.", ClienteDeepSeek(config))
                st.session_state["api_comprobada"] = True
            programar("Probando una consulta breve sin documentos…", probar)
        if st.session_state.get("api_comprobada"):
            st.success("La API respondió correctamente a la prueba de esta sesión.")
        st.caption("La prueba envía una pregunta sintética al proveedor. No envía tus documentos.")
    with st.expander("Qué falta para la actividad completa"):
        st.write("Además de hacer funcionar el anclaje, necesitas procedencia y gestor de referencias, tabla de trazabilidad, experimento A/B/C con revisión de referencias y acuerdo entre clasificadores, caso de fallo, auditoría cruzada y memoria. B se realiza con la herramienta bibliográfica externa elegida.")
        st.write("Los PDF escaneados requieren OCR externo. La cita se comprueba por existencia del texto; revisa manualmente si sostiene cada afirmación.")


def mostrar_preparacion(config, index, estado, demo):
    st.write("Pulsa el botón para leer tus archivos, conservar sus páginas y construir el índice de búsqueda local.")
    st.metric("Documentos incorporados", len(estado["documentos"]))
    if demo:
        st.success("El índice de demostración ya está preparado. Puedes continuar a consultar.")
        return
    if not estado["documentos"]:
        st.info("Primero importa los documentos de Edward/C en el paso Fuentes.")
        st.button("Ir a incorporar fuentes", key="volver_fuentes", on_click=ir_a, args=("Fuentes",))
    if st.button("Preparar documentos", key="actualizar_indice", type="primary", disabled=not estado["documentos"]):
        def preparar():
            summary = actualizar_indice(config, index)
            st.session_state["indice_pendiente"] = False
            st.session_state["preparacion_resultado"] = summary
        programar("Preparando el índice local. La primera vez puede tardar varios minutos…", preparar)
    if summary := st.session_state.get("preparacion_resultado"):
        st.success(f"Preparación completada: {summary['documentos']} documentos, {summary['paginas']} páginas y {summary['fragmentos']} fragmentos.")
        for notice in summary["avisos"]:
            st.warning(notice)
    st.caption("La primera preparación descarga los pesos del modelo de embeddings. El texto se procesa localmente; este paso no llama a DeepSeek.")
    if not estado["indice_listo"] and not st.session_state.get("preparacion_resultado"):
        st.info("Después de preparar, revisa los avisos y prueba una pregunta cuya respuesta puedas localizar tú mismo.")


def mostrar_evaluacion(config, index, estado, demo):
    path = ruta_banco(config, demo)
    questions = leer_banco(path) if path.exists() else []
    st.write("Escribe preguntas con respuesta conocida y ubicación real. Incluye al menos tres cuya respuesta no esté en tus documentos.")
    a, b = st.columns(2)
    metrics_a, metrics_b = a.empty(), b.empty()
    bank_notice = st.empty()
    with st.expander("Agregar una pregunta", expanded=not questions):
        with st.form("pregunta_banco", clear_on_submit=True):
            text = st.text_input("Pregunta del banco", key="banco_pregunta")
            known = st.text_area("Respuesta conocida", key="banco_respuesta")
            kind = st.selectbox("Tipo de pregunta", ["en_corpus", "fuera_de_corpus"], key="banco_tipo")
            st.caption("Para fuera_de_corpus deja la ubicación vacía; la respuesta esperada es No está en las fuentes.")
            document = st.text_input("Documento relativo a docs", placeholder="publicos/edward/articulo.pdf", key="banco_documento")
            page = st.number_input("Página", min_value=1, value=1, step=1, key="banco_pagina")
            add = st.form_submit_button("Guardar pregunta", key="agregar_pregunta")
        if add:
            questions = agregar_pregunta(config, {"pregunta": text, "respuesta_conocida": known if kind == "en_corpus" else known or "No está en las fuentes.",
                                                  "documento": document if kind == "en_corpus" else "", "pagina": page if kind == "en_corpus" else None,
                                                  "tipo": kind}, demo)
            st.success("Pregunta guardada. Ya puedes agregar la siguiente.")
    with st.expander("Usar un banco CSV existente"):
        uploaded = st.file_uploader("Seleccionar banco de evaluación", type=["csv"], key="archivo_banco")
        if st.button("Importar banco CSV", key="importar_banco", disabled=not uploaded):
            questions = importar_banco(config, uploaded.getvalue(), demo)
            st.success(f"Banco importado: {len(questions)} preguntas.")
        example = config.root / "eval/banco_ejemplo.csv"
        if example.exists():
            st.download_button("Descargar formato de ejemplo", data=example.read_bytes(), file_name="banco_ejemplo.csv", mime="text/csv")
    stats = resumen_banco(questions)
    metrics_a.metric("Preguntas en el banco", stats["total"])
    metrics_b.metric("Fuera del corpus", stats["fuera"])
    if not stats["completo_para_actividad"]:
        bank_notice.info("Para la entrega se requieren 15–20 preguntas y al menos tres fuera del corpus. Puedes hacer una prueba pequeña mientras preparas el banco.")
    else:
        bank_notice.success("El banco cumple la cantidad requerida y contiene al menos tres preguntas fuera del corpus.")
    if questions:
        st.dataframe([asdict(q) for q in questions], hide_index=True, width="stretch")
        st.download_button("Descargar mi banco", data=path.read_bytes(), file_name="banco.csv", mime="text/csv")
    if demo and "evaluacion_falsa" not in st.session_state:
        st.session_state["evaluacion_falsa"] = True
    fake = st.checkbox("Practicar con cliente falso (sin API)", key="evaluacion_falsa", disabled=demo)
    origin = st.selectbox("Origen para evaluar C", ["publicos", "contraparte", "ambos"], key="origen_evaluacion")
    ready = bool(questions) and estado["indice_listo"] and (fake or estado["clave_configurada"])
    st.caption("A responde sin fuentes y C recibe los fragmentos recuperados. En modo real se envían preguntas y fuentes permitidas a DeepSeek. B y la revisión de referencias se realizan con tu herramienta bibliográfica externa.")
    if st.button("Ejecutar evaluación A y C", key="ejecutar_evaluacion", disabled=not ready, type="primary"):
        run_config = replace(config, llm_model="cliente-falso") if fake else config
        client = ClienteFalso() if fake else ClienteDeepSeek(config)
        def medir():
            invalidar_avance(config, "evaluacion", demo)
            output, metrics = evaluar(path, run_config, index, client, origen=origin)
            st.session_state["evaluacion_resultado"] = (output, metrics, fake)
            if not any(row["errores"] for row in metrics):
                marcar_avance(config, "evaluacion", demo)
        programar("Evaluando las preguntas y guardando los resultados…", medir)
    if result := st.session_state.get("evaluacion_resultado"):
        output, metrics, synthetic = result
        if synthetic:
            st.warning("Resultados con cliente falso: sirven para comprobar el circuito y no miden calidad real.")
        failures = max(row["errores"] for row in metrics)
        if failures:
            st.warning("Hubo consultas que no se completaron. Sus errores están guardados y se excluyen de las proporciones.")
        labels = {"hit@k": "Documento y página recuperados", "cita_verificada": "Respuesta con cita verificada",
                  "abstencion_correcta_fuera": "Abstención correcta fuera del corpus", "invencion_fuera": "Respuesta fuera del corpus sin abstención"}
        table = [{"Tratamiento": row["tratamiento"], "Indicador": labels[row["metrica"]],
                  "Proporción": f"{row['proporcion']:.1%}" if row["proporcion"] is not None else "Sin datos",
                  "IC 95 % Wilson": f"[{row['ic95_inferior']:.1%}, {row['ic95_superior']:.1%}]" if row["n"] else "Sin datos",
                  "Preguntas evaluadas": row["n"], "Errores excluidos": row["errores"]} for row in metrics]
        st.dataframe(table, hide_index=True, width="stretch")
        st.caption("El indicador de recuperación usa las preguntas en corpus; abstención e invención usan las preguntas fuera del corpus. En A no aplica recuperación. Los intervalos muestran incertidumbre con el tamaño de muestra indicado.")
        st.download_button("Descargar respuestas para revisión manual", data=output.read_bytes(), file_name=output.name, mime="text/csv")
        st.info("Completa revision_manual en el CSV. Una cita existente puede estar mal interpretada. Usa estos resultados y un caso de fallo real en la memoria.")
    if not ready:
        st.info("Para evaluar necesitas preguntas guardadas y el índice preparado; en modo real también una clave configurada.")
