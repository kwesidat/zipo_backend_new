# Zipo Backend (FastAPI)

FastAPI backend for ZipoHub. Includes authentication, products, orders, payments and more.

## Local Development

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open http://localhost:8000/docs

## Serverless Deployment (AWS Lambda)

See detailed steps in [DEPLOYMENT.md](./DEPLOYMENT.md).

Quickstart:

```bash
# Build zip for Lambda
bash deployment/build.sh

# Deploy infra with Terraform
cd infra/terraform
terraform init
terraform apply -var-file=example.tfvars

# Get API Gateway URL and test
terraform output -raw api_url
curl "$(terraform output -raw api_url)/health"
```

## Security

- Function URL requires AWS_IAM
- CORS origins are restricted via `ALLOWED_ORIGINS`
- Consider moving secrets to AWS SSM/Secrets Manager
