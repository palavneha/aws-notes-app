import uuid
import boto3
from botocore.exceptions import ClientError

REGION = "ap-south-1"

def attempt(name, fn):
    try:
        fn()
        print(f"OK      {name}")
    except ClientError as e:
        print(f"DENIED  {name}: {e.response['Error']['Code']}")
    except Exception as e:
        print(f"ERROR   {name}: {e}")

def s3_bucket():
    s3 = boto3.client("s3", region_name=REGION)
    b = f"notes-test-{uuid.uuid4().hex[:10]}"
    s3.create_bucket(Bucket=b, CreateBucketConfiguration={"LocationConstraint": REGION})
    s3.delete_bucket(Bucket=b)

def ddb_list():
    boto3.client("dynamodb", region_name=REGION).list_tables()

def ddb_provisioned():
    d = boto3.client("dynamodb", region_name=REGION)
    n = f"test-{uuid.uuid4().hex[:8]}"
    d.create_table(
        TableName=n,
        KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
        ProvisionedThroughput={"ReadCapacityUnits": 1, "WriteCapacityUnits": 1},
    )
    d.get_waiter("table_exists").wait(TableName=n)
    d.delete_table(TableName=n)

def sqs_queue():
    q = boto3.client("sqs", region_name=REGION)
    url = q.create_queue(QueueName=f"t{uuid.uuid4().hex[:8]}")["QueueUrl"]
    q.delete_queue(QueueUrl=url)

def lambda_list():
    boto3.client("lambda", region_name=REGION).list_functions()

attempt("S3: create + delete bucket", s3_bucket)
attempt("DynamoDB: list tables", ddb_list)
attempt("DynamoDB: create table (provisioned mode)", ddb_provisioned)
attempt("SQS: create + delete queue", sqs_queue)
attempt("Lambda: list functions", lambda_list)