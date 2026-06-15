import * as cdk from "aws-cdk-lib";
import { Construct } from "constructs";
import * as s3 from "aws-cdk-lib/aws-s3";
import * as cloudfront from "aws-cdk-lib/aws-cloudfront";
import * as origins from "aws-cdk-lib/aws-cloudfront-origins";
import * as s3deploy from "aws-cdk-lib/aws-s3-deployment";
import * as path from "path";
import * as fs from "fs";

interface Props extends cdk.StackProps {
  envName: string;
  domainName?: string;
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

    const distribution = new cloudfront.Distribution(this, "Distribution", {
      defaultRootObject: "index.html",
      defaultBehavior: {
        origin: origins.S3BucketOrigin.withOriginAccessControl(bucket),
        viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
        cachePolicy: cloudfront.CachePolicy.CACHING_OPTIMIZED,
      },
      // SPA fallback: client-side routes resolve to index.html.
      errorResponses: [
        { httpStatus: 403, responseHttpStatus: 200, responsePagePath: "/index.html" },
        { httpStatus: 404, responseHttpStatus: 200, responsePagePath: "/index.html" },
      ],
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
