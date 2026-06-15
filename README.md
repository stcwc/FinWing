# FinWing

AI-assisted financial news tracker: ingests news, matches it to user-defined
"lenses" (sets of topics), abstracts each article once with Claude, and
produces per-lens daily summaries with asset movement and hedged rationale.

Design docs: see `~/Documents/FinWing/` (One-Pager, HLD, LLD).

## Layout

```
backend/
  app/        FastAPI application (API Gateway + Lambda via Mangum)
  workers/    Async pipeline: ingestion, matching, abstraction, scheduling, summaries
  tests/      pytest + moto
frontend/     React + Vite + TypeScript + Tailwind SPA
infra/
  lib/        CDK stacks (TypeScript)
  config/     taxonomy.yaml, assets.yaml, feed_sources.yaml, cross_asset_map.json
  scripts/    seed_taxonomy.py, backfill_topic.py, migrate_embeddings.py
```

## Local development

```bash
# Backend
cd backend && python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
pytest

# Frontend
cd frontend && npm install && npm run dev

# Infra
cd infra && npm install && npx cdk synth
```

## Environments

| Env  | Domain                | Deploy trigger                  |
|------|-----------------------|---------------------------------|
| beta | CloudFront URL        | push to `main` (after tests)    |
| prod | finwingnews.com       | manual approval after beta      |

Secrets (`ANTHROPIC_API_KEY`, `FINNHUB_API_KEY`) live in SSM Parameter Store.
