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
const region = process.env.CDK_DEFAULT_REGION ?? "us-west-2";
const cdkEnv = { account, region };

// finwingnews.com is served by the (promoted) beta distribution. The hosted
// zone and the us-east-1 CloudFront certificate already exist; reference them.
const domainName = "finwingnews.com";
const hostedZoneId = "Z03738783BIVY9U0GLXJ3";
const certArn =
  "arn:aws:acm:us-east-1:410834168390:certificate/c924620f-1f53-4ebd-9308-e5313a23b2d3";

const foundation = new FoundationStack(app, `FinWing-Foundation-${env}`, {
  env: cdkEnv,
  envName: env,
});

const apiStack = new ApiStack(app, `FinWing-Api-${env}`, {
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
  hostedZoneId,
  certArn,
  httpApi: apiStack.httpApi,
});

app.synth();
