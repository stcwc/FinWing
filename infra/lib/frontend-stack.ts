import * as cdk from "aws-cdk-lib";
import { Construct } from "constructs";
import * as s3 from "aws-cdk-lib/aws-s3";
import * as cloudfront from "aws-cdk-lib/aws-cloudfront";
import * as origins from "aws-cdk-lib/aws-cloudfront-origins";
import * as s3deploy from "aws-cdk-lib/aws-s3-deployment";
import * as apigw from "aws-cdk-lib/aws-apigatewayv2";
import * as path from "path";
import * as fs from "fs";

interface Props extends cdk.StackProps {
  envName: string;
  domainName?: string;
  httpApi: apigw.HttpApi;
}

/** SPA hosting: private S3 bucket behind CloudFront with SPA routing. The
 *  built frontend (frontend/dist) and seeded /static config are deployed if
 *  present. (LLD §11) */
export class FrontendStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: Props) {
    super(scope, id, props);
    const { envName } = props;

    const bucket = new s3.Bucket(this, "SpaBucket", {
      bucketName: `finwing-spa-${envName}-${this.account}`,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      encryption: s3.BucketEncryption.S3_MANAGED,
      removalPolicy:
        envName === "prod" ? cdk.RemovalPolicy.RETAIN : cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: envName !== "prod",
    });

    // API Gateway HTTP API endpoint host: <apiId>.execute-api.<region>.amazonaws.com.
    const apiHost = cdk.Fn.select(2, cdk.Fn.split("/", props.httpApi.apiEndpoint));
    const apiOrigin = new origins.HttpOrigin(apiHost, {
      protocolPolicy: cloudfront.OriginProtocolPolicy.HTTPS_ONLY,
    });

    // Strip the "/api" prefix before forwarding to the API (FastAPI routes live
    // at root). Keeps the SPA and API same-origin so httpOnly cookies work
    // without third-party-cookie restrictions.
    const stripApi = new cloudfront.Function(this, "StripApiPrefix", {
      code: cloudfront.FunctionCode.fromInline(
        `function handler(event) {
  var r = event.request;
  r.uri = r.uri.replace(/^\\/api/, '');
  if (r.uri === '') { r.uri = '/'; }
  return r;
}`
      ),
    });

    // SPA routing: extensionless paths (client-side routes like /lenses) serve
    // index.html. Real files (.js/.css/.json) pass through. Done as a function
    // rather than distribution error responses so API 4xx responses are not
    // rewritten.
    const spaRouter = new cloudfront.Function(this, "SpaRouter", {
      code: cloudfront.FunctionCode.fromInline(
        `function handler(event) {
  var r = event.request;
  if (r.uri.indexOf('.') === -1) { r.uri = '/index.html'; }
  return r;
}`
      ),
    });

    const distribution = new cloudfront.Distribution(this, "Distribution", {
      defaultRootObject: "index.html",
      defaultBehavior: {
        origin: origins.S3BucketOrigin.withOriginAccessControl(bucket),
        viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
        cachePolicy: cloudfront.CachePolicy.CACHING_OPTIMIZED,
        functionAssociations: [
          { function: spaRouter, eventType: cloudfront.FunctionEventType.VIEWER_REQUEST },
        ],
      },
      additionalBehaviors: {
        "/api/*": {
          origin: apiOrigin,
          viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
          allowedMethods: cloudfront.AllowedMethods.ALLOW_ALL,
          cachePolicy: cloudfront.CachePolicy.CACHING_DISABLED,
          // Forward everything except Host (origin must see its own host) so
          // cookies and bodies reach the Lambda.
          originRequestPolicy: cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
          functionAssociations: [
            { function: stripApi, eventType: cloudfront.FunctionEventType.VIEWER_REQUEST },
          ],
        },
      },
      priceClass: cloudfront.PriceClass.PRICE_CLASS_100,
    });

    // Deploy the built SPA only if it exists (CI builds it before cdk deploy).
    const distDir = path.resolve(__dirname, "../../frontend/dist");
    if (fs.existsSync(distDir)) {
      new s3deploy.BucketDeployment(this, "DeploySpa", {
        sources: [s3deploy.Source.asset(distDir)],
        destinationBucket: bucket,
        distribution,
        distributionPaths: ["/*"],
      });
    }

    new cdk.CfnOutput(this, "DistributionDomain", {
      value: distribution.distributionDomainName,
    });
    new cdk.CfnOutput(this, "SpaBucketName", { value: bucket.bucketName });
  }
}
