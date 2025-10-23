# Deployment Guide: FastAPI on AWS Lambda (Zip + Mangum + API Gateway)

This guide describes how to build and deploy the FastAPI app to AWS Lambda using a zip package, API Gateway HTTP API, and Terraform.

## Prerequisites

- AWS account with credentials configured (`aws configure`)
- Terraform >= 1.5
- Python 3.12 on your machine
- Make sure you have permission to create Lambda, API Gateway, IAM resources

## One-time setup

1. Create your tfvars
   - Copy `infra/terraform/example.tfvars.example` to `infra/terraform/example.tfvars`
   - Fill in your Supabase values and CORS allowlist:

```hcl
ALLOWED_ORIGINS = "https://zipohubonline.com,https://zipohub.com"
```

2. Ensure `.gitignore` excludes `infra/terraform/example.tfvars` and build artifacts

## Build the Lambda package

From the repo root:

```bash
rm -rf deployment/build
bash deployment/build.sh
```

This will:

- download manylinux wheels for Python 3.12 on Amazon Linux 2023
- vendor dependencies and source into `deployment/build/function/`
- create the zip at `deployment/build/function.zip`

## Deploy infrastructure

From the repo root:

```bash
cd infra/terraform
terraform init
terraform apply -var-file=example.tfvars
```

Outputs:

- `api_url`: API Gateway base URL → `GET $api_url/health` and `$api_url/docs`
- `function_url`: Lambda Function URL (IAM-protected)

## Updating the app

Whenever you make changes:

```bash
# Rebuild zip
rm -rf deployment/build
bash deployment/build.sh

# Re-apply infra to update code
cd infra/terraform
terraform apply -var-file=example.tfvars
```

## Security hardening included

- Lambda Function URL requires `AWS_IAM` (no public anonymous access)
- CORS restricted by `ALLOWED_ORIGINS` env variable
- Secrets passed as environment variables (consider AWS SSM/Secrets Manager)

## Troubleshooting

- Import error: `email-validator is not installed`

  - Ensure `pydantic[email]` is present in `deployment/requirements-lambda.txt`

- Wheel not found for a dependency

  - The build script downloads manylinux_2_28 wheels; if a package doesn’t publish one, consider pinning a compatible version or switch to the container-based Lambda path.

- HTTP 500 on `/health`

  - Check CloudWatch logs for the function. We guard DB startup so `/health` should still succeed even without DB/Prisma. Verify Supabase env vars and network access.

- CORS not applying
  - Confirm `ALLOWED_ORIGINS` is set (comma-separated) in your tfvars and redeploy. Make sure your Origin header matches exactly.

## Alternative: Container-based Lambda

If you require native/binary-heavy packages, use an AWS-provided base image and the Lambda Web Adapter. This repo is prepared for zip + Mangum; container steps are out of scope for now.
