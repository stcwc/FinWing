# FinWing

> **⚠️ SUNSET (2026-11-09).** This project is retired — it had no active users,
> so all live AWS resources were torn down to stop ongoing cost. **This repo is
> the source of truth and is fully revivable from code** (CDK IaC). Deployed
> data (DynamoDB, Cognito users) was intentionally discarded; a revival starts
> fresh. Auto-deploy is disabled. See **[Sunset & revival](#sunset--revival)**.

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

| Env  | Domain                | Deploy trigger                       |
|------|-----------------------|--------------------------------------|
| beta | finwingnews.com       | manual `workflow_dispatch` (sunset)  |
| prod | —                     | n/a (beta was promoted to the domain)|

> Historically beta auto-deployed on push to `main`; that is disabled as of the
> sunset. Beta was promoted to `finwingnews.com`, so there was no separate prod.

Secrets (`ANTHROPIC_API_KEY`, `FINNHUB_API_KEY`) live in SSM Parameter Store.

## Sunset & revival

Retired 2026-11-09. The five CDK stacks (`FinWing-Foundation/Api/Pipeline/Mail/Frontend-beta`,
all in account `410834168390` / `us-west-2`) were destroyed to stop recurring
cost. On `beta` every stateful resource uses `RemovalPolicy.DESTROY`, so teardown
is clean and all stored data is gone by design — a revival is a fresh start.

**Revival is one deploy** — the infra is entirely in `infra/`:

```bash
cd infra && npm ci
npx cdk deploy --all --context env=beta   # recreates all app resources (see Domain & DNS caveat for the custom domain)
# then re-seed the taxonomy (same step the deploy workflow runs):
python infra/scripts/seed_taxonomy.py --table finwing-content-beta --static-out frontend/dist
```

To restore continuous deployment, re-add the `push:` trigger in
`.github/workflows/deploy.yml` (see the SUNSET comment there).

Resources **preserved** across the sunset so revival stays easy:

- ACM certs in `us-east-1` (site + Cognito hosted-UI wildcard), referenced by ARN
- The CDK bootstrap stack and the GitHub OIDC deploy role

**Secrets were deleted.** All `/finwing/beta/*` SSM params were removed at sunset.
On revival, `cdk deploy` recreates the three placeholder params
(`anthropic-api-key`, `finnhub-api-key`, `twelvedata-api-key`) as `REPLACE_ME`,
and you must re-create/populate every secret before the app works:
`google-client-id`, `google-client-secret`, `fred-api-key`, `feed-sources`,
`unsubscribe-secret`, plus real values for the three placeholders. Treat the old
keys as retired and issue fresh ones at each provider.

### Domain & DNS caveat

At sunset the `finwingnews.com` **domain registration was kept but auto-renew was
turned off** — it stays yours until it **expires on 2027-06-18**, then lapses with
no further charge. Its Route 53 **hosted zone was deleted** along with everything
else, so DNS is no longer served for the name.

Because the zone is gone, the one-command revival above brings the app back on its
raw CloudFront/API URLs but **not** on `finwingnews.com`. Restoring the custom
domain is a race against the expiry date and takes extra steps — realistically
unlikely, but if you do it before **2027-06-18**:

1. Recreate a hosted zone for `finwingnews.com` (Route 53 issues a **new** zone id
   and **new** name servers).
2. Point the domain's NS delegation at those name servers and wait for propagation.
3. Update the hardcoded `hostedZoneId` (and cert ARNs, if re-issued) in
   `infra/bin/finwing.ts`, then `cdk deploy --all --context env=beta` to recreate
   the A/AAAA + SES DNS records.

After 2027-06-18 the name may be registered by anyone, so revival then means a
brand-new domain plus the same steps.
