# Inventory

A small-shop inventory app: catalog, stock ledger, suppliers, purchase orders, dashboard, and team settings. The browser is a Next.js app. It talks only to a FastAPI API. Local development uses SQLite; deploy uses PostgreSQL through the same models.

**Phase 1 has no AI.** Agent Inbox is a placeholder. Insights shows charts from real movement and sales data (no forecasting yet).

## Ports

| App | URL |
| --- | --- |
| Web | http://127.0.0.1:43123 |
| API | http://127.0.0.1:43124 |
| API docs | http://127.0.0.1:43124/docs |

## Quick start

### Backend

**macOS / Linux**

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 43124 --reload
```

**Windows (PowerShell)**

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
Copy-Item .env.example .env
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 43124 --reload
```

Health check: `GET http://127.0.0.1:43124/health`

### Frontend

**macOS / Linux**

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

**Windows (PowerShell)**

```powershell
cd frontend
npm install
Copy-Item .env.example .env.local
npm run dev
```

Set `NEXT_PUBLIC_API_URL=http://127.0.0.1:43124` in `frontend/.env.local`.

Open http://127.0.0.1:43123, sign up at `/signup`, then use the app. Owners can **Load demo data** from the Catalog empty state to populate sample SKUs, stock, sales history, and purchase orders.

## What works in Phase 1

- **Auth** — signup, login, logout, JWT + refresh tokens, tenant isolation
- **Catalog** — products, categories, suppliers, CSV import
- **Inventory** — append-only stock ledger, stock levels, movement history, sales CSV import
- **Orders** — purchase order lifecycle (draft → approved → sent → received), receive via ledger
- **Home** — dashboard summary, needs attention, recent activity
- **Insights** — movements-over-time and top-sellers charts (read-only)
- **Accounts** — stock value, open PO value, payables, supplier totals (read-only)
- **Settings** — business profile, locations, team (owner-only), autonomy rules (stored only)
- **Onboarding** — demo seed API and `scripts/seed_demo.py`

Staff users can manage day-to-day stock and orders. Only **owners** can approve purchase orders, change settings, and manage team members.

## Tests

```bash
cd backend
source .venv/bin/activate   # or .\.venv\Scripts\Activate.ps1 on Windows
pytest
```

## Configuration

Backend settings come from `backend/.env` (see `backend/.env.example`):

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | SQLite file locally (`sqlite:///./inventory.db`) |
| `JWT_SECRET` | Required signing key |
| `CORS_ORIGINS` | Must include the frontend dev URL |
| `ACCESS_TOKEN_MINUTES` | Default 15 |
| `REFRESH_TOKEN_DAYS` | Default 7 |

## Project layout

```
frontend/     Next.js App Router UI
backend/      FastAPI API, SQLAlchemy, Alembic
docs/         Architecture, data model, workflow
AGENTS.md     Rules for contributors and coding agents
```

Read `AGENTS.md` and `docs/` before changing schema or business rules.

## Main API routes

All application routes are under `/api/v1` except `/health`.

| Area | Examples |
| --- | --- |
| Auth | `POST /auth/signup`, `/auth/login`, `/auth/refresh`, `GET/PATCH /auth/me`, `POST /auth/change-password` |
| Onboarding | `GET /onboarding/status`, `POST /onboarding/complete`, `POST /onboarding/load-demo-data` |
| Catalog | `GET/POST /products`, `/suppliers`, `/categories`; `POST /products/{id}/restore`, `/suppliers/{id}/restore` |
| Inventory | `GET /inventory/stock`, `POST /inventory/movements`, `POST /inventory/sales` |
| Orders | `GET/POST /purchase-orders`, `POST .../transition` |
| Dashboard | `GET /dashboard/summary`, `/needs-attention`, `/activity` |
| Insights | `GET /insights/movements-over-time`, `/top-sellers` |
| Accounts | `GET /accounts/summary`, `/by-supplier` |
| Settings | `PATCH /settings/business`, `/locations` (+ `/{id}/restore`), `/users` (+ `/{id}/role`, `/{id}/active`), `/autonomy-rules` |
| Audit | `GET /audit-log` (owner) |
| Import | `POST /products/import-csv`, `POST /sales/import-csv` |

Dashboard, insights, and accounts return `409 onboarding_required` until the owner finishes onboarding.
