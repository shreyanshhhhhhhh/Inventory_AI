---
name: explainer_explain
version: "1"
description: Plain-language explanation grounded in stored evidence fields
---

Explain a stored inventory decision. Return JSON only.

Rules:
- Use only fields in the DATA evidence object.
- Do not add, multiply, or invent quantities, money, dates, or scores.
- Every number or date you mention must already appear in the DATA.
- Cite the fields in words (on-hand, forecast, lead time, reliability, reason codes).
- Include a confidence word that already appears, or high/medium/low when the DATA has confidence.
- Say what would change the decision using only stored fields.
- If answerable is false, say the evidence cannot answer and list missing.

JSON shape:
{"explanation":"...","confidence":"high","what_would_change":"..."}
