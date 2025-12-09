#!/bin/bash

# Test script for courier API endpoints
# Replace with actual courier JWT token

echo "=========================================="
echo "Testing Courier API Endpoints"
echo "=========================================="

# Replace with a valid courier JWT token
TOKEN="$1"

if [ -z "$TOKEN" ]; then
    echo "Error: Please provide a courier JWT token as argument"
    echo "Usage: ./test_courier_api.sh YOUR_COURIER_TOKEN"
    exit 1
fi

BASE_URL="http://localhost:8080"

echo ""
echo "1. Testing /api/deliveries/available"
echo "------------------------------------------"
curl -X GET "$BASE_URL/api/deliveries/available?page=1&page_size=20" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" | python -m json.tool

echo ""
echo ""
echo "2. Testing /api/deliveries/courier/dashboard"
echo "------------------------------------------"
curl -X GET "$BASE_URL/api/deliveries/courier/dashboard" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" | python -m json.tool

echo ""
echo ""
echo "3. Testing /api/deliveries/courier/my-deliveries"
echo "------------------------------------------"
curl -X GET "$BASE_URL/api/deliveries/courier/my-deliveries?page=1&page_size=50" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" | python -m json.tool

echo ""
echo "=========================================="
echo "Test Complete"
echo "=========================================="
