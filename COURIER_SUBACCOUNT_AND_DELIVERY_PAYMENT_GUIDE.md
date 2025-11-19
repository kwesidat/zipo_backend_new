# Courier Subaccount & Scheduled Delivery Payment Implementation Guide

This guide covers two key features for your React Native app:
1. **Couriers creating Paystack subaccounts and viewing their status**
2. **Users initializing, paying for, and verifying courier scheduled deliveries with 70/30 split**

---

## Table of Contents
- [Overview](#overview)
- [Backend Requirements](#backend-requirements)
- [Feature 1: Courier Subaccount Management](#feature-1-courier-subaccount-management)
- [Feature 2: Scheduled Delivery Payment Flow](#feature-2-scheduled-delivery-payment-flow)
- [React Native Implementation](#react-native-implementation)
- [Database Schema](#database-schema)
- [Testing Checklist](#testing-checklist)

---

## Overview

### Architecture
```
User schedules delivery → Payment initialized →
User pays via Paystack → Payment verified →
70% to courier subaccount + 30% to platform
```

### Key Endpoints
- **Courier Subaccounts**: `/api/payments/*` (existing)
- **Scheduled Deliveries**: `/api/deliveries/schedule` (existing)
- **Payment Flow**: New endpoints needed

---

## Backend Requirements

### 1. Update Backend Models

#### Add to `app/models/payments.py`:
```python
class ScheduledDeliveryPaymentRequest(BaseModel):
    delivery_id: str = Field(..., description="Delivery ID to pay for")
    payment_gateway: PaymentGateway = PaymentGateway.PAYSTACK

class ScheduledDeliveryPaymentInitResponse(BaseModel):
    authorization_url: str
    access_code: str
    reference: str
    delivery_id: str
    delivery_fee: Decimal
    courier_fee: Decimal
    platform_fee: Decimal

class ScheduledDeliveryPaymentVerificationResponse(BaseModel):
    status: str
    reference: str
    amount: float
    currency: str
    paid_at: Optional[str]
    delivery: Optional[DeliveryResponse]
    message: str
```

### 2. Create Payment Routes for Scheduled Deliveries

Add to `app/routes/delivery.py`:

```python
# ========== INITIALIZE PAYMENT FOR SCHEDULED DELIVERY ==========

@router.post("/payment/initialize", response_model=ScheduledDeliveryPaymentInitResponse)
async def initialize_delivery_payment(
    request: ScheduledDeliveryPaymentRequest,
    current_user = Depends(get_current_user)
):
    """
    Initialize payment for a scheduled delivery.
    User must pay before courier accepts the delivery.
    """
    try:
        user_id = current_user["user_id"]
        user_email = current_user.get("email")

        logger.info(f"=== DELIVERY PAYMENT INITIALIZATION ===")
        logger.info(f"User ID: {user_id}")
        logger.info(f"Delivery ID: {request.delivery_id}")

        if not user_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User email is required"
            )

        # Get delivery
        delivery_response = supabase.table("Delivery").select("*").eq(
            "id", request.delivery_id
        ).eq("scheduled_by_user", user_id).execute()

        if not delivery_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Delivery not found or you don't have permission"
            )

        delivery = delivery_response.data[0]

        # Check if delivery is already paid
        if delivery.get("payment_status") == "COMPLETED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Delivery has already been paid for"
            )

        # Check if delivery is still pending (not yet assigned)
        if delivery["status"] != "PENDING":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot pay for delivery with status: {delivery['status']}"
            )

        delivery_fee = Decimal(str(delivery["delivery_fee"]))
        courier_fee = Decimal(str(delivery["courier_fee"]))
        platform_fee = Decimal(str(delivery["platform_fee"]))

        # Convert to kobo (smallest unit)
        amount_in_kobo = int(delivery_fee * 100)

        logger.info(f"Delivery Fee: GHS {delivery_fee} ({amount_in_kobo} kobo)")
        logger.info(f"Courier Fee (70%): GHS {courier_fee}")
        logger.info(f"Platform Fee (30%): GHS {platform_fee}")

        # Create metadata for payment
        metadata = {
            "userId": user_id,
            "deliveryId": request.delivery_id,
            "transactionType": "scheduled_delivery",
            "email": user_email,
            "courierFee": float(courier_fee),
            "platformFee": float(platform_fee),
        }

        # Callback URL
        callback_url = f"{NEXT_PUBLIC_BASE_URL}/api/payment-callback"

        # Initialize payment with Paystack (NO subaccount yet - courier not assigned)
        paystack_data = {
            "email": user_email,
            "amount": amount_in_kobo,
            "callback_url": callback_url,
            "channels": ["card", "bank", "ussd", "qr", "mobile_money", "bank_transfer"],
            "metadata": metadata,
            "reference": f"DEL-{request.delivery_id[:8]}-{uuid.uuid4().hex[:8]}"
        }

        logger.info("Calling Paystack API...")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{PAYSTACK_BASE_URL}/transaction/initialize",
                json=paystack_data,
                headers={
                    "Authorization": f"Bearer {PAYSTACK_SECRET_KEY}",
                    "Content-Type": "application/json"
                },
                timeout=30.0
            )

        if response.status_code != 200:
            logger.error(f"Paystack initialization failed: {response.text}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to initialize payment"
            )

        paystack_response = response.json()

        if not paystack_response.get("status"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=paystack_response.get("message", "Payment initialization failed")
            )

        data = paystack_response["data"]

        # Update delivery with payment reference
        supabase.table("Delivery").update({
            "payment_reference": data["reference"],
            "payment_status": "PENDING",
            "updated_at": datetime.now(timezone.utc).isoformat()
        }).eq("id", request.delivery_id).execute()

        logger.info(f"✅ Payment initialized successfully!")
        logger.info(f"Reference: {data['reference']}")

        return ScheduledDeliveryPaymentInitResponse(
            authorization_url=data["authorization_url"],
            access_code=data["access_code"],
            reference=data["reference"],
            delivery_id=request.delivery_id,
            delivery_fee=delivery_fee,
            courier_fee=courier_fee,
            platform_fee=platform_fee
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"💥 Error initializing delivery payment: {str(e)}")
        logger.exception(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initialize payment"
        )


# ========== VERIFY PAYMENT FOR SCHEDULED DELIVERY ==========

@router.post("/payment/verify")
async def verify_delivery_payment(
    reference: str = Query(..., description="Payment reference from Paystack"),
    current_user = Depends(get_current_user)
):
    """
    Verify payment for scheduled delivery after user completes Paystack checkout.
    Updates delivery payment status and makes it available for couriers.
    Note: Split to courier subaccount happens when courier is assigned and completes delivery.
    """
    try:
        user_id = current_user["user_id"]

        logger.info(f"=== DELIVERY PAYMENT VERIFICATION ===")
        logger.info(f"User ID: {user_id}")
        logger.info(f"Reference: {reference}")

        # Verify with Paystack
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{PAYSTACK_BASE_URL}/transaction/verify/{reference}",
                headers={
                    "Authorization": f"Bearer {PAYSTACK_SECRET_KEY}"
                },
                timeout=30.0
            )

        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to verify payment"
            )

        paystack_response = response.json()

        if not paystack_response.get("status"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Payment verification failed"
            )

        data = paystack_response["data"]

        # Extract metadata
        metadata = data.get("metadata", {})
        delivery_id = metadata.get("deliveryId")
        metadata_user_id = metadata.get("userId")

        if metadata_user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Unauthorized: This payment does not belong to you"
            )

        if not delivery_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid payment: No delivery ID in metadata"
            )

        # Get delivery
        delivery_response = supabase.table("Delivery").select("*").eq(
            "id", delivery_id
        ).eq("scheduled_by_user", user_id).execute()

        if not delivery_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Delivery not found"
            )

        delivery = delivery_response.data[0]

        # Update delivery payment status
        if data["status"] == "success":
            now = datetime.now(timezone.utc)

            update_data = {
                "payment_status": "COMPLETED",
                "payment_reference": reference,
                "paid_at": data.get("paid_at") or now.isoformat(),
                "updated_at": now.isoformat()
            }

            supabase.table("Delivery").update(update_data).eq("id", delivery_id).execute()

            # Update order payment status
            supabase.table("Order").update({
                "paymentStatus": "COMPLETED",
                "paymentReference": reference,
                "updatedAt": now.isoformat()
            }).eq("id", delivery["order_id"]).execute()

            logger.info(f"✅ Delivery {delivery_id} payment completed")

            # Create success notification
            notification_data = {
                "userId": user_id,
                "title": "Delivery Payment Successful",
                "notificationType": "SUCCESS",
                "body": f"Your payment of GHS {data['amount'] / 100:.2f} for delivery has been confirmed. Couriers can now accept your delivery request.",
                "dismissed": False,
                "createdAt": now.isoformat(),
                "expiresAt": (now + timedelta(days=7)).isoformat()
            }

            supabase.table("Notification").insert(notification_data).execute()

            message = "Payment successful! Your delivery is now available for couriers to accept."
        else:
            message = "Payment is pending or incomplete"

        # Return updated delivery info
        delivery_response = supabase.table("Delivery").select("*").eq("id", delivery_id).execute()

        return {
            "status": data["status"],
            "reference": reference,
            "amount": data["amount"] / 100,
            "currency": data["currency"],
            "paid_at": data.get("paid_at"),
            "delivery": delivery_response.data[0] if delivery_response.data else None,
            "message": message
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"💥 Error verifying delivery payment: {str(e)}")
        logger.exception(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to verify payment"
        )
```

### 3. Update Delivery Acceptance to Handle Payment Split

Modify the `accept_delivery` endpoint in `app/routes/delivery.py`:

```python
@router.post("/accept", response_model=DeliveryResponse)
async def accept_delivery(
    request: AcceptDeliveryRequest, current_user=Depends(get_current_user)
):
    """
    Courier accepts a PAID delivery request.
    When courier completes delivery, payment is split 70/30.
    """
    try:
        # ... existing code to get courier and delivery ...

        # ✅ NEW: Check if delivery is paid before allowing acceptance
        if delivery.get("payment_status") != "COMPLETED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot accept unpaid delivery. Customer must complete payment first."
            )

        # ✅ NEW: Get courier's Paystack subaccount
        courier_subaccount_response = supabase.table("CourierSubaccount").select("*").eq(
            "courier_id", courier_id
        ).execute()

        if not courier_subaccount_response.data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You must create a Paystack subaccount before accepting deliveries. Go to Settings > Payment Details."
            )

        courier_subaccount = courier_subaccount_response.data[0]
        subaccount_code = courier_subaccount.get("subaccount_code")

        if not subaccount_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Your subaccount is not properly configured. Please contact support."
            )

        # ... rest of existing acceptance logic ...

        # ✅ NEW: Store subaccount code for payment split on delivery completion
        update_data["courier_subaccount_code"] = subaccount_code

        # ... existing code ...
```

### 4. Update Delivery Completion to Split Payment

Modify the `update_delivery_status` endpoint when status is `DELIVERED`:

```python
# In update_delivery_status endpoint, after status is set to DELIVERED:

if request.status == DeliveryStatus.DELIVERED:
    # ... existing code ...

    # ✅ NEW: Create courier earning with split payment
    courier_fee = Decimal(str(delivery.get("courier_fee", 0)))
    platform_fee = Decimal(str(delivery.get("platform_fee", 0)))

    if courier_fee > 0:
        # Create earning record for courier
        earning_data = {
            "id": str(uuid.uuid4()),
            "courier_id": courier_id,
            "delivery_id": delivery_id,
            "amount": float(courier_fee),
            "type": "DELIVERY",
            "description": f"Delivery completed - 70% of GHS {delivery['delivery_fee']}",
            "status": "COMPLETED",  # Mark as completed since payment already received
            "payment_reference": delivery.get("payment_reference"),
            "subaccount_code": delivery.get("courier_subaccount_code"),
            "created_at": now.isoformat(),
            "completed_at": now.isoformat()
        }
        supabase.table("CourierEarning").insert(earning_data).execute()

        # Update courier balance
        updated_balance = courier.get("available_balance", 0) + float(courier_fee)
        updated_earnings = courier.get("total_earnings", 0) + float(courier_fee)

        supabase.table("Courier").update({
            "available_balance": updated_balance,
            "total_earnings": updated_earnings,
            "completed_deliveries": courier.get("completed_deliveries", 0) + 1,
            "updated_at": now.isoformat()
        }).eq("id", courier_id).execute()

        logger.info(f"✅ Courier earned GHS {courier_fee} (70% of delivery fee)")

        # Create notification for courier
        courier_notification = {
            "userId": courier.get("user_id"),
            "title": "Delivery Completed - Payment Received",
            "notificationType": "SUCCESS",
            "body": f"You earned GHS {courier_fee} from completing this delivery. 70% of the delivery fee has been added to your balance.",
            "dismissed": False,
            "createdAt": now.isoformat(),
            "expiresAt": (now + timedelta(days=7)).isoformat()
        }
        supabase.table("Notification").insert(courier_notification).execute()
```

### 5. Add Courier Subaccount Endpoints

Create `app/routes/courier_payments.py`:

```python
from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.database import supabase
from app.utils.auth_utils import AuthUtils
from pydantic import BaseModel
import httpx
import os
import logging
from datetime import datetime
import re

logger = logging.getLogger(__name__)
router = APIRouter()
security = HTTPBearer()

PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY")
PAYSTACK_BASE_URL = "https://api.paystack.co"


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get current authenticated courier user"""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )

    try:
        user_data = AuthUtils.verify_supabase_token(credentials.credentials)
        if not user_data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token"
            )
        return user_data
    except Exception as e:
        logger.error(f"Authentication failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed"
        )


class CourierSubaccountRequest(BaseModel):
    business_name: str
    bank_code: str
    account_number: str
    primary_contact_name: str
    primary_contact_phone: str


class CourierSubaccountStatusResponse(BaseModel):
    has_subaccount: bool
    subaccount: dict = None


@router.post("/subaccount/create")
async def create_courier_subaccount(
    request: CourierSubaccountRequest,
    current_user = Depends(get_current_user)
):
    """
    Create a Paystack subaccount for a courier to receive delivery payments.
    Couriers get 70% of delivery fees, platform keeps 30%.
    """
    try:
        user_id = current_user["user_id"]
        user_type = current_user.get("user_type")
        user_email = current_user.get("email")

        # Verify user is a courier
        if user_type != "COURIER":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only couriers can create subaccounts"
            )

        logger.info(f"=== COURIER SUBACCOUNT CREATION ===")
        logger.info(f"User ID: {user_id}")
        logger.info(f"Business Name: {request.business_name}")

        # Get courier profile
        courier_response = supabase.table("Courier").select("*").eq(
            "user_id", user_id
        ).execute()

        if not courier_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Courier profile not found"
            )

        courier = courier_response.data[0]
        courier_id = courier["id"]

        # Check if courier already has subaccount
        existing_subaccount = supabase.table("CourierSubaccount").select("*").eq(
            "courier_id", courier_id
        ).execute()

        if existing_subaccount.data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You already have a subaccount"
            )

        # Validate phone number
        clean_phone = re.sub(r'[^\d]', '', request.primary_contact_phone)
        if not clean_phone or len(clean_phone) < 9:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid phone number format"
            )

        # Handle mobile money vs bank account
        MOBILE_MONEY_PROVIDERS = {'MTN', 'ATL', 'VOD'}
        is_mobile_money = request.bank_code.upper() in MOBILE_MONEY_PROVIDERS

        account_number = request.account_number
        if is_mobile_money:
            clean_account = re.sub(r'[^\d]', '', account_number)
            if clean_account.startswith('233') and len(clean_account) == 12:
                clean_account = '0' + clean_account[3:]
            elif clean_account.startswith('0') and len(clean_account) == 10:
                pass
            elif len(clean_account) == 9:
                clean_account = '0' + clean_account
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Mobile money account must be a valid Ghanaian phone number"
                )
            account_number = clean_account

        # Create subaccount with Paystack (30% platform fee)
        subaccount_data = {
            "business_name": request.business_name,
            "bank_code": request.bank_code,
            "account_number": account_number,
            "percentage_charge": 30,  # Platform keeps 30%, courier gets 70%
            "primary_contact_email": user_email,
            "primary_contact_name": request.primary_contact_name,
            "primary_contact_phone": request.primary_contact_phone
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{PAYSTACK_BASE_URL}/subaccount",
                json=subaccount_data,
                headers={
                    "Authorization": f"Bearer {PAYSTACK_SECRET_KEY}",
                    "Content-Type": "application/json"
                },
                timeout=30.0
            )

        if response.status_code not in [200, 201]:
            error_data = response.json()
            logger.error(f"Paystack error: {response.text}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_data.get("message", "Failed to create subaccount")
            )

        paystack_response = response.json()

        if not paystack_response.get("status"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=paystack_response.get("message", "Subaccount creation failed")
            )

        subaccount_code = paystack_response["data"]["subaccount_code"]

        # Save to database
        db_subaccount = supabase.table("CourierSubaccount").insert({
            "courier_id": courier_id,
            "subaccount_code": subaccount_code,
            "business_name": request.business_name,
            "bank_code": request.bank_code,
            "account_number": account_number,  # Store masked version
            "is_active": True,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }).execute()

        if not db_subaccount.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to save subaccount"
            )

        logger.info(f"✅ Courier subaccount created: {subaccount_code}")

        return {
            "message": "Subaccount created successfully",
            "subaccount_code": subaccount_code,
            "business_name": request.business_name
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"💥 Error creating courier subaccount: {str(e)}")
        logger.exception(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create subaccount"
        )


@router.get("/subaccount/status", response_model=CourierSubaccountStatusResponse)
async def get_courier_subaccount_status(current_user = Depends(get_current_user)):
    """
    Check if the authenticated courier has a Paystack subaccount.
    """
    try:
        user_id = current_user["user_id"]
        user_type = current_user.get("user_type")

        if user_type != "COURIER":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only couriers can check subaccount status"
            )

        # Get courier profile
        courier_response = supabase.table("Courier").select("id").eq(
            "user_id", user_id
        ).execute()

        if not courier_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Courier profile not found"
            )

        courier_id = courier_response.data[0]["id"]

        # Check for subaccount
        subaccount_response = supabase.table("CourierSubaccount").select("*").eq(
            "courier_id", courier_id
        ).execute()

        if not subaccount_response.data:
            return CourierSubaccountStatusResponse(
                has_subaccount=False,
                subaccount=None
            )

        subaccount = subaccount_response.data[0]

        return CourierSubaccountStatusResponse(
            has_subaccount=True,
            subaccount={
                "subaccount_code": subaccount["subaccount_code"],
                "business_name": subaccount["business_name"],
                "bank_code": subaccount["bank_code"],
                "is_active": subaccount.get("is_active", True),
                "created_at": subaccount["created_at"]
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"💥 Error checking subaccount status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to check subaccount status"
        )
```

### 6. Register Routes

Add to `app/main.py`:

```python
from app.routes import courier_payments

app.include_router(courier_payments.router, prefix="/api/couriers", tags=["Courier Payments"])
```

---

## Database Schema

### Add New Tables (SQL)

```sql
-- Courier Subaccounts Table
CREATE TABLE "CourierSubaccount" (
    "id" UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    "courier_id" UUID NOT NULL REFERENCES "Courier"("id") ON DELETE CASCADE,
    "subaccount_code" TEXT NOT NULL UNIQUE,
    "business_name" TEXT NOT NULL,
    "bank_code" TEXT NOT NULL,
    "account_number" TEXT NOT NULL,
    "is_active" BOOLEAN DEFAULT TRUE,
    "created_at" TIMESTAMPTZ DEFAULT NOW(),
    "updated_at" TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_courier_subaccount_courier ON "CourierSubaccount"("courier_id");

-- Add payment fields to Delivery table
ALTER TABLE "Delivery"
ADD COLUMN IF NOT EXISTS "payment_status" TEXT DEFAULT 'PENDING',
ADD COLUMN IF NOT EXISTS "payment_reference" TEXT,
ADD COLUMN IF NOT EXISTS "paid_at" TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS "courier_subaccount_code" TEXT;

-- Update CourierEarning table
ALTER TABLE "CourierEarning"
ADD COLUMN IF NOT EXISTS "payment_reference" TEXT,
ADD COLUMN IF NOT EXISTS "subaccount_code" TEXT,
ADD COLUMN IF NOT EXISTS "completed_at" TIMESTAMPTZ;
```

---

## React Native Implementation

### 1. API Service Setup

Create `src/services/courierApi.ts`:

```typescript
import axios from 'axios';
import AsyncStorage from '@react-native-async-storage/async-storage';

const API_BASE_URL = 'https://your-backend-url.com/api';

const api = axios.create({
  baseURL: API_BASE_URL,
});

// Add auth token to requests
api.interceptors.request.use(async (config) => {
  const token = await AsyncStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Courier Subaccount APIs
export const courierSubaccountApi = {
  // Check if courier has subaccount
  getSubaccountStatus: async () => {
    const response = await api.get('/couriers/subaccount/status');
    return response.data;
  },

  // Create courier subaccount
  createSubaccount: async (data: {
    business_name: string;
    bank_code: string;
    account_number: string;
    primary_contact_name: string;
    primary_contact_phone: string;
  }) => {
    const response = await api.post('/couriers/subaccount/create', data);
    return response.data;
  },

  // Get supported banks
  getSupportedBanks: async () => {
    const response = await api.get('/payments/banks/ghana');
    return response.data;
  },
};

// Delivery Payment APIs
export const deliveryPaymentApi = {
  // Initialize payment for scheduled delivery
  initializePayment: async (deliveryId: string) => {
    const response = await api.post('/deliveries/payment/initialize', {
      delivery_id: deliveryId,
      payment_gateway: 'PAYSTACK',
    });
    return response.data;
  },

  // Verify payment
  verifyPayment: async (reference: string) => {
    const response = await api.post(
      `/deliveries/payment/verify?reference=${reference}`
    );
    return response.data;
  },

  // Get delivery details
  getDelivery: async (deliveryId: string) => {
    const response = await api.get(`/deliveries/${deliveryId}`);
    return response.data;
  },
};

export default api;
```

### 2. Courier Subaccount Setup Screen

Create `src/screens/courier/SubaccountSetupScreen.tsx`:

```typescript
import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  ScrollView,
  Alert,
  ActivityIndicator,
} from 'react-native';
import { Picker } from '@react-native-picker/picker';
import { courierSubaccountApi } from '../../services/courierApi';

export default function SubaccountSetupScreen({ navigation }) {
  const [loading, setLoading] = useState(false);
  const [banks, setBanks] = useState([]);
  const [formData, setFormData] = useState({
    business_name: '',
    bank_code: '',
    account_number: '',
    primary_contact_name: '',
    primary_contact_phone: '',
  });

  useEffect(() => {
    fetchBanks();
  }, []);

  const fetchBanks = async () => {
    try {
      const banksData = await courierSubaccountApi.getSupportedBanks();
      setBanks(banksData);
    } catch (error) {
      Alert.alert('Error', 'Failed to load banks');
    }
  };

  const handleSubmit = async () => {
    // Validate inputs
    if (!formData.business_name || !formData.bank_code || !formData.account_number) {
      Alert.alert('Error', 'Please fill in all required fields');
      return;
    }

    setLoading(true);
    try {
      const result = await courierSubaccountApi.createSubaccount(formData);
      Alert.alert(
        'Success',
        'Your payment account has been created! You can now accept deliveries.',
        [{ text: 'OK', onPress: () => navigation.goBack() }]
      );
    } catch (error) {
      Alert.alert(
        'Error',
        error.response?.data?.detail || 'Failed to create subaccount'
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <ScrollView style={{ flex: 1, backgroundColor: '#fff', padding: 16 }}>
      <Text style={{ fontSize: 24, fontWeight: 'bold', marginBottom: 8 }}>
        Setup Payment Account
      </Text>
      <Text style={{ color: '#666', marginBottom: 24 }}>
        Setup your payment details to receive 70% of delivery fees directly to your account.
      </Text>

      <Text style={{ fontWeight: '600', marginBottom: 8 }}>Business Name *</Text>
      <TextInput
        style={{
          borderWidth: 1,
          borderColor: '#ddd',
          borderRadius: 8,
          padding: 12,
          marginBottom: 16,
        }}
        placeholder="Your business name"
        value={formData.business_name}
        onChangeText={(text) => setFormData({ ...formData, business_name: text })}
      />

      <Text style={{ fontWeight: '600', marginBottom: 8 }}>Bank/Mobile Money *</Text>
      <Picker
        selectedValue={formData.bank_code}
        onValueChange={(value) => setFormData({ ...formData, bank_code: value })}
        style={{
          borderWidth: 1,
          borderColor: '#ddd',
          borderRadius: 8,
          marginBottom: 16,
        }}
      >
        <Picker.Item label="Select Bank or Mobile Money" value="" />
        {banks.map((bank) => (
          <Picker.Item key={bank.code} label={bank.name} value={bank.code} />
        ))}
      </Picker>

      <Text style={{ fontWeight: '600', marginBottom: 8 }}>Account Number *</Text>
      <TextInput
        style={{
          borderWidth: 1,
          borderColor: '#ddd',
          borderRadius: 8,
          padding: 12,
          marginBottom: 16,
        }}
        placeholder="Account number or mobile money number"
        value={formData.account_number}
        onChangeText={(text) => setFormData({ ...formData, account_number: text })}
        keyboardType="numeric"
      />

      <Text style={{ fontWeight: '600', marginBottom: 8 }}>Contact Name *</Text>
      <TextInput
        style={{
          borderWidth: 1,
          borderColor: '#ddd',
          borderRadius: 8,
          padding: 12,
          marginBottom: 16,
        }}
        placeholder="Your full name"
        value={formData.primary_contact_name}
        onChangeText={(text) =>
          setFormData({ ...formData, primary_contact_name: text })
        }
      />

      <Text style={{ fontWeight: '600', marginBottom: 8 }}>Contact Phone *</Text>
      <TextInput
        style={{
          borderWidth: 1,
          borderColor: '#ddd',
          borderRadius: 8,
          padding: 12,
          marginBottom: 24,
        }}
        placeholder="0241234567"
        value={formData.primary_contact_phone}
        onChangeText={(text) =>
          setFormData({ ...formData, primary_contact_phone: text })
        }
        keyboardType="phone-pad"
      />

      <TouchableOpacity
        style={{
          backgroundColor: '#007AFF',
          padding: 16,
          borderRadius: 8,
          alignItems: 'center',
        }}
        onPress={handleSubmit}
        disabled={loading}
      >
        {loading ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <Text style={{ color: '#fff', fontWeight: 'bold', fontSize: 16 }}>
            Create Payment Account
          </Text>
        )}
      </TouchableOpacity>

      <View
        style={{
          backgroundColor: '#f0f9ff',
          padding: 12,
          borderRadius: 8,
          marginTop: 16,
        }}
      >
        <Text style={{ fontSize: 12, color: '#0369a1' }}>
          ℹ️ You'll receive 70% of each delivery fee directly to this account when
          you complete deliveries. The platform keeps 30%.
        </Text>
      </View>
    </ScrollView>
  );
}
```

### 3. Subaccount Status Component

Create `src/components/courier/SubaccountStatus.tsx`:

```typescript
import React, { useState, useEffect } from 'react';
import { View, Text, TouchableOpacity, ActivityIndicator } from 'react-native';
import { courierSubaccountApi } from '../../services/courierApi';

export default function SubaccountStatus({ navigation }) {
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState(null);

  useEffect(() => {
    checkStatus();
  }, []);

  const checkStatus = async () => {
    try {
      const data = await courierSubaccountApi.getSubaccountStatus();
      setStatus(data);
    } catch (error) {
      console.error('Error checking subaccount status:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <View style={{ padding: 16, alignItems: 'center' }}>
        <ActivityIndicator />
      </View>
    );
  }

  if (!status?.has_subaccount) {
    return (
      <View
        style={{
          backgroundColor: '#fef3c7',
          padding: 16,
          borderRadius: 8,
          margin: 16,
        }}
      >
        <Text style={{ fontWeight: 'bold', marginBottom: 8 }}>
          ⚠️ Payment Account Required
        </Text>
        <Text style={{ marginBottom: 12 }}>
          Setup your payment account to start accepting deliveries and earning money.
        </Text>
        <TouchableOpacity
          style={{
            backgroundColor: '#ea580c',
            padding: 12,
            borderRadius: 6,
            alignItems: 'center',
          }}
          onPress={() => navigation.navigate('SubaccountSetup')}
        >
          <Text style={{ color: '#fff', fontWeight: 'bold' }}>
            Setup Payment Account
          </Text>
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <View
      style={{
        backgroundColor: '#dcfce7',
        padding: 16,
        borderRadius: 8,
        margin: 16,
      }}
    >
      <Text style={{ fontWeight: 'bold', color: '#166534', marginBottom: 8 }}>
        ✅ Payment Account Active
      </Text>
      <Text style={{ color: '#166534' }}>
        Business: {status.subaccount.business_name}
      </Text>
      <Text style={{ color: '#166534', fontSize: 12, marginTop: 4 }}>
        You're all set to receive delivery payments!
      </Text>
    </View>
  );
}
```

### 4. Schedule Delivery with Payment Screen

Create `src/screens/customer/ScheduleDeliveryScreen.tsx`:

```typescript
import React, { useState } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  ScrollView,
  Alert,
  ActivityIndicator,
} from 'react-native';
import { Picker } from '@react-native-picker/picker';
import { WebView } from 'react-native-webview';
import { deliveryPaymentApi } from '../../services/courierApi';

export default function ScheduleDeliveryScreen({ navigation }) {
  const [loading, setLoading] = useState(false);
  const [step, setStep] = useState(1); // 1: Form, 2: Payment, 3: Success
  const [deliveryId, setDeliveryId] = useState(null);
  const [paymentUrl, setPaymentUrl] = useState(null);
  const [paymentReference, setPaymentReference] = useState(null);

  const [formData, setFormData] = useState({
    pickup_address: {
      address: '',
      city: '',
      country: 'Ghana',
    },
    delivery_address: {
      address: '',
      city: '',
      country: 'Ghana',
    },
    pickup_contact_name: '',
    pickup_contact_phone: '',
    delivery_contact_name: '',
    delivery_contact_phone: '',
    priority: 'STANDARD',
    notes: '',
    item_description: '',
  });

  const handleScheduleDelivery = async () => {
    // Validate form
    if (
      !formData.pickup_address.address ||
      !formData.delivery_address.address ||
      !formData.pickup_contact_phone ||
      !formData.delivery_contact_phone
    ) {
      Alert.alert('Error', 'Please fill in all required fields');
      return;
    }

    setLoading(true);
    try {
      // Step 1: Schedule delivery
      const scheduleResponse = await deliveryPaymentApi.scheduleDelivery(formData);
      const newDeliveryId = scheduleResponse.id;
      setDeliveryId(newDeliveryId);

      // Step 2: Initialize payment
      const paymentResponse = await deliveryPaymentApi.initializePayment(
        newDeliveryId
      );
      setPaymentUrl(paymentResponse.authorization_url);
      setPaymentReference(paymentResponse.reference);
      setStep(2); // Move to payment step
    } catch (error) {
      Alert.alert(
        'Error',
        error.response?.data?.detail || 'Failed to schedule delivery'
      );
    } finally {
      setLoading(false);
    }
  };

  const handlePaymentCallback = async (url) => {
    // Check if payment was successful
    if (url.includes('payment-callback') || url.includes('success')) {
      setLoading(true);
      try {
        // Verify payment
        const verifyResponse = await deliveryPaymentApi.verifyPayment(
          paymentReference
        );

        if (verifyResponse.status === 'success') {
          setStep(3); // Move to success step
        } else {
          Alert.alert('Payment Failed', verifyResponse.message);
          navigation.goBack();
        }
      } catch (error) {
        Alert.alert('Error', 'Failed to verify payment');
        navigation.goBack();
      } finally {
        setLoading(false);
      }
    }
  };

  // Step 1: Delivery Form
  if (step === 1) {
    return (
      <ScrollView style={{ flex: 1, backgroundColor: '#fff', padding: 16 }}>
        <Text style={{ fontSize: 24, fontWeight: 'bold', marginBottom: 16 }}>
          Schedule Delivery
        </Text>

        <Text style={{ fontSize: 18, fontWeight: 'bold', marginTop: 16, marginBottom: 8 }}>
          Pickup Details
        </Text>
        <TextInput
          style={styles.input}
          placeholder="Pickup Address *"
          value={formData.pickup_address.address}
          onChangeText={(text) =>
            setFormData({
              ...formData,
              pickup_address: { ...formData.pickup_address, address: text },
            })
          }
        />
        <TextInput
          style={styles.input}
          placeholder="Pickup City *"
          value={formData.pickup_address.city}
          onChangeText={(text) =>
            setFormData({
              ...formData,
              pickup_address: { ...formData.pickup_address, city: text },
            })
          }
        />
        <TextInput
          style={styles.input}
          placeholder="Pickup Contact Name *"
          value={formData.pickup_contact_name}
          onChangeText={(text) =>
            setFormData({ ...formData, pickup_contact_name: text })
          }
        />
        <TextInput
          style={styles.input}
          placeholder="Pickup Contact Phone *"
          value={formData.pickup_contact_phone}
          onChangeText={(text) =>
            setFormData({ ...formData, pickup_contact_phone: text })
          }
          keyboardType="phone-pad"
        />

        <Text style={{ fontSize: 18, fontWeight: 'bold', marginTop: 16, marginBottom: 8 }}>
          Delivery Details
        </Text>
        <TextInput
          style={styles.input}
          placeholder="Delivery Address *"
          value={formData.delivery_address.address}
          onChangeText={(text) =>
            setFormData({
              ...formData,
              delivery_address: { ...formData.delivery_address, address: text },
            })
          }
        />
        <TextInput
          style={styles.input}
          placeholder="Delivery City *"
          value={formData.delivery_address.city}
          onChangeText={(text) =>
            setFormData({
              ...formData,
              delivery_address: { ...formData.delivery_address, city: text },
            })
          }
        />
        <TextInput
          style={styles.input}
          placeholder="Delivery Contact Name *"
          value={formData.delivery_contact_name}
          onChangeText={(text) =>
            setFormData({ ...formData, delivery_contact_name: text })
          }
        />
        <TextInput
          style={styles.input}
          placeholder="Delivery Contact Phone *"
          value={formData.delivery_contact_phone}
          onChangeText={(text) =>
            setFormData({ ...formData, delivery_contact_phone: text })
          }
          keyboardType="phone-pad"
        />

        <Text style={{ fontWeight: '600', marginTop: 16, marginBottom: 8 }}>
          Priority *
        </Text>
        <Picker
          selectedValue={formData.priority}
          onValueChange={(value) => setFormData({ ...formData, priority: value })}
          style={styles.picker}
        >
          <Picker.Item label="Standard (Normal delivery)" value="STANDARD" />
          <Picker.Item label="Express (Fast delivery - 1.5x cost)" value="EXPRESS" />
          <Picker.Item label="Urgent (Immediate delivery - 2x cost)" value="URGENT" />
        </Picker>

        <TextInput
          style={[styles.input, { height: 80 }]}
          placeholder="Item Description (Optional)"
          value={formData.item_description}
          onChangeText={(text) => setFormData({ ...formData, item_description: text })}
          multiline
        />

        <TextInput
          style={[styles.input, { height: 80 }]}
          placeholder="Special Instructions (Optional)"
          value={formData.notes}
          onChangeText={(text) => setFormData({ ...formData, notes: text })}
          multiline
        />

        <TouchableOpacity
          style={styles.button}
          onPress={handleScheduleDelivery}
          disabled={loading}
        >
          {loading ? (
            <ActivityIndicator color="#fff" />
          ) : (
            <Text style={styles.buttonText}>Continue to Payment</Text>
          )}
        </TouchableOpacity>
      </ScrollView>
    );
  }

  // Step 2: Payment
  if (step === 2) {
    return (
      <View style={{ flex: 1 }}>
        <WebView
          source={{ uri: paymentUrl }}
          onNavigationStateChange={(navState) => handlePaymentCallback(navState.url)}
          startInLoadingState
          renderLoading={() => (
            <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center' }}>
              <ActivityIndicator size="large" />
              <Text>Loading Payment...</Text>
            </View>
          )}
        />
      </View>
    );
  }

  // Step 3: Success
  if (step === 3) {
    return (
      <View
        style={{
          flex: 1,
          backgroundColor: '#fff',
          justifyContent: 'center',
          alignItems: 'center',
          padding: 16,
        }}
      >
        <Text style={{ fontSize: 60, marginBottom: 16 }}>✅</Text>
        <Text style={{ fontSize: 24, fontWeight: 'bold', marginBottom: 8 }}>
          Payment Successful!
        </Text>
        <Text style={{ textAlign: 'center', color: '#666', marginBottom: 24 }}>
          Your delivery has been scheduled and paid for. Couriers can now accept your
          request.
        </Text>

        <TouchableOpacity
          style={styles.button}
          onPress={() => navigation.navigate('MyDeliveries')}
        >
          <Text style={styles.buttonText}>View My Deliveries</Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.button, { backgroundColor: '#fff', borderWidth: 1, borderColor: '#007AFF' }]}
          onPress={() => navigation.navigate('Home')}
        >
          <Text style={[styles.buttonText, { color: '#007AFF' }]}>Go Home</Text>
        </TouchableOpacity>
      </View>
    );
  }

  return null;
}

const styles = {
  input: {
    borderWidth: 1,
    borderColor: '#ddd',
    borderRadius: 8,
    padding: 12,
    marginBottom: 12,
  },
  picker: {
    borderWidth: 1,
    borderColor: '#ddd',
    borderRadius: 8,
    marginBottom: 12,
  },
  button: {
    backgroundColor: '#007AFF',
    padding: 16,
    borderRadius: 8,
    alignItems: 'center',
    marginVertical: 8,
  },
  buttonText: {
    color: '#fff',
    fontWeight: 'bold',
    fontSize: 16,
  },
};
```

---

## Testing Checklist

### Courier Subaccount Setup
- [ ] Courier can sign up and login
- [ ] Courier sees warning when no subaccount exists
- [ ] Courier can view list of supported banks/mobile money
- [ ] Courier can create subaccount with bank account
- [ ] Courier can create subaccount with mobile money (MTN, Vodafone, AirtelTigo)
- [ ] Courier receives error for invalid account details
- [ ] Courier sees success message after subaccount creation
- [ ] Courier can view their subaccount status (active/inactive)
- [ ] Courier cannot create duplicate subaccount

### Scheduled Delivery Payment
- [ ] User can fill delivery form with pickup/delivery details
- [ ] User sees calculated delivery fee based on priority
- [ ] User can initialize payment
- [ ] User redirects to Paystack payment page
- [ ] User can pay with card/mobile money/bank transfer
- [ ] Payment verification works correctly
- [ ] Delivery status updates to "PAID" after successful payment
- [ ] Courier can see paid deliveries in available deliveries list
- [ ] Courier cannot accept unpaid deliveries
- [ ] Courier with no subaccount cannot accept deliveries

### Payment Split (70/30)
- [ ] When courier completes delivery, 70% goes to courier balance
- [ ] Platform keeps 30% of delivery fee
- [ ] Courier sees earning record in their earnings list
- [ ] Courier balance updates correctly
- [ ] Courier receives notification of earnings
- [ ] Customer receives delivery completion notification

### Edge Cases
- [ ] Payment fails gracefully with proper error messages
- [ ] Courier tries to accept already-assigned delivery
- [ ] User tries to pay for already-paid delivery
- [ ] Network errors are handled properly
- [ ] Invalid payment references return proper errors

---

## API Endpoints Summary

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/couriers/subaccount/status` | GET | Check if courier has subaccount |
| `/api/couriers/subaccount/create` | POST | Create courier subaccount (70/30 split) |
| `/api/payments/banks/ghana` | GET | Get list of supported banks |
| `/api/deliveries/schedule` | POST | Schedule delivery (existing) |
| `/api/deliveries/payment/initialize` | POST | Initialize delivery payment |
| `/api/deliveries/payment/verify` | POST | Verify delivery payment |
| `/api/deliveries/available` | GET | Get available PAID deliveries (existing) |
| `/api/deliveries/accept` | POST | Courier accepts PAID delivery (modified) |
| `/api/deliveries/{id}/status` | PUT | Update delivery status (modified for split) |

---

## Payment Flow Diagram

```
┌─────────────────┐
│  User Schedules │
│   Delivery      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Initialize     │
│  Payment        │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  User Pays via  │
│  Paystack       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Verify Payment │
│  Status: PAID   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Courier Sees   │
│  Paid Delivery  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Courier Accepts│
│  (Has Subacct)  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Courier Picks  │
│  Up & Delivers  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Status:        │
│  DELIVERED      │
│  ┌────────────┐ │
│  │ 70% → 🚚  │ │
│  │ 30% → 💼  │ │
│  └────────────┘ │
└─────────────────┘
```

---

## Notes

1. **Payment Split**: The 70/30 split is configured in the courier's subaccount creation with `percentage_charge: 30`
2. **Payment Before Acceptance**: Deliveries must be paid before couriers can accept them
3. **Subaccount Requirement**: Couriers must have a subaccount to accept deliveries
4. **Mobile Money**: Supports MTN, Vodafone, and AirtelTigo for Ghana
5. **Notifications**: Both customer and courier receive notifications at each step
6. **Error Handling**: All endpoints have proper error handling and validation

---

## Support & Troubleshooting

### Common Issues

**Courier can't create subaccount:**
- Check if bank/mobile money code is valid
- Verify account number format
- Ensure phone number is valid Ghanaian format

**Payment initialization fails:**
- Verify Paystack API keys are set
- Check delivery exists and is pending
- Ensure user email is available

**Payment verification fails:**
- Check payment reference is valid
- Verify user owns the delivery
- Check Paystack webhook is configured

**Courier can't accept delivery:**
- Verify delivery is paid
- Check courier has active subaccount
- Ensure delivery is still pending (not assigned)

---

## Next Steps

1. Test thoroughly in sandbox mode
2. Switch to live Paystack keys for production
3. Monitor payment splits in Paystack dashboard
4. Add withdrawal functionality for couriers
5. Implement real-time tracking
6. Add rating/review system

---

**Generated for Zipo Backend**
Last Updated: 2025-11-18
