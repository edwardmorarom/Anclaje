from time import perf_counter

INICIO = perf_counter()

import os
import sys
from pathlib import Path

import streamlit as st

from anclaje.cli import preparar_humo
from anclaje.config import ADVERTENCIA, cargar_config
from anclaje.embeddings import EmbeddingsLocales
from anclaje.indice import Indice
from anclaje.llm import ClienteDeepSeek, ClienteFalso, ErrorLLM
from anclaje.responder import responder

st.set_page_config(page_title="Anclaje · Nada sin fuente", page_icon="⚓")
st.title("Anclaje")
st.caption("Consulta tus documentos y comprueba de dónde sale cada respuesta.")


@st.cache_resource
def recursos(archivo: str, firma: int, demo: bool):
    config = cargar_config(archivo)
    if demo:
        config, index = preparar_humo(config)
        return config, index
    return config, Indice(config.index_dir, EmbeddingsLocales(config.embedding_model),
                         chunk_size=config.chunk_size, chunk_overlap=config.chunk_overlap)


try:
    archivo = Path(os.getenv("ANCLAJE_CONFIG", "config.yaml")).resolve()
    demo = "--demo" in sys.argv or os.getenv("ANCLAJE_DEMO", "false").lower() == "true"
    firma = max(archivo.stat().st_mtime_ns, (archivo.parent / ".env").stat().st_mtime_ns if (archivo.parent / ".env").exists() else 0)
    config, index = recursos(str(archivo), firma, demo)
    if demo:
        st.warning("Demostración con documentos sintéticos, embeddings falsos y cliente falso. No mide calidad real.")
    if config.allow_counterpart_cloud:
        st.warning(ADVERTENCIA)
    origen = st.selectbox("Origen de las fuentes", ["publicos", "contraparte", "ambos"])
    st.info("Contraparte se consulta localmente con buscar. Enviar sus fragmentos a DeepSeek requiere autorización escrita y ALLOW_COUNTERPART_CLOUD=true.")
    try:
        state = index.estado()
        st.caption(f"Índice disponible: {state['fragmentos']} fragmentos.")
    except ValueError:
        st.warning("Añade tus documentos y ejecuta python -m anclaje reindexar antes de consultar.")
    st.caption(f"Preparación de interfaz e índice: {perf_counter() - INICIO:.3f} s. El modelo local se carga al consultar.")
    with st.form("consulta"):
        pregunta = st.text_input("Pregunta sobre tus fuentes")
        enviado = st.form_submit_button("Consultar")
    if enviado:
        with st.spinner("Consultando las fuentes…"):
            start = perf_counter()
            client = ClienteFalso() if demo else ClienteDeepSeek(config)
            result = responder(pregunta, config, index, client, origen=origen)
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
        with st.expander("Fragmentos recuperados"):
            for fragment in result.fragmentos:
                st.caption(f"[{fragment.documento}, p. {fragment.pagina}] · similitud {fragment.similitud:.3f}")
                st.text(fragment.texto)
        st.caption(f"Consulta completada en {perf_counter() - start:.3f} s.")
except (ValueError, ErrorLLM) as error:
    st.error(str(error))
except OSError:
    st.error("No se pudo leer la configuración o el protocolo. Revisa las rutas y permisos.")
