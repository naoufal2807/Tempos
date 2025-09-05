
<p align="center">
  <img src="https://github.com/user-attachments/assets/efc2aaf7-50d7-4b1a-aee7-bccbbf7f6ab5" alt="Tempos Logo" width="200"/>
</p>
# Tempos

Turn messy notes into **structured tasks** using **FastAPI + Streamlit + Ollama**.  
Minimal setup. Clear APIs. Built to iterate fast.

## Features
- 🧠 Extract tasks from free text (LLM → validated schema)
- 🗂️ Store & query tasks (SQLModel + SQLite)
- ⚡ Dev hot-reload for API & UI (Docker)
- 🔌 Pluggable LLM via Ollama (`/api/generate`)

---

## Quickstart (Docker)

```bash
# 1) Clone
git clone https://github.com/naoufal2807/Tempos
cd Tempos

# 2) Backend env
cp backend/.env.example backend/.env
# Example:
# OLLAMA_HOST=http://ollama:11434
# OLLAMA_MODEL=llama3

# 3) Run
docker compose up --build
```

- UI → http://localhost:8501  
- API docs → http://localhost:8000/docs  
- Health → http://localhost:8000/health and http://localhost:8000/api/v1/health

---

## Development (hot reload)

- **Backend** mounts `./backend → /app` and runs `uvicorn --reload`.
- **Frontend** mounts `./frontend/streamlit_app → /ui` and Streamlit reloads on save.

```bash
docker compose up --build
# edit files → containers reload automatically
```

---

## API — quick smoke test

```bash
# Health
curl http://localhost:8000/health
curl http://localhost:8000/api/v1/health

# Parse tasks from text (example)
curl -X POST http://localhost:8000/api/v1/tasks/parse \
  -H "Content-Type: application/json" \
  -d '{"text":"Tomorrow 9am deploy API, 45min, office"}'
```

---

## Architecture

```mermaid
flowchart LR
  User[User (Browser)] -->|HTTP 8501| UI[Streamlit UI]
  UI -->|HTTP 8000| API[FastAPI API]
  API -->|HTTP 11434| OLL[Ollama Server]
  API --> DB[(SQLite)]
  subgraph Docker_Network
    UI
    API
    OLL
    DB
  end
```

```mermaid
flowchart TB
  M[app/main.py] --> R[include_router(/api/v1)]
  R --> H[/api/v1/health/]
  R --> T[/api/v1/tasks/]
  R --> Q[/api/v1/query/]

  subgraph Services
    NLP[services/nlp_parse.py\nparse_tasks()]
    OGEN[ollama_generate()\nPOST /api/generate]
    CFG[settings (.env)]
  end

  subgraph Schemas
    S1[TaskCreate]
    S2[TaskRead]
    S3[TaskUpdate]
  end

  subgraph Models
    TM[Task (SQLModel, table=True)]
  end

  T --> NLP --> OGEN --> NLP
  T --> TM
  Q --> TM
```

---

## Project Structure (relevant bits)

```
backend/
  app/
    api/v1/
      health.py
      tasks.py
      query.py
    models/
      task.py
    schemas/
      tasks.py         # TaskCreate / TaskRead / TaskUpdate
    services/
      nlp_parse.py     # uses ollama_generate()
    main.py            # FastAPI app
frontend/
  streamlit_app/
    app.py             # calls API_URL
docker-compose.yml     # ui + api + ollama
```

---

## Configuration (`backend/.env`)

```
# Ollama connectivity
OLLAMA_HOST=http://ollama:11434
OLLAMA_MODEL=llama3

# DB lives under ./data (mounted to /app/data)
```

---

## Troubleshooting

- **API unhealthy**
  - `docker logs tempos-api --tail=200`
  - Start command should bind: `uvicorn main:app --host 0.0.0.0 --port 8000 --reload`
  - Ensure both `/health` and `/api/v1/health` exist.

- **ImportError: TaskCreate**
  - Define `TaskCreate`, `TaskRead`, `TaskUpdate` in `app/schemas/tasks.py`.
  - Prefer absolute imports: `from app.schemas.tasks import TaskCreate`.
  - Make sure packages have `__init__.py`.

- **Ollama not ready**
  - `/health` should be shallow (no external calls).
  - Test Ollama: `curl http://localhost:11434/api/tags`.

---

## License (MIT)

Copyright (c) 2025 Naoufal Saadi

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the “Software”), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.



