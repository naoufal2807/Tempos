from .provider import ollama_generate

SYSTEM = "You extract tasks from free text. Output a bullet list with title only."

def parse_tasks(text: str) -> list[dict]:
    _ = SYSTEM  # not used in this stub, but ready for richer prompts
    resp = ollama_generate(f"Extract tasks (titles) from:\n{text}\nReturn JSON list of titles.")
    # naive fallback for MVP
    titles = [t.strip("- ").strip() for t in resp.splitlines() if t.strip()]
    return [{"title": t} for t in titles if t]
