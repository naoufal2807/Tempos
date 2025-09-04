import requests
from ..core.config import settings

def ollama_generate(prompt: str) -> str:
    r = requests.post(
        f"{settings.OLLAMA_HOST}/api/generate",
        json={"model": settings.OLLAMA_MODEL, "prompt": prompt, "stream": False},
        timeout=120,
    )
    r.raise_for_status()
    return r.json().get("response", "")
