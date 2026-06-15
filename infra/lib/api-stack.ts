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
}

export class ApiStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: Props) {
    super(scope, id, props);
    const { envName, appTable, contentTable, userPool, userPoolClient } = props;

    const allowedOrigins =
      envName === "prod"
        ? ["https://finwingnews.com"]
        : ["http://localhost:5173"];

    const cognitoDomain = `https://cognito-idp.${this.region}.amazonaws.com/${userPool.userPoolId}`;

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

    const httpApi = new apigw.HttpApi(this, "HttpApi", {
      apiName: `finwing-${envName}`,
      corsPreflight: {
        allowOrigins: allowedOrigins,
        allowMethods: [apigw.CorsHttpMethod.ANY],
        allowHeaders: ["Content-Type"],
        allowCredentials: true,
      },
    });

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
