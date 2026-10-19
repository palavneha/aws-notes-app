"""One-time setup: creates the DynamoDB table the app uses.

Usage:  python create_table.py
Env:    DYNAMODB_TABLE (default "notes"), AWS_REGION (default "ap-south-1")
"""
import os

import boto3
from botocore.exceptions import ClientError

TABLE_NAME = os.environ.get("DYNAMODB_TABLE", "notes")
REGION = os.environ.get("AWS_REGION", "ap-south-1")

dynamodb = boto3.resource("dynamodb", region_name=REGION)

try:
    table = dynamodb.create_table(
        TableName=TABLE_NAME,
        KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",  # no capacity planning; cost is ~zero at low traffic
    )
    table.wait_until_exists()
    print(f"Created table '{TABLE_NAME}' in {REGION}.")
except ClientError as e:
    if e.response["Error"]["Code"] == "ResourceInUseException":
        print(f"Table '{TABLE_NAME}' already exists in {REGION}.")
    else:
        raise
