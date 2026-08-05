# Interview Intelligence Platform — Backend

Event-driven AI interview analysis platform. Receives transcript uploads, processes them through multiple AI agents, and exposes results via a REST API.

## Architecture

```
Desktop App → S3 → EventBridge → SQS → Worker → Inngest → Workflow
                                                              │
                              ┌────────────────────────────────┤
                              ▼                                ▼
                       Conversation Parser            Analysis Agents (parallel)
                              │                      Coach · English · Vocab · Metrics
                              ▼                                │
                         Q&A Pairs                             ▼
                              │                          Recommendation
                              └──────────┬───────────────────┤
                                         ▼                   ▼
                                  Question Reviewer    PostgreSQL
                                         │                   │
                                         └─────────┬─────────┘
                                                   ▼
                                              REST API
```

## Quick Start

```bash
# Prerequisites: Docker, Python 3.12+
cp .env.example .env
# Set DEEPSEEK_API_KEY in .env

docker-compose up
```

| Service | Port | Purpose |
|---------|------|---------|
| API | `8000` | FastAPI REST + Inngest function host |
| Inngest Dev Server | `8288` | Workflow runner + dashboard |
| PostgreSQL | `5432` | Interview data + analytics |
| Worker | — | SQS consumer (idle in local dev) |

## Project Structure

```
backend/
├── api/              FastAPI app, routers, middleware, DI
├── agents/           8 AI agents (all implement BaseAgent)
├── orchestration/    Inngest wiring (client, functions, workflows)
├── services/         S3, DeepSeek, SQS, prompts, persistence, preprocessor
├── repositories/     Database access layer
├── database/         SQLAlchemy models + Alembic migrations
├── models/           Pydantic schemas (transcript, API responses, agent outputs)
├── prompts/          LLM prompt templates (.md with YAML frontmatter)
├── sdk/              Agent SDK (BaseAgent, AgentContext, AgentResult, AgentRegistry)
├── common/           Config, structured JSON logging
├── scripts/          Worker entrypoints
└── tests/            Unit + integration tests
```

## Agents

| # | Agent | Purpose | Uses LLM |
|---|-------|---------|----------|
| 1 | Transcription Corrector | Fix STT mis-transcriptions (batched) | ✅ |
| 2 | Conversation Parser | Extract Q&A pairs (batched) | ✅ |
| 3 | Interview Coach | Score 7 dimensions (technical, communication, confidence, STAR, ownership, clarity, completeness) | ✅ |
| 4 | English Coach | Grammar, fluency, naturalness + corrections | ✅ |
| 5 | Vocabulary | Extract useful interviewer phrases | ✅ |
| 6 | Metrics | WPM, ratios, fillers, word counts | ❌ |
| 7 | Recommendation | Strengths, weaknesses, learning plan | ✅ |
| 8 | Question Reviewer | Per-question improved answers | ✅ |

## REST API

```bash
GET  /interviews                    # List all interviews
GET  /interviews/{id}               # Interview detail + transcript
GET  /interviews/{id}/analysis      # Coach scores (7 dimensions)
GET  /interviews/{id}/english       # English corrections
GET  /interviews/{id}/vocabulary    # Extracted phrases
GET  /interviews/{id}/metrics       # WPM, ratios, counts
GET  /interviews/{id}/recommendations  # Strengths, weaknesses, plan
GET  /interviews/{id}/reviews       # Per-question improved answers
GET  /interviews/{id}/corrections   # STT word corrections
GET  /healthz                       # Health check
```

## Local Testing

```bash
# 1. Place a transcript in data/transcripts/{id}.json
#    (matches the desktop app's transcript.json format)

# 2. Trigger the workflow via Inngest Dev Server:
curl -X POST http://localhost:8288/e/local \
  -H "Content-Type: application/json" \
  -d '{"name":"interview/uploaded","data":{"interview_id":"demo-001","bucket":"","object_key":"interviews/demo-001/transcript.json"}}'

# 3. Check results:
curl http://localhost:8000/interviews/demo-001/analysis
```

## Testing

```bash
pip install -e ".[dev]"
pytest                          # 64 unit tests
python -m tests.integration.test_full_workflow  # End-to-end with real DeepSeek
```

## Deployment

```bash
cd ../terraform
terraform init && terraform apply
```

See `../docs/deployment.md` for full AWS deployment guide.

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `DEEPSEEK_API_KEY` | — | DeepSeek API key (required) |
| `DATABASE_URL` | `postgresql+psycopg://...` | PostgreSQL connection |
| `INNGEST_DEV` | `true` | Dev server mode |
| `SQS_QUEUE_URL` | — | SQS queue (production) |
| `AWS_REGION` | `us-east-2` | AWS region |
