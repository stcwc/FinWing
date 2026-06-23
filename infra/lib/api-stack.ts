import * as cdk from "aws-cdk-lib";
import { Construct } from "constructs";
import * as lambda from "aws-cdk-lib/aws-lambda";
import * as dynamodb from "aws-cdk-lib/aws-dynamodb";
import * as cognito from "aws-cdk-lib/aws-cognito";
import * as apigw from "aws-cdk-lib/aws-apigatewayv2";
import * as integrations from "aws-cdk-lib/aws-apigatewayv2-integrations";
import * as logs from "aws-cdk-lib/aws-logs";
import { backendCode } from "./lambda-code";

interface Props extends cdk.StackProps {
  envName: string;
  appTable: dynamodb.Table;
  contentTable: dynamodb.Table;
  userPool: cognito.UserPool;
  userPoolClient: cognito.UserPoolClient;
  /** Branded Hosted-UI domain (auth.finwingnews.com); falls back to the
   *  Cognito prefix domain when unset. Used for the OAuth token endpoints. */
  authDomain?: string;
}

export class ApiStack extends cdk.Stack {
  readonly httpApi: apigw.HttpApi;

  constructor(scope: Construct, id: string, props: Props) {
    super(scope, id, props);
    const { envName, appTable, contentTable, userPool, userPoolClient } = props;

    // Same-origin in practice (SPA calls /api on its own host), but list the
    // custom domain + CloudFront URL so credentialed CORS works from any of them.
    const allowedOrigins = [
      "https://finwingnews.com",
      "https://www.finwingnews.com",
      "https://d3anxrgbzxir7p.cloudfront.net",
      "http://localhost:5173",
    ];

    // Hosted-UI domain host (no scheme) for the OAuth token/refresh endpoints.
    // Prefer the branded custom domain; fall back to the Cognito prefix domain
    // (which the Foundation stack still serves) when no branded domain is set.
    const domainPrefix = `finwing-${envName}-${this.account.slice(0, 6)}`;
    const cognitoDomain =
      props.authDomain ?? `${domainPrefix}.auth.${this.region}.amazoncognito.com`;

    const apiFn = new lambda.Function(this, "ApiHandler", {
      functionName: `finwing-api-${envName}`,
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: "app.main.handler",
      code: backendCode(),
      memorySize: 512,
      timeout: cdk.Duration.seconds(30),
      logRetention: logs.RetentionDays.TWO_WEEKS,
      environment: {
        FINWING_ENV: envName,
        APP_TABLE: appTable.tableName,
        CONTENT_TABLE: contentTable.tableName,
        COGNITO_USER_POOL_ID: userPool.userPoolId,
        COGNITO_CLIENT_ID: userPoolClient.userPoolClientId,
        COGNITO_DOMAIN: cognitoDomain,
        ALLOWED_ORIGINS: allowedOrigins.join(","),
        BACKFILL_FN_NAME: `finwing-backfill-${envName}`,
      },
    });

    appTable.grantReadWriteData(apiFn);
    contentTable.grantReadData(apiFn);
    apiFn.addToRolePolicy(
      new cdk.aws_iam.PolicyStatement({
        actions: ["ssm:GetParameter"],
        resources: [
          `arn:aws:ssm:${this.region}:${this.account}:parameter/finwing/${envName}/*`,
        ],
      })
    );
    // Code-exchange + refresh against the Cognito token endpoint.
    apiFn.addToRolePolicy(
      new cdk.aws_iam.PolicyStatement({
        actions: ["cognito-idp:InitiateAuth"],
        resources: [userPool.userPoolArn],
      })
    );
    // Async-invoke the backfill function on lens creation (referenced by ARN to
    // avoid a stack dependency on the pipeline stack).
    apiFn.addToRolePolicy(
      new cdk.aws_iam.PolicyStatement({
        actions: ["lambda:InvokeFunction"],
        resources: [
          `arn:aws:lambda:${this.region}:${this.account}:function:finwing-backfill-${envName}`,
        ],
      })
    );

    const httpApi = new apigw.HttpApi(this, "HttpApi", {
      apiName: `finwing-${envName}`,
      corsPreflight: {
        allowOrigins: allowedOrigins,
        allowMethods: [apigw.CorsHttpMethod.ANY],
        allowHeaders: ["Content-Type"],
        allowCredentials: true,
      },
    });
    this.httpApi = httpApi;

    httpApi.addRoutes({
      path: "/{proxy+}",
      methods: [apigw.HttpMethod.ANY],
      integration: new integrations.HttpLambdaIntegration("ApiIntegration", apiFn),
    });

    // Per-stage throttle ≈ the 10 TPS/account limit (HLD §7.1). Fine-grained
    // per-user throttling is enforced in-app via the authorizer context.
    const stage = httpApi.defaultStage?.node.defaultChild as apigw.CfnStage;
    stage.defaultRouteSettings = { throttlingBurstLimit: 20, throttlingRateLimit: 10 };

    new cdk.CfnOutput(this, "ApiUrl", { value: httpApi.apiEndpoint });
  }
}
