# Interview Intelligence Platform — Backend

Event-driven AI interview analysis platform. Receives transcript uploads, processes them through multiple AI agents, and exposes results via a REST API.

## Architecture

```
Desktop App → S3 → EventBridge → Worker Lambda → Inngest → Workflow
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
                                  Question Reviewer    PostgreSQL (Neon)
                                         │                   │
                                         └─────────┬─────────┘
                                                   ▼
                                              REST API (Lambda + Function URL)
```

## Quick Start

```bash
# Prerequisites: Docker, Python 3.12+
cp .env.example .env
# Set DEEPSEEK_API_KEY and JWT_SECRET_KEY in .env

docker-compose up

# Seed the initial admin user (defaults: admin / admin123)
docker-compose exec api python -m scripts.seed_admin
```

| Service | Port | Purpose |
|---------|------|---------|
| API | `8000` | FastAPI REST + Inngest function host |
| Inngest Dev Server | `8288` | Workflow runner + dashboard |
| PostgreSQL | `5432` | Interview data + analytics + users |

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
├── scripts/          Migrations, Lambda entrypoints, admin seeding
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

All `/api/*` endpoints require a Bearer token obtained from `POST /api/auth/login`.
Role-based access:

- **admin** — full access: user management + interview data (incl. delete)
- **user** — read-only access to interview data

### Auth

```bash
POST /api/auth/login        # {username, password} → {access_token, user}
GET  /api/auth/me           # Current user (requires token)
```

### Users (admin only)

```bash
GET    /api/users           # List users
POST   /api/users           # Create user {username, password, role}
PUT    /api/users/{id}      # Update user {username, role, password?}
DELETE /api/users/{id}      # Delete user
```

### Interviews (requires auth)

```bash
GET  /api/interviews                    # List interviews (paginated)
GET  /api/interviews/{id}               # Interview detail + transcript
GET  /api/interviews/{id}/analysis      # Coach scores (7 dimensions)
GET  /api/interviews/{id}/english       # English corrections
GET  /api/interviews/{id}/vocabulary    # Extracted phrases
GET  /api/interviews/{id}/metrics       # WPM, ratios, counts
GET  /api/interviews/{id}/recommendations  # Strengths, weaknesses, plan
GET  /api/interviews/{id}/reviews       # Per-question improved answers
GET  /api/interviews/{id}/corrections   # STT word corrections
DELETE /api/interviews/{id}             # Delete interview (admin only)
GET  /healthz                           # Health check (public)
```

List supports pagination via `limit` (default 50) and `offset`:

```bash
GET /api/interviews?limit=10&offset=20
# → { "items": [...], "total": 34, "limit": 10, "offset": 20 }
```

### Authentication flow

```bash
# 1. Login to get a token
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# 2. Use the token on protected endpoints
curl http://localhost:8000/api/interviews -H "Authorization: Bearer $TOKEN"
```

## Local Testing

```bash
# 1. Place a transcript in data/transcripts/{id}.json
#    (matches the desktop app's transcript.json format)

# 2. Seed a user and login
python -m scripts.seed_admin
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# 3. Trigger the workflow via Inngest Dev Server:
curl -X POST http://localhost:8288/e/local \
  -H "Content-Type: application/json" \
  -d '{"name":"interview/uploaded","data":{"interview_id":"demo-001","bucket":"","object_key":"interviews/demo-001/transcript.json"}}'

# 4. Check results:
curl http://localhost:8000/api/interviews/demo-001/analysis -H "Authorization: Bearer $TOKEN"
```

## Testing

```bash
pip install -e ".[dev]"
pytest                          # 83 unit tests
python -m tests.integration.test_full_workflow  # End-to-end with real DeepSeek
```

## Deployment (AWS Lambda)

Production runs entirely on AWS Lambda + Neon Postgres — no ECS, no Docker:

```bash
# 1. Build the deployment zip (Linux-compatible, from any OS)
python scripts/build_lambda.py

# 2. Upload the zip to the code bucket, then deploy infra
aws s3 cp dist/lambda.zip s3://interview-intelligence-transcripts-lambda-code/lambda.zip
cd ../terraform
terraform init && terraform apply

# 3. Run migrations (or the CI/CD pipeline does this automatically)
aws lambda invoke --function-name interview-intelligence-migrate --payload '{}' out.json
```

CI/CD (`.github/workflows/ci.yml`) lints, tests, rebuilds the zip, uploads it
to S3, updates all three Lambda functions, and runs migrations on every push
to `main`.

See `../docs/deployment.md` for the full guide.

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `DEEPSEEK_API_KEY` | — | DeepSeek API key (required) |
| `DATABASE_URL` | `postgresql+psycopg://...` | PostgreSQL connection |
| `JWT_SECRET_KEY` | `change-me-in-production` | JWT signing key — **must change in production** |
| `JWT_ALGORITHM` | `HS256` | JWT signing algorithm |
| `JWT_EXPIRE_MINUTES` | `1440` | Token lifetime (minutes) |
| `ADMIN_USERNAME` | `admin` | Initial admin username (seed script) |
| `ADMIN_PASSWORD` | `admin123` | Initial admin password (seed script) |
| `INNGEST_DEV` | `true` | Dev server mode |
| `AWS_REGION` | `us-east-2` | AWS region |

On Lambda, secrets (`DATABASE_URL`, `DEEPSEEK_API_KEY`, `INNGEST_EVENT_KEY`,
`INNGEST_SIGNING_KEY`, `JWT_SECRET_KEY`) are read from AWS Secrets Manager at
cold start — see `api/lambda_runtime.py`.
