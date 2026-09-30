# Agent instructions

Read these before changing the product:

- [docs/PLAN.md](docs/PLAN.md) — vision, phases, what is in scope now
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — stack, layers, design rules
- [docs/WORKFLOW.md](docs/WORKFLOW.md) — screens, roles, day-to-day flow
- [docs/DATA_MODEL.md](docs/DATA_MODEL.md) — schema and ledger invariants

**Phase 1 has no AI.** Do not add agent frameworks, LLM calls, or forecasting libraries until those phases. That includes LangGraph, LangChain, any chat/completions client, statsforecast, Prophet, and Langfuse.

Current implementation scope is Phase 1 only: catalog, stock ledger, purchase orders, suppliers, basic dashboard, auth, and onboarding.

## Layout

Monorepo. Do not invent a third app. Create these trees when implementation starts; do not create them as empty placeholders during planning.

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

Do not add a frontend test framework in Phase 1. Walk the flows in `docs/WORKFLOW.md` by hand.

## Hard rules

1. **Never edit stock outside the ledger service.** No on-hand column, no `UPDATE`/`DELETE` on `stock_movements`, no "fix up" scripts that rewrite history. Post a new movement.
2. **Small commits.** One concern per commit. Do not mix a schema change with an unrelated UI pass.
3. **Update docs when design changes.** If a column, rule, phase boundary, or screen flow changes, update the doc in the same commit as the code.
4. **Do not widen Phase 1.** No accounting, barcode hardware, mobile client, multi-currency, or AI dependencies.
5. **Hash passwords with argon2id.** Store refresh tokens only as a SHA-256 hash.

## When you are unsure

Prefer the data model over a new table. If the schema must change, say so in the doc and keep SQLite and PostgreSQL on one migration path.
