import hashlib
import re
import unicodedata

from .modelos import Fragmento, Pagina


def normalizar(texto: str) -> str:
    text = unicodedata.normalize("NFD", texto.casefold())
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", text).strip()


def fragmentar(paginas: list[Pagina], chunk_size: int, chunk_overlap: int) -> list[Fragmento]:
    if not 0 <= chunk_overlap < chunk_size:
        raise ValueError("Se requiere 0 <= chunk_overlap < chunk_size.")
    fragments = []
    for page in paginas:
        for offset in range(0, len(page.texto), chunk_size - chunk_overlap):
            text = page.texto[offset:offset + chunk_size].strip()
            if text:
                identity = f"{page.origen}\0{page.documento}\0{page.pagina}\0{offset}\0{text}"
                fragments.append(Fragmento(
                    hashlib.sha256(identity.encode()).hexdigest(),
                    page.documento, page.pagina, page.origen, text,
                ))
            if offset + chunk_size >= len(page.texto):
                break
    return fragments
