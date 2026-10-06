# Agent instructions

Read these before changing the product:

- [docs/PLAN.md](docs/PLAN.md) — vision, phases, what is in scope now
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — stack, layers, design rules
- [docs/WORKFLOW.md](docs/WORKFLOW.md) — screens, roles, day-to-day flow
- [docs/DATA_MODEL.md](docs/DATA_MODEL.md) — schema and ledger invariants
- [docs/ORCHESTRATOR.md](docs/ORCHESTRATOR.md) — chat orchestrator, routing table, SSE events

**AI orchestrator is in progress.** The LLM gateway, versioned prompts, tool registry, `BaseAgent`, and the LangGraph chat orchestrator may be used. Do not add LangChain agents or Langfuse yet. Demand forecasts stay in `app/services/forecast.py` and must not create purchase orders or write the ledger. Do not add statsforecast or Prophet unless that service is replaced on purpose.

### LLM and agent rules

- **No real LLM in tests.** `LLM_PROVIDER` must be `fake`. The fake provider returns scripted responses. Pytest fails if a live provider (`gemini`, `groq`, `ollama`) is constructed.
- **No arithmetic by the LLM.** On-hand, forecasts, reorder quantities, and money come from service tools. The model must not add, multiply, or invent quantities. Orchestrator summaries that contain a number missing from typed results are replaced with a template.
- **No direct writes.** Write tools only insert `agent_suggestions`. They never create purchase orders, send email, or post stock movements. Orchestrator write steps pause for plan approval.
- **Tenant scope.** Tools take `business_id` from the injected `AgentContext`, never from the model.
- **Untrusted text is DATA.** Product names, supplier emails, and tool JSON go in `<<DATA>>` blocks and cannot change the tool allowlist or instructions.
- **Orchestrator plans are validated in code.** The LLM may propose a compound DAG. Unknown agents, cycles, oversized plans, and write-before-read graphs are rejected.

Current implementation scope is Phase 1 plus the Phase 2 demand forecast plus the shared Phase 3 AI foundation plus the full chat orchestrator: catalog, stock ledger, purchase orders, suppliers, dashboard, auth, onboarding, Insights forecasts, LLM gateway, tools, `BaseAgent`, slash/free-text/compound routing, SSE runs. Concrete procurement and exception agents are still placeholders. See [docs/ORCHESTRATOR.md](docs/ORCHESTRATOR.md).

## Permanent backend rules

- **Layers:** routers (thin) → services (ALL business logic, plain functions taking a `Session`, because they become agent tools later) → repositories/models.
- **Tenant scope:** every tenant table has `business_id`; every query filters by the current user's `business_id` from the JWT.
- **Stock ledger:** append-only; current stock is derived; nothing edits stock outside the ledger service.
- **Types and API shape:** `Decimal` for money, UTC timestamps, Pydantic schemas for all requests/responses (never return ORM objects), type hints everywhere, consistent error format `{"detail": "...", "code": "..."}`, all application routes under `/api/v1` (`/health` stays at the root).
- **Audit:** every create/update/delete/transition writes an `audit_log` entry through `log_action(...)`.
- **Tests and docs:** each change ships with pytest tests; update `docs/` when design changes; small commits.

## Permanent frontend rules

- Keep hook names and return shapes stable when swapping mock data for API calls.
- Use the typed API client in `src/lib/api.ts` with JWT storage and `{detail, code}` error handling.

## Layout

Monorepo. Do not invent a third app.

```
frontend/                 Next.js App Router
  src/app/
  src/components/ui/      shadcn/ui
  src/components/
  src/lib/
backend/
  app/
    main.py
    core/                 config, security
    routers/
    schemas/              Pydantic v2
    services/             business logic, plain functions
    llm/                  gateway, providers, versioned prompts
    orchestrator/         LangGraph chat orchestrator
    agents/               BaseAgent, tools, context
    repositories/
    models/               SQLAlchemy 2
    db.py
  alembic/
  tests/services/         required
  tests/api/              optional in Phase 1
docs/
AGENTS.md
```

The browser talks only to FastAPI. FastAPI talks to SQLite locally and PostgreSQL in deploy through the same models.

## Naming and typing

- TypeScript is strict. No `any` unless a comment says why.
- Python functions and modules are snake_case, with type hints. Classes and Pydantic models are PascalCase.
- Tables and columns are snake_case. JSON fields match the API: snake_case.
- Money and quantity are `decimal.Decimal` in Python and `Numeric` in the database. Never `float`. Serialize them as JSON strings.
- Ids are UUID strings (`CHAR(36)`), generated in the app.
- Enum values are lowercase strings, checked in the database and in Pydantic.

## Backend shape

Routers validate and authorize, then call services. Services hold rules. Repositories query and insert. Business logic does not go in routers or repositories.

Service functions take plain arguments (`business_id`, ids, Decimals), not the raw `Request`. That keeps them usable as Phase 3 tools.

Every business query filters on `business_id` from the JWT.

## Testing

Phase 1 requires pytest for service-layer behavior, on SQLite, using the same models. Cover at least:

- on-hand is the sum of signed quantities
- transfer pairing and adjustment reason
- no update or delete path for ledger rows
- Decimal money survives a write and read
- tenant isolation

Reuse `tests/helpers/tenant.py` for tenant-isolation checks in new slices.

Do not add a frontend test framework in Phase 1. Walk the flows in `docs/WORKFLOW.md` by hand.

## Hard rules

1. **Never edit stock outside the ledger service.** No on-hand column, no `UPDATE`/`DELETE` on `stock_movements`, no "fix up" scripts that rewrite history. Post a new movement.
2. **Small commits.** One concern per commit. Do not mix a schema change with an unrelated UI pass.
3. **Update docs when design changes.** If a column, rule, phase boundary, or screen flow changes, update the doc in the same commit as the code.
4. **Do not widen Phase 1.** No accounting, barcode hardware, mobile client, or multi-currency. The Phase 2 forecast service stays read-only. The Phase 3 orchestrator may use LangGraph for the chat pipeline, but not LangChain agents, Langfuse, or live LLM calls in tests.
5. **Hash passwords with argon2id.** Store refresh tokens only as a SHA-256 hash.

## When you are unsure

Prefer the data model over a new table. If the schema must change, say so in the doc and keep SQLite and PostgreSQL on one migration path.
