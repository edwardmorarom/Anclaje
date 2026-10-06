"""Destino de resultados elegido explícitamente antes de procesar."""
import json
import tempfile
from dataclasses import replace
from pathlib import Path

from .operaciones import controles as st

from .biblioteca import seleccionar_carpeta


def archivo_preferencia(config, demo=False):
    return config.results_dir / ("humo/destino.json" if demo else "destino.json")


def cargar_destino(config, demo=False):
    path = archivo_preferencia(config, demo)
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))["carpeta"]
        if not isinstance(value, str) or not value.strip():
            raise ValueError
        return validar_destino(config, value)
    except (ValueError, KeyError, TypeError):
        raise ValueError("No se pudo recuperar la carpeta de salida. Elige una carpeta válida de nuevo.") from None


def validar_destino(config, texto):
    if not str(texto).strip():
        raise ValueError("Elige una carpeta de salida antes de comenzar.")
    path = Path(texto).expanduser()
    if not path.is_absolute():
        raise ValueError("Usa la ruta completa de la carpeta de salida.")
    path = path.resolve()
    root = config.root.resolve()
    # Dentro del repositorio, solo resultados está excluido de Git.
    if path.is_relative_to(root) and not path.is_relative_to(config.results_dir.resolve()):
        raise ValueError("Dentro del repositorio usa la carpeta resultados; también puedes elegir una carpeta fuera del repositorio.")
    if any(part.casefold() in {".git", ".venv"} for part in path.parts):
        raise ValueError("Elige una carpeta para documentos, fuera de .git y .venv.")
    if path.exists() and not path.is_dir():
        raise ValueError("El destino debe ser una carpeta, no un archivo.")
    return path


def guardar_destino(config, texto, demo=False):
    folder = validar_destino(config, texto)
    comprobar_escritura(folder)
    preference = archivo_preferencia(config, demo)
    preference.parent.mkdir(parents=True, exist_ok=True)
    temporary = preference.with_suffix(".tmp.json")
    temporary.write_text(json.dumps({"version": 1, "carpeta": str(folder)}, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(preference)
    return folder


def comprobar_escritura(folder):
    folder.mkdir(parents=True, exist_ok=True)
    # Comprueba permisos sin sobrescribir documentos del usuario.
    with tempfile.TemporaryFile(dir=folder) as probe:
        probe.write(b"anclaje")
        probe.flush()


def elegir_salida(config, demo=False):
    try:
        chosen = cargar_destino(config, demo)
        if chosen:
            comprobar_escritura(chosen)
    except (ValueError, OSError) as error:
        chosen = None
        st.warning(str(error))
    with st.expander("Dónde guardar los resultados", expanded=chosen is None):
        st.write("Selecciona la carpeta antes de comenzar. Allí se guardarán consultas, CSV, memoria y evidencias generadas.")
        if st.button("Elegir carpeta de salida", key="elegir_salida"):
            try:
                selected = seleccionar_carpeta()
                if selected:
                    st.session_state["ruta_salida"] = selected
            except (ValueError, OSError):
                st.warning("No se pudo abrir el selector. Puedes escribir la ruta completa abajo.")
        if "ruta_salida" not in st.session_state:
            st.session_state["ruta_salida"] = str(chosen or config.results_dir.resolve())
        text = st.text_input("Carpeta para guardar los resultados", key="ruta_salida")
        st.caption("Puedes elegir una carpeta existente o escribir una nueva. Se creará al confirmar. El selector se abre en el computador donde ejecutas la app.")
        if st.button("Confirmar carpeta de salida", key="confirmar_salida", type="primary"):
            try:
                chosen = guardar_destino(config, text, demo)
            except (ValueError, OSError) as error:
                st.error(f"No se pudo confirmar el destino: {error}")
            else:
                # Las memorias de carpetas distintas nunca se mezclan en pantalla.
                if str(chosen) != st.session_state.get("salida_activa"):
                    for key in ("lote_memoria", "lote_tabla_inicial", "tabla_preguntas", "evaluacion_resultado", "consulta_resultado", "consulta_salida"):
                        st.session_state.pop(key, None)
                    for key in list(st.session_state):
                        if key.startswith("memoria_"):
                            st.session_state.pop(key, None)
                            st.session_state.get("campos_recorrido", {}).pop(key, None)
                st.success("Carpeta confirmada. Los documentos nuevos se guardarán en ese destino.")
    if chosen:
        st.session_state["salida_activa"] = str(chosen)
        st.info(f"Destino de guardado: {chosen}")
        st.caption("Cambiar el destino no mueve los archivos anteriores. Las descargas del navegador siguen sus propias preferencias de ubicación.")
        return replace(config, results_dir=chosen), True
    st.info("Confirma dónde guardar los resultados para habilitar el proceso.")
    return config, False
