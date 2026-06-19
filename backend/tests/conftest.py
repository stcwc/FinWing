import os
import sys
from pathlib import Path

# Make `app` and `workers` importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("APP_TABLE", "finwing-app-test")
os.environ.setdefault("CONTENT_TABLE", "finwing-content-test")
os.environ.setdefault("AWS_REGION", "us-east-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("FINWING_ENV", "test")
os.environ.setdefault("UNSUBSCRIBE_SECRET", "test-unsub-secret")
os.environ.setdefault("EMAIL_SENDER", "noreply@finwingnews.com")
os.environ.setdefault("APP_URL", "https://example.test")

import boto3
import pytest
from moto import mock_aws

import app.services.db as db_module


@pytest.fixture
def tables():
    with mock_aws():
        ddb = boto3.resource("dynamodb", region_name="us-east-1")
        ddb.create_table(
            TableName="finwing-app-test",
            KeySchema=[
                {"AttributeName": "PK", "KeyType": "HASH"},
                {"AttributeName": "SK", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "PK", "AttributeType": "S"},
                {"AttributeName": "SK", "AttributeType": "S"},
                {"AttributeName": "GSI1PK", "AttributeType": "S"},
                {"AttributeName": "GSI1SK", "AttributeType": "S"},
                {"AttributeName": "GSI2PK", "AttributeType": "S"},
                {"AttributeName": "GSI2SK", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "GSI1",
                    "KeySchema": [
                        {"AttributeName": "GSI1PK", "KeyType": "HASH"},
                        {"AttributeName": "GSI1SK", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                },
                {
                    "IndexName": "GSI2",
                    "KeySchema": [
                        {"AttributeName": "GSI2PK", "KeyType": "HASH"},
                        {"AttributeName": "GSI2SK", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                },
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        ddb.create_table(
            TableName="finwing-content-test",
            KeySchema=[
                {"AttributeName": "PK", "KeyType": "HASH"},
                {"AttributeName": "SK", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "PK", "AttributeType": "S"},
                {"AttributeName": "SK", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        # Reset cached boto3 clients so they bind inside the mock
        db_module._dynamodb = None
        db_module._ddb_client = None
        yield ddb
        db_module._dynamodb = None
        db_module._ddb_client = None
