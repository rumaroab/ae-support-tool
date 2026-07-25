import os
from urllib.parse import urlparse

import requests

from src.prompts import build_meeting_brief_prompt

DEFAULT_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
DEFAULT_MODEL = os.environ.get("OLLAMA_MODEL", "gemma4:12b")
LOCAL_HOSTS = {"localhost", "127.0.0.1"}


def _validated_host(host: str) -> str:
    host = host.rstrip("/")
    parsed = urlparse(host)
    if parsed.scheme != "http" or parsed.hostname not in LOCAL_HOSTS:
        raise ValueError(
            "OLLAMA_HOST must use http:// with localhost or 127.0.0.1"
        )
    return host


def _check_ollama(host: str, model: str) -> None:
    try:
        response = requests.get(f"{host}/api/tags", timeout=5)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(
            "Ollama is unavailable. Start it with `ollama serve` and try again."
        ) from exc

    available = {
        value
        for item in response.json().get("models", [])
        for value in (item.get("name"), item.get("model"))
        if value
    }
    if model not in available:
        raise RuntimeError(
            f"Model `{model}` is not installed. Run `ollama pull {model}`."
        )


def generate_brief(
    context: dict,
    mode: str,
    model: str | None = None,
    host: str | None = None,
) -> str:
    model = model or DEFAULT_MODEL
    host = _validated_host(host or DEFAULT_HOST)
    _check_ollama(host, model)
    prompt = build_meeting_brief_prompt(context, mode)

    response = requests.post(
        f"{host}/api/generate",
        json={
            "model": model,
            "prompt": prompt,
            "stream": False,
            "think": False,
            "options": {"temperature": 0.2, "num_predict": 400},
        },
        timeout=(5, 120),
    )
    response.raise_for_status()
    brief = response.json().get("response", "").strip()
    if not brief:
        raise RuntimeError("Ollama returned an empty brief.")
    return brief
