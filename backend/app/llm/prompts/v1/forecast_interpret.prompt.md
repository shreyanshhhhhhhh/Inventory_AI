---
name: forecast_interpret
version: "1"
description: One-line forecast interpretation grounded in typed eval fields
---

Write one plain-language sentence about the forecast. Return JSON only: {"interpretation":"..."}.

Rules:
- Use only fields in the DATA forecast object.
- Do not add, multiply, or invent quantities, WAPE, dates, or SKU counts.
- Every number you mention must already appear in the DATA.
- Name the trend, chosen model, confidence, and caveats in words when those fields exist.
- One sentence. No bullet lists.
