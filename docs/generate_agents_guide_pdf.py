"""Generate docs/Inventory_AI_Agents_and_Commands_Guide.pdf from project docs."""

from __future__ import annotations

from pathlib import Path

from fpdf import FPDF

OUTPUT = Path(__file__).resolve().parent / "Inventory_AI_Agents_and_Commands_Guide.pdf"


class GuidePDF(FPDF):
    def header(self) -> None:
        if self.page_no() == 1:
            return
        self.set_font("Helvetica", "I", 9)
        self.set_text_color(100, 100, 100)
        self.cell(0, 8, "Inventory AI - Agents and Slash Commands Guide", align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def footer(self) -> None:
        self.set_y(-12)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 8, f"Page {self.page_no()}", align="C")

    def title_page(self) -> None:
        self.add_page()
        self.ln(40)
        self.set_font("Helvetica", "B", 24)
        self.set_text_color(20, 20, 20)
        self.multi_cell(self.epw, 12, "Inventory AI", align="C")
        self.ln(4)
        self.set_font("Helvetica", "", 16)
        self.multi_cell(self.epw, 10, "Agents and Slash Commands Guide", align="C")
        self.ln(12)
        self.set_font("Helvetica", "", 11)
        self.set_text_color(60, 60, 60)
        body = (
            "This guide explains every AI agent in Inventory AI: why it exists, what it does, "
            "which tools it uses, and how it fits the owner approval workflow. It also documents "
            "every slash command available in Agent Inbox chat (/stock, /forecast, /scan, and so on), "
            "including examples, roles, and what appears in the UI.\n\n"
            "Inventory AI is inventory management for a small retailer (roughly 50-500 SKUs). "
            "Phase 1 is the system of record: catalog, stock ledger, purchase orders, suppliers. "
            "Phase 2 adds demand forecasts from sale history. Phase 3 adds agentic AI: agents propose; "
            "people approve. Agents never post stock, never send email, and never create purchase orders "
            "without owner approval."
        )
        self.multi_cell(self.epw, 6, body)
        self.ln(6)
        self.set_font("Helvetica", "I", 10)
        self.multi_cell(self.epw, 5, "Generated from docs/ORCHESTRATOR.md, AGENTS.md, WORKFLOW.md, and PLAN.md.")

    def h1(self, text: str) -> None:
        self.ln(4)
        self.set_font("Helvetica", "B", 16)
        self.set_text_color(20, 20, 20)
        self.multi_cell(self.epw, 9, text)
        self.ln(2)

    def h2(self, text: str) -> None:
        self.ln(3)
        self.set_font("Helvetica", "B", 13)
        self.set_text_color(30, 30, 30)
        self.multi_cell(self.epw, 8, text)
        self.ln(1)

    def h3(self, text: str) -> None:
        self.ln(2)
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(40, 40, 40)
        self.multi_cell(self.epw, 7, text)
        self.ln(1)

    def body(self, text: str) -> None:
        self.set_font("Helvetica", "", 10)
        self.set_text_color(30, 30, 30)
        self.multi_cell(self.epw, 5.5, text)
        self.ln(1)

    def bullet(self, text: str) -> None:
        self.set_font("Helvetica", "", 10)
        self.set_text_color(30, 30, 30)
        self.multi_cell(self.epw, 5.5, f"  - {text}")
        self.ln(0.5)

    def table_header(self, cols: list[str], widths: list[int]) -> None:
        self.set_font("Helvetica", "B", 9)
        self.set_fill_color(230, 230, 230)
        for col, width in zip(cols, widths):
            self.cell(width, 7, col, border=1, fill=True)
        self.ln()

    def table_row(self, cols: list[str], widths: list[int]) -> None:
        self.set_font("Helvetica", "", 8)
        x0 = self.get_x()
        y0 = self.get_y()
        heights: list[float] = []
        lines_per_col: list[list[str]] = []
        for col, width in zip(cols, widths):
            self.set_xy(x0 + sum(widths[: cols.index(col)]), y0)
            lines = self.multi_cell(width, 4, col, split_only=True)
            lines_per_col.append(lines)
            heights.append(len(lines) * 4)
        row_h = max(heights) if heights else 4
        if y0 + row_h > 270:
            self.add_page()
            y0 = self.get_y()
        for idx, (col, width) in enumerate(zip(cols, widths)):
            x = x0 + sum(widths[:idx])
            self.rect(x, y0, width, row_h)
            self.set_xy(x, y0)
            for line in lines_per_col[idx]:
                self.cell(width, 4, line, border=0)
                self.set_xy(x, self.get_y())
        self.set_xy(x0, y0 + row_h)


def build() -> None:
    pdf = GuidePDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.title_page()

    # --- Orchestrator ---
    pdf.add_page()
    pdf.h1("1. How the Chat Orchestrator Works")
    pdf.body(
        "All agent work starts in Agent Inbox chat. You type a slash command or plain English. "
        "The orchestrator is a LangGraph pipeline with seven nodes: understand, validate, plan, "
        "approve_plan, dispatch, aggregate, and reply. Run state is stored on agent_runs with "
        "plan_data, state_data, and events_data. The browser receives Server-Sent Events (SSE) "
        "so you see thinking, a plan checklist, step progress, typed result cards, and a summary."
    )
    pdf.h2("Pipeline stages")
    pdf.bullet("understand: Slash commands map directly to intents. Free text goes to the LLM, which returns intents with confidence. Names like supplier or SKU are resolved to tenant ids in code.")
    pdf.bullet("validate: Staff cannot run owner-only intents. Low confidence or ambiguous text becomes a clarification card. Unknown requests are refused with the supported command list.")
    pdf.bullet("plan: Single intents use a fixed routing table. Compound requests (e.g. /scan /reorder /email) let the LLM propose a DAG, which code validates for cycles, unknown agents, and write-before-read errors.")
    pdf.bullet("approve_plan: Any plan with a write step (draft PO or draft email) pauses until the owner clicks Run, Edit, or Cancel. Read-only plans run immediately.")
    pdf.bullet("dispatch: Steps run in dependency order; independent reads may run in parallel. Each step returns a TypedResult (structured data), not free-form prose.")
    pdf.bullet("aggregate: The LLM writes a short summary. If it invents a number not in the typed results, code replaces the summary with a template.")
    pdf.bullet("reply: Emits token, card, and done events to the chat UI.")

    pdf.h2("Core safety rules (all agents)")
    pdf.bullet("No LLM arithmetic: on-hand, forecasts, reorder quantities, and money come from service tools only.")
    pdf.bullet("No direct writes: write tools insert agent_suggestions and supplier_messages drafts only.")
    pdf.bullet("Tenant scope: business_id always comes from the JWT, never from the model.")
    pdf.bullet("Untrusted text is DATA: product names and tool JSON cannot change instructions or tool allowlists.")
    pdf.bullet("Grounding: summaries and explanations that contain numbers or dates not in evidence are replaced with templates.")

    # --- Forecast agent ---
    pdf.add_page()
    pdf.h1("2. Forecast Agent")
    pdf.h2("Use case")
    pdf.body(
        "A shop owner needs to see expected demand before buying stock. The forecast agent answers "
        "questions about on-hand levels and projected sales. It powers the /stock and /forecast "
        "commands in chat and complements the Insights page charts."
    )
    pdf.h2("Why it was added")
    pdf.body(
        "Phase 2 added demand forecasting from sale movements (read-only, no purchase orders). "
        "Phase 3 wrapped that service in an agent so chat can show forecasts and stock in one place. "
        "Later agents (replenishment, exception monitor) consume the same forecast numbers."
    )
    pdf.h2("Tasks")
    pdf.h3("forecast")
    pdf.body(
        "Runs demand analysis for one SKU or all products. Calls run_forecast (backtests daily_average "
        "vs seasonal_naive over the last 7 days, picks lower WAPE), get_forecast, get_history, and "
        "get_forecast_accuracy. Returns a forecast_chart card with per-SKU: history units, forecast "
        "units, trend (up/down/flat), chosen model, backtest WAPE, naive WAPE, confidence, and caveats "
        "(low_history, intermittent_demand). The LLM may add one grounded interpretation sentence; "
        "invented numbers are replaced with a template."
    )
    pdf.h3("get_stock")
    pdf.body(
        "Returns on-hand by product and location via get_stock. Shows a stock_table card with SKU, "
        "name, on-hand, reorder point, and low/out status. Read-only."
    )
    pdf.h2("Tools used")
    pdf.bullet("get_stock, get_forecast, get_history, run_forecast, get_forecast_accuracy")
    pdf.h2("What it does NOT do")
    pdf.bullet("Does not create purchase orders or post stock movements.")
    pdf.bullet("Does not invent quantities; all numbers come from the forecast and inventory services.")

    # --- Exception monitor ---
    pdf.add_page()
    pdf.h1("3. Exception Monitor Agent")
    pdf.h2("Use case")
    pdf.body(
        "Small shops miss stockouts, overdue POs, demand spikes, and data errors because nobody scans "
        "every SKU daily. The exception monitor runs deterministic detectors and surfaces findings in "
        "chat (/scan) and via a nightly job (owner-configurable in Settings)."
    )
    pdf.h2("Why it was added")
    pdf.body(
        "Phase 4 (exception handling) turns silent drift into inbox work. Detectors run in pure Python; "
        "the LLM only ranks playbook actions from an allowlist. Findings persist to the exceptions table "
        "with structured evidence for the explainer agent."
    )
    pdf.h2("Task: scan")
    pdf.body(
        "1) scan_detectors runs all detectors for the tenant.\n"
        "2) The LLM ranks candidate playbook actions per finding (reorder_now, expedite, alternate_supplier, "
        "transfer_stock, count_stock, ignore).\n"
        "3) record_exception_actions upserts open exceptions and may create generic agent_suggestions "
        "when approval is needed.\n"
        "Returns an exception_list card. Orchestrator treats /scan as read-only (no plan pause), even "
        "though persistence happens inside the agent tools."
    )
    pdf.h2("Detectors (code, not LLM)")
    pdf.bullet("stockout_risk: days of cover (on_hand / daily_demand) below lead time; critical if on-hand is 0 with demand.")
    pdf.bullet("overstock: more than 90 days of cover (180 = high severity).")
    pdf.bullet("demand_spike / demand_drop: last 7 vs prior 7 ratio or robust z-score.")
    pdf.bullet("supplier_delay: overdue approved/sent POs; or supplier reliability score below 0.7 with 2+ overdue.")
    pdf.bullet("data_anomaly: negative on-hand, duplicate sales in the same minute, large unexplained adjustments.")
    pdf.bullet("chase_no_reply: sent supplier chase with no reply after chase_followup_days (default 3).")
    pdf.h2("Evidence stored")
    pdf.body(
        "Each exception stores detector evidence plus reason_codes, forecast method/model, lead time, "
        "and supplier reliability when known. Generic suggestions copy evidence into payload.extra."
    )

    # --- Replenishment ---
    pdf.add_page()
    pdf.h1("4. Replenishment Agent")
    pdf.h2("Use case")
    pdf.body(
        "Turn forecast and on-hand into concrete buy quantities and optional draft purchase-order "
        "suggestions. Answers /reorder (read-only recommendations) and /draft-po (owner write after approval)."
    )
    pdf.h2("Why it was added")
    pdf.body(
        "Phase 3 procurement closes the loop from forecast to action with a human gate. Quantities use "
        "the deterministic formula in replenishment.py: needed = max(reorder_point, forecast_units) + "
        "safety_stock; recommended_quantity = needed - on_hand. The LLM never computes these numbers."
    )
    pdf.h2("Task: recommend")
    pdf.body(
        "Calls reorder_recommendations, get_supplier_reliability, and get_open_pos. The LLM may filter "
        "which SKUs to include, prefer an alternate supplier when the preferred one is late, and set "
        "confidence. Returns a text card with lines, reason codes, and evidence per SKU. Does not write."
    )
    pdf.h2("Task: draft_po")
    pdf.body(
        "Same reads as recommend, then create_po_suggestion per supplier after validate_po_proposal passes. "
        "Stores draft_po suggestions with reason codes (LOW_COVER, FORECAST_UP, SUPPLIER_LATE, "
        "ALTERNATE_SUPPLIER), evidence (on_hand, forecast, lead time, reliability, unit cost), and confidence. "
        "Skips SKUs already covered by open POs. Requires owner role and plan approval before dispatch."
    )
    pdf.h2("Reason codes")
    pdf.bullet("LOW_COVER: on-hand below needed level.")
    pdf.bullet("FORECAST_UP: forecast exceeds reorder point.")
    pdf.bullet("SUPPLIER_LATE: chosen or preferred supplier reliability below 0.7 or has overdue POs.")
    pdf.bullet("ALTERNATE_SUPPLIER: chosen supplier is not the preferred link.")
    pdf.h2("Approval outcome")
    pdf.body(
        "Owner approves a po_suggestion card or Approvals tab item. That creates a draft purchase order "
        "via the same service a person uses. Reject stores a reason on the suggestion and audit_log."
    )

    # --- Guardrail ---
    pdf.add_page()
    pdf.h1("5. Purchase Guardrail (guardrail agent)")
    pdf.h2("Use case")
    pdf.body(
        "Block unsafe or malformed purchase proposals before they become suggestions or orders. "
        "Every write path (draft_po) ends with guardrail.review."
    )
    pdf.h2("Why it was added")
    pdf.body(
        "Phase 6 guardrails: agents share the ledger with the shop, so spend caps, cost matching, "
        "and duplicate-PO checks must run in code without LLM discretion."
    )
    pdf.h2("Task: review")
    pdf.body(
        "Re-validates proposals with validate_po_proposal: supplier and SKUs belong to tenant; "
        "active supplier; positive whole-number quantities; line count and total caps; unit cost matches "
        "product_suppliers within tolerance; no open PO already covering the SKU quantity. "
        "Does not create a purchase order itself."
    )

    # --- Supplier comm ---
    pdf.h1("6. Supplier Communication Agent")
    pdf.h2("Use case")
    pdf.body(
        "Draft supplier emails for order confirmation, chasing overdue POs, expediting, or delay notices. "
        "Triggered by /email and compound plans that include draft emails after scan/reorder."
    )
    pdf.h2("Why it was added")
    pdf.body(
        "Owners chase suppliers manually. This agent fills templates from PO facts (PO number, quantities, "
        "dates) so wording stays grounded. Email is never sent until the owner clicks Approve and Send."
    )
    pdf.h2("Task: draft_emails")
    pdf.body(
        "Uses get_po, get_supplier, get_exception, draft_email. LLM writes greeting, ask, and closing only. "
        "Code renders the template, checks draft_is_grounded (every PO number, quantity, date must appear "
        "in facts), retries once, then falls back to plain template. Inserts supplier_messages (draft) and "
        "a draft_email suggestion. Console mode (EMAIL_SENDER=console) logs only."
    )
    pdf.h2("Email kinds")
    pdf.bullet("order: new order or confirmation.")
    pdf.bullet("chase: follow up on overdue or sent PO (default when supplier has open PO).")
    pdf.bullet("expedite: request faster delivery.")
    pdf.bullet("delay-notice: notify supplier of accepted delay.")
    pdf.h2("Reply handling")
    pdf.body(
        "POST /api/v1/supplier-replies stores inbound text. Extracted dates or delays become owner-approved "
        "suggestions to update PO expected date. chase_no_reply detector fires when no reply after follow-up days."
    )

    # --- Explainer ---
    pdf.add_page()
    pdf.h1("7. Explainer Agent")
    pdf.h2("Use case")
    pdf.body(
        "Owners will not delegate purchasing they cannot verify. The explainer answers why a suggestion "
        "or exception fired, and what would change under different assumptions, using stored evidence only."
    )
    pdf.h2("Why it was added")
    pdf.body(
        "Phase 5 explainability. Every decision should tie to forecast, on-hand, lead time, and supplier "
        "reliability figures that were stored when the decision was made."
    )
    pdf.h2("Task: explain (/why, /explain)")
    pdf.body(
        "Tools: get_suggestion, get_run_trace, get_evidence, get_history. Targets: suggestion id, "
        "exception id, or PO. LLM writes prose from typed evidence only. Post-check: every number and date "
        "in the answer must exist in evidence, else template fallback. Card includes confidence, what would "
        "change the decision, and collapsible evidence table. If evidence cannot answer, says so and lists missing data."
    )
    pdf.h2("Task: whatif (/whatif)")
    pdf.body(
        "Scenarios: supplier delay N days, demand up/down X percent, lead time change. Calls whatif_compare "
        "(replenishment formula with modified inputs, no LLM math). Returns whatif_compare card with before/after "
        "stockout date, recommended quantity, and cost. LLM narrates the difference only."
    )
    pdf.h2("UI integration")
    pdf.bullet("Why? button on PO suggestions, email drafts, exception cards, and Approvals tab.")
    pdf.bullet("Insights Ask why box opens Inbox with the question.")

    # --- Data quality placeholder ---
    pdf.h1("8. Data Quality Agent (placeholder)")
    pdf.body(
        "Registered for /quality but not implemented yet. Returns a typed not implemented yet result so "
        "orchestrator plumbing can be tested. Future scope: catalog and ledger consistency checks."
    )

    # --- Slash commands ---
    pdf.add_page()
    pdf.h1("9. Slash Commands Reference")
    pdf.body(
        "Type commands in Agent Inbox chat. You can combine several in one message for compound plans. "
        "Staff can run read-only commands; draft_po and draft_email are owner-only."
    )

    commands = [
        (
            "/stock [search]",
            "get_stock",
            "forecast.get_stock",
            "No",
            "Owner, Staff",
            "Shows on-hand stock by SKU and location. Optional search filters by product name or SKU. "
            "Returns stock_table card. Use before reordering to see current levels and low/out flags.",
        ),
        (
            "/forecast [sku]",
            "forecast",
            "forecast.forecast",
            "No",
            "Owner, Staff",
            "14-day demand forecast from sale history. Optional SKU or product name. Returns forecast_chart "
            "with trend, model, WAPE, confidence, and daily series. Same math as Insights page.",
        ),
        (
            "/scan or /exceptions",
            "scan_exceptions",
            "exception_monitor.scan",
            "No",
            "Owner, Staff",
            "Runs all exception detectors for the shop. Returns exception_list with severity, recommended "
            "playbook action, and evidence. Persists open exceptions; may create approval suggestions.",
        ),
        (
            "/reorder",
            "reorder",
            "replenishment.recommend",
            "No",
            "Owner, Staff",
            "Deterministic reorder quantities from on-hand, reorder point, safety stock, and forecast. "
            "Shows which SKUs need buying and suggested quantities. Does not create a PO or suggestion.",
        ),
        (
            "/draft-po <supplier> or /po <supplier>",
            "draft_po",
            "replenishment.recommend then draft_po + guardrail",
            "Yes",
            "Owner only",
            "Pauses for plan approval. Recommends quantities, then stores one draft_po suggestion per supplier "
            "after guardrail passes. Remainder of command is supplier name (resolved to id in code). "
            "Approve suggestion in Inbox to create a draft purchase order.",
        ),
        (
            "/email <supplier> [kind]",
            "draft_email",
            "replenishment.recommend then supplier_comm.draft_emails + guardrail",
            "Yes",
            "Owner only",
            "Pauses for plan approval. Kind: order, chase, expedite, delay-notice (default chase if open PO). "
            "Drafts grounded email from PO facts. Owner edits subject/body, then Approve and Send, Save, or Reject.",
        ),
        (
            "/explain or /why <target>",
            "explain",
            "explainer.explain",
            "No",
            "Owner, Staff",
            "Grounded explanation of a suggestion, exception, or PO. Examples: /why suggestion <id>, "
            "/why exception <id>. Free text like why did you suggest 200 units? also maps here. "
            "Returns explanation card with evidence table.",
        ),
        (
            "/whatif <scenario>",
            "whatif",
            "explainer.whatif",
            "No",
            "Owner, Staff",
            "Counterfactual replenishment analysis. Examples: demand up 20%, supplier delay 5 days, "
            "lead time 10 days. Returns whatif_compare before/after card. Math is deterministic in code.",
        ),
        (
            "/quality",
            "data_quality",
            "data_quality.check",
            "No",
            "Owner, Staff",
            "Placeholder: not implemented yet. Will check catalog and ledger data quality when filled in.",
        ),
    ]

    widths = [28, 22, 38, 10, 18, 74]
    pdf.table_header(["Command", "Intent", "Agent.task", "Write", "Role", "Description"], widths)
    for row in commands:
        pdf.table_row(list(row), widths)

    pdf.add_page()
    pdf.h1("10. Compound Requests and Free Text")
    pdf.body(
        "Example: /scan /reorder /email or plain English: scan for problems, reorder what's needed and "
        "draft emails to the suppliers. The LLM proposes a DAG; code validates it. Typical compound flow: "
        "exception_monitor.scan and replenishment.recommend run in parallel; supplier_comm.draft_emails "
        "waits for both; guardrail.review runs last. Write steps require owner Run click on the plan card."
    )
    pdf.h2("Name resolution")
    pdf.body(
        "Supplier names, product names, and SKUs in commands or free text are resolved to tenant-scoped ids "
        "in code. The model never supplies business_id or cross-tenant ids."
    )

    pdf.h1("11. UI Cards and Approval Flow")
    pdf.body("Each finished orchestrator step emits a typed card:")
    pdf.bullet("stock_table, forecast_chart: forecast agent reads.")
    pdf.bullet("exception_list: exception monitor.")
    pdf.bullet("po_suggestion: replenishment draft with Approve/Reject and Why?.")
    pdf.bullet("email_draft: editable subject/body, Approve and Send, Save draft, Reject, Why?.")
    pdf.bullet("explanation: prose, confidence, evidence table, missing-data notice.")
    pdf.bullet("whatif_compare: before/after metrics per SKU.")
    pdf.bullet("clarification / refusal: orchestrator could not proceed safely.")
    pdf.body(
        "Write plans show a plan card with Run / Edit / Cancel before any draft suggestion is stored."
    )

    pdf.h1("12. Roles")
    pdf.bullet("Owner: all commands including /draft-po and /email; approves suggestions and sends email.")
    pdf.bullet("Staff: read-only agent commands (/stock, /forecast, /scan, /reorder, /why, /whatif); "
                 "cannot draft POs or supplier emails.")

    pdf.h1("13. Nightly Exception Scan")
    pdf.body(
        "POST /api/v1/jobs/exception-scan (owner JWT or X-Job-Secret). Optional scheduler when "
        "EXCEPTION_SCAN_SCHEDULER_ENABLED=true. Owners set exception_scan_enabled, exception_scan_hour_utc "
        "(default 02:00 UTC), and chase_followup_days (default 3) in Settings autonomy rules."
    )

    pdf.h1("14. Key Assumptions and Limits")
    pdf.bullet("Forecasts use seasonal naive or daily average from 56 days of sales; no Prophet/statsforecast.")
    pdf.bullet("Replenishment what-if delay/lead-time adds daily_average x extra days to needed quantity.")
    pdf.bullet("Stockout date in what-if = on_hand / daily_average from today, or none if no demand.")
    pdf.bullet("Tests use LLM_PROVIDER=fake; live LLMs are not called in pytest.")
    pdf.bullet("data_quality agent is still a placeholder.")
    pdf.bullet("Agents never post stock; only the ledger service can.")

    pdf.h1("15. Detailed Command Walkthroughs")

    walkthroughs = [
        (
            "/stock",
            "When to use",
            "Before placing orders, after a big sale day, or when a staff member asks how much is on hand for a SKU or location.",
            "Examples",
            "/stock\n/stock OATS-1\n/stock oats",
            "What happens",
            "Orchestrator routes to forecast.get_stock. get_stock tool queries the inventory service (sum of ledger movements). "
            "You receive a stock_table card listing SKU, product name, on-hand, and low/out status per location.",
            "Write?",
            "No. Read-only for owner and staff.",
        ),
        (
            "/forecast",
            "When to use",
            "Planning purchases for the next two weeks, validating Insights numbers in chat, or checking one SKU's demand pattern.",
            "Examples",
            "/forecast\n/forecast SKU-100\nWhy is demand up for olive oil?",
            "What happens",
            "forecast.forecast runs run_forecast and related tools. Default window: 56 days history, 14-day horizon. "
            "Methods: seasonal_naive (repeat last 7 days), daily_average (short history), no_sales (zeros). "
            "Card: forecast_chart with trend, chosen model, WAPE, confidence, caveats.",
            "Write?",
            "No. Same forecast service as Insights; does not create POs.",
        ),
        (
            "/scan and /exceptions",
            "When to use",
            "Start of day review, after receiving goods, or when something feels off. Nightly job runs the same detectors automatically.",
            "Examples",
            "/scan\n/exceptions",
            "What happens",
            "exception_monitor.scan runs detectors, LLM ranks playbook actions, findings persist to exceptions table. "
            "Card: exception_list with severity, title, recommended_action, id for /why. May create generic suggestions for approval actions.",
            "Write?",
            "Orchestrator read-only (no plan pause). Persistence is internal to agent tools.",
        ),
        (
            "/reorder",
            "When to use",
            "Buying meeting: see which SKUs need stock and how many units, without committing a draft PO yet.",
            "Examples",
            "/reorder\nreorder what's low",
            "What happens",
            "replenishment.recommend calls reorder_recommendations (formula in code), supplier reliability, open POs. "
            "LLM may filter SKUs or prefer alternate supplier when preferred is late. Text card with lines and evidence.",
            "Write?",
            "No. Staff and owner can run this.",
        ),
        (
            "/draft-po and /po",
            "When to use",
            "Owner wants the agent to propose a purchase order for a specific supplier after reviewing recommendations.",
            "Examples",
            "/draft-po Mill Co\n/po Acme Supplies",
            "What happens",
            "Plan: recommend -> draft_po -> guardrail.review. Pauses for Run/Edit/Cancel. On Run, creates draft_po "
            "suggestion(s) with evidence. po_suggestion card in Inbox; Approvals tab lists pending items. "
            "Approve creates draft PO in Orders (still needs normal approve/send/receive flow).",
            "Write?",
            "Yes. Owner only. Requires plan approval and suggestion approval.",
        ),
        (
            "/email",
            "When to use",
            "Chase overdue PO, confirm a new order, expedite shipment, or send delay notice. Always review before send.",
            "Examples",
            "/email Mill chase\n/email Acme order\n/email Metro expedite\n/email Acme delay-notice",
            "What happens",
            "Plan: recommend -> draft_emails -> guardrail. draft_email tool stores supplier_messages draft + suggestion. "
            "email_draft card: edit subject/body, Approve and Send (calls EmailSender), Save draft, Reject. "
            "Console mode logs only; SMTP mode sends after approval.",
            "Write?",
            "Yes. Owner only.",
        ),
        (
            "/why and /explain",
            "When to use",
            "Verify a PO suggestion quantity, understand an exception, or audit agent reasoning before approving.",
            "Examples",
            "/why suggestion <uuid>\n/why exception <uuid>\n/why did you suggest 200 units?\n/explain",
            "What happens",
            "explainer.explain loads evidence from suggestion/exception/PO, run trace from agent_steps, optional sales history. "
            "LLM prose is grounded; bad numbers fall back to template. explanation card with evidence table, confidence, "
            "what would change the decision. Why? buttons on cards pre-fill /why commands.",
            "Write?",
            "No. Read-only.",
        ),
        (
            "/whatif",
            "When to use",
            "Sensitivity analysis before approving a large PO: what if demand rises or supplier is late?",
            "Examples",
            "/whatif demand up 20%\n/whatif demand down 10%\n/whatif supplier delay 5 days\n/whatif lead time 14 days",
            "What happens",
            "whatif_compare reruns replenishment math with modified demand_pct, delay_days, or lead_time_days. "
            "whatif_compare card shows before/after stockout date, recommended qty, cost per SKU. LLM narrates only.",
            "Write?",
            "No. Read-only.",
        ),
        (
            "/quality",
            "When to use",
            "Future: catalog/ledger consistency checks. Not available yet.",
            "Examples",
            "/quality",
            "What happens",
            "data_quality.check placeholder returns not implemented yet text card.",
            "Write?",
            "No.",
        ),
    ]

    for wt in walkthroughs:
        pdf.h2(wt[0])
        pdf.h3(wt[1])
        pdf.body(wt[2])
        pdf.h3(wt[3])
        pdf.body(wt[4])
        pdf.h3(wt[5])
        pdf.body(wt[6])
        pdf.h3(wt[7])
        pdf.body(wt[8])

    pdf.add_page()
    pdf.h1("16. Agent Tool Registry")
    pdf.body("Read tools are tenant-scoped via AgentContext.business_id from the JWT.")
    tool_rows = [
        ("forecast", "get_stock, get_forecast, get_history, run_forecast, get_forecast_accuracy", "Read"),
        ("exception_monitor", "scan_detectors, record_exception_actions", "Write suggestions/exceptions"),
        ("replenishment", "reorder_recommendations, get_supplier_reliability, get_open_pos, create_po_suggestion", "Read + guarded write"),
        ("supplier_comm", "get_po, get_supplier, get_exception, draft_email", "Write draft only"),
        ("explainer", "get_suggestion, get_run_trace, get_evidence, get_history, whatif_reorder", "Read"),
        ("guardrail", "(validates proposals in code)", "Read"),
    ]
    tw = [35, 100, 55]
    pdf.table_header(["Agent", "Tools", "Access"], tw)
    for row in tool_rows:
        pdf.table_row(list(row), tw)

    pdf.h1("17. Daily Owner Workflow with Agents")
    pdf.body(
        "1) Morning: /scan to see exceptions; /stock and /forecast for hot SKUs.\n"
        "2) Planning: /reorder for quantities; /why on anything unclear.\n"
        "3) Action: /draft-po for suppliers (owner); approve suggestions in Inbox.\n"
        "4) Suppliers: /email chase for overdue POs; approve send when ready.\n"
        "5) What-if: /whatif demand up 15% before increasing order size.\n"
        "6) Overnight: nightly exception scan (if enabled) surfaces new inbox work.\n"
        "Every write path leaves audit_log and suggestion decision history."
    )

    pdf.h1("18. SSE Events (what you see in chat)")
    pdf.bullet("thinking - orchestrator node started.")
    pdf.bullet("plan - DAG accepted; checklist appears.")
    pdf.bullet("step_started / step_done / step_failed - per-agent progress.")
    pdf.bullet("card - typed result (table, chart, suggestion, explanation, etc.).")
    pdf.bullet("awaiting_approval - write plan paused for Run.")
    pdf.bullet("token + done - streamed summary text, run complete.")

    pdf.h1("19. Quick Command Cheat Sheet")
    pdf.body(
        "/stock - what do I have?\n"
        "/forecast - what will sell next 14 days?\n"
        "/scan - what is wrong?\n"
        "/reorder - what should I buy?\n"
        "/draft-po Acme - propose a PO (owner, needs approval)\n"
        "/email Acme chase - draft chase email (owner, needs approval)\n"
        "/why suggestion <id> - why was this suggested?\n"
        "/whatif demand up 20% - counterfactual reorder impact\n"
        "/quality - data checks (coming soon)"
    )

    pdf.ln(4)
    pdf.set_font("Helvetica", "I", 9)
    pdf.body(
        "Regenerate this PDF: python docs/generate_agents_guide_pdf.py (requires fpdf2 in backend venv)."
    )

    pdf.output(str(OUTPUT))
    print(f"Wrote {OUTPUT} ({OUTPUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    build()
