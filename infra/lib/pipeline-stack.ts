import * as cdk from "aws-cdk-lib";
import { Construct } from "constructs";
import * as lambda from "aws-cdk-lib/aws-lambda";
import * as dynamodb from "aws-cdk-lib/aws-dynamodb";
import * as sqs from "aws-cdk-lib/aws-sqs";
import * as events from "aws-cdk-lib/aws-events";
import * as targets from "aws-cdk-lib/aws-events-targets";
import * as logs from "aws-cdk-lib/aws-logs";
import { SqsEventSource } from "aws-cdk-lib/aws-lambda-event-sources";
import * as iam from "aws-cdk-lib/aws-iam";
import { backendCode, matchingImage } from "./lambda-code";

interface Props extends cdk.StackProps {
  envName: string;
  appTable: dynamodb.Table;
  contentTable: dynamodb.Table;
  matchingQueue: sqs.Queue;
  abstractionQueue: sqs.Queue;
}

/** Async pipeline: ingestion → matching → abstraction, plus summary
 *  scheduler/generator. (LLD §6) */
export class PipelineStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: Props) {
    super(scope, id, props);
    const { envName, appTable, contentTable, matchingQueue, abstractionQueue } = props;

    const ssmStmt = new iam.PolicyStatement({
      actions: ["ssm:GetParameter"],
      resources: [
        `arn:aws:ssm:${this.region}:${this.account}:parameter/finwing/${envName}/*`,
      ],
    });

    const baseEnv = {
      FINWING_ENV: envName,
      APP_TABLE: appTable.tableName,
      CONTENT_TABLE: contentTable.tableName,
      MATCHING_QUEUE_URL: matchingQueue.queueUrl,
      ABSTRACTION_QUEUE_URL: abstractionQueue.queueUrl,
    };

    // ── Ingestion (EventBridge every minute) ────────────────────
    const ingestion = new lambda.Function(this, "Ingestion", {
      functionName: `finwing-ingestion-${envName}`,
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: "workers.ingestion.handler",
      code: backendCode(),
      memorySize: 256,
      timeout: cdk.Duration.seconds(30),
      logRetention: logs.RetentionDays.TWO_WEEKS,
      environment: baseEnv,
    });
    contentTable.grantReadWriteData(ingestion);
    matchingQueue.grantSendMessages(ingestion);
    ingestion.addToRolePolicy(ssmStmt);
    new events.Rule(this, "IngestionSchedule", {
      ruleName: `finwing-ingestion-${envName}`,
      schedule: events.Schedule.rate(cdk.Duration.minutes(1)),
      targets: [new targets.LambdaFunction(ingestion)],
    });

    // ── Matching (container Lambda, SQS-driven) ─────────────────
    const matching = new lambda.DockerImageFunction(this, "Matching", {
      functionName: `finwing-matching-${envName}`,
      code: matchingImage(["workers.matching.handler"]),
      memorySize: 1024,
      timeout: cdk.Duration.seconds(60),
      // Room to copy the baked embedding-model cache from /opt to /tmp.
      ephemeralStorageSize: cdk.Size.mebibytes(1024),
      logRetention: logs.RetentionDays.TWO_WEEKS,
      environment: baseEnv,
    });
    contentTable.grantReadWriteData(matching);
    abstractionQueue.grantSendMessages(matching);
    matching.addToRolePolicy(ssmStmt);
    matching.addEventSource(
      new SqsEventSource(matchingQueue, { batchSize: 10, maxBatchingWindow: cdk.Duration.seconds(10) })
    );

    // ── Abstraction (zip Lambda, SQS-driven) ────────────────────
    const abstraction = new lambda.Function(this, "Abstraction", {
      functionName: `finwing-abstraction-${envName}`,
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: "workers.abstraction.handler",
      code: backendCode(),
      memorySize: 256,
      timeout: cdk.Duration.seconds(60),
      logRetention: logs.RetentionDays.TWO_WEEKS,
      environment: baseEnv,
    });
    contentTable.grantReadWriteData(abstraction);
    abstraction.addToRolePolicy(ssmStmt);
    abstraction.addEventSource(
      new SqsEventSource(abstractionQueue, { batchSize: 10, maxBatchingWindow: cdk.Duration.seconds(30) })
    );

    // ── Summary generator (async-invoked per lens) ──────────────
    // Emails the daily summary via SES; EMAIL_SENDER must be a verified SES
    // identity (the finwingnews.com domain / noreply@ address).
    const emailSender = process.env.FINWING_EMAIL_SENDER ?? "noreply@finwingnews.com";
    const appUrl = process.env.FINWING_APP_URL ?? "https://finwingnews.com";
    const summaryGen = new lambda.Function(this, "SummaryGenerator", {
      functionName: `finwing-summary-generator-${envName}`,
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: "workers.summary_generator.handler",
      code: backendCode(),
      memorySize: 512,
      timeout: cdk.Duration.seconds(300),
      logRetention: logs.RetentionDays.TWO_WEEKS,
      environment: {
        ...baseEnv,
        EMAIL_SENDER: emailSender,
        EMAIL_SENDER_NAME: "FinWing",
        APP_URL: appUrl,
      },
    });
    appTable.grantReadWriteData(summaryGen);
    contentTable.grantReadWriteData(summaryGen);
    summaryGen.addToRolePolicy(ssmStmt);
    // Send-only; scoped to the verified sender identity.
    summaryGen.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ["ses:SendEmail"],
        resources: [
          `arn:aws:ses:${this.region}:${this.account}:identity/finwingnews.com`,
          `arn:aws:ses:${this.region}:${this.account}:identity/${emailSender}`,
        ],
      })
    );

    // ── Backfill (async-invoked from POST /lenses) ──────────────
    const backfill = new lambda.Function(this, "Backfill", {
      functionName: `finwing-backfill-${envName}`,
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: "workers.backfill.handler",
      code: backendCode(),
      memorySize: 512,
      timeout: cdk.Duration.seconds(300),
      logRetention: logs.RetentionDays.TWO_WEEKS,
      environment: baseEnv,
    });
    appTable.grantReadWriteData(backfill);
    contentTable.grantReadWriteData(backfill);
    backfill.addToRolePolicy(ssmStmt);

    // ── Summary scheduler (EventBridge every 5 min) ─────────────
    const scheduler = new lambda.Function(this, "SummaryScheduler", {
      functionName: `finwing-summary-scheduler-${envName}`,
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: "workers.summary_scheduler.handler",
      code: backendCode(),
      memorySize: 128,
      timeout: cdk.Duration.seconds(30),
      logRetention: logs.RetentionDays.TWO_WEEKS,
      environment: { ...baseEnv, SUMMARY_GENERATOR_ARN: summaryGen.functionArn },
    });
    appTable.grantReadWriteData(scheduler);
    summaryGen.grantInvoke(scheduler);
    new events.Rule(this, "SummarySchedule", {
      ruleName: `finwing-summary-${envName}`,
      schedule: events.Schedule.rate(cdk.Duration.minutes(5)),
      targets: [new targets.LambdaFunction(scheduler)],
    });
  }
}
