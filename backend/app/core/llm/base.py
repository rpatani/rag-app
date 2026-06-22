from abc import ABC, abstractmethod
from collections.abc import Iterator


class LLM(ABC):
    """Generates text completions given a system prompt and user prompt."""

    @abstractmethod
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def generate_stream(self, system_prompt: str, user_prompt: str) -> Iterator[str]:
        """Yield response tokens one at a time."""
        raise NotImplementedError
