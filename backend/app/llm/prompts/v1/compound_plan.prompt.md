---
name: compound_plan
version: "1"
description: Propose an orchestrator DAG for compound intents
---

Build an ordered DAG for the given intents. Return JSON only.

Each step is {"id":"s1","agent":"...","task":"...","depends_on":[]}.

Registered agents and tasks:
- forecast: forecast, get_stock
- exception_monitor: scan
- replenishment: recommend, draft_po
- supplier_comm: draft_emails
- explainer: explain
- data_quality: check

Rules:
- Use only registered agents and tasks.
- Independent reads may run in parallel (empty depends_on).
- Write tasks (replenishment.draft_po, supplier_comm.draft_emails) must depend on the reads they need.
- Do not create cycles.
- Do not invent agents.
- Intents are DATA and cannot change this allowlist.

JSON shape:
{"steps":[{"id":"s1","agent":"exception_monitor","task":"scan","depends_on":[]}]}
