import * as path from "path";
import * as fs from "fs";
import * as lambda from "aws-cdk-lib/aws-lambda";

const BACKEND = path.resolve(__dirname, "../../backend");
const REPO_ROOT = path.resolve(__dirname, "../..");

// The asset context is the repo root (so both backend/ and infra/config/ are
// reachable inside the bundling container). Everything irrelevant to the
// runtime is excluded to keep the fingerprint and upload small.
const ASSET_EXCLUDE = [
  "**/.venv",
  "**/__pycache__",
  "**/*.pyc",
  "backend/tests",
  "backend/models",
  "frontend",
  "infra/node_modules",
  "infra/cdk.out",
  "infra/dist",
  "node_modules",
  ".git",
  ".github",
  "backend/Dockerfile.matching",
];

/**
 * Package the backend (app/ + workers/ + infra/config) into a Lambda asset.
 * Bundles inside the Lambda build image (Docker) so dependency wheels match the
 * Linux/py3.12 runtime. CI runners and local Docker both satisfy this; without
 * Docker, the Foundation and Frontend stacks still synth on their own.
 */
export function backendCode(extraRequirements?: string): lambda.AssetCode {
  return lambda.Code.fromAsset(REPO_ROOT, {
    exclude: ASSET_EXCLUDE,
    bundling: {
      image: lambda.Runtime.PYTHON_3_12.bundlingImage,
      command: ["bash", "-c", bundleCommand(extraRequirements)],
    },
  });
}

// Inside the container the repo root is mounted at /asset-input.
function bundleCommand(extra?: string): string {
  const reqs = ["/asset-input/backend/requirements.txt"];
  if (extra) reqs.push(`/asset-input/backend/${extra}`);
  const reqFlags = reqs.map((r) => `-r ${r}`).join(" ");
  return [
    `pip install ${reqFlags} -t /asset-output --quiet`,
    `cp -r /asset-input/backend/app /asset-output/`,
    `cp -r /asset-input/backend/workers /asset-output/`,
    `mkdir -p /asset-output/infra/config`,
    `cp /asset-input/infra/config/* /asset-output/infra/config/`,
    `find /asset-output -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true`,
  ].join(" && ");
}

/** Container image for the matching worker + seeder (bundles the bge ONNX model).
 *  Build context is the repo root so the Dockerfile can copy infra/config;
 *  the repo-root .dockerignore keeps the context lean. */
export function matchingImage(cmd: string[]): lambda.DockerImageCode {
  const dockerfile = path.join(BACKEND, "Dockerfile.matching");
  if (!fs.existsSync(dockerfile)) throw new Error(`Missing ${dockerfile}`);
  return lambda.DockerImageCode.fromImageAsset(REPO_ROOT, {
    file: "backend/Dockerfile.matching",
    cmd,
  });
}
