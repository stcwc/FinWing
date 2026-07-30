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
import * as ses from "aws-cdk-lib/aws-ses";
import * as sns from "aws-cdk-lib/aws-sns";
import * as subs from "aws-cdk-lib/aws-sns-subscriptions";
import * as cloudwatch from "aws-cdk-lib/aws-cloudwatch";
import * as cwActions from "aws-cdk-lib/aws-cloudwatch-actions";
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

    // ── Email bounce/complaint handling ─────────────────────────
    // Digest sends reference this config set; SES publishes Bounce/Complaint
    // events to SNS; the handler suppresses the address and disables the user's
    // email preference. (Account-level suppression is enabled out of band too.)
    const emailConfigSet = new ses.ConfigurationSet(this, "EmailConfigSet", {
      configurationSetName: `finwing-${envName}`,
    });
    const sesEventsTopic = new sns.Topic(this, "SesEventsTopic", {
      topicName: `finwing-ses-events-${envName}`,
    });
    emailConfigSet.addEventDestination("BounceComplaint", {
      destination: ses.EventDestination.snsTopic(sesEventsTopic),
      events: [ses.EmailSendingEvent.BOUNCE, ses.EmailSendingEvent.COMPLAINT],
    });
    const sesEvents = new lambda.Function(this, "SesEvents", {
      functionName: `finwing-ses-events-${envName}`,
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: "workers.ses_events.handler",
      code: backendCode(),
      memorySize: 128,
      timeout: cdk.Duration.seconds(30),
      logRetention: logs.RetentionDays.TWO_WEEKS,
      environment: baseEnv,
    });
    appTable.grantReadWriteData(sesEvents);
    sesEvents.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ["ses:PutSuppressedDestination"],
        resources: ["*"],
      })
    );
    sesEventsTopic.addSubscription(new subs.LambdaSubscription(sesEvents));

    // ── Reputation kill-switch (CloudWatch alarms → auto-pause) ──
    // Alarms watch the digest config set's bounce/complaint rates against the
    // SES enforcement thresholds (bounce 5%, complaint 0.1%). On breach they
    // fan out to an alarm topic that (a) notifies the operator and (b) triggers
    // a Lambda that disables sending on the config set, halting digests before
    // the account's reputation can degrade far enough for SES to suspend it.
    const alarmTopic = new sns.Topic(this, "SesAlarmTopic", {
      topicName: `finwing-ses-alarms-${envName}`,
    });
    const alarmEmail = process.env.FINWING_ALARM_EMAIL ?? "john0707ieem@gmail.com";
    alarmTopic.addSubscription(new subs.EmailSubscription(alarmEmail));

    const sesPause = new lambda.Function(this, "SesPause", {
      functionName: `finwing-ses-pause-${envName}`,
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: "workers.ses_pause.handler",
      code: backendCode(),
      memorySize: 128,
      timeout: cdk.Duration.seconds(30),
      logRetention: logs.RetentionDays.TWO_WEEKS,
      environment: { ...baseEnv, EMAIL_CONFIG_SET: emailConfigSet.configurationSetName },
    });
    sesPause.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ["ses:PutConfigurationSetSendingOptions"],
        resources: [
          `arn:aws:ses:${this.region}:${this.account}:configuration-set/finwing-${envName}`,
        ],
      })
    );
    alarmTopic.addSubscription(new subs.LambdaSubscription(sesPause));

    // Reputation metrics are attributed to the config set that sent the mail.
    // Rates are fractions (5% = 0.05); alarm on the worst reading each hour and
    // treat "no sending" as healthy so idle periods never trip the switch.
    const repDim = { "ses:configuration-set": emailConfigSet.configurationSetName };
    const bounceAlarm = new cloudwatch.Alarm(this, "SesBounceRateAlarm", {
      alarmName: `finwing-ses-bounce-rate-${envName}`,
      alarmDescription: "SES bounce rate for the digest config set at/above the 5% enforcement threshold",
      metric: new cloudwatch.Metric({
        namespace: "AWS/SES",
        metricName: "Reputation.BounceRate",
        dimensionsMap: repDim,
        statistic: "Maximum",
        period: cdk.Duration.hours(1),
      }),
      threshold: 0.05,
      comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
      evaluationPeriods: 1,
      datapointsToAlarm: 1,
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
    });
    const complaintAlarm = new cloudwatch.Alarm(this, "SesComplaintRateAlarm", {
      alarmName: `finwing-ses-complaint-rate-${envName}`,
      alarmDescription: "SES complaint rate for the digest config set at/above the 0.1% enforcement threshold",
      metric: new cloudwatch.Metric({
        namespace: "AWS/SES",
        metricName: "Reputation.ComplaintRate",
        dimensionsMap: repDim,
        statistic: "Maximum",
        period: cdk.Duration.hours(1),
      }),
      threshold: 0.001,
      comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
      evaluationPeriods: 1,
      datapointsToAlarm: 1,
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
    });
    for (const a of [bounceAlarm, complaintAlarm]) {
      a.addAlarmAction(new cwActions.SnsAction(alarmTopic));
    }

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
        EMAIL_CONFIG_SET: emailConfigSet.configurationSetName,
      },
    });
    appTable.grantReadWriteData(summaryGen);
    contentTable.grantReadWriteData(summaryGen);
    summaryGen.addToRolePolicy(ssmStmt);
    // SendEmail authorizes against every identity it references — including the
    // recipient identities (which must be verified in the SES sandbox) — plus the
    // configuration set, which is a separate resource. Scoping only to the sender
    // identity 403s on the recipient identity, so allow any identity + the config set.
    summaryGen.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ["ses:SendEmail"],
        resources: [
          `arn:aws:ses:${this.region}:${this.account}:identity/*`,
          `arn:aws:ses:${this.region}:${this.account}:configuration-set/finwing-${envName}`,
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

    // ── Quote refresher (EventBridge every 15 min) ──────────────
    // Refreshes the shared lens-ticker quote cache. The cadence is the capacity
    // knob for the Twelve Data free tier (~2 distinct symbols per refresh-minute,
    // app-wide); the worker self-gates to US market hours. Reads lenses (scan)
    // and writes ASSET#<id>/QUOTE into the content table.
    const quoteRefresher = new lambda.Function(this, "QuoteRefresher", {
      functionName: `finwing-quote-refresher-${envName}`,
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: "workers.quote_refresher.handler",
      code: backendCode(),
      memorySize: 256,
      // Paces Twelve Data /quote chunks ~1 min apart to respect 8 credits/min;
      // refreshing ~17 symbols spans a few minutes per run.
      timeout: cdk.Duration.seconds(300),
      logRetention: logs.RetentionDays.TWO_WEEKS,
      environment: baseEnv,
    });
    appTable.grantReadData(quoteRefresher);
    contentTable.grantReadWriteData(quoteRefresher);
    quoteRefresher.addToRolePolicy(ssmStmt);
    new events.Rule(this, "QuoteRefreshSchedule", {
      ruleName: `finwing-quote-refresh-${envName}`,
      schedule: events.Schedule.rate(cdk.Duration.minutes(15)),
      targets: [new targets.LambdaFunction(quoteRefresher)],
    });
  }
}
