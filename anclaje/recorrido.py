from dataclasses import asdict

from .biblioteca import explorar_carpeta

PASOS = ("Inicio", "Fuentes", "Preparar", "Consultar", "Evaluar", "Memoria")
DESCRIPCIONES = (
    "Comprueba qué está disponible y qué falta para trabajar con tus fuentes.",
    "Elige la carpeta de Edward, revisa los documentos e importa la selección.",
    "Convierte los documentos importados en un índice local que puedas consultar.",
    "Haz una pregunta conocida y comprueba su cita. Prueba también una pregunta fuera del corpus.",
    "Prepara tus preguntas conocidas, compara A y C y revisa las respuestas.",
    "Redacta los seis apartados con las evidencias de tu experimento.",
)


def ruta_banco(config, demo=False):
    return config.results_dir / "humo" / "banco.csv" if demo else config.root / "eval" / "banco.csv"


def estado_proyecto(config, indice, demo=False) -> dict:
    documents = [f"{origin}/{item.relativo}" for origin in ("publicos", "contraparte")
                 if (config.docs_dir / origin).is_dir()
                 for item in explorar_carpeta(config.docs_dir / origin, True)]
    pending = not demo and (config.docs_dir / ".indice_pendiente").exists()
    try:
        meta = indice.estado()
        fragments = meta["fragmentos"]
        ready = fragments > 0 and not pending
    except ValueError:
        fragments, ready = 0, False
    return {"documentos": documents, "indice_listo": ready, "fragmentos": fragments,
            "indice_pendiente": pending, "clave_configurada": bool(config.api_key.strip()),
            "banco_existe": ruta_banco(config, demo).is_file(), "demo": demo}


def guardar_banco(config, filas, demo=False):
    from .evaluar import guardar_csv, leer_banco

    path = ruta_banco(config, demo)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp.csv")
    try:
        guardar_csv(temporary, filas)
        questions = leer_banco(temporary)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    return questions


def importar_banco(config, contenido: bytes, demo=False):
    from .evaluar import leer_banco

    path = ruta_banco(config, demo)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp.csv")
    try:
        temporary.write_bytes(contenido)
        questions = leer_banco(temporary)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    return questions


def agregar_pregunta(config, pregunta: dict, demo=False):
    from .evaluar import leer_banco

    path = ruta_banco(config, demo)
    existing = [asdict(q) for q in leer_banco(path)] if path.exists() else []
    return guardar_banco(config, [*existing, pregunta], demo)


def resumen_banco(questions):
    outside = sum(q.tipo == "fuera_de_corpus" for q in questions)
    return {"total": len(questions), "fuera": outside,
            "completo_para_actividad": 15 <= len(questions) <= 20 and outside >= 3}
