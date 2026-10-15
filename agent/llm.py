"""Chat model factory for the local Ollama server."""

from __future__ import annotations

import os

from dotenv import load_dotenv
from langchain_ollama import ChatOllama

DEFAULT_MODEL = "qwen2.5:3b"
DEFAULT_BASE_URL = "http://localhost:11434"


def get_llm(model: str | None = None, temperature: float = 0.0) -> ChatOllama:
    """Return a ChatOllama client.

    ``reasoning=False`` turns off qwen3's hidden thinking step, which keeps
    tool-calling turns fast on a laptop. ``temperature=0`` makes answers
    repeatable, which matters for the prompt evaluation in Module 2.5.
    """
    load_dotenv()
    return ChatOllama(
        model=model or os.getenv("OLLAMA_MODEL", DEFAULT_MODEL),
        base_url=os.getenv("OLLAMA_BASE_URL", DEFAULT_BASE_URL),
        temperature=temperature,
        reasoning=False,
        num_ctx=8192,
    )
