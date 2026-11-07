from time import perf_counter

INICIO = perf_counter()

import os
import sys
import json
from pathlib import Path

from anclaje.operaciones import controles as st

from anclaje.cli import preparar_humo
from anclaje.config import cargar_config
from anclaje.embeddings import EmbeddingsLocales
from anclaje.diseno import aplicar_diseno, destacar_accion
from anclaje.interfaz_lotes import mostrar_lotes
from anclaje.indice import Indice
from anclaje.interfaz_fuentes import mostrar_fuentes, mostrar_memoria
from anclaje.interfaz_recorrido import botones_paso, seleccionar_paso, conservar_campos, mostrar_evaluacion, mostrar_inicio, mostrar_preparacion, restaurar_campos
from anclaje.llm import ClienteDeepSeek, ClienteFalso, ErrorLLM
from anclaje.memoria import TRATAMIENTOS
from anclaje.recorrido import DESCRIPCIONES, PASOS, estado_proyecto
from anclaje.responder import control, responder
from anclaje.salida import elegir_salida
from anclaje.evaluar import sello
from anclaje.operaciones import ocupado, programar, ejecutar_pendiente
from anclaje.flujo import estado_flujo, primer_pendiente, marcar_avance, invalidar_avance

st.set_page_config(page_title="Anclaje · Nada sin fuente", page_icon="⚓", layout="wide")
aplicar_diseno()


@st.cache_resource
def recursos(archivo: str, firma: int, demo: bool):
    config = cargar_config(archivo)
    if demo:
        config, index = preparar_humo(config)
        return config, index
    return config, Indice(config.index_dir, EmbeddingsLocales(config.embedding_model),
                         chunk_size=config.chunk_size, chunk_overlap=config.chunk_overlap)


def mostrar_consulta(config, index, demo):
    view = st.radio("Espacio de consulta", ["Una pregunta", "Tabla de preguntas"], horizontal=True, key="espacio_consulta")
    if view == "Tabla de preguntas":
        mostrar_lotes(config, index, demo)
        return
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
        def consultar():
            if treatment == "C":
                invalidar_avance(config, "consulta", demo)
            start = perf_counter()
            client = ClienteFalso() if demo else ClienteDeepSeek(config)
            result = responder(pregunta, config, index, client, origen=origin) if treatment == "C" else control(pregunta, client)
            st.session_state["consulta_resultado"] = (treatment, result, perf_counter() - start)
            output = config.results_dir / ("humo/consultas" if demo else "consultas") / f"consulta_{sello()}.json"
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps({"pregunta": pregunta, "tratamiento": treatment, **result.como_dict()}, ensure_ascii=False, indent=2), encoding="utf-8")
            st.session_state["consulta_salida"] = str(output)
            if treatment == "C" and result.citas_verificadas:
                st.session_state["consulta_verificada"] = True
            if treatment == "C" and result.motivo not in {"salida_json_invalida", "sin_citas_verificadas", "citas_invalidas", "cifras_sin_respaldo"}:
                marcar_avance(config, "consulta", demo)
        programar("Preparando la respuesta…", consultar)
    if previous := st.session_state.get("consulta_resultado"):
        result_treatment, result, elapsed = previous
        if result_treatment != treatment:
            return
        st.write(result.respuesta)
        if treatment == "C":
            st.caption("Citas textuales comprobadas; respaldo de la respuesta pendiente de revisión humana." if result.citas_verificadas else f"Motivo: {result.motivo or 'abstención'}")
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
        if st.session_state.get("consulta_salida"):
            st.caption(f"Respuesta guardada en: {st.session_state['consulta_salida']}")


try:
    archivo = Path(os.getenv("ANCLAJE_CONFIG", "config.yaml")).resolve()
    demo = "--demo" in sys.argv or os.getenv("ANCLAJE_DEMO", "false").lower() == "true"
    firma = max(archivo.stat().st_mtime_ns, (archivo.parent / ".env").stat().st_mtime_ns if (archivo.parent / ".env").exists() else 0)
    config, index = recursos(str(archivo), firma, demo)
    restaurar_campos()
    config, salida_lista = elegir_salida(config, demo)
    estado = estado_proyecto(config, index, demo)
    flujo = estado_flujo(config, estado, salida_lista, demo)
    st.session_state["pasos_habilitados"] = flujo["habilitados"]
    st.session_state["motivos_pasos"] = flujo["motivos"]
    actual = st.session_state.get("paso_activo", "Inicio")
    if not flujo["habilitados"].get(actual, False):
        actual = primer_pendiente(flujo)
    # Los checks cambian las etiquetas del radio; conserva su selección explícita.
    st.session_state["paso_activo"] = actual
    st.sidebar.title("Anclaje")
    def etiqueta(value):
        icon = "✓" if flujo["completados"][value] else "→" if flujo["habilitados"][value] else "🔒"
        return f"{icon} {PASOS.index(value) + 1}. {value}"
    paso = st.sidebar.radio("Tu recorrido", PASOS, key="paso_activo", on_change=seleccionar_paso,
                            format_func=etiqueta, disabled=ocupado())
    st.session_state["ultimo_paso_valido"] = paso
    st.sidebar.caption("✓ Completado · → Disponible · 🔒 Requisito pendiente")
    st.sidebar.caption("Puedes volver atrás. Los pasos pendientes se habilitan al completar sus requisitos.")
    st.sidebar.divider()
    st.sidebar.write("Estado del proyecto")
    st.sidebar.caption(f"Documentos C: {len(estado['documentos'])}")
    st.sidebar.caption("✓ Índice listo" if estado["indice_listo"] else "○ Índice por preparar")
    st.sidebar.caption("✓ Clave configurada" if estado["clave_configurada"] else "○ Clave pendiente")
    st.title(f"{PASOS.index(paso) + 1}. {paso}")
    st.caption(DESCRIPCIONES[PASOS.index(paso)])
    completed = sum(flujo["completados"].values())
    st.progress(completed / len(PASOS), text=f"{completed} de {len(PASOS)} pasos con requisitos completados")
    if aviso := st.session_state.pop("aviso_navegacion", None):
        st.warning(aviso)
    if aviso := st.session_state.pop("aviso_operacion", None):
        getattr(st, aviso[0])(aviso[1])
    if ocupado():
        st.info("⏳ Proceso en curso. Los botones y campos están bloqueados hasta terminar.")
    guias = {
        "Inicio": "→ Confirma arriba la carpeta de salida. Después pulsa Continuar a fuentes.",
        "Fuentes": "→ Elige una carpeta, pulsa Revisar carpeta y después Importar selección para C · Edward.",
        "Preparar": "→ Pulsa Preparar documentos. Al terminar, continúa a Consultar.",
        "Consultar": "→ Escribe una pregunta y pulsa Consultar, o ejecuta la Tabla de preguntas con C. Luego revisa el resultado.",
        "Evaluar": "→ Guarda o importa preguntas y pulsa Ejecutar evaluación A y C. Corrige los errores antes de continuar.",
        "Memoria": "→ Completa los seis apartados y pulsa Guardar borrador. El check aparece cuando todos tienen contenido.",
    }
    st.info(guias[paso])
    acciones = {"Inicio": "confirmar_salida", "Fuentes": "revisar_carpeta", "Preparar": "actualizar_indice",
                "Consultar": "analizar_lote" if st.session_state.get("espacio_consulta") == "Tabla de preguntas" else "consultar",
                "Evaluar": "ejecutar_evaluacion" if estado["banco_existe"] else "agregar_pregunta", "Memoria": "guardar_memoria"}
    if paso == "Fuentes" and st.session_state.get("vista_fuentes"):
        acciones[paso] = "importar_carpeta"
    if paso == "Fuentes" and st.session_state.get("metodo_importacion") == "Archivos desde el navegador":
        acciones[paso] = "importar_archivos"
    destacar_accion("paso_siguiente" if flujo["completados"][paso] and paso != "Memoria" else acciones[paso])
    st.caption("El borde dorado señala la siguiente acción. Los checks indican avance del recorrido; la evidencia académica requiere revisión.")
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
        if salida_lista:
            function(*args)
    except (ValueError, ErrorLLM) as error:
        st.error(str(error))
    except OSError:
        st.error("No se pudo acceder a la carpeta o al archivo. Revisa la ruta y los permisos.")
    conservar_campos()
    estado = estado_proyecto(config, index, demo)
    flujo = estado_flujo(config, estado, salida_lista, demo)
    st.session_state["pasos_habilitados"] = flujo["habilitados"]
    st.session_state["motivos_pasos"] = flujo["motivos"]
    siguiente = PASOS[min(PASOS.index(paso) + 1, len(PASOS) - 1)]
    botones_paso(paso, puede_continuar=flujo["habilitados"][siguiente], motivo=flujo["motivos"][siguiente])
    ejecutar_pendiente()
    st.caption(f"Preparación de interfaz e índice: {perf_counter() - INICIO:.3f} s. El modelo local se carga al consultar.")
except (ValueError, ErrorLLM) as error:
    st.error(str(error))
except OSError:
    st.error("No se pudo leer la configuración o el protocolo. Revisa las rutas y permisos.")
