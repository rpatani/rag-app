import json
from collections.abc import Iterator

import httpx

from app.core.llm.base import LLM

_COMMON_BODY = {"stream": True, "think": False}


class OllamaLLM(LLM):
    """Talks to a local Ollama server for fully local LLM inference."""

    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama3.1"):
        self._base_url = base_url.rstrip("/")
        self._model = model

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        return "".join(self.generate_stream(system_prompt, user_prompt))

    def generate_stream(self, system_prompt: str, user_prompt: str) -> Iterator[str]:
        with httpx.stream(
            "POST",
            f"{self._base_url}/api/chat",
            json={
                "model": self._model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                **_COMMON_BODY,
            },
            timeout=300,
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line:
                    continue
                chunk = json.loads(line)
                if chunk.get("done"):
                    break
                content = chunk.get("message", {}).get("content", "")
                if content:
                    yield content
