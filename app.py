from time import perf_counter

INICIO = perf_counter()

import os
import sys
from pathlib import Path

import streamlit as st

from anclaje.cli import preparar_humo
from anclaje.config import cargar_config
from anclaje.embeddings import EmbeddingsLocales
from anclaje.indice import Indice
from anclaje.interfaz_fuentes import mostrar_fuentes, mostrar_memoria
from anclaje.interfaz_recorrido import botones_paso, conservar_campos, mostrar_evaluacion, mostrar_inicio, mostrar_preparacion, restaurar_campos
from anclaje.llm import ClienteDeepSeek, ClienteFalso, ErrorLLM
from anclaje.memoria import TRATAMIENTOS
from anclaje.recorrido import DESCRIPCIONES, PASOS, estado_proyecto
from anclaje.responder import control, responder

st.set_page_config(page_title="Anclaje · Nada sin fuente", page_icon="⚓")


@st.cache_resource
def recursos(archivo: str, firma: int, demo: bool):
    config = cargar_config(archivo)
    if demo:
        config, index = preparar_humo(config)
        return config, index
    return config, Indice(config.index_dir, EmbeddingsLocales(config.embedding_model),
                         chunk_size=config.chunk_size, chunk_overlap=config.chunk_overlap)


def mostrar_consulta(config, index, demo):
    pending = not demo and (st.session_state.get("indice_pendiente", False) or (config.docs_dir / ".indice_pendiente").exists())
    ready = estado_proyecto(config, index, demo)["indice_listo"]
    treatment = st.selectbox("Tratamiento de la consulta", ["C", "A", "B"], key="tratamiento_consulta",
                             format_func=lambda code: f"{code} · {TRATAMIENTOS[code][0]} · {TRATAMIENTOS[code][1]}")
    if treatment == "B":
        st.info("B corresponde a Natalia: realiza la consulta en el buscador bibliográfico elegido, abre las referencias y registra los resultados en tu experimento. Puedes guardar sus documentos como evidencias en el paso Fuentes.")
        return
    origin = "publicos"
    if treatment == "C":
        origin = st.selectbox("Qué fuentes usar para responder", ["publicos", "contraparte", "ambos"], key="origen_consulta",
                              format_func=lambda value: {"publicos": "Fuentes públicas", "contraparte": "Documentos de contraparte", "ambos": "Ambos orígenes"}[value])
        st.caption("Los documentos de contraparte requieren autorización escrita y permiso de nube para enviarse a DeepSeek.")
        try:
            state = index.estado()
            st.caption(f"Índice disponible: {state['fragmentos']} fragmentos.")
        except ValueError:
            st.info("Primero incorpora los documentos en Fuentes y prepara el índice en el paso Preparar.")
        if pending:
            st.info("Hay fuentes nuevas. Vuelve al paso Preparar antes de consultarlas.")
    else:
        st.info("A corresponde a Harold: la pregunta se envía a DeepSeek sin documentos ni navegación. Su respuesta se revisa como control del experimento.")
    with st.form("consulta"):
        pregunta = st.text_input("Pregunta", key="pregunta_consulta")
        enviado = st.form_submit_button("Consultar", key="consultar", disabled=treatment == "C" and (pending or not ready))
    if enviado:
        if not pregunta.strip():
            raise ValueError("La pregunta no puede estar vacía.")
        if treatment == "C" and pending:
            raise ValueError("Actualiza el índice antes de consultar las nuevas fuentes.")
        with st.spinner("Preparando la respuesta…"):
            start = perf_counter()
            client = ClienteFalso() if demo else ClienteDeepSeek(config)
            result = responder(pregunta, config, index, client, origen=origin) if treatment == "C" else control(pregunta, client)
        st.session_state["consulta_resultado"] = (treatment, result, perf_counter() - start)
        if treatment == "C" and result.sostenida_por_fragmento:
            st.session_state["consulta_verificada"] = True
    if previous := st.session_state.get("consulta_resultado"):
        result_treatment, result, elapsed = previous
        if result_treatment != treatment:
            return
        st.write(result.respuesta)
        if any(c.estado == "no_verificada" for c in result.citas):
            st.warning("Hay citas no verificadas. Revisa la respuesta manualmente.")
        for cite in result.citas:
            label = f"[{cite.documento}, p. {cite.pagina}] · {cite.estado}"
            with st.expander(label, expanded=True):
                st.text(cite.cita_textual)
                if cite.fragmento:
                    st.caption("Fragmento de soporte")
                    st.text(cite.fragmento)
        if treatment == "C":
            with st.expander("Fragmentos recuperados"):
                for fragment in result.fragmentos:
                    st.caption(f"[{fragment.documento}, p. {fragment.pagina}] · similitud {fragment.similitud:.3f}")
                    st.text(fragment.texto)
        st.caption(f"Consulta completada en {elapsed:.3f} s.")


try:
    archivo = Path(os.getenv("ANCLAJE_CONFIG", "config.yaml")).resolve()
    demo = "--demo" in sys.argv or os.getenv("ANCLAJE_DEMO", "false").lower() == "true"
    firma = max(archivo.stat().st_mtime_ns, (archivo.parent / ".env").stat().st_mtime_ns if (archivo.parent / ".env").exists() else 0)
    config, index = recursos(str(archivo), firma, demo)
    restaurar_campos()
    estado = estado_proyecto(config, index, demo)
    st.sidebar.title("Anclaje")
    paso = st.sidebar.radio("Tu recorrido", PASOS, key="paso_activo", on_change=conservar_campos,
                            format_func=lambda value: f"{PASOS.index(value) + 1}. {value}")
    st.sidebar.caption("Avanza con Continuar. Puedes volver a cualquier paso desde aquí.")
    st.sidebar.divider()
    st.sidebar.write("Estado del proyecto")
    st.sidebar.caption(f"Documentos C: {len(estado['documentos'])}")
    st.sidebar.caption("Índice: listo" if estado["indice_listo"] else "Índice: por preparar")
    st.sidebar.caption("Clave: configurada" if estado["clave_configurada"] else "Clave: pendiente")
    st.title(f"{PASOS.index(paso) + 1}. {paso}")
    st.caption(DESCRIPCIONES[PASOS.index(paso)])
    st.progress(PASOS.index(paso) / (len(PASOS) - 1), text=f"Paso {PASOS.index(paso) + 1} de {len(PASOS)}")
    if demo:
        st.warning("Demostración con documentos sintéticos, embeddings falsos y cliente falso. No mide calidad real.")
    if config.allow_counterpart_cloud:
        st.warning("El envío de documentos de contraparte a DeepSeek está habilitado. Usa esos documentos solo con autorización escrita.")
    pantallas = {
        "Inicio": (mostrar_inicio, (config, estado, demo)),
        "Fuentes": (mostrar_fuentes, (config, index, demo)),
        "Preparar": (mostrar_preparacion, (config, index, estado, demo)),
        "Consultar": (mostrar_consulta, (config, index, demo)),
        "Evaluar": (mostrar_evaluacion, (config, index, estado, demo)),
        "Memoria": (mostrar_memoria, (config,)),
    }
    function, args = pantallas[paso]
    try:
        function(*args)
    except (ValueError, ErrorLLM) as error:
        st.error(str(error))
    except OSError:
        st.error("No se pudo acceder a la carpeta o al archivo. Revisa la ruta y los permisos.")
    conservar_campos()
    estado = estado_proyecto(config, index, demo)
    allowed, reason = True, ""
    if paso == "Fuentes" and not estado["documentos"] and not demo:
        allowed, reason = False, "Importa al menos un documento de Edward/C para continuar."
    if paso == "Preparar" and not estado["indice_listo"]:
        allowed, reason = False, "Prepara los documentos para habilitar las consultas."
    botones_paso(paso, puede_continuar=allowed, motivo=reason)
    st.caption(f"Preparación de interfaz e índice: {perf_counter() - INICIO:.3f} s. El modelo local se carga al consultar.")
except (ValueError, ErrorLLM) as error:
    st.error(str(error))
except OSError:
    st.error("No se pudo leer la configuración o el protocolo. Revisa las rutas y permisos.")
