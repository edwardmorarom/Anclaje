from pathlib import Path

import streamlit as st

from .biblioteca import explorar_carpeta, importar_archivos, importar_carpeta, seleccionar_carpeta
from .memoria import APARTADOS, TRATAMIENTOS, cargar_memoria, destino_tratamiento, exportar_memoria, guardar_memoria, reconocer_tratamiento


def _importados(results, config, tratamiento):
    new = sum(item.nuevo for item in results)
    st.success(f"{new} archivos incorporados; {len(results) - new} ya estaban guardados con el mismo contenido.")
    if tratamiento == "C" and new:
        st.session_state["indice_pendiente"] = True
        (config.docs_dir / ".indice_pendiente").touch()
        for key in ("preparacion_resultado", "consulta_resultado", "consulta_verificada", "evaluacion_resultado"):
            st.session_state.pop(key, None)
    st.caption(f"Destino local: {destino_tratamiento(config, tratamiento)}. Originales conservados.")
    st.info("Se registró la procedencia. Completa o verifica licencia/permiso y quién revisó cada documento.")


def mostrar_fuentes(config, index, demo):
    st.subheader("Incorporar documentos")
    st.write("Selecciona una carpeta como Edward o elige archivos. Primero revisa la selección y después importa las copias locales.")
    st.table([{"Responsable": person, "Tratamiento": code, "Método": method} for code, (person, method) in TRATAMIENTOS.items()])
    st.caption("La carpeta de una persona permite sugerir su tratamiento. A, B y C representan métodos de consulta; el origen público/contraparte representa privacidad.")
    st.caption("Esta asignación organiza el trabajo del equipo. Para comparar A, B y C, ejecuten la misma consulta en los tres tratamientos.")
    if demo:
        st.info("Para incorporar tus documentos y actualizar el índice, abre la app sin --demo.")
    method = st.radio("Cómo incorporar fuentes", ["Carpeta del computador", "Archivos desde el navegador"], key="metodo_importacion")
    origin = st.selectbox("Privacidad de los documentos que vas a incorporar", ["publicos", "contraparte"], key="origen_importacion",
                          format_func=lambda value: "Fuentes públicas" if value == "publicos" else "Documentos de contraparte")
    if origin == "contraparte":
        st.info("Importación local. El envío a DeepSeek sigue requiriendo autorización escrita y el permiso de nube.")
    with st.expander("Procedencia de las fuentes (puedes completarla después)"):
        permission = st.text_input("Licencia o permiso", key="permiso_importacion")
        verifier = st.text_input("Quién verificó las fuentes", key="verificador_importacion")
    if method == "Carpeta del computador":
        if st.button("Elegir carpeta del computador", key="elegir_carpeta", disabled=demo):
            try:
                chosen = seleccionar_carpeta()
                if chosen:
                    st.session_state["carpeta_fuentes"] = chosen
                    st.session_state.pop("vista_fuentes", None)
            except (ValueError, OSError):
                st.warning("No se pudo abrir el selector. Puedes pegar la ruta en el campo siguiente.")
        folder = st.text_input("Ruta de la carpeta", key="carpeta_fuentes", placeholder="C:\\Users\\edwar\\Desktop\\II\\edward")
        recursive = st.checkbox("Incluir subcarpetas", key="subcarpetas_fuentes")
        st.caption("PDF, TXT, MD y DOCX. Se omiten temporales de Word (~$...), archivos ocultos y CSV/XLSX. El selector nativo se abre en el computador donde ejecutas la app.")
        if st.button("Revisar carpeta", key="revisar_carpeta", disabled=demo):
            candidates = explorar_carpeta(folder, recursive)
            st.session_state["vista_fuentes"] = (folder, recursive, candidates)
        preview = st.session_state.get("vista_fuentes")
        if preview and preview[:2] == (folder, recursive):
            candidates = preview[2]
            if not candidates:
                st.info("No se encontraron documentos admitidos en esta selección.")
            else:
                recognized = {recognize for item in candidates if (recognize := reconocer_tratamiento(folder, item.relativo))}
                default = next(iter(recognized)) if len(recognized) == 1 else "C"
                treatment_key = f"tratamiento_importacion:{folder}:{recursive}"
                treatment = st.selectbox("Guardar documentos para el tratamiento", list(TRATAMIENTOS),
                                         index=0 if treatment_key in st.session_state else list(TRATAMIENTOS).index(default), key=treatment_key,
                                         format_func=lambda code: f"{code} · {TRATAMIENTOS[code][0]} · {TRATAMIENTOS[code][1]}")
                rows = [{"Archivo": item.relativo, "Tratamiento reconocido": reconocer_tratamiento(folder, item.relativo) or "Sin asignar",
                         "Tamaño (MB)": round(item.bytes / 1_000_000, 2)} for item in candidates]
                st.dataframe(rows, hide_index=True, width="stretch")
                choices = [item.relativo for item in candidates]
                suggested = [item.relativo for item in candidates if reconocer_tratamiento(folder, item.relativo) in (None, treatment)]
                selection_key = f"seleccion_fuentes:{folder}:{recursive}:{treatment}"
                selected = st.multiselect("Documentos a importar", choices, default=None if selection_key in st.session_state else suggested,
                                          key=selection_key)
                group_key = f"grupo_fuentes:{folder}"
                group = st.text_input("Nombre del grupo", value="" if group_key in st.session_state else Path(folder).name, key=group_key)
                st.caption("C se incorpora al corpus del anclaje. A y B se guardan como evidencias locales del experimento.")
                if st.button("Importar selección", key="importar_carpeta", disabled=demo or not selected):
                    mismatches = [name for name in selected if reconocer_tratamiento(folder, name) not in (None, treatment)]
                    if mismatches:
                        st.error("La selección mezcla responsables de otros tratamientos. Ajusta el tratamiento o desmarca esos documentos.")
                    else:
                        results = importar_carpeta(folder, destino_tratamiento(config, treatment), origin, selected,
                                                   grupo=group, incluir_subcarpetas=recursive, permiso=permission, verificado_por=verifier)
                        _importados(results, config, treatment)
    else:
        treatment = st.selectbox("Guardar documentos para el tratamiento", list(TRATAMIENTOS), index=0 if "tratamiento_archivos" in st.session_state else 2,
                                 key="tratamiento_archivos", format_func=lambda code: f"{code} · {TRATAMIENTOS[code][0]} · {TRATAMIENTOS[code][1]}")
        group_key = f"grupo_archivos:{treatment}"
        group = st.text_input("Nombre del grupo", value="" if group_key in st.session_state else TRATAMIENTOS[treatment][0], key=group_key)
        uploaded = st.file_uploader("Seleccionar documentos", type=["pdf", "txt", "md", "docx"],
                                    accept_multiple_files=True, key="archivos_fuentes", disabled=demo)
        if st.button("Importar archivos", key="importar_archivos", disabled=demo or not uploaded):
            results = importar_archivos(uploaded, destino_tratamiento(config, treatment), origin,
                                        grupo=group, permiso=permission, verificado_por=verifier)
            _importados(results, config, treatment)
    if not demo and (st.session_state.get("indice_pendiente") or (config.docs_dir / ".indice_pendiente").exists()):
        st.info("Documentos incorporados. Continúa al paso Preparar para dejarlos listos para consultar.")
    library = [{"Documento": item.relativo, "Origen": origin}
               for origin in ("publicos", "contraparte") if (config.docs_dir / origin).is_dir()
               for item in explorar_carpeta(config.docs_dir / origin, True)]
    with st.expander(f"Documentos incorporados al corpus C ({len(library)})"):
        st.dataframe(library, hide_index=True, width="stretch") if library else st.info("Todavía no hay documentos incorporados.")


def mostrar_memoria(config):
    st.subheader("Memoria · 2 a 4 páginas · semana 3")
    st.write("Los seis apartados de la imagen del enunciado. Completa cada uno con tus resultados y evidencias reales.")
    st.table([{"Responsable": person, "Tratamiento": code, "Método": method} for code, (person, method) in TRATAMIENTOS.items()])
    path = config.results_dir / "memoria" / "borrador.json"
    try:
        saved = cargar_memoria(path)
    except (ValueError, OSError):
        saved = {}
        st.warning("No se pudo leer el borrador guardado. Los campos de esta sesión siguen disponibles.")
    contents = {}
    for key, title, help_text in APARTADOS:
        widget_key = f"memoria_{key}"
        contents[key] = st.text_area(title, value="" if widget_key in st.session_state else saved.get(key, ""), help=help_text, height=150, key=widget_key)
    completed = sum(bool(value.strip()) for value in contents.values())
    st.caption(f"{completed} de 6 apartados con contenido. La extensión de 2 a 4 páginas se revisa al dar formato al documento final.")
    markdown = exportar_memoria(contents)
    if st.button("Guardar borrador", key="guardar_memoria"):
        guardar_memoria(path, contents)
        path.with_suffix(".md").write_text(markdown, encoding="utf-8")
        st.success("Borrador guardado localmente en resultados/memoria/.")
    st.download_button("Descargar memoria en Markdown", data=markdown, file_name="memoria_nada_sin_fuente.md",
                       mime="text/markdown", key="descargar_memoria")
