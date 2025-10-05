# Paystack Webhook Setup Guide

This document explains how to set up and use the Paystack webhook integration for your FastAPI backend.

## Features Implemented

✅ **Paystack signature verification** for security
✅ **Agent commission system** (10% on all transactions)
✅ **Referral commission tracking** for new user signups
✅ **Subscription payment handling** (new + renewals)
✅ **Product purchase handling**
✅ **One-time payment processing**
✅ **Duplicate transaction prevention**
✅ **Background task processing** for better performance

## Setup Instructions

### 1. Environment Variables

Add the following to your `.env` file:

```env
# Paystack Configuration
PAYSTACK_SECRET_KEY=sk_test_your_secret_key_here
PAYSTACK_API_KEY=sk_test_your_secret_key_here  # Same as above

# Database (already configured)
DATABASE_URL=your_database_url
SUPABASE_URL=your_supabase_url
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

This will install `httpx` which is used for HTTP requests.

### 3. Create Database Function

Run the SQL function in your Supabase SQL Editor:

```bash
# The SQL file is located at:
sql/increment_agent_balances.sql
```

This function safely increments agent balances and prevents race conditions.

### 4. Start Your Server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 5. Configure Paystack Webhook

1. Go to [Paystack Dashboard](https://dashboard.paystack.com)
2. Navigate to **Settings → Webhooks**
3. Add your webhook URL:
   ```
   https://your-domain.com/api/webhooks/paystack
   ```
4. For local testing, use ngrok:
   ```bash
   ngrok http 8000
   # Use the ngrok URL: https://your-ngrok-url.ngrok.io/api/webhooks/paystack
   ```

## Webhook Endpoints

### POST `/api/webhooks/paystack`
Main webhook endpoint that receives all Paystack events.

**Events Handled:**
- `charge.success` - Payment completed successfully
- `charge.failed` - Payment failed
- `subscription.create` - New subscription created
- `subscription.not_renew` - Subscription cancelled
- `subscription.disable` - Subscription disabled
- `invoice.create` - Invoice created
- `invoice.update` - Invoice updated (handles renewals)
- `invoice.payment_failed` - Invoice payment failed

### GET `/api/webhooks/paystack/health`
Health check endpoint to verify webhook is running.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-10-04T12:00:00",
  "webhook_events": ["charge.success", "charge.failed", ...],
  "version": "2.0.0"
}
```

## How It Works

### 1. Subscription Payment Flow

```
User pays for subscription
    ↓
Paystack sends webhook to /api/webhooks/paystack
    ↓
Signature verification (security)
    ↓
Check if user has referral code in metadata
    ↓
Create/renew subscription in database
    ↓
Process regular agent commission (if user registered by agent)
    ↓
Process referral commission (if referral code present)
    ↓
Create activity logs for agents
    ↓
Return success response
```

### 2. Agent Commission System

**Regular Commission (10%)**
- Paid when a user registered by an agent makes a purchase
- Stored in `CommissionTransaction` table
- Updates agent's `total_earnings` and `available_balance`

**Referral Commission (10%)**
- Paid when a NEW user uses a referral code
- Only for standalone referrals (not double commission)
- Tracked in `ReferralConversions` table
- Prevents duplicate commissions

### 3. Metadata Structure

When initializing payments, include this metadata:

```python
metadata = {
    "userId": "user_uuid",
    "subscriptionId": "plan_uuid",  # For subscriptions
    "productId": "product_uuid",     # For products
    "transactionType": "subscription",  # or "product" or "one-time"
    "referralCode": "AGENT123"       # Optional: for referral tracking
}
```

## Testing

### Test Webhook Locally with ngrok

1. Start your server:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

2. Start ngrok:
   ```bash
   ngrok http 8000
   ```

3. Update Paystack webhook URL with ngrok URL

4. Make a test payment using Paystack test cards

### Test Webhook with curl

```bash
# Test signature verification
curl -X POST http://localhost:8000/api/webhooks/paystack \
  -H "Content-Type: application/json" \
  -H "x-paystack-signature: your_signature_here" \
  -d '{
    "event": "charge.success",
    "data": {
      "id": 123456,
      "domain": "test",
      "status": "success",
      "reference": "test_ref_123",
      "amount": 10000,
      "gateway_response": "Successful",
      "paid_at": "2025-10-04T12:00:00Z",
      "created_at": "2025-10-04T12:00:00Z",
      "channel": "card",
      "currency": "GHS",
      "metadata": {
        "userId": "user_uuid_here",
        "subscriptionId": "plan_uuid_here",
        "transactionType": "subscription",
        "referralCode": "AGENT123"
      }
    }
  }'
```

### Health Check

```bash
curl http://localhost:8000/api/webhooks/paystack/health
```

## Database Tables Used

1. **CommissionTransaction** - Stores all commission records
2. **Agent** - Agent profiles with balances
3. **AgentRegisteredSeller** - Links agents to their registered sellers
4. **AgentActivity** - Activity logs for agents
5. **agent_referral_links** - Referral codes for agents
6. **referral_conversions** - Tracks referral conversions
7. **UserSubscriptions** - User subscription records
8. **ProductPurchase** - Product purchase records

## Important Notes

### Security
- ✅ Webhook signature verification is MANDATORY
- ✅ All signatures are verified using HMAC SHA512
- ✅ Invalid signatures are rejected with 401 error

### Duplicate Prevention
- ✅ Checks for duplicate subscriptions (5-minute window)
- ✅ Checks for duplicate commission transactions
- ✅ Checks for duplicate referral conversions

### Commission Rules
1. **Regular commission** is paid when registered sellers make purchases
2. **Referral commission** is paid ONLY for standalone referrals
3. **No double commission** - if user is registered by agent, no referral commission
4. **Minimum commission** - 100 kobo (1 GHS)

### Amount Handling
- Paystack sends amounts in **kobo** (smallest unit)
- Database stores amounts in **cedis** (GHS)
- Conversion: `amount_in_cedis = amount_in_kobo / 100`

## Troubleshooting

### Webhook not receiving events
1. Check Paystack dashboard webhook logs
2. Verify webhook URL is correct and accessible
3. Check server logs for errors
4. Ensure server is running and port is open

### Signature verification fails
1. Verify `PAYSTACK_SECRET_KEY` in `.env`
2. Check that raw body is being used (not parsed JSON)
3. Ensure webhook URL uses HTTPS in production

### Commission not processing
1. Check user exists in database
2. Verify agent relationship exists
3. Check for duplicate transactions in logs
4. Ensure minimum amount requirement is met (1 GHS)

### Referral commission not working
1. Verify referral code is valid and active
2. Check that user is not already registered by agent
3. Ensure metadata contains `referralCode` field
4. Check for duplicate conversions

## Logs

The webhook provides detailed logging:

```
🔄 Webhook received at: 2025-10-04T12:00:00
✅ Signature verified
📨 Processing event: charge.success
👤 User: user@example.com (user_uuid)
🏷️ Transaction type: subscription
💰 Payment amount: 10000 kobo (GHS 100.00)
🔍 Processing commission for user: user_uuid
💵 Commission amount: 1000 kobo (GHS 10.00)
✅ Commission processed successfully!
⚡ Webhook acknowledged in 250ms
```

## Support

For issues or questions:
1. Check server logs for detailed error messages
2. Verify database connections
3. Test with Paystack test cards
4. Check Paystack dashboard webhook logs

## Version

Current version: **2.0.0**

Last updated: October 4, 2025
