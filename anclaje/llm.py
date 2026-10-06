import copy
import json
from typing import Protocol

from .config import Config


class ErrorLLM(RuntimeError):
    pass


class ClienteLLM(Protocol):
    def generar(self, mensajes: list[dict]) -> str | dict: ...


class ClienteDeepSeek:
    def __init__(self, config: Config):
        self.config = config
        self._client = None

    def generar(self, mensajes: list[dict]) -> str:
        if not self.config.api_key:
            raise ErrorLLM("Falta DEEPSEEK_API_KEY en el entorno o .env; no se llamó a la API.")
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI(
                api_key=self.config.api_key, base_url="https://api.deepseek.com",
                timeout=self.config.timeout, max_retries=0,
            )
        try:
            response = self._client.chat.completions.create(
                model=self.config.llm_model, messages=mensajes,
                temperature=self.config.temperature, max_tokens=self.config.max_tokens,
                response_format={"type": "json_object"},
                extra_body={"thinking": {"type": "disabled"}},
            )
        except Exception:
            raise ErrorLLM(
                "Falló la solicitud a DeepSeek. Revisa conexión, saldo, "
                "credenciales y disponibilidad de DEEPSEEK_MODEL."
            ) from None
        if not response.choices or response.choices[0].finish_reason != "stop":
            raise ErrorLLM("DeepSeek devolvió una respuesta incompleta; revisa max_tokens.")
        return response.choices[0].message.content or ""


class ClienteFalso:
    def __init__(self, salida: str | dict | None = None):
        self.salida = salida
        self.llamadas: list[list[dict]] = []

    def generar(self, mensajes: list[dict]) -> str | dict:
        self.llamadas.append(copy.deepcopy(mensajes))
        if self.salida is not None:
            return copy.deepcopy(self.salida)
        data = json.loads(mensajes[-1]["content"])
        sources = data.get("fuentes", [])
        if not sources:
            return {"respuesta": "No está en las fuentes.", "abstencion": True, "citas": []}
        first = sources[0]
        quote = first["texto"][:200]
        return {
            "respuesta": quote, "abstencion": False,
            "citas": [{"documento": first["documento"], "pagina": first["pagina"], "cita_textual": quote}],
        }
