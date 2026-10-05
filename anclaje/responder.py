import json
from dataclasses import asdict, dataclass, field

from .config import Config
from .fragmentos import normalizar
from .llm import ClienteLLM
from .modelos import Fragmento

ABSTENCION = "No está en las fuentes."


@dataclass
class Cita:
    documento: str
    pagina: int
    cita_textual: str
    estado: str
    fragmento: str = ""


@dataclass
class Resultado:
    respuesta: str = ABSTENCION
    abstencion: bool = True
    citas: list[Cita] = field(default_factory=list)
    fragmentos: list[Fragmento] = field(default_factory=list)
    motivo: str = ""

    @property
    def sostenida_por_fragmento(self) -> bool:
        return not self.abstencion and any(c.estado == "verificada" for c in self.citas)

    def como_dict(self) -> dict:
        return asdict(self)


def verificar_citas(citas: list[dict], fuentes: list[Fragmento]) -> list[Cita]:
    verified = []
    for raw in citas:
        document, page, quote = raw["documento"], raw["pagina"], raw["cita_textual"]
        normalized = normalizar(quote)
        support = next((
            f.texto for f in fuentes
            if f.documento == document and f.pagina == page
            and normalized and normalized in normalizar(f.texto)
        ), "")
        verified.append(Cita(document, page, quote, "verificada" if support else "no_verificada", support))
    return verified


def interpretar(raw: str | dict, fuentes: list[Fragmento]) -> Resultado:
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
        if not isinstance(data, dict) or set(data) != {"respuesta", "abstencion", "citas"}:
            raise ValueError
        if not isinstance(data["respuesta"], str) or type(data["abstencion"]) is not bool:
            raise ValueError
        if not isinstance(data["citas"], list):
            raise ValueError
        for cite in data["citas"]:
            if not isinstance(cite, dict) or set(cite) != {"documento", "pagina", "cita_textual"}:
                raise ValueError
            if not isinstance(cite["documento"], str) or not isinstance(cite["cita_textual"], str):
                raise ValueError
            if type(cite["pagina"]) is not int or cite["pagina"] < 1:
                raise ValueError
    except (ValueError, TypeError, KeyError):
        return Resultado(motivo="salida_json_invalida")
    cites = verificar_citas(data["citas"], fuentes)
    if data["abstencion"]:
        return Resultado(citas=cites, motivo="abstencion_modelo")
    if not data["respuesta"].strip() or not any(c.estado == "verificada" for c in cites):
        return Resultado(citas=cites, motivo="sin_citas_verificadas")
    return Resultado(data["respuesta"], False, cites)


def origenes_permitidos(config: Config, origen: str = "publicos") -> tuple[str, ...]:
    if origen not in {"publicos", "contraparte", "ambos"}:
        raise ValueError("Origen inválido.")
    if origen != "publicos" and not config.allow_counterpart_cloud:
        raise ValueError("Contraparte bloqueada para la nube. Requiere ALLOW_COUNTERPART_CLOUD=true.")
    return ("publicos", "contraparte") if origen == "ambos" else (origen,)


def responder(pregunta: str, config: Config, indice, cliente: ClienteLLM, *, origen: str = "publicos") -> Resultado:
    if not pregunta.strip():
        raise ValueError("La pregunta no puede estar vacía.")
    origins = origenes_permitidos(config, origen)
    retrieved = indice.consultar(pregunta, config.top_k, origins)
    retrieved = [f for f in retrieved if f.origen in origins]
    sources = [f for f in retrieved if f.similitud >= config.similarity_threshold]
    if not sources:
        return Resultado(fragmentos=retrieved, motivo="sin_fuentes_sobre_umbral")
    protocol = config.protocol.read_text(encoding="utf-8")
    data = {
        "pregunta": pregunta,
        "fuentes": [{**f.metadata(), "id": f.id, "texto": f.texto} for f in sources],
    }
    messages = [
        {"role": "system", "content": protocol},
        {"role": "user", "content": json.dumps(data, ensure_ascii=False)},
    ]
    result = interpretar(cliente.generar(messages), sources)
    result.fragmentos = retrieved
    return result


def control(pregunta: str, cliente: ClienteLLM) -> Resultado:
    messages = [
        {"role": "system", "content": (
            "Responde en español sin fuentes ni navegación. Si no sabes, abstente. "
            'Devuelve json con {"respuesta": "texto", "abstencion": false, "citas": []}. '
            'Para abstenerte devuelve {"respuesta": "No está en las fuentes.", "abstencion": true, "citas": []}.'
        )},
        {"role": "user", "content": json.dumps({"pregunta": pregunta}, ensure_ascii=False)},
    ]
    raw = cliente.generar(messages)
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
        if not isinstance(data, dict) or set(data) != {"respuesta", "abstencion", "citas"}:
            raise ValueError
        if not isinstance(data["respuesta"], str) or not data["respuesta"].strip():
            raise ValueError
        if type(data["abstencion"]) is not bool or not isinstance(data["citas"], list):
            raise ValueError
    except (ValueError, TypeError, KeyError):
        raise ValueError("El tratamiento A devolvió JSON inválido; no cuenta como abstención correcta.") from None
    return Resultado(ABSTENCION if data["abstencion"] else data["respuesta"], data["abstencion"], motivo="control_sin_fuentes")
