import json
from typing import Generator

import requests

_OLLAMA_TEMPERATURE_GENERATION = 0.4
_OLLAMA_NUM_CTX = 4096


def improve_outcome(
    prompt: str,
    ollama_url: str = "http://localhost:11434",
    model: str = "llama3",
) -> Generator[str, None, None]:
    """Streams improved outcome text from Ollama, yielding chunks as they arrive."""
    resp = requests.post(
        f"{ollama_url.rstrip('/')}/api/chat",
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": True,
            "options": {
                "temperature": _OLLAMA_TEMPERATURE_GENERATION,
                "num_ctx": _OLLAMA_NUM_CTX,
            },
        },
        stream=True,
        timeout=120,
    )
    resp.raise_for_status()

    for line in resp.iter_lines():
        if line:
            try:
                chunk = json.loads(line)
                token = chunk.get("message", {}).get("content", "")
                if token:
                    yield token
                if chunk.get("done"):
                    break
            except (json.JSONDecodeError, KeyError):
                continue


def improve_outcome_sync(
    prompt: str,
    ollama_url: str = "http://localhost:11434",
    model: str = "llama3",
) -> str:
    """Non-streaming version — returns complete improved text or empty string on failure."""
    try:
        return "".join(improve_outcome(prompt, ollama_url, model))
    except Exception:
        return ""
