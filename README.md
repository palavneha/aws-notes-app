# Notes app: Flask + AWS DynamoDB

A small web app to create, edit and delete notes, stored in a DynamoDB table.

## Setup

1. Install dependencies:

   ```bash
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. Configure AWS credentials (any one of these):

   ```bash
   aws configure            # writes ~/.aws/credentials
   # or export AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY
   ```

3. Choose a region and table name (optional, these are the defaults):

   ```bash
   export AWS_REGION=ap-south-1
   export DYNAMODB_TABLE=notes
   ```

4. Create the table (once):

   ```bash
   python create_table.py
   ```

5. Run the app and open http://127.0.0.1:5000:

   ```bash
   python app.py
   ```

## Minimum IAM permissions

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": ["dynamodb:Scan", "dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:DeleteItem", "dynamodb:CreateTable", "dynamodb:DescribeTable"],
    "Resource": "arn:aws:dynamodb:ap-south-1:*:table/notes"
  }]
}
```

`CreateTable` and `DescribeTable` are only needed for the setup script; remove them afterwards.

## Notes

- Never commit AWS keys. When deployed on EC2, ECS or App Runner, attach an IAM role instead of using keys.
- Set `FLASK_SECRET_KEY` to a random value outside local development.
- The list view uses `Scan`, which is fine for a small app. For large data, switch to a `Query` on a suitable key.
- For production, run behind gunicorn (`pip install gunicorn && gunicorn app:app`), not the Flask dev server.
