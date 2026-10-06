# Architecture

Phase 1 is a Next.js client and a FastAPI server. The browser never touches the database. The demand forecast is computed in the API from sale history. The Phase 3 AI layer adds an LLM gateway, versioned prompts, a tool registry, `BaseAgent`, and a LangGraph chat orchestrator. Langfuse and LangChain agents are later and are not dependencies.

See [PLAN.md](PLAN.md), [WORKFLOW.md](WORKFLOW.md), [DATA_MODEL.md](DATA_MODEL.md), and [ORCHESTRATOR.md](ORCHESTRATOR.md).

## System

```mermaid
flowchart TB
  subgraph client ["Browser"]
    UI["Next.js UI"]
  end

  subgraph server ["FastAPI"]
    Routers[Routers]
    Services["Services as plain functions"]
    Repos[Repositories]
    Models[SQLAlchemy models]
  end

  DB[("SQLite or PostgreSQL")]

  UI -->|"HTTPS JSON, JWT"| Routers
  Routers --> Services
  Services --> Repos
  Repos --> Models
  Models --> DB

  subgraph later ["Phase 3"]
    Gateway[LLM gateway]
    Tools[Agent tools]
    BaseAgent[BaseAgent]
    Orch[LangGraph orchestrator]
  end

  Orch --> BaseAgent
  BaseAgent --> Gateway
  BaseAgent --> Tools
  Tools -->|"same service functions"| Services
```

## Components

| Piece | Role |
| --- | --- |
| Next.js UI | App Router, TypeScript, Tailwind, shadcn/ui. Renders workflow screens and calls the API. |
| Routers | HTTP, auth dependency, status codes. Map requests to services. No business rules. |
| Pydantic schemas | Request and response models. Decimal fields serialize as JSON strings. |
| Services | All business rules, as plain functions. Phase 3 registers these as agent tools without rewriting them. |
| Ledger service | The only writer of `stock_movements`. Insert only. |
| Audit service | The only writer of `audit_log`. Called in the same transaction as the change it records. |
| Forecast service | Reads `sale` movements and returns a 14-day demand forecast per SKU. Does not write stock or purchase orders. |
| LLM gateway | Provider-agnostic `complete` / `complete_structured`. Providers: `fake`, `gemini`, `groq`, `ollama`. Daily UTC request and token budgets per business. Structured output uses JSON schema when the provider supports it, otherwise parse, validate, and retry up to twice. |
| Prompt registry | Versioned files under `app/llm/prompts/`. Every LLM call records prompt name and version. |
| Agent tools | Thin typed wrappers over services. Tenant-scoped via `AgentContext`. Write tools only create `agent_suggestions`. |
| BaseAgent | Name, allowlist, max tool calls, `run(task, context)`. Concrete procurement agents are later. |
| Orchestrator | LangGraph pipeline: understand → validate → plan → approve_plan → dispatch → aggregate → reply. Slash commands, free text, and compound requests. SSE events. |
| Repositories | Queries and inserts scoped by `business_id`. No business rules. |
| Models | One SQLAlchemy mapping shared by SQLite and PostgreSQL. |
| Alembic | Migrations for both databases. No database-specific types. |

Phase 1 modules: auth, onboarding, catalog, inventory, purchase orders, suppliers, dashboard reads, team, settings, audit read. Phase 2 adds the forecast read on Insights. Phase 3 adds the LLM gateway, prompts, tools, `BaseAgent`, and the chat orchestrator. Inbox UI and filled-in procurement agents are later.

## LLM layer

Tests always use `LLM_PROVIDER=fake`. The fake provider returns scripted responses keyed by prompt name and never opens a network connection. Live providers are selected by env (`gemini`, `groq`, `ollama`) with timeouts and exponential backoff on rate limits.

The daily budget is one UTC calendar day per business (`llm_usage_counters`). A call that would exceed the request or token cap fails with `{"detail": "...", "code": "llm_budget_exceeded"}`.

Untrusted product names, supplier emails, and tool JSON are wrapped in `<<DATA>>` blocks. That text cannot change the tool allowlist or system instructions.

`reorder_recommendations` is deterministic Python (on-hand, reorder point, 14-day forecast). The LLM does not compute quantities.

## Data flow

**Read on-hand.** The UI requests on-hand for a product and location. The stock service returns `SUM(quantity)` from `stock_movements`. Products have no on-hand column.

**Post a movement.** The UI submits a receipt, sale, adjustment, or transfer. The router calls a service. The ledger service inserts one row, or two rows for a transfer, then the audit service inserts `audit_log`, in one transaction. The response includes the new on-hand sum.

**Receive a purchase order.**

```mermaid
sequenceDiagram
  actor Owner
  participant UI as Next.js
  participant Router
  participant PO as Purchase order service
  participant Ledger as Ledger service
  participant Audit as Audit service
  participant DB as Database

  Owner->>UI: Receive quantities
  UI->>Router: POST receive
  Router->>PO: receive_items
  PO->>Ledger: post purchase_receipt rows
  Ledger->>DB: INSERT stock_movements
  PO->>DB: UPDATE purchase order status via repository
  PO->>Audit: before and after
  Audit->>DB: INSERT audit_log
  PO-->>UI: order plus on-hand
```

The purchase-order service does not update a stored on-hand balance. Received quantity on a line is the sum of its `purchase_receipt` movements.

## Stack

| Layer | Choice |
| --- | --- |
| Frontend | Next.js (App Router), TypeScript, Tailwind, shadcn/ui |
| Backend | FastAPI, SQLAlchemy 2, Alembic, Pydantic v2 |
| Database | SQLite for local dev. PostgreSQL (Supabase or Neon free tier) for deploy |
| Auth | JWT access token plus refresh token. Passwords hashed with argon2id |
| Tests | pytest for backend services |
| Forecast | Weekly seasonal naive (or a short-history daily average), computed in the forecast service. Not statsforecast or Prophet. |
| LLM | Gateway in `app/llm/`. Default and CI provider is `fake`. Live: Gemini, Groq, or Ollama over HTTP. |
| Orchestrator | LangGraph in `app/orchestrator/`. Chat runs under `/api/v1/chat`. |
| Later | Langfuse, filled-in procurement and exception agents |

Auth details:

- Access token lasts 15 minutes. Claims: `sub` (user id), `business_id`, `role`.
- Refresh token lasts 7 days. It is an opaque random value stored only as a SHA-256 hash in `refresh_tokens`. Rotating refresh revokes the old row and inserts a new one.
- Password hashes use argon2id (`argon2-cffi`). Refresh tokens are not argon2-hashed.

Local dev uses `DATABASE_URL` pointing at a SQLite file. Deploy points the same setting at PostgreSQL. Application code does not branch on the dialect.

## Key design rules

1. **Layered backend.** Routers call services. Services call repositories and models. All business logic lives in the service layer as plain functions, because in Phase 3 these become agent tools.
2. **Stock is an append-only ledger.** Table `stock_movements` is insert-only. Current stock is derived from it and never edited directly. Corrections are new rows.
3. **`audit_log` exists from day one.** Every state change records who, what, when, before, and after, so agent decisions can be traced later.
4. **Money uses Decimal, never float.** Columns are `Numeric(18, 4)`. Python values are `decimal.Decimal`. JSON encodes them as strings.
5. **One model set for SQLite and PostgreSQL.** Use `Numeric` for money and quantity, `CHAR(36)` for ids (app-generated UUID strings), `VARCHAR` plus `CHECK` for enums, and `JSON` for audit payloads. No PostgreSQL-only column types and no float columns.
6. **Tenant scope comes from the token.** Repository reads and writes for business data filter on `business_id` from the JWT. The client's body does not choose the tenant.
7. **LLM foundation is isolated.** Tests use the fake provider. Write tools only create `agent_suggestions`. The forecast service and replenishment math stay in Python. Orchestrator plans are validated in code. LangGraph stores run state on `agent_runs`, not checkpoint tables.
