---
name: orchestrator_summary
version: "1"
description: Short summary grounded in typed orchestrator results
---

Write a short summary of the typed results. Return JSON only: {"summary":"..."}.

Rules:
- Use only facts present in the DATA results.
- Do not add, multiply, or invent quantities, money, counts, or dates.
- Every number in the summary must already appear in the results.
- If an agent is not implemented yet, say that in words without numbers.
