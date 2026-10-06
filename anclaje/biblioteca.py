import hashlib
import json
import os
import subprocess
import sys
import warnings
from dataclasses import dataclass
from datetime import date
from pathlib import Path, PurePosixPath

from .embeddings import EmbeddingsLocales
from .fragmentos import fragmentar
from .indice import Indice
from .ingesta import EXTENSIONES, PLANTILLA_PROCEDENCIA, leer_corpus


@dataclass(frozen=True)
class ArchivoLocal:
    ruta: Path
    relativo: str
    bytes: int


@dataclass(frozen=True)
class Importacion:
    documento: str
    nuevo: bool


def relativa_segura(nombre: str) -> PurePosixPath:
    path = PurePosixPath(nombre.replace("\\", "/"))
    if not path.parts or path.is_absolute() or any(
        part == ".." or any(char in part for char in ':<>|?*\x00') for part in path.parts
    ):
        raise ValueError("El nombre debe ser una ruta relativa sin '..' ni unidades de disco.")
    return path


def admitido(nombre: str) -> bool:
    path = PurePosixPath(nombre.replace("\\", "/"))
    return path.suffix.lower() in EXTENSIONES and not any(
        part.startswith((".", "~$")) for part in path.parts
    )


def explorar_carpeta(carpeta: str | Path, incluir_subcarpetas: bool = False) -> list[ArchivoLocal]:
    if not str(carpeta).strip():
        raise ValueError("Selecciona una carpeta o escribe su ruta.")
    root = Path(carpeta).expanduser().resolve()
    if not root.is_dir():
        raise ValueError("La carpeta no existe o no es accesible en este computador.")
    candidates = []
    for folder, directories, names in os.walk(root, followlinks=False):
        directories[:] = sorted(d for d in directories if not d.startswith(".") and d not in {
            "node_modules", "__pycache__", ".venv",
        }) if incluir_subcarpetas else []
        for name in sorted(names):
            path = Path(folder) / name
            relative = path.relative_to(root).as_posix()
            if not admitido(relative) or path.is_symlink() or not path.resolve().is_relative_to(root):
                continue
            candidates.append(ArchivoLocal(path, relative, path.stat().st_size))
    return sorted(candidates, key=lambda item: item.relativo.casefold())


def seleccionar_carpeta() -> str:
    script = """
import json
import tkinter as tk
from tkinter import filedialog
root = tk.Tk()
root.withdraw()
root.attributes('-topmost', True)
try:
    path = filedialog.askdirectory(title='Selecciona la carpeta de tus fuentes', parent=root)
    print(json.dumps(path))
finally:
    root.destroy()
"""
    hidden = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, creationflags=hidden,
    )
    if result.returncode:
        raise ValueError("No se pudo abrir el selector. Pega la ruta de la carpeta o elige archivos en el navegador.")
    return json.loads(result.stdout)


def _guardar(docs_dir: Path, origen: str, relativo: str, contenido: bytes) -> Importacion:
    if origen not in {"publicos", "contraparte"}:
        raise ValueError("El origen de importación debe ser publicos o contraparte.")
    relative = relativa_segura(relativo)
    if not admitido(relative.as_posix()):
        raise ValueError("Solo se importan PDF, TXT, MD y DOCX; se omiten temporales y archivos ocultos.")
    root = docs_dir.resolve()
    base = root / origen
    target = base.joinpath(*relative.parts)
    if base.resolve() != base or not target.resolve().is_relative_to(base):
        raise ValueError("La carpeta de destino contiene un enlace fuera del origen autorizado.")
    target.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(contenido).digest()
    original = target
    number = 1
    while True:
        if target.is_symlink() or not target.resolve().is_relative_to(base):
            raise ValueError("El destino no puede ser un enlace fuera de la carpeta autorizada.")
        if target.exists():
            if not target.is_file():
                raise ValueError("Hay una carpeta con el nombre del documento de destino.")
            with target.open("rb") as existing:
                identical = hashlib.file_digest(existing, "sha256").digest() == digest
            if identical:
                return Importacion(target.relative_to(root).as_posix(), False)
            number += 1
            target = original.with_name(f"{original.stem}_{number}{original.suffix}")
            continue
        try:
            with target.open("xb") as file:
                file.write(contenido)
        except FileExistsError:
            continue
        return Importacion(target.relative_to(root).as_posix(), True)


def guardar_procedencia(docs_dir: Path, resultados: list[Importacion], origen: str, permiso: str = "", verificado_por: str = ""):
    path = docs_dir / "PROCEDENCIA.md"
    if not path.exists():
        path.write_text(PLANTILLA_PROCEDENCIA, encoding="utf-8")
    text = path.read_text(encoding="utf-8")
    registered = {line.split("|")[1].strip().strip("`") for line in text.splitlines() if line.strip().startswith("|")}

    def cell(value):
        return value.replace("|", "\\|").replace("\n", " ").replace("\r", " ")

    rows = []
    for result in resultados:
        if result.documento not in registered:
            rows.append(f"| {result.documento} | {origen} | {date.today().isoformat()} | {cell(permiso) or 'Pendiente de verificar'} | {cell(verificado_por) or 'Pendiente'} |")
            registered.add(result.documento)
    if rows:
        path.write_text(text.rstrip() + "\n" + "\n".join(rows) + "\n", encoding="utf-8")


def importar_carpeta(carpeta: str | Path, docs_dir: Path, origen: str, seleccion: list[str], *,
                     grupo: str = "", incluir_subcarpetas: bool = False,
                     permiso: str = "", verificado_por: str = "") -> list[Importacion]:
    available = {item.relativo: item for item in explorar_carpeta(carpeta, incluir_subcarpetas)}
    if not seleccion or any(name not in available for name in seleccion):
        raise ValueError("Selecciona archivos presentes en la vista previa de la carpeta.")
    prefix = relativa_segura(grupo).as_posix() + "/" if grupo.strip() else ""
    results = [_guardar(docs_dir, origen, prefix + name, available[name].ruta.read_bytes()) for name in dict.fromkeys(seleccion)]
    guardar_procedencia(docs_dir, results, origen, permiso, verificado_por)
    return results


def importar_archivos(archivos, docs_dir: Path, origen: str, *, grupo: str = "", permiso: str = "", verificado_por: str = "") -> list[Importacion]:
    archivos = list(archivos)
    if not archivos:
        raise ValueError("Selecciona al menos un archivo.")
    prefix = relativa_segura(grupo).as_posix() + "/" if grupo.strip() else ""
    names = [relativa_segura(file.name).as_posix() for file in archivos]
    if any(not admitido(name) for name in names):
        raise ValueError("Hay un archivo temporal o de un formato no admitido.")
    results = [_guardar(docs_dir, origen, prefix + name, file.getvalue()) for name, file in zip(names, archivos)]
    guardar_procedencia(docs_dir, results, origen, permiso, verificado_por)
    return results


def actualizar_indice(config, indice=None) -> dict:
    with warnings.catch_warnings(record=True) as notices:
        warnings.simplefilter("always", UserWarning)
        pages = leer_corpus(config.docs_dir)
    chunks = fragmentar(pages, config.chunk_size, config.chunk_overlap)
    if not chunks:
        raise ValueError("No hay texto legible para indexar. Importa documentos con texto; un PDF escaneado requiere OCR.")
    index = indice or Indice(config.index_dir, EmbeddingsLocales(config.embedding_model))
    local = isinstance(index.embedder, EmbeddingsLocales)
    previous = index.embedder.permitir_descarga if local else False
    if local:
        index.embedder.permitir_descarga = True
    try:
        index.reconstruir(chunks, chunk_size=config.chunk_size, chunk_overlap=config.chunk_overlap)
    finally:
        if local:
            index.embedder.permitir_descarga = previous
    (config.docs_dir / ".indice_pendiente").unlink(missing_ok=True)
    return {"documentos": len({p.documento for p in pages}), "paginas": len(pages),
            "fragmentos": len(chunks), "avisos": [str(w.message) for w in notices]}
