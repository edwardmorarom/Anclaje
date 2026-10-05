import warnings
from pathlib import Path

from .modelos import Pagina

EXTENSIONES = {".pdf", ".txt", ".md", ".docx"}
PLANTILLA_PROCEDENCIA = """# Procedencia del corpus

Una fila por archivo. Usa rutas relativas a docs, por ejemplo publicos/articulo.pdf.
No registres datos personales innecesarios. Este archivo permanece fuera de Git.

| archivo | origen | fecha de obtención | licencia o permiso | quién verificó |
| --- | --- | --- | --- | --- |
"""


def _texto_docx(path: Path) -> str:
    from docx import Document
    from docx.oxml.ns import qn

    doc = Document(path)
    parts = []
    for node in doc.element.body.iter():
        if node.tag == qn("w:t"):
            parts.append(node.text or "")
        elif node.tag == qn("w:tab"):
            parts.append("\t")
        elif node.tag == qn("w:br"):
            parts.append("\f" if node.get(qn("w:type")) == "page" else "\n")
        elif node.tag == qn("w:lastRenderedPageBreak"):
            if not parts or parts[-1] != "\f":
                parts.append("\f")
        elif node.tag in (qn("w:p"), qn("w:tc")):
            parts.append("\n")
    warnings.warn(
        f"{path.name}: páginas DOCX estimadas por saltos explícitos/renderizados; "
        "exporta a PDF para ubicaciones estables.", stacklevel=2,
    )
    return "".join(parts)


def leer_archivo(path: Path, documento: str, origen: str) -> list[Pagina]:
    if path.suffix.lower() == ".pdf":
        import pymupdf

        with pymupdf.open(path) as pdf:
            texts = [page.get_text(sort=True) for page in pdf]
    elif path.suffix.lower() == ".docx":
        texts = _texto_docx(path).split("\f")
    else:
        texts = path.read_text(encoding="utf-8-sig").split("\f")
    pages = []
    for number, text in enumerate(texts, 1):
        if not text.strip():
            warnings.warn(
                f"{documento}, p. {number}: página sin texto; podría requerir OCR.", stacklevel=2,
            )
        pages.append(Pagina(documento, number, origen, text))
    return pages


def leer_corpus(docs_dir: Path) -> list[Pagina]:
    docs_dir.mkdir(parents=True, exist_ok=True)
    provenance = docs_dir / "PROCEDENCIA.md"
    if not provenance.exists():
        provenance.write_text(PLANTILLA_PROCEDENCIA, encoding="utf-8")
        warnings.warn("Se creó docs/PROCEDENCIA.md: completa una fila por archivo.", stacklevel=2)
    registered = set()
    for line in provenance.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("|"):
            registered.add(line.split("|")[1].strip().strip("`"))
    pages = []
    for origin in ("publicos", "contraparte"):
        folder = docs_dir / origin
        folder.mkdir(exist_ok=True)
        for path in sorted(folder.rglob("*")):
            if not path.is_file() or path.name == ".gitkeep":
                continue
            if path.is_symlink() or not path.resolve().is_relative_to(folder.resolve()):
                warnings.warn(f"Se omite enlace fuera de la carpeta autorizada: {path.name}", stacklevel=2)
                continue
            if path.suffix.lower() not in EXTENSIONES:
                warnings.warn(f"Formato no admitido: {path.name}", stacklevel=2)
                continue
            document = path.relative_to(docs_dir).as_posix()
            if document not in registered:
                warnings.warn(f"{document}: no aparece en docs/PROCEDENCIA.md.", stacklevel=2)
            try:
                pages.extend(leer_archivo(path, document, origin))
            except Exception:
                raise ValueError(f"No se pudo leer {document}; revisa formato, permisos o cifrado.") from None
    return pages
