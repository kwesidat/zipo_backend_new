output "api_url" {
  value = aws_apigatewayv2_api.http.api_endpoint
}

output "function_url" {
  value = aws_lambda_function_url.fastapi.function_url
}

