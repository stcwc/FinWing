import * as cdk from "aws-cdk-lib";
import { Construct } from "constructs";
import * as dynamodb from "aws-cdk-lib/aws-dynamodb";
import * as cognito from "aws-cdk-lib/aws-cognito";
import * as sqs from "aws-cdk-lib/aws-sqs";
import * as ssm from "aws-cdk-lib/aws-ssm";

interface Props extends cdk.StackProps {
  envName: string;
}

/** Shared stateful resources: DynamoDB tables, Cognito, SQS queues, secrets. */
export class FoundationStack extends cdk.Stack {
  readonly appTable: dynamodb.Table;
  readonly contentTable: dynamodb.Table;
  readonly userPool: cognito.UserPool;
  readonly userPoolClient: cognito.UserPoolClient;
  readonly matchingQueue: sqs.Queue;
  readonly abstractionQueue: sqs.Queue;

  constructor(scope: Construct, id: string, props: Props) {
    super(scope, id, props);
    const { envName } = props;
    const removalPolicy =
      envName === "prod" ? cdk.RemovalPolicy.RETAIN : cdk.RemovalPolicy.DESTROY;

    // ── App table (per-user) ────────────────────────────────────
    this.appTable = new dynamodb.Table(this, "AppTable", {
      tableName: `finwing-app-${envName}`,
      partitionKey: { name: "PK", type: dynamodb.AttributeType.STRING },
      sortKey: { name: "SK", type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      timeToLiveAttribute: "ttl",
      pointInTimeRecovery: envName === "prod",
      removalPolicy,
    });
    this.appTable.addGlobalSecondaryIndex({
      indexName: "GSI1",
      partitionKey: { name: "GSI1PK", type: dynamodb.AttributeType.STRING },
      sortKey: { name: "GSI1SK", type: dynamodb.AttributeType.STRING },
      projectionType: dynamodb.ProjectionType.ALL,
    });
    this.appTable.addGlobalSecondaryIndex({
      indexName: "GSI2",
      partitionKey: { name: "GSI2PK", type: dynamodb.AttributeType.STRING },
      sortKey: { name: "GSI2SK", type: dynamodb.AttributeType.STRING },
      projectionType: dynamodb.ProjectionType.INCLUDE,
      nonKeyAttributes: ["timezone", "summaryTimePref", "lensCount"],
    });

    // ── Content table (shared news) ─────────────────────────────
    this.contentTable = new dynamodb.Table(this, "ContentTable", {
      tableName: `finwing-content-${envName}`,
      partitionKey: { name: "PK", type: dynamodb.AttributeType.STRING },
      sortKey: { name: "SK", type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      timeToLiveAttribute: "ttl",
      removalPolicy,
    });

    // ── Cognito ─────────────────────────────────────────────────
    this.userPool = new cognito.UserPool(this, "UserPool", {
      userPoolName: `finwing-${envName}`,
      selfSignUpEnabled: true,
      signInAliases: { email: true },
      autoVerify: { email: true },
      standardAttributes: { email: { required: true, mutable: true } },
      passwordPolicy: { minLength: 8, requireDigits: true, requireLowercase: true },
      accountRecovery: cognito.AccountRecovery.EMAIL_ONLY,
      removalPolicy,
    });
    new cognito.CfnUserPoolGroup(this, "AdminGroup", {
      userPoolId: this.userPool.userPoolId,
      groupName: "finwing-admins",
      description: "FinWing administrators",
    });

    const domainPrefix = `finwing-${envName}-${this.account.slice(0, 6)}`;
    this.userPool.addDomain("HostedUiDomain", {
      cognitoDomain: { domainPrefix },
    });

    // Google federation. Client ID + secret come from SSM (set out-of-band so
    // the secret never lives in source); the IdP is created only when the
    // params exist. Deploy with `-c enableGoogle=true` after setting them.
    let googleIdp: cognito.UserPoolIdentityProviderGoogle | undefined;
    if (this.node.tryGetContext("enableGoogle") !== "false") {
      googleIdp = new cognito.UserPoolIdentityProviderGoogle(this, "GoogleIdp", {
        userPool: this.userPool,
        clientId: ssm.StringParameter.valueForStringParameter(
          this,
          `/finwing/${envName}/google-client-id`
        ),
        // CloudFormation does not support ssm-secure references on this field,
        // so the secret is a plain SSM String resolved at deploy ({{resolve:ssm}}).
        // Cognito stores the secret anyway; SSM access stays IAM-restricted.
        clientSecretValue: cdk.SecretValue.unsafePlainText(
          ssm.StringParameter.valueForStringParameter(
            this,
            `/finwing/${envName}/google-client-secret`
          )
        ),
        scopes: ["openid", "email", "profile"],
        attributeMapping: {
          email: cognito.ProviderAttribute.GOOGLE_EMAIL,
          givenName: cognito.ProviderAttribute.GOOGLE_GIVEN_NAME,
          familyName: cognito.ProviderAttribute.GOOGLE_FAMILY_NAME,
        },
      });
    }

    // App origins Cognito will accept for OAuth redirect/logout. The custom
    // domain (apex + www) is served by the same CloudFront distribution as the
    // original *.cloudfront.net URL, so we keep all of them valid — sign-in
    // works whether the user lands on finwingnews.com or the CloudFront URL.
    const appOrigins = [
      "https://finwingnews.com",
      "https://www.finwingnews.com",
      "https://d3anxrgbzxir7p.cloudfront.net",
    ];
    const callbackUrls = [
      ...appOrigins.map((o) => `${o}/auth/callback`),
      "http://localhost:5173/auth/callback",
    ];
    const logoutUrls = [
      ...appOrigins.map((o) => `${o}/signin`),
      "http://localhost:5173/signin",
    ];

    this.userPoolClient = this.userPool.addClient("WebClient", {
      generateSecret: false,
      authFlows: { userSrp: true },
      oAuth: {
        flows: { authorizationCodeGrant: true },
        scopes: [
          cognito.OAuthScope.OPENID,
          cognito.OAuthScope.EMAIL,
          cognito.OAuthScope.PROFILE,
        ],
        callbackUrls,
        logoutUrls,
      },
      supportedIdentityProviders: [
        cognito.UserPoolClientIdentityProvider.COGNITO,
        ...(googleIdp ? [cognito.UserPoolClientIdentityProvider.GOOGLE] : []),
      ],
    });
    // The client must be created after the Google IdP it references.
    if (googleIdp) {
      this.userPoolClient.node.addDependency(googleIdp);
    }

    // ── SQS pipeline queues (with DLQs) ─────────────────────────
    const matchingDlq = new sqs.Queue(this, "MatchingDLQ", {
      queueName: `finwing-matching-dlq-${envName}`,
    });
    this.matchingQueue = new sqs.Queue(this, "MatchingQueue", {
      queueName: `finwing-matching-${envName}`,
      visibilityTimeout: cdk.Duration.seconds(90),
      deadLetterQueue: { queue: matchingDlq, maxReceiveCount: 3 },
    });

    const abstractionDlq = new sqs.Queue(this, "AbstractionDLQ", {
      queueName: `finwing-abstraction-dlq-${envName}`,
    });
    this.abstractionQueue = new sqs.Queue(this, "AbstractionQueue", {
      queueName: `finwing-abstraction-${envName}`,
      visibilityTimeout: cdk.Duration.seconds(90),
      deadLetterQueue: { queue: abstractionDlq, maxReceiveCount: 3 },
    });

    // ── Secret placeholders (values set manually, never in source) ──
    for (const name of ["anthropic-api-key", "finnhub-api-key", "twelvedata-api-key"]) {
      new ssm.StringParameter(this, `Param-${name}`, {
        parameterName: `/finwing/${envName}/${name}`,
        stringValue: "REPLACE_ME",
        tier: ssm.ParameterTier.STANDARD,
      });
    }

    new cdk.CfnOutput(this, "UserPoolId", { value: this.userPool.userPoolId });
    new cdk.CfnOutput(this, "UserPoolClientId", {
      value: this.userPoolClient.userPoolClientId,
    });
    new cdk.CfnOutput(this, "CognitoDomain", {
      value: `${domainPrefix}.auth.${this.region}.amazoncognito.com`,
    });
  }
}
