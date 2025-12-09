#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

BASE_URL="http://localhost:8080"

echo -e "${BLUE}=======================================${NC}"
echo -e "${BLUE}Testing Courier API Endpoints${NC}"
echo -e "${BLUE}=======================================${NC}"
echo ""

# Test 1: Login
echo -e "${BLUE}1. Testing Courier Login${NC}"
echo "Email: rhntssk@gmail.com"
echo "Password: 123456789Aa@"
echo ""

LOGIN_RESPONSE=$(curl -s -X POST "${BASE_URL}/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "rhntssk@gmail.com",
    "password": "123456789Aa@"
  }')

echo "$LOGIN_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$LOGIN_RESPONSE"
echo ""

# Extract access token
ACCESS_TOKEN=$(echo "$LOGIN_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('access_token', ''))" 2>/dev/null)

if [ -z "$ACCESS_TOKEN" ]; then
  echo -e "${RED}❌ Login failed - no access token received${NC}"
  exit 1
fi

echo -e "${GREEN}✅ Login successful!${NC}"
echo "Access Token: ${ACCESS_TOKEN:0:50}..."
echo ""

# Test 2: Get available deliveries
echo -e "${BLUE}=======================================${NC}"
echo -e "${BLUE}2. Testing Available Deliveries${NC}"
echo -e "${BLUE}=======================================${NC}"
echo ""

AVAILABLE_DELIVERIES=$(curl -s -X GET "${BASE_URL}/api/deliveries/available" \
  -H "Authorization: Bearer $ACCESS_TOKEN")

echo "$AVAILABLE_DELIVERIES" | python3 -m json.tool 2>/dev/null || echo "$AVAILABLE_DELIVERIES"
echo ""

# Test 3: Get courier's assigned deliveries
echo -e "${BLUE}=======================================${NC}"
echo -e "${BLUE}3. Testing Courier's My Deliveries${NC}"
echo -e "${BLUE}=======================================${NC}"
echo ""

MY_DELIVERIES=$(curl -s -X GET "${BASE_URL}/api/deliveries/courier/my-deliveries" \
  -H "Authorization: Bearer $ACCESS_TOKEN")

echo "$MY_DELIVERIES" | python3 -m json.tool 2>/dev/null || echo "$MY_DELIVERIES"
echo ""

echo -e "${GREEN}=======================================${NC}"
echo -e "${GREEN}✅ All tests completed!${NC}"
echo -e "${GREEN}=======================================${NC}"
