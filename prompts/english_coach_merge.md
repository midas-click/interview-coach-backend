---
version: "1.0.0"
purpose: "Synthesize one overall English assessment from per-batch analysis results."
variables:
  - interview_id
  - batch_summaries
---

# English Analysis Merger

A long interview transcript was analyzed in batches. Each batch produced its
own metrics and a summary of the candidate's spoken English.

Write a single final summary (2–4 sentences) covering the candidate's overall
spoken-English quality across the WHOLE interview: main strengths, the most
important weaknesses, and the first thing they should work on.

Return ONLY valid JSON:

{
  "summary": "The candidate's English is generally X, but struggles with Y... Focus on Z first."
}

## Input

interview_id: {{ interview_id }}

Per-batch summaries:
{{ batch_summaries }}
