---
name: explainer_whatif
version: "1"
description: Narrate a before-versus-after what-if from typed replenishment results
---

Narrate the difference between before and after. Return JSON only.

Rules:
- Use only fields in the DATA what-if object.
- Do not add, multiply, or invent quantities, costs, or dates.
- Every number or date you mention must already appear in the DATA.
- Compare recommended quantity, stockout date, and cost.
- If answerable is false, say what data is missing.

JSON shape:
{"explanation":"...","confidence":"high","what_would_change":"..."}
