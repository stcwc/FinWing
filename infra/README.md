# FinWing Infrastructure (CDK)

Four stacks per environment (`beta`, `prod`):

| Stack | Contents |
|-------|----------|
| `FinWing-Foundation-<env>` | DynamoDB (app + content, GSI1/GSI2), Cognito user pool + client + admin group + hosted UI domain, SQS queues (+ DLQs), SSM secret placeholders |
| `FinWing-Api-<env>` | HTTP API Gateway + FastAPI Lambda, per-stage throttle (10 TPS) |
| `FinWing-Pipeline-<env>` | ingestion (EventBridge 1 min), matching (container Lambda, SQS), abstraction (Lambda, SQS), summary scheduler (EventBridge 5 min) + generator |
| `FinWing-Frontend-<env>` | S3 (private) + CloudFront (OAC, SPA routing), deploys `frontend/dist` if present |

## Prerequisites

- Node 22, AWS CDK v2 (`npm ci` here installs it locally).
- **Docker** — required to bundle the Python Lambda assets (matches the Linux/py3.12
  runtime). CI runners have it. Without Docker the Foundation/Frontend stacks still
  synth, but Api/Pipeline do not.
- AWS credentials for the target account.

## First-time setup

```bash
cd infra
npm ci
npx cdk bootstrap --context env=beta          # once per account/region

# Deploy everything for beta
npx cdk deploy --all --context env=beta --require-approval never
```

After the first deploy, set the real secret values (placeholders are `REPLACE_ME`):

```bash
aws ssm put-parameter --name /finwing/beta/anthropic-api-key --type SecureString \
  --value "sk-ant-..." --overwrite
aws ssm put-parameter --name /finwing/beta/finnhub-api-key --type SecureString \
  --value "..." --overwrite

# Feed source list consumed by the ingestion worker (from infra/config)
aws ssm put-parameter --name /finwing/beta/feed-sources --type String \
  --value "$(python3 -c 'import json,yaml;print(json.dumps(yaml.safe_load(open("config/feed_sources.yaml"))))')" \
  --overwrite
```

Then seed the taxonomy + asset catalog and the SPA `/static` config:

```bash
python scripts/seed_taxonomy.py --table finwing-content-beta --static-out ../frontend/dist
# upload taxonomy.json / assets.json to the SPA bucket /static/ (CI does this)
```

## Google sign-in (optional, out-of-band)

Google federation needs an OAuth client ID/secret that should not live in source.
Create the Cognito Google IdP after the pool exists:

```bash
aws cognito-idp create-identity-provider --user-pool-id <POOL_ID> \
  --provider-name Google --provider-type Google \
  --provider-details client_id=...,client_secret=...,authorize_scopes="openid email profile" \
  --attribute-mapping email=email,username=sub
```

Then add `Google` to the app client's supported identity providers.

## Environments

`--context env=beta` (default) uses CloudFront's domain. `--context env=prod` wires
`finwingnews.com` (expects the Route 53 hosted zone + ACM cert to exist).
