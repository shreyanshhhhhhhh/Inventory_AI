# Plan

Inventory management for a small retailer (about 50–500 SKUs). The owner should trust on-hand counts, place purchase orders, and see what is low.

Later phases add the differentiator: agentic AI. Agents turn forecasts into actions, handle exceptions, and explain every decision. Those phases are not this project yet.

**Current work is project prep and Phase 1 only. Phase 1 has no AI** — no agents, no LLM calls, no forecasting.

Design lives in [ARCHITECTURE.md](ARCHITECTURE.md), [WORKFLOW.md](WORKFLOW.md), and [DATA_MODEL.md](DATA_MODEL.md). Coding agents follow [AGENTS.md](../AGENTS.md).

## Phase 1 assumptions

- One business per account. A user has one business. The owner adds staff to that business.
- Currency is one ISO 4217 code per business, set in onboarding and immutable afterward.
- On-hand stock is `SUM(stock_movements.quantity)` per product per location. Quantity is signed (inbound positive, outbound negative).
- A transfer is two ledger rows (out at the source, in at the destination) that share a `transfer_group_id`. Each row has one `location_id`.
- An adjustment requires a reason.
- Products are archived, not hard-deleted, so ledger history stays valid. Locations and suppliers are archived the same way once they are referenced.
- Auth is a JWT access token plus a refresh token. Passwords are hashed with argon2id.
- SQLite (local) and PostgreSQL (deploy) share one set of SQLAlchemy models. Money is `Numeric`, never float.
- A sale is a ledger posting, not a customer sales-order document.
- Reorder point is one number per SKU, compared with on-hand across all locations.
- Staff logins are created in the app by the owner (name, email, temporary password). Phase 1 does not send email.
- The ledger service rejects any posting that would make on-hand negative at that location.
- Inventory value is computed as on-hand times the preferred supplier unit cost. It is not stored. SKUs without a preferred cost show no value.
- CSV opening quantities are `adjustment` rows with reason `Opening balance`.

## Non-goals

No mobile app, barcode hardware, accounting or general ledger, multi-currency, multi-warehouse optimization, or AI inside Phase 1.

## Phases

### P0 — Scope and design

- **Goal:** Lock the product slice, architecture, workflow, and schema before code.
- **Deliverables:** This plan, architecture, workflow, data model, and `AGENTS.md`.
- **Why it matters:** Phase 1 services become the tools agents call later. A sloppy ledger cannot be bolted on afterward.
- **Done when:** The five docs are merged, Phase 1 is explicitly non-AI, and open product questions are either decided here or listed for the owner.

### P1 — Core inventory (no AI)

- **Goal:** One business can run day-to-day stock and purchasing without AI.
- **Deliverables:** Auth, onboarding, catalog, locations, suppliers, append-only stock ledger, purchase orders, basic home dashboard, team accounts, settings, audit log. Agent Inbox and Insights stay visible placeholders.
- **Why it matters:** This is the system of record. Forecasts and agents in later phases read and write through these services.
- **Done when:**
  - An owner can sign up, finish onboarding (CSV or demo data), and land on the dashboard.
  - Receipts, sales, adjustments, and transfers change on-hand only by inserting ledger rows. On-hand equals the sum of signed quantities.
  - Receiving a purchase order posts `purchase_receipt` rows and moves the order status.
  - Adjustments without a reason are rejected. Archived products remain on old ledger rows.
  - A staff user can do stock and orders and cannot manage team, settings, or billing.
  - Pytest covers the ledger, transfer pairing, adjustment reason, tenant scoping, and Decimal money.

### P2 — Data and forecasting

- **Goal:** Turn ledger history into a demand forecast the owner can see.
- **Deliverables:** Demand series from `sale` movements, a forecast per SKU (statsforecast or Prophet), Insights page with real numbers. No automatic purchasing.
- **Why it matters:** The procurement agent needs a quantity to act on.
- **Done when:** Insights shows a forecast from real sales history, and nothing in this phase creates a purchase order.

### P3 — Tool layer, procurement agent, approval inbox

- **Goal:** An agent proposes purchase orders; a person approves them before they exist as orders.
- **Deliverables:** Phase 1 service functions registered as tools, a LangGraph procurement agent, Agent Inbox (approve / reject).
- **Why it matters:** First closed loop from forecast to action, with a human gate.
- **Done when:** A proposal shows up in the inbox, approval calls the same purchase-order service a person uses, and both the proposal and the decision are in `audit_log`.

### P4 — Exception handling

- **Goal:** Stock and order problems surface as inbox work, not silent drift.
- **Deliverables:** Exception detection (stockout risk, overdue purchase order, receive mismatch) and agent-suggested next steps in the inbox.
- **Why it matters:** The daily value of agents is catching what the owner will not scan by hand.
- **Done when:** A seeded exception creates an inbox item with a recommended action, and approve / dismiss writes an audit row.

### P5 — Explainability

- **Goal:** Every agent decision can be read in plain language and tied to data.
- **Deliverables:** Explanation on each inbox decision (inputs, tools called, why this action).
- **Why it matters:** A small business will not delegate purchasing it cannot check.
- **Done when:** The owner can open a decision and see why, including the forecast and stock figures that drove it, with an audit trail.

### P6 — Evaluation and guardrails

- **Goal:** Measure agent quality and block unsafe actions.
- **Deliverables:** An evaluation set, guardrails (approval required before a purchase order is placed, no tool that edits stock outside the ledger service, a cap on unapproved spend), Langfuse traces.
- **Why it matters:** Agents that share the ledger with the shop need a checked boundary.
- **Done when:** Evals run with a documented command, traces land in Langfuse, and a test proves a blocked action never writes the ledger or a purchase order.

### P7 — Deploy and polish

- **Goal:** Run the app on hosted Postgres and close the obvious product gaps.
- **Deliverables:** PostgreSQL deploy (Supabase or Neon free tier), configuration, migrations, empty/loading/error states, desktop and mobile layout pass.
- **Why it matters:** Phase 1 can be developed on SQLite; a shop needs a hosted database and a UI that holds up.
- **Done when:** The app runs against PostgreSQL with the same models and migrations, auth works, and the Phase 1 flows in the workflow doc are usable on a phone-width screen.
