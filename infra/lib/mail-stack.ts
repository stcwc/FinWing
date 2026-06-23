import * as cdk from "aws-cdk-lib";
import { Construct } from "constructs";
import * as lambda from "aws-cdk-lib/aws-lambda";
import * as s3 from "aws-cdk-lib/aws-s3";
import * as ses from "aws-cdk-lib/aws-ses";
import * as sesActions from "aws-cdk-lib/aws-ses-actions";
import * as iam from "aws-cdk-lib/aws-iam";
import * as logs from "aws-cdk-lib/aws-logs";
import * as route53 from "aws-cdk-lib/aws-route53";
import * as cr from "aws-cdk-lib/custom-resources";
import * as path from "path";

interface Props extends cdk.StackProps {
  envName: string;
  /** Domain that receives mail (must be a verified SES identity). */
  mailDomain: string;
  /** Local part(s) to receive, e.g. ["support"]. */
  recipients: string[];
  /** Personal inbox the mail is forwarded to. */
  forwardTo: string;
  hostedZoneName: string;
  hostedZoneId: string;
}

/**
 * Inbound email for finwingnews.com. SES receives mail for support@…, drops the
 * raw message in S3, and invokes a Lambda that re-sends it to a personal inbox.
 * Kept in its own stack because SES receiving is account-global (one active rule
 * set per region) and unrelated to the app's request path.
 */
export class MailStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: Props) {
    super(scope, id, props);
    const { envName, mailDomain, recipients, forwardTo, hostedZoneName, hostedZoneId } = props;
    const keyPrefix = "inbound/";
    const mailFrom = `${recipients[0]}@${mailDomain}`;

    // Raw inbound messages. Short retention — the forwarder reads them once.
    const bucket = new s3.Bucket(this, "MailBucket", {
      bucketName: `finwing-mail-${envName}-${this.account}`,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      encryption: s3.BucketEncryption.S3_MANAGED,
      lifecycleRules: [{ prefix: keyPrefix, expiration: cdk.Duration.days(30) }],
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
    });
    // The S3 receipt action below grants SES PutObject on this bucket and makes
    // the rule depend on that grant, so no explicit bucket policy is needed here.

    const forwarder = new lambda.Function(this, "Forwarder", {
      functionName: `finwing-mail-forwarder-${envName}`,
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: "index.handler",
      code: lambda.Code.fromAsset(path.resolve(__dirname, "../lambda/mail-forwarder")),
      timeout: cdk.Duration.seconds(30),
      logRetention: logs.RetentionDays.TWO_WEEKS,
      environment: {
        MAIL_BUCKET: bucket.bucketName,
        KEY_PREFIX: keyPrefix,
        FORWARD_TO: forwardTo,
        MAIL_FROM: mailFrom,
      },
    });
    bucket.grantRead(forwarder, `${keyPrefix}*`);
    forwarder.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ["ses:SendRawEmail"],
        resources: ["*"],
      })
    );
    // Let SES invoke the forwarder (the rule's Lambda action).
    forwarder.addPermission("AllowSesInvoke", {
      principal: new iam.ServicePrincipal("ses.amazonaws.com"),
      sourceAccount: this.account,
    });

    // Receive → store in S3 → invoke forwarder (actions run in order).
    const ruleSet = new ses.ReceiptRuleSet(this, "RuleSet", {
      receiptRuleSetName: `finwing-inbound-${envName}`,
    });
    ruleSet.addRule("SupportRule", {
      recipients: recipients.map((r) => `${r}@${mailDomain}`),
      actions: [
        new sesActions.S3({ bucket, objectKeyPrefix: keyPrefix }),
        new sesActions.Lambda({
          function: forwarder,
          invocationType: sesActions.LambdaInvocationType.EVENT,
        }),
      ],
    });

    // CloudFormation can't mark a rule set active; do it with an API call.
    new cr.AwsCustomResource(this, "ActivateRuleSet", {
      onCreate: {
        service: "SES",
        action: "setActiveReceiptRuleSet",
        parameters: { RuleSetName: ruleSet.receiptRuleSetName },
        physicalResourceId: cr.PhysicalResourceId.of(`active-${ruleSet.receiptRuleSetName}`),
      },
      onUpdate: {
        service: "SES",
        action: "setActiveReceiptRuleSet",
        parameters: { RuleSetName: ruleSet.receiptRuleSetName },
        physicalResourceId: cr.PhysicalResourceId.of(`active-${ruleSet.receiptRuleSetName}`),
      },
      onDelete: {
        service: "SES",
        action: "setActiveReceiptRuleSet", // no RuleSetName ⇒ deactivate
      },
      policy: cr.AwsCustomResourcePolicy.fromSdkCalls({
        resources: cr.AwsCustomResourcePolicy.ANY_RESOURCE,
      }),
    });

    // MX so mail for the apex is delivered to SES's inbound endpoint.
    const zone = route53.PublicHostedZone.fromHostedZoneAttributes(this, "Zone", {
      hostedZoneId,
      zoneName: hostedZoneName,
    });
    new route53.MxRecord(this, "InboundMx", {
      zone,
      recordName: hostedZoneName,
      values: [{ priority: 10, hostName: `inbound-smtp.${this.region}.amazonaws.com` }],
      ttl: cdk.Duration.minutes(30),
    });
  }
}
