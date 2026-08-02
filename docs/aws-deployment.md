# AWS EC2 Deployment

This guide keeps the deployment small: one Dockerized FastAPI service on EC2,
S3 for uploaded documents and generated reports, and CloudWatch for container
logs. Job state remains on an EC2 Docker volume.

## 1. Create the S3 bucket

Create a private bucket in the same AWS Region as the EC2 instance. Keep
**Block all public access** enabled. The application accesses it through an EC2
IAM role, so no AWS access keys belong in `.env`.

## 2. Create and attach an EC2 IAM role

Replace `BUCKET_NAME` in this policy and attach it to the EC2 instance:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:ListBucket"],
      "Resource": "arn:aws:s3:::BUCKET_NAME"
    },
    {
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject"],
      "Resource": "arn:aws:s3:::BUCKET_NAME/research-platform/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents",
        "logs:DescribeLogStreams"
      ],
      "Resource": "*"
    }
  ]
}
```

## 3. Configure the EC2 instance

Launch a small Linux EC2 instance, attach the IAM role, allow SSH only from your
IP, and temporarily allow TCP port `8000` only from the addresses that need to
test the API. Install Git and Docker, then clone this repository.

Create `.env` from `.env.example` and set:

```text
OPENAI_API_KEY=your-key
TAVILY_API_KEY=your-key
STORAGE_BACKEND=s3
AWS_REGION=your-region
S3_BUCKET=your-private-bucket
S3_PREFIX=research-platform
```

Do not commit `.env` or place AWS access keys in it.

## 4. Build and run

```bash
docker build -t research-platform .
docker run -d \
  --name research-platform \
  --restart unless-stopped \
  -p 8000:8000 \
  --env-file .env \
  -v research-state:/app/state \
  --log-driver=awslogs \
  --log-opt awslogs-region=YOUR_REGION \
  --log-opt awslogs-group=/research-platform/backend \
  --log-opt awslogs-create-group=true \
  research-platform
```

## 5. Verify the deployment

```bash
curl http://localhost:8000/health
docker ps
```

Then upload a document through `/docs`, run a research job, and verify that the
bucket contains objects under `research-platform/uploads/` and
`research-platform/reports/`. Confirm that the CloudWatch log group receives
application logs before describing the project as deployed.
