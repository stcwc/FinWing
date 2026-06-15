#!/usr/bin/env node
import "source-map-support/register";
import * as cdk from "aws-cdk-lib";
import { FoundationStack } from "../lib/foundation-stack";
import { ApiStack } from "../lib/api-stack";
import { PipelineStack } from "../lib/pipeline-stack";
import { FrontendStack } from "../lib/frontend-stack";

const app = new cdk.App();
const env = app.node.tryGetContext("env") ?? "beta";
const account = process.env.CDK_DEFAULT_ACCOUNT;
const region = process.env.CDK_DEFAULT_REGION ?? "us-east-1";
const cdkEnv = { account, region };

// Production domain config is only applied when env=prod and a hosted zone exists.
const domainName = env === "prod" ? "finwingnews.com" : undefined;

const foundation = new FoundationStack(app, `FinWing-Foundation-${env}`, {
  env: cdkEnv,
  envName: env,
});

new ApiStack(app, `FinWing-Api-${env}`, {
  env: cdkEnv,
  envName: env,
  appTable: foundation.appTable,
  contentTable: foundation.contentTable,
  userPool: foundation.userPool,
  userPoolClient: foundation.userPoolClient,
});

new PipelineStack(app, `FinWing-Pipeline-${env}`, {
  env: cdkEnv,
  envName: env,
  appTable: foundation.appTable,
  contentTable: foundation.contentTable,
  matchingQueue: foundation.matchingQueue,
  abstractionQueue: foundation.abstractionQueue,
});

new FrontendStack(app, `FinWing-Frontend-${env}`, {
  env: cdkEnv,
  envName: env,
  domainName,
});

app.synth();
