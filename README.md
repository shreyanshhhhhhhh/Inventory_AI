# Inventory

A small-shop inventory app: catalog, on-hand counts, suppliers, and purchase orders. The browser is a Next.js app. It talks only to a FastAPI API. Local development uses SQLite.

Phase 1 has no AI. Agent Inbox and Insights are placeholders.

## Ports

| App | URL |
| --- | --- |
| Web | http://127.0.0.1:43123 |
| API | http://127.0.0.1:43124 |

## Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 43124 --reload
```

Health check: `GET http://127.0.0.1:43124/health`

Tests:

```bash
cd backend
source .venv/bin/activate
pytest
```

Settings come from environment variables (see `backend/.env.example`). `DATABASE_URL` defaults to a SQLite file, `inventory.db`, in the backend working directory.

## Frontend

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

`NEXT_PUBLIC_API_URL` should be `http://127.0.0.1:43124`. The API allows that origin and `http://localhost:43123`.
