# RyThM Music Backend

FastAPI backend for audio analysis, ONNX genre inference, AI-assisted music
generation, publishing, and HttpOnly-cookie authentication. PostgreSQL is used
in Docker/production; SQLite is used by the fast test suite. Payment endpoints
are not mounted in MVP v0.1.

## Run

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
cd ..
cp .env.example .env
PYTHONPATH=backend backend/.venv/bin/python -m alembic -c backend/alembic.ini upgrade head
backend/.venv/bin/python -m uvicorn app.main:app --app-dir backend --reload
```

## MVP endpoints

| Area | Endpoint |
| --- | --- |
| Cookie authentication | `POST /api/v1/auth/register`, `POST /api/v1/auth/login`, `POST /api/v1/auth/logout` |
| Recovery and verification | `POST /api/v1/auth/verify-email`, `POST /api/v1/auth/forgot-password`, `POST /api/v1/auth/reset-password` |
| Device sessions | `GET /api/v1/auth/sessions`, `DELETE /api/v1/auth/sessions/{id}` |
| Analysis | `POST /api/v1/songs/analyze`, `GET /api/v1/songs/history` |
| Generation | `POST /api/v1/music/generations`, `GET /api/v1/music/generations` |
| Publishing | `POST /api/v1/music/works`, `GET /api/v1/music/works` |
| Founder | `GET /api/v1/music/founder` |
| Operations | `/health`, `/ready`, `/metrics`, `/docs` |

All optional provider credentials use `AUDIO_`-prefixed environment variables. See the root `.env.example` and `models/genre/README.md`.

## Quality checks

Run from the repository root:

```bash
ruff check backend
mypy backend/app backend/scripts
bandit -r backend/app backend/scripts -x backend/tests
pytest -q
```
