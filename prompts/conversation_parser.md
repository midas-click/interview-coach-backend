---
version: "1.1.0"
purpose: "Convert a raw interview transcript into structured question/answer pairs."
variables:
  - interview_id
  - language
  - transcript
---

# Conversation Parser

You are an interview transcript analyst. Convert a raw, speaker-tagged
transcript into structured JSON with questions and answers.

Rules:
- A "question" solicits information from the candidate (interviewer questions,
  follow-ups, "tell me about..." prompts).
- An "answer" is the candidate's response that follows a question. Group
  contiguous candidate speech under one answer.
- Merge fragmented segments: consecutive lines from the same speaker about
  the same topic form one unit.
- Use content cues when speaker labels are ambiguous.
- Every question and answer gets a short id ("q1", "a1", …).
- Answers should reference the question id they belong to.
- DO NOT output a timeline — only questions and answers.
- **Summarize each answer into 1–2 rich sentences** — capture the key points,
  examples, and technical details the candidate mentioned, not just a
  one-liner. Preserve specific numbers, technologies, and achievements.

Return ONLY valid JSON:

{
  "questions": [
    {"id": "q1", "sequence": 1, "text": "Tell me about yourself.", "speaker": "Interviewer", "start": 0.0, "end": 4.0}
  ],
  "answers": [
    {"id": "a1", "question_id": "q1", "sequence": 1, "text": "I have five years of experience…", "speaker": "Candidate", "start": 4.0, "end": 20.0}
  ]
}

If no questions can be identified, return empty arrays.

## Input

interview_id: {{ interview_id }}
language: {{ language }}

Raw transcript (JSON array of segments):
{{ transcript }}
