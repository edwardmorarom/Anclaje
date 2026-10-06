"""Una operación a la vez, con controles nativamente deshabilitados."""
import streamlit as _st

from .llm import ErrorLLM


def ocupado():
    return bool(_st.session_state.get("operacion_pendiente"))


class Controles:
    widgets = {"button", "download_button", "form_submit_button", "text_input", "text_area", "number_input",
               "selectbox", "multiselect", "radio", "checkbox", "file_uploader", "data_editor"}

    def button_in(self, container, *args, **kwargs):
        with container:
            return self.button(*args, **kwargs)

    def __getattr__(self, name):
        target = getattr(_st, name)
        if name not in self.widgets:
            return target

        def widget(*args, **kwargs):
            # data_editor admite una lista de columnas deshabilitadas.
            if ocupado():
                kwargs["disabled"] = True
            return target(*args, **kwargs)
        return widget


controles = Controles()


def programar(titulo, accion):
    if ocupado():
        return False
    _st.session_state["operacion_pendiente"] = (titulo, accion)
    _st.rerun()


def ejecutar_pendiente():
    pending = _st.session_state.get("operacion_pendiente")
    if not pending:
        return
    title, action = pending
    try:
        with _st.spinner(title):
            action()
        _st.session_state["aviso_operacion"] = ("success", "✓ Proceso terminado. Revisa el resultado y continúa cuando esté listo.")
    except (ValueError, ErrorLLM, OSError) as error:
        _st.session_state["aviso_operacion"] = ("error", str(error))
    except Exception:
        _st.session_state["aviso_operacion"] = ("error", "El proceso no se completó. Los controles se han liberado; revisa los archivos y vuelve a intentarlo.")
    finally:
        _st.session_state.pop("operacion_pendiente", None)
    _st.rerun()
