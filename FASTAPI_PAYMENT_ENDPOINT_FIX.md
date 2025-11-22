# FastAPI Payment Endpoint Fix - 404 Error Resolution

## Problem
Your React Native app is getting a **404 Not Found** error when calling:
```
POST /api/deliveries/delivery/initialize-payment
```

Error details:
```
INFO:app.middleware.mobile_auth:Response: 404 - 0.0006s
ERROR Payment initialization error: [AxiosError: Request failed with status code 404]
ERROR Error response: {"detail": "Not Found"}
```

## Root Cause
The endpoint `/api/deliveries/delivery/initialize-payment` **does not exist** in your FastAPI backend.

---

## Solution: Add Missing Payment Endpoints

### Step 1: Add Required Models

Add these models to your `app/models/delivery.py` or create them if they don't exist:

```python
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from enum import Enum

class DeliveryPriority(str, Enum):
    STANDARD = "STANDARD"
    EXPRESS = "EXPRESS"
    URGENT = "URGENT"

class AddressRequest(BaseModel):
    address: str
    city: str
    country: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    additional_info: Optional[str] = ""

class ScheduleDeliveryRequest(BaseModel):
    pickup_address: AddressRequest
    delivery_address: AddressRequest
    pickup_contact_name: str
    pickup_contact_phone: str
    delivery_contact_name: str
    delivery_contact_phone: str
    priority: DeliveryPriority = DeliveryPriority.STANDARD
    scheduled_date: Optional[datetime] = None
    notes: Optional[str] = ""
    item_description: Optional[str] = ""

class CalculateDeliveryFeeRequest(BaseModel):
    priority: DeliveryPriority = DeliveryPriority.STANDARD
    distance_km: Optional[float] = None
```

### Step 2: Add Helper Functions

Add these fee calculation functions to your delivery route file (`app/routes/delivery.py`):

```python
from decimal import Decimal

def calculate_delivery_fee(distance_km: Optional[float], priority: str) -> Decimal:
    """Calculate delivery fee based on distance and priority"""
    # Base fee calculation
    base_fee = Decimal("10.00")  # GHS 10 base fee

    if distance_km:
        distance_fee = Decimal(str(distance_km)) * Decimal("2.00")  # GHS 2 per km
        base_fee += distance_fee

    # Priority multipliers
    if priority == "EXPRESS":
        base_fee *= Decimal("1.5")
    elif priority == "URGENT":
        base_fee *= Decimal("2.0")

    return base_fee.quantize(Decimal("0.01"))

def calculate_courier_and_platform_fees(total_fee: Decimal) -> tuple[Decimal, Decimal]:
    """Split fee between courier and platform"""
    # Platform takes 20%, courier gets 80%
    platform_fee = (total_fee * Decimal("0.20")).quantize(Decimal("0.01"))
    courier_fee = (total_fee - platform_fee).quantize(Decimal("0.01"))

    return courier_fee, platform_fee
```

### Step 3: Add Required Imports

At the top of your `app/routes/delivery.py`, ensure you have:

```python
import os
import uuid
import httpx
from datetime import datetime, timezone
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Your existing imports...
```

### Step 4: Add the Payment Initialization Endpoint

Add this endpoint to `app/routes/delivery.py`:

```python
@router.post("/delivery/initialize-payment")
async def initialize_delivery_payment(
    request: ScheduleDeliveryRequest,
    current_user=Depends(get_current_user)
):
    """Initialize Paystack payment for delivery"""
    try:
        user_id = current_user["user_id"]
        user_email = current_user.get("email")

        logger.info(f"🔄 Initializing delivery payment for user {user_id}")

        # Calculate delivery fee
        distance_km = None  # You can calculate this using addresses if needed
        delivery_fee = calculate_delivery_fee(distance_km, request.priority.value)
        courier_fee, platform_fee = calculate_courier_and_platform_fees(delivery_fee)

        logger.info(f"💰 Calculated fee: {delivery_fee} GHS (Courier: {courier_fee}, Platform: {platform_fee})")

        # Convert to kobo/pesewas (multiply by 100 for Paystack)
        amount_in_kobo = int(float(delivery_fee) * 100)

        # Store delivery data temporarily (needed after payment verification)
        temp_delivery_id = str(uuid.uuid4())

        metadata = {
            "userId": user_id,
            "transactionType": "delivery",
            "tempDeliveryId": temp_delivery_id,
            "deliveryData": {
                "pickup_address": request.pickup_address.dict(),
                "delivery_address": request.delivery_address.dict(),
                "pickup_contact_name": request.pickup_contact_name,
                "pickup_contact_phone": request.pickup_contact_phone,
                "delivery_contact_name": request.delivery_contact_name,
                "delivery_contact_phone": request.delivery_contact_phone,
                "priority": request.priority.value,
                "scheduled_date": request.scheduled_date.isoformat() if request.scheduled_date else None,
                "notes": request.notes,
                "item_description": request.item_description,
            },
            "deliveryFee": float(delivery_fee),
            "courierFee": float(courier_fee),
            "platformFee": float(platform_fee),
        }

        # Initialize Paystack payment
        callback_url = f"{os.getenv('NEXT_PUBLIC_BASE_URL')}/api/payment-callback"

        paystack_data = {
            "email": user_email,
            "amount": amount_in_kobo,
            "callback_url": callback_url,
            "channels": ["card", "bank", "ussd", "qr", "mobile_money", "bank_transfer"],
            "metadata": metadata
        }

        logger.info(f"📤 Calling Paystack API with amount {amount_in_kobo} kobo")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{os.getenv('PAYSTACK_BASE_URL')}/transaction/initialize",
                json=paystack_data,
                headers={
                    "Authorization": f"Bearer {os.getenv('PAYSTACK_SECRET_KEY')}",
                    "Content-Type": "application/json"
                },
                timeout=30.0
            )

        if response.status_code != 200:
            logger.error(f"❌ Paystack initialization failed: {response.text}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to initialize payment with Paystack"
            )

        paystack_response = response.json()

        if not paystack_response.get("status"):
            logger.error(f"❌ Paystack returned error: {paystack_response}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Payment initialization failed"
            )

        data = paystack_response["data"]

        logger.info(f"✅ Payment initialized successfully. Reference: {data['reference']}")

        return {
            "authorization_url": data["authorization_url"],
            "access_code": data["access_code"],
            "reference": data["reference"],
            "delivery_fee": float(delivery_fee)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error initializing delivery payment: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initialize payment: {str(e)}"
        )
```

### Step 5: Add the Payment Verification Endpoint

Add this endpoint right after the initialization endpoint:

```python
@router.post("/delivery/verify-and-schedule")
async def verify_payment_and_schedule_delivery(
    reference: str = Query(...),
    current_user=Depends(get_current_user)
):
    """Verify payment and create delivery after successful payment"""
    try:
        user_id = current_user["user_id"]

        logger.info(f"🔍 Verifying payment for reference: {reference}")

        # Verify payment with Paystack
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{os.getenv('PAYSTACK_BASE_URL')}/transaction/verify/{reference}",
                headers={
                    "Authorization": f"Bearer {os.getenv('PAYSTACK_SECRET_KEY')}"
                },
                timeout=30.0
            )

        if response.status_code != 200:
            logger.error(f"❌ Paystack verification failed: {response.text}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Payment verification failed"
            )

        paystack_response = response.json()

        if not paystack_response.get("status"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Payment verification failed"
            )

        data = paystack_response["data"]

        if data["status"] != "success":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Payment was not successful"
            )

        # Get delivery data from metadata
        metadata = data.get("metadata", {})
        delivery_data = metadata.get("deliveryData", {})

        if metadata.get("userId") != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Unauthorized: User mismatch"
            )

        # Create the delivery
        order_id = str(uuid.uuid4())
        delivery_fee = Decimal(str(metadata["deliveryFee"]))
        courier_fee = Decimal(str(metadata["courierFee"]))
        platform_fee = Decimal(str(metadata["platformFee"]))

        logger.info(f"💾 Creating order for delivery with fee {delivery_fee}")

        # Create order with PAID status
        order_data = {
            "id": order_id,
            "userId": user_id,
            "subtotal": 0,
            "discountAmount": 0,
            "tax": 0,
            "deliveryFee": float(delivery_fee),
            "total": float(delivery_fee),
            "status": "PENDING",
            "paymentStatus": "PAID",  # ✅ Mark as PAID
            "currency": "GHS",
            "shippingAddress": delivery_data["delivery_address"],
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "updatedAt": datetime.now(timezone.utc).isoformat(),
        }

        # Replace 'supabase' with your actual database client
        order_response = supabase.table("Order").insert(order_data).execute()

        if not order_response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create order"
            )

        # Create delivery record
        delivery_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        delivery_record = {
            "id": delivery_id,
            "order_id": order_id,
            "pickup_address": delivery_data["pickup_address"],
            "delivery_address": delivery_data["delivery_address"],
            "pickup_contact_name": delivery_data["pickup_contact_name"],
            "pickup_contact_phone": delivery_data["pickup_contact_phone"],
            "delivery_contact_name": delivery_data["delivery_contact_name"],
            "delivery_contact_phone": delivery_data["delivery_contact_phone"],
            "scheduled_by_user": user_id,
            "scheduled_by_type": current_user.get("user_type", "CUSTOMER"),
            "delivery_fee": float(delivery_fee),
            "courier_fee": float(courier_fee),
            "platform_fee": float(platform_fee),
            "distance_km": None,
            "status": "PENDING",
            "priority": delivery_data["priority"],
            "scheduled_date": delivery_data.get("scheduled_date"),
            "notes": delivery_data.get("notes"),
            "item_description": delivery_data.get("item_description"),
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }

        delivery_response = supabase.table("Delivery").insert(delivery_record).execute()

        if not delivery_response.data:
            # Rollback order if delivery creation fails
            supabase.table("Order").delete().eq("id", order_id).execute()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create delivery"
            )

        delivery = delivery_response.data[0]

        logger.info(f"✅ Paid delivery {delivery_id} created successfully for user {user_id}")

        return {
            "delivery": delivery,
            "payment": {
                "reference": reference,
                "amount": data["amount"] / 100,  # Convert back from kobo
                "status": data["status"]
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error verifying payment and scheduling: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process delivery: {str(e)}"
        )
```

### Step 6: (Optional) Add Fee Calculator Endpoint

```python
@router.post("/delivery/calculate-fee")
async def calculate_delivery_fee_endpoint(
    request: CalculateDeliveryFeeRequest,
    current_user=Depends(get_current_user)
):
    """Calculate delivery fee before payment"""
    try:
        distance_km = request.distance_km

        fee = calculate_delivery_fee(distance_km, request.priority.value)
        courier_fee, platform_fee = calculate_courier_and_platform_fees(fee)

        return {
            "delivery_fee": float(fee),
            "courier_fee": float(courier_fee),
            "platform_fee": float(platform_fee),
            "distance_km": distance_km,
            "priority": request.priority
        }
    except Exception as e:
        logger.error(f"Error calculating delivery fee: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to calculate delivery fee"
        )
```

---

## Environment Variables Required

Add these to your `.env` file:

```env
PAYSTACK_SECRET_KEY=sk_test_your_secret_key_here
PAYSTACK_BASE_URL=https://api.paystack.co
NEXT_PUBLIC_BASE_URL=https://your-backend-url.com
```

---

## Testing the Fix

### 1. Restart Your FastAPI Server

```bash
# Stop the current server (Ctrl+C)
# Then restart it
uvicorn app.main:app --reload
```

### 2. Test with cURL

```bash
# Get your auth token first
TOKEN="your_jwt_token_here"

# Test initialization endpoint
curl -X POST "http://your-backend-url/api/deliveries/delivery/initialize-payment" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "pickup_address": {
      "address": "123 Main St",
      "city": "Accra",
      "country": "Ghana",
      "latitude": 5.6037,
      "longitude": -0.1870
    },
    "delivery_address": {
      "address": "456 Oak Ave",
      "city": "Tema",
      "country": "Ghana",
      "latitude": 5.6698,
      "longitude": 0.0171
    },
    "pickup_contact_name": "John Doe",
    "pickup_contact_phone": "0201234567",
    "delivery_contact_name": "Jane Smith",
    "delivery_contact_phone": "0207654321",
    "priority": "STANDARD",
    "item_description": "Package"
  }'
```

Expected response:
```json
{
  "authorization_url": "https://checkout.paystack.com/...",
  "access_code": "...",
  "reference": "...",
  "delivery_fee": 10.00
}
```

### 3. Test from React Native App

After restarting your backend, try scheduling a delivery from the app. You should see:

```
LOG  Initializing payment with delivery data: {...}
LOG  Payment response: {
  "authorization_url": "https://checkout.paystack.com/...",
  "reference": "...",
  "delivery_fee": 10.00
}
```

---

## Troubleshooting

### Still Getting 404?

1. **Check router registration**: Ensure your delivery router is registered in `app/main.py`:
   ```python
   from app.routes import delivery

   app.include_router(delivery.router, prefix="/api/deliveries", tags=["deliveries"])
   ```

2. **Check route path**: The full path should be `/api/deliveries/delivery/initialize-payment`

3. **Verify server restart**: Make sure you restarted the FastAPI server after adding the endpoints

### Getting 500 Internal Server Error?

1. **Check Paystack credentials**: Verify `PAYSTACK_SECRET_KEY` in `.env`
2. **Check logs**: Look at your FastAPI logs for the actual error
3. **Missing dependencies**: Install httpx if not installed:
   ```bash
   pip install httpx
   ```

### Payment initialization works but verification fails?

1. **Check reference**: Make sure the reference from initialization is passed to verification
2. **Check Paystack dashboard**: Verify the transaction exists
3. **Check metadata**: Ensure delivery data is stored in Paystack metadata

---

## What Changed

Before:
- ❌ No payment endpoint
- ❌ Frontend gets 404 error
- ❌ Cannot schedule deliveries

After:
- ✅ Payment initialization endpoint created
- ✅ Payment verification endpoint created
- ✅ Full payment flow working
- ✅ Deliveries created with PAID status

---

## Next Steps

1. **Add the endpoints** to your FastAPI backend
2. **Restart the server**
3. **Test from the app**
4. **Monitor the logs** for any errors
5. **Test the full flow**: Initialize → Pay → Verify → Delivery created
