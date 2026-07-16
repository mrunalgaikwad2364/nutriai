# NutriAI v3 — FastAPI + HTMX

Your personalised Indian dietician, rebuilt from Streamlit onto FastAPI + Jinja2 + HTMX.

## Tech Stack

- **Framework:** Streamlit → FastAPI (backend) + Jinja2 templates + HTMX (frontend)
- **Auth:** raw SHA-256 password hashing → bcrypt
- **LLM output:** trusted via `.get()` defaults → validated against Pydantic schemas (`utils/schemas.py`) before use
- **Provider references:** all leftover Gemini/Google AI Studio text removed (app was already using Groq)
- **Tests:** added `tests/` covering `utils/nutrition.py` and `utils/validators.py` (19 tests, pure functions, no mocking needed)
- **Deployment:** added Dockerfile + docker-compose.yml

`agents/graph.py`, `database/db.py`'s schema, `prompts/templates.py`, and `utils/nutrition.py` — the actual ML/agentic logic — are functionally the same as before. That work didn't need to change; only the UI layer and the security/reliability gaps did.

## Local setup (no Docker)

```bash
python -m venv venv
source venv/bin/activate       # venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.example .env           # then fill in your real GROQ_API_KEY and a random SESSION_SECRET
uvicorn app:app --reload
```
Visit http://localhost:8000

## Running tests

```bash
pytest tests/ -v
```

## Running with Docker

```bash
cp .env.example .env           # fill in real values first
docker compose up --build
```
Visit http://localhost:8000. Your SQLite data persists in a named Docker volume across restarts.

## Project structure

```
app.py                 FastAPI routes
agents/graph.py         LangGraph multi-agent pipeline
database/db.py          SQLite layer (bcrypt auth, profiles, logs)
prompts/templates.py     LLM prompt templates
utils/llm_client.py      Groq API wrapper with retries
utils/schemas.py        Pydantic validation for LLM JSON output
utils/nutrition.py      BMR/TDEE/macro calculations (deterministic, tested)
utils/validators.py     Form input validation (tested)
utils/pdf_report.py     PDF report generation (fpdf2)
templates/              Jinja2 HTML templates
static/style.css        Styling (same brand palette as v2)
tests/                  pytest suite
```
