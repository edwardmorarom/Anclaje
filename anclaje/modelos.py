from dataclasses import dataclass


@dataclass(frozen=True)
class Pagina:
    documento: str
    pagina: int
    origen: str
    texto: str


@dataclass(frozen=True)
class Fragmento:
    id: str
    documento: str
    pagina: int
    origen: str
    texto: str
    similitud: float = 0.0

    def metadata(self) -> dict:
        return {"documento": self.documento, "pagina": self.pagina, "origen": self.origen}
