# Deployment Guide — AWS

Step-by-step instructions for deploying Clevercolab Classifier on AWS.

## Prerequisites

- AWS CLI configured (`aws configure`)
- AWS SAM CLI installed (`sam --version`)
- Node.js 20+ and npm
- Python 3.12+
- A GitHub repository with this project pushed
- API keys: Anthropic (required), Mistral (optional, only if `OCR_PROVIDER=mistral`)

---

## 1. Create S3 Buckets

Three buckets: uploaded files, processed output, and OCR results archive.

```bash
AWS_REGION=us-east-1

aws s3 mb s3://clevercolab-input --region $AWS_REGION
aws s3 mb s3://clevercolab-output --region $AWS_REGION
aws s3 mb s3://clevercolab-ocr-results --region $AWS_REGION
```

### Enable encryption and lifecycle rules

```bash
# Server-side encryption (SSE-S3)
for BUCKET in clevercolab-input clevercolab-output; do
  aws s3api put-bucket-encryption --bucket $BUCKET \
    --server-side-encryption-configuration '{
      "Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]
    }'
done

# Auto-delete uploaded/output files after 24 hours
for BUCKET in clevercolab-input clevercolab-output; do
  aws s3api put-bucket-lifecycle-configuration --bucket $BUCKET \
    --lifecycle-configuration '{
      "Rules": [{
        "ID": "auto-purge-24h",
        "Status": "Enabled",
        "Expiration": {"Days": 1}
      }]
    }'
done
```

> OCR results bucket has no lifecycle rule — results are kept for future reprocessing.

### Block public access (all three buckets)

```bash
for BUCKET in clevercolab-input clevercolab-output clevercolab-ocr-results; do
  aws s3api put-public-access-block --bucket $BUCKET \
    --public-access-block-configuration \
    BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
done
```

---

## 2. Create DynamoDB Table

Single-table design for job metadata and progress tracking.

```bash
aws dynamodb create-table \
  --table-name clevercolab-jobs \
  --attribute-definitions AttributeName=job_id,AttributeType=S \
  --key-schema AttributeName=job_id,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region $AWS_REGION
```

### Enable TTL (auto-delete expired jobs)

```bash
aws dynamodb update-time-to-live \
  --table-name clevercolab-jobs \
  --time-to-live-specification Enabled=true,AttributeName=ttl \
  --region $AWS_REGION
```

---

## 3. Create SQS Queue

Decouples file upload from document processing.

```bash
aws sqs create-queue \
  --queue-name clevercolab-process \
  --attributes '{
    "VisibilityTimeout": "900",
    "MessageRetentionPeriod": "86400"
  }' \
  --region $AWS_REGION
```

> `VisibilityTimeout=900` (15 min) matches the Lambda processing timeout.

### Create Dead Letter Queue (for failed jobs)

```bash
aws sqs create-queue \
  --queue-name clevercolab-process-dlq \
  --region $AWS_REGION

# Get DLQ ARN
DLQ_ARN=$(aws sqs get-queue-attributes \
  --queue-url https://sqs.$AWS_REGION.amazonaws.com/$(aws sts get-caller-identity --query Account --output text)/clevercolab-process-dlq \
  --attribute-names QueueArn --query Attributes.QueueArn --output text)

# Attach DLQ to main queue (move to DLQ after 3 failures)
QUEUE_URL=$(aws sqs get-queue-url --queue-name clevercolab-process --query QueueUrl --output text)
aws sqs set-queue-attributes --queue-url $QUEUE_URL \
  --attributes "{\"RedrivePolicy\": \"{\\\"deadLetterTargetArn\\\":\\\"$DLQ_ARN\\\",\\\"maxReceiveCount\\\":\\\"3\\\"}\"}"
```

---

## 4. Store API Keys in Secrets Manager

```bash
aws secretsmanager create-secret \
  --name clevercolab/anthropic-api-key \
  --secret-string "sk-ant-your-key-here" \
  --region $AWS_REGION

# Only if using Mistral OCR
aws secretsmanager create-secret \
  --name clevercolab/mistral-api-key \
  --secret-string "your-mistral-key-here" \
  --region $AWS_REGION
```

---

## 5. Create IAM Role for Lambda Functions

```bash
# Create the role
aws iam create-role \
  --role-name clevercolab-lambda-role \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {"Service": "lambda.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }]
  }'

# Attach basic Lambda execution policy (CloudWatch Logs)
aws iam attach-role-policy \
  --role-name clevercolab-lambda-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
```

### Create and attach custom policy

```bash
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

aws iam put-role-policy \
  --role-name clevercolab-lambda-role \
  --policy-name clevercolab-permissions \
  --policy-document "{
    \"Version\": \"2012-10-17\",
    \"Statement\": [
      {
        \"Effect\": \"Allow\",
        \"Action\": [\"s3:GetObject\", \"s3:PutObject\", \"s3:DeleteObject\"],
        \"Resource\": [
          \"arn:aws:s3:::clevercolab-input/*\",
          \"arn:aws:s3:::clevercolab-output/*\",
          \"arn:aws:s3:::clevercolab-ocr-results/*\"
        ]
      },
      {
        \"Effect\": \"Allow\",
        \"Action\": [
          \"dynamodb:GetItem\", \"dynamodb:PutItem\",
          \"dynamodb:UpdateItem\", \"dynamodb:Query\", \"dynamodb:Scan\"
        ],
        \"Resource\": \"arn:aws:dynamodb:${AWS_REGION}:${ACCOUNT_ID}:table/clevercolab-jobs\"
      },
      {
        \"Effect\": \"Allow\",
        \"Action\": [\"sqs:SendMessage\", \"sqs:ReceiveMessage\", \"sqs:DeleteMessage\", \"sqs:GetQueueAttributes\"],
        \"Resource\": \"arn:aws:sqs:${AWS_REGION}:${ACCOUNT_ID}:clevercolab-process\"
      },
      {
        \"Effect\": \"Allow\",
        \"Action\": [\"textract:DetectDocumentText\"],
        \"Resource\": \"*\"
      },
      {
        \"Effect\": \"Allow\",
        \"Action\": [\"secretsmanager:GetSecretValue\"],
        \"Resource\": \"arn:aws:secretsmanager:${AWS_REGION}:${ACCOUNT_ID}:secret:clevercolab/*\"
      }
    ]
  }"
```

---

## 6. Build and Deploy Lambda Functions

### Build the container image

```bash
cd backend

# Build the Docker image
docker build -t clevercolab-processor .

# Create ECR repository
aws ecr create-repository --repository-name clevercolab-processor --region $AWS_REGION

# Login to ECR
aws ecr get-login-password --region $AWS_REGION | \
  docker login --username AWS --password-stdin $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

# Tag and push
docker tag clevercolab-processor:latest \
  $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/clevercolab-processor:latest

docker push $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/clevercolab-processor:latest
```

### Create the Process Lambda (container image, high memory)

```bash
ROLE_ARN=$(aws iam get-role --role-name clevercolab-lambda-role --query Role.Arn --output text)

aws lambda create-function \
  --function-name clevercolab-process \
  --package-type Image \
  --code ImageUri=$ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/clevercolab-processor:latest \
  --role $ROLE_ARN \
  --timeout 900 \
  --memory-size 4096 \
  --environment "Variables={
    AWS_REGION_NAME=$AWS_REGION,
    S3_INPUT_BUCKET=clevercolab-input,
    S3_OUTPUT_BUCKET=clevercolab-output,
    S3_OCR_RESULTS_BUCKET=clevercolab-ocr-results,
    DYNAMODB_TABLE=clevercolab-jobs,
    OCR_PROVIDER=textract,
    ANTHROPIC_SECRET_NAME=clevercolab/anthropic-api-key
  }" \
  --region $AWS_REGION
```

### Create API Lambdas (upload, status, download, dashboard)

These are lightweight functions — use zip packaging instead of container images.

```bash
# Repeat for each handler: upload, status, download, dashboard
for HANDLER in upload status download dashboard; do
  aws lambda create-function \
    --function-name clevercolab-$HANDLER \
    --runtime python3.12 \
    --handler app.handlers.$HANDLER.handler \
    --role $ROLE_ARN \
    --timeout 30 \
    --memory-size 256 \
    --environment "Variables={
      AWS_REGION_NAME=$AWS_REGION,
      S3_INPUT_BUCKET=clevercolab-input,
      S3_OUTPUT_BUCKET=clevercolab-output,
      DYNAMODB_TABLE=clevercolab-jobs
    }" \
    --region $AWS_REGION
done
```

### Enable Function URLs (HTTPS endpoints)

```bash
for HANDLER in upload status download dashboard; do
  aws lambda create-function-url-config \
    --function-name clevercolab-$HANDLER \
    --auth-type NONE \
    --cors '{
      "AllowOrigins": ["*"],
      "AllowMethods": ["GET", "POST", "OPTIONS"],
      "AllowHeaders": ["Content-Type", "Authorization"],
      "MaxAge": 3600
    }'

  # Allow public invocation via Function URL
  aws lambda add-permission \
    --function-name clevercolab-$HANDLER \
    --statement-id FunctionURLAllowPublicAccess \
    --action lambda:InvokeFunctionUrl \
    --principal "*" \
    --function-url-auth-type NONE
done
```

### Connect SQS to Process Lambda

```bash
QUEUE_ARN=$(aws sqs get-queue-attributes \
  --queue-url $QUEUE_URL \
  --attribute-names QueueArn --query Attributes.QueueArn --output text)

aws lambda create-event-source-mapping \
  --function-name clevercolab-process \
  --event-source-arn $QUEUE_ARN \
  --batch-size 1
```

---

## 7. Get Function URLs

```bash
for HANDLER in upload status download dashboard; do
  URL=$(aws lambda get-function-url-config \
    --function-name clevercolab-$HANDLER \
    --query FunctionUrl --output text 2>/dev/null)
  echo "$HANDLER: $URL"
done
```

Save these URLs — the frontend needs them as environment variables.

---

## 8. Deploy Frontend on AWS Amplify

### Connect repository

1. Go to [AWS Amplify Console](https://console.aws.amazon.com/amplify/)
2. Click **"Create new app"** → **"Host web app"**
3. Select your Git provider (GitHub, CodeCommit, etc.) and authorize
4. Choose the repository and branch (`main`)
5. Amplify will auto-detect the Next.js framework

### Configure build settings

In the Amplify console, set the build specification:

```yaml
version: 1
applications:
  - frontend:
      phases:
        preBuild:
          commands:
            - cd frontend
            - npm ci
        build:
          commands:
            - npm run build
      artifacts:
        baseDirectory: frontend/.next
        files:
          - '**/*'
      cache:
        paths:
          - frontend/node_modules/**/*
          - frontend/.next/cache/**/*
    appRoot: frontend
```

### Set environment variables

In Amplify Console → App settings → Environment variables:

| Variable | Value |
|----------|-------|
| `NEXT_PUBLIC_API_UPLOAD_URL` | Upload Lambda Function URL |
| `NEXT_PUBLIC_API_STATUS_URL` | Status Lambda Function URL |
| `NEXT_PUBLIC_API_DOWNLOAD_URL` | Download Lambda Function URL |
| `NEXT_PUBLIC_API_DASHBOARD_URL` | Dashboard Lambda Function URL |

### Custom domain (optional)

1. Amplify Console → Domain management → Add domain
2. Enter your domain (e.g., `app.clevercolab.cl`)
3. Amplify provisions an SSL certificate and configures the DNS

### Deploy

Push to the connected branch — Amplify triggers a build and deploy automatically.

```bash
git push origin main
```

Monitor the build at: Amplify Console → App → Build status

---

## 9. Verify Deployment

### Check Lambda Functions

```bash
# Test upload handler
aws lambda invoke --function-name clevercolab-upload \
  --payload '{}' /dev/stdout

# Check Process Lambda logs
aws logs tail /aws/lambda/clevercolab-process --since 1h
```

### Check frontend

Open the Amplify app URL (shown in the Amplify Console) in a browser.

### End-to-end test

1. Open the app in browser
2. Upload a sample logistics PDF
3. Watch progress polling
4. Verify the report shows classified documents
5. Download the ZIP and check renamed files

---

## 10. Monitoring

### CloudWatch Alarms (recommended)

```bash
# Alert on Process Lambda errors
aws cloudwatch put-metric-alarm \
  --alarm-name clevercolab-process-errors \
  --namespace AWS/Lambda \
  --metric-name Errors \
  --dimensions Name=FunctionName,Value=clevercolab-process \
  --statistic Sum \
  --period 300 \
  --threshold 1 \
  --comparison-operator GreaterThanOrEqualToThreshold \
  --evaluation-periods 1 \
  --alarm-actions "arn:aws:sns:$AWS_REGION:$ACCOUNT_ID:your-alert-topic"

# Alert on DLQ messages (failed jobs)
aws cloudwatch put-metric-alarm \
  --alarm-name clevercolab-dlq-messages \
  --namespace AWS/SQS \
  --metric-name ApproximateNumberOfMessagesVisible \
  --dimensions Name=QueueName,Value=clevercolab-process-dlq \
  --statistic Sum \
  --period 300 \
  --threshold 1 \
  --comparison-operator GreaterThanOrEqualToThreshold \
  --evaluation-periods 1 \
  --alarm-actions "arn:aws:sns:$AWS_REGION:$ACCOUNT_ID:your-alert-topic"
```

### Useful log queries

```bash
# Recent processing jobs
aws logs tail /aws/lambda/clevercolab-process --since 1h --filter-pattern "Extracted text"

# OCR fallback usage
aws logs tail /aws/lambda/clevercolab-process --since 1h --filter-pattern "need OCR"

# Errors
aws logs tail /aws/lambda/clevercolab-process --since 1h --filter-pattern "ERROR"
```

---

## Updating

### Backend (Lambda)

```bash
cd backend
docker build -t clevercolab-processor .
docker tag clevercolab-processor:latest \
  $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/clevercolab-processor:latest
docker push $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/clevercolab-processor:latest

aws lambda update-function-code \
  --function-name clevercolab-process \
  --image-uri $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/clevercolab-processor:latest
```

### Frontend (Amplify)

```bash
git push origin main
# Amplify auto-builds and deploys
```

---

## Cost Estimate

Assumes **low-medium usage**: ~500 document batches/month, ~10 pages average per batch, ~20% of pages requiring OCR.

### Fixed costs (always-on infrastructure)

| Service | What you pay for | Monthly estimate | Notes |
|---------|-----------------|-----------------|-------|
| **Lambda (API handlers)** | Invocations + compute time | < $1 | upload/status/download/dashboard are lightweight (~100ms, 256 MB). 1M free requests/month in free tier. |
| **DynamoDB (on-demand)** | Read/write request units | < $1 | ~$1.25 per million writes, ~$0.25 per million reads. 500 jobs = ~2,500 WRUs + ~25,000 RRUs (polling). Well within free tier (25 WCU + 25 RCU perpetual). |
| **S3 (storage + requests)** | Storage GB + PUT/GET requests | < $2 | Input/output buckets auto-purge after 24h, so storage stays minimal. OCR results bucket grows slowly (~1 KB per page). Requests: $0.005/1K PUTs, $0.0004/1K GETs. |
| **Amplify Hosting** | Build minutes + bandwidth | $0–5 | Free tier: 1,000 build minutes + 15 GB bandwidth/month. Exceeding free tier: ~$0.01/build-minute, $0.15/GB served. |
| **CloudWatch Logs** | Log ingestion + storage | < $1 | $0.50/GB ingested. Lambda logs are small; ~100 MB/month at this volume. |

**Fixed subtotal: ~$2–8/month** (much of it covered by AWS Free Tier in the first 12 months)

### Variable costs (per-use, scales with volume)

| Service | Unit cost | At 500 batches/month | Notes |
|---------|-----------|---------------------|-------|
| **Lambda (processing)** | $0.0000167/GB-s | **$5–15** | 4 GB memory × ~15s avg = 60 GB-s per invocation. 500 invocations = 30,000 GB-s. At $0.0000167/GB-s = ~$0.50. But cold starts + retries push real cost to $5–15. Free tier: 400,000 GB-s/month. |
| **AWS Textract OCR** | $1.50 / 1,000 pages | **$1.50** | Only scanned pages (~20% of 5,000 pages = 1,000 pages). Text-layer PDFs use PyMuPDF (free). |
| **Mistral OCR** (if used instead) | $2.00 / 1,000 pages | **$2.00** | Alternative to Textract. Set via `OCR_PROVIDER` env var. |
| **Claude API (classification)** | ~$0.003/1K input + $0.015/1K output tokens | **$3–5** | 1 classify call per PDF (~2K input tokens, ~500 output tokens). 500 calls ≈ 1M input + 250K output tokens. |
| **Claude API (extraction)** | Same token pricing | **$5–10** | 1 extract call per *document segment* (avg ~2 segments per PDF = 1,000 calls). Smaller prompts than classification. |
| **SQS** | $0.40 / 1M requests | < $0.01 | Negligible at this volume. 1M requests/month free tier. |
| **Secrets Manager** | $0.40/secret/month + $0.05/10K API calls | ~$1 | 2 secrets (Anthropic + optional Mistral). Cached in Lambda memory between invocations. |

**Variable subtotal: ~$15–30/month** at 500 batches

### Total monthly cost by usage tier

| Usage | Batches/month | Pages processed | Est. monthly cost |
|-------|--------------|----------------|-------------------|
| **Low** | ~100 | ~1,000 | **$5–12** (mostly free tier) |
| **Medium** | ~500 | ~5,000 | **$18–35** |
| **High** | ~2,000 | ~20,000 | **$60–120** |
| **Very high** | ~10,000 | ~100,000 | **$300–550** |

### Cost optimization tips

- **PyMuPDF first**: The two-tier OCR strategy saves ~80% on OCR costs since most logistics docs have text layers.
- **Free Tier**: AWS Free Tier covers most fixed costs for 12 months (Lambda 400K GB-s, DynamoDB 25 WCU/RCU, S3 5 GB, 1M SQS requests).
- **S3 lifecycle rules**: 24h auto-purge on input/output buckets prevents storage cost accumulation.
- **DynamoDB TTL**: Auto-deletes expired job records, keeping table small.
- **Claude prompt caching**: If Anthropic prompt caching is enabled, the classification system prompt (~1.5K tokens) is cached across calls, reducing input token costs by ~90% for the cached portion.
- **Reserved Textract pricing**: Not available, but batching pages reduces API call overhead.

> **Note**: Prices based on `us-east-1` region as of early 2025. Check [AWS Pricing](https://aws.amazon.com/pricing/) for current rates. Claude API pricing at [Anthropic Pricing](https://www.anthropic.com/pricing).
