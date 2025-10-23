locals {
  lambda_name = "${var.project_name}-${var.stage}"
  lambda_zip  = "${path.module}/../../deployment/build/function.zip"
}

resource "aws_iam_role" "lambda_exec" {
  name = "${local.lambda_name}-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "basic" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_lambda_function" "fastapi" {
  function_name    = local.lambda_name
  role             = aws_iam_role.lambda_exec.arn
  handler          = "handler.handler"
  runtime          = "python3.12"
  filename         = local.lambda_zip
  source_code_hash = filebase64sha256(local.lambda_zip)
  timeout          = var.timeout_s
  memory_size      = var.memory_mb
  architectures    = ["x86_64"]
  environment {
    variables = {
      STAGE                     = var.stage
      SUPABASE_URL              = var.SUPABASE_URL
      SUPABASE_ANON_KEY         = var.SUPABASE_ANON_KEY
      SUPABASE_SERVICE_ROLE_KEY = var.SUPABASE_SERVICE_ROLE_KEY
      SUPABASE_BUCKET           = var.SUPABASE_BUCKET
      SUPABASE_JWT_SECRET       = var.SUPABASE_JWT_SECRET
      ALLOWED_ORIGINS           = var.ALLOWED_ORIGINS
    }
  }
}

resource "aws_apigatewayv2_api" "http" {
  name          = "${local.lambda_name}-http-api"
  protocol_type = "HTTP"
}

resource "aws_apigatewayv2_integration" "lambda" {
  api_id                 = aws_apigatewayv2_api.http.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.fastapi.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "proxy" {
  api_id    = aws_apigatewayv2_api.http.id
  route_key = "$default"
  target    = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.http.id
  name        = "$default"
  auto_deploy = true
}

resource "aws_lambda_permission" "allow_apigw" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.fastapi.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.http.execution_arn}/*/*"
}

# Optional: Public Lambda Function URL for direct invocation (bypasses API Gateway)
resource "aws_lambda_function_url" "fastapi" {
  function_name      = aws_lambda_function.fastapi.function_name
  authorization_type = "AWS_IAM"
  cors {
    allow_origins  = ["*"]
    allow_methods  = ["*"]
    allow_headers  = ["*"]
    expose_headers = ["*"]
  }
}

// No explicit permission block needed for public Function URL with authorization_type = "NONE"

