# Workflow

Phase 1 is a person using the app. The agent loop at the bottom is future work and is not built in Phase 1.

## First visit

1. **Landing.** Explain a straight inventory tool for a small shop: catalog, on-hand counts, suppliers, purchase orders. Actions are sign up and log in.
2. **Sign up or log in.** Email and password. Passwords are hashed with argon2id. Session is an access token plus a refresh token.
3. **Onboarding, once.** The owner cannot open the dashboard until this wizard finishes. A staff user never sees it.
   1. Business name and currency (ISO 4217). Currency cannot be changed later in Phase 1.
   2. Locations. At least one. One location is the default.
   3. Catalog, either a CSV import or demo data (about 20 SKUs, two locations, two suppliers, a few movements, one open purchase order).
   4. Suppliers. Demo data and a CSV that includes suppliers satisfy this step. Otherwise the owner adds at least one supplier.
4. **Home dashboard.** Later logins go straight here.

Opening quantities from the CSV are posted as `adjustment` movements with reason `Opening balance`. They are not a column on the product.

CSV header: `sku`, `name`, `category`, `location`, `quantity`, `unit`, `reorder_point`, `supplier`, `unit_cost`, `lead_time_days`. Required fields are `sku` and `name`. `unit_cost` requires `supplier`.

## Sidebar

| Section | What it does |
| --- | --- |
| Home | On-hand units, inventory value where a preferred supplier cost exists, low-stock list (`on-hand <= reorder_point`), open purchase orders, recent movements. |
| Catalog | Categories, products, archive, supplier links (cost, lead time, preferred flag). |
| Inventory | On-hand by location, post a sale, adjustment, or transfer, movement history. |
| Orders & Suppliers | Suppliers and purchase orders: draft, approved, sent, received, or cancelled. |
| Agent Inbox | Chat with the orchestrator over SSE. Slash commands and free text, including compound requests. Write plans wait for Run / Edit / Cancel. `/reorder` lists what to buy. `/draft-po <supplier>` stores a purchase suggestion. Approving it creates a draft purchase order. `/email <supplier> <order|chase|expedite|delay-notice>` stores an email draft. Approve and Send, Save draft, or Reject. Nothing is delivered until the owner approves. |
| Insights | Demand forecast per SKU for the next 14 days, from `sale` movements, plus movement and top-seller charts. Forecasting does not create a purchase order. |
| Accounts (lite) | Profile, password change, and the team list. This is not a general ledger. |
| Settings | Business name and locations. Currency is shown and not editable. Owners also set the nightly exception scan hour. |

Desktop uses a sidebar. Narrow screens use the same sections in a nav drawer.

## Roles

Two roles. There is no finer permission matrix in Phase 1.

**Owner** has full access: catalog, inventory, purchase orders, suppliers, settings, and team. Billing does not exist in Phase 1; when it does, it is owner-only.

**Staff** handle day-to-day stock and orders: view the catalog, post sales, adjustments, transfers, and receipts, and create and receive purchase orders. Staff can add a product or supplier when that is needed to record stock or an order. Staff cannot change settings, currency, locations, team membership, or billing.

The owner adds a staff member from Accounts with name, email, and a temporary password. Phase 1 does not send invite email. Deactivate a user instead of deleting them; their ledger and audit rows stay. Staff cannot trigger owner-only orchestrator intents (`/draft-po`, `/email`).

## Daily stock and purchasing

- **Sale.** Post one movement per SKU at a location, quantity negative. Lines from one checkout share a `sale_group_id`. The service rejects a sale that would push on-hand below zero.
- **Adjustment.** Signed quantity and a required reason. Use this for damage, count corrections, and opening balances.
- **Transfer.** Two rows in one action: negative at the source, positive at the destination, same absolute quantity, same `transfer_group_id`.
- **Purchase order.** Draft lines (product, quantity, unit cost snapshot), then approve and send. Receiving posts `purchase_receipt` rows with positive quantity. Status moves `draft` → `approved` → `sent` → `received`, or to `cancelled`. There is no partial-receipt status.

Inventory value on Home is on-hand times the preferred supplier `unit_cost`. If no preferred cost exists, the UI shows the value as unknown.

## Chat orchestrator

`POST /api/v1/chat/runs` accepts slash commands and free text, including compound requests. The Agent Inbox chat UI streams SSE events, shows a thinking bubble then a plan checklist, and hydrates the agent timeline from `GET /api/v1/chat/runs/{id}`. `/stock` and `/forecast` return live stock tables and demand charts from the forecast agent. `/scan` runs detectors in code and lists findings with playbook actions. `/reorder` returns reorder lines from the replenishment service. `/draft-po <supplier>` pauses for plan approval, then stores a guarded purchase suggestion. `/email <supplier> chase` pauses, then stores a grounded email draft. The owner approves or rejects purchase suggestions from the card or Approvals. Email cards let the owner edit subject and body, then Approve and Send, Save draft, or Reject. Approval of a purchase suggestion creates a draft purchase order. Sending email uses `EmailSender` (console in dev). Write plans wait for Run / Edit / Cancel. See [ORCHESTRATOR.md](ORCHESTRATOR.md).

## Daily agent workflow

The exception monitor, replenishment agent, and supplier communication agent propose. They do not place a purchase order, send email, or post stock on their own. The owner accepts or rejects a purchase suggestion in Agent Inbox. Acceptance creates a draft purchase order through the purchase-order service. A supplier email is sent only after Approve and Send. The draft, the decision, and the send are `audit_log` rows. A scheduled run of every agent and any ledger post from an agent are still ahead.

1. **Trigger.** A schedule or a manual "run agents" action. `/reorder` and `/draft-po` are the manual path today. Nightly exception scans are separate.
2. **Detect.** Low stock, forecasted stockout, overdue purchase orders, receive mismatches. The exception monitor covers the detectors in [ORCHESTRATOR.md](ORCHESTRATOR.md).
3. **Agents act.** Replenishment copies quantities and costs from services and may store a purchase suggestion. It does not commit purchasing on its own.
4. **Approval inbox.** The owner accepts or rejects each purchase suggestion. Email drafts wait for Approve and Send, Save draft, or Reject.
5. **Execute.** Acceptance of a purchase suggestion creates a draft purchase order. Approve and send stay on the Orders screen. Email send uses `EmailSender` after owner approval.
6. **Audit log.** The proposal, the human decision, the draft, and the send are `audit_log` rows. Accept and reject history also stays on the suggestion payload for later evaluation.
