from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from app.database import supabase
from app.utils.auth_utils import AuthUtils
from typing import Optional
from datetime import datetime
import logging
import httpx
import os
import uuid

logger = logging.getLogger(__name__)

router = APIRouter()
security = HTTPBearer(auto_error=False)

# Paystack configuration
PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY")
PAYSTACK_BASE_URL = "https://api.paystack.co"

def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)):
    """Get current authenticated user (optional for some endpoints)"""
    if not credentials:
        return None

    try:
        user_data = AuthUtils.verify_supabase_token(credentials.credentials)
        return user_data
    except Exception:
        return None

def get_required_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get current authenticated user (required)"""
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
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed"
        )

# ========== PYDANTIC MODELS ==========

class SubscribeRequest(BaseModel):
    subscriptionPlanId: str
    referralCode: Optional[str] = None


class SubscriptionStatusResponse(BaseModel):
    has_subscription: bool
    can_create_product: bool
    max_products: Optional[int]
    current_products: int
    expires_at: Optional[str]
    plan: Optional[dict]
    message: str


# ========== GET SUBSCRIPTION PLANS ==========

@router.get("/subscription-plans")
async def get_subscription_plans(
    tier: Optional[str] = None,
    region: Optional[str] = "GHANA",
    interval: Optional[str] = None
):
    """
    Get available subscription plans with optional filters
    """
    try:
        query = supabase.table("SubscriptionPlans").select("*")
        
        if tier:
            query = query.eq("subscriptionTier", tier)
        if region:
            query = query.eq("region", region)
        if interval:
            query = query.eq("interval", interval)
        
        response = query.execute()
        
        return response.data or []
        
    except Exception as e:
        logger.error(f"Error fetching subscription plans: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch subscription plans"
        )


# ========== GET USER SUBSCRIPTION STATUS ==========

@router.get("/subscription/status", response_model=SubscriptionStatusResponse)
async def get_subscription_status(current_user = Depends(get_required_user)):
    """
    Get current user's subscription status
    """
    try:
        user_id = current_user["user_id"]
        
        # Get active subscription
        subscription_response = supabase.table("UserSubscriptions").select(
            "*, SubscriptionPlans!inner(*)"
        ).eq("userId", user_id).gt("expiresAt", datetime.utcnow().isoformat()).execute()
        
        # Count user's products
        products_response = supabase.table("Products").select(
            "id", count="exact"
        ).eq("sellerId", user_id).execute()
        
        current_products = products_response.count or 0
        
        if not subscription_response.data:
            return {
                "has_subscription": False,
                "can_create_product": False,
                "max_products": 0,
                "current_products": current_products,
                "expires_at": None,
                "plan": None,
                "message": "No active subscription. Subscribe to start selling."
            }
        
        subscription = subscription_response.data[0]
        plan = subscription["SubscriptionPlans"]
        
        # Determine product limits based on tier
        tier_limits = {
            "LEVEL1": 5,
            "LEVEL2": 20,
            "LEVEL3": None  # Unlimited
        }
        
        max_products = tier_limits.get(plan["subscriptionTier"])
        can_create = max_products is None or current_products < max_products
        
        message = "Unlimited products allowed" if max_products is None else \
                  f"You can create {max_products - current_products} more products"
        
        return {
            "has_subscription": True,
            "can_create_product": can_create,
            "max_products": max_products,
            "current_products": current_products,
            "expires_at": subscription["expiresAt"],
            "plan": plan,
            "message": message
        }
        
    except Exception as e:
        logger.error(f"Error fetching subscription status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch subscription status"
        )


# ========== SUBSCRIBE TO PLAN (INITIALIZE PAYMENT) ==========

@router.post("/subscribe")
async def subscribe_to_plan(
    request: SubscribeRequest,
    current_user = Depends(get_required_user)
):
    """
    Initialize subscription payment with Paystack.
    Supports referral codes for commission tracking.
    The webhook will handle subscription creation.
    """
    try:
        user_id = current_user["user_id"]
        user_email = current_user.get("email")
        
        if not user_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User email is required"
            )
        
        # Get subscription plan
        plan_response = supabase.table("SubscriptionPlans").select("*").eq(
            "id", request.subscriptionPlanId
        ).eq("region", "GHANA").execute()
        
        if not plan_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Subscription plan not found"
            )
        
        plan = plan_response.data[0]
        
        # Convert amount to kobo (Paystack smallest unit)
        amount_in_kobo = int(float(plan["amount"]))
        
        # Prepare metadata - this will be sent to your Next.js webhook
        metadata = {
            "userId": user_id,
            "subscriptionId": plan["id"],
            "transactionType": "subscription"
        }
        
        # Include referral code if provided
        if request.referralCode:
            metadata["referralCode"] = request.referralCode
            logger.info(f"Referral code included: {request.referralCode}")
        
        # Initialize payment with Paystack
        paystack_data = {
            "email": user_email,
            "plan": plan["planCode"],
            "amount": amount_in_kobo,
            "callback_url": os.getenv("PAYMENT_CALLBACK_URL", ""),
            "metadata": metadata
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{PAYSTACK_BASE_URL}/transaction/initialize",
                json=paystack_data,
                headers={
                    "Authorization": f"Bearer {PAYSTACK_SECRET_KEY}",
                    "Content-Type": "application/json"
                }
            )
        
        if response.status_code != 200:
            logger.error(f"Paystack initialization failed: {response.text}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to initialize payment with Paystack"
            )
        
        paystack_response = response.json()
        
        if not paystack_response.get("status"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=paystack_response.get("message", "Payment initialization failed")
            )
        
        data = paystack_response["data"]
        
        logger.info(f"Subscription payment initialized for user {user_id}")
        
        return {
            "data": {
                "authorization_url": data["authorization_url"],
                "access_code": data["access_code"],
                "reference": data["reference"]
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error initializing subscription: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process subscription"
        )


# ========== VERIFY SUBSCRIPTION PAYMENT ==========

@router.post("/subscription/verify")
async def verify_subscription_payment(
    reference: str,
    current_user = Depends(get_required_user)
):
    """
    Verify subscription payment after user completes Paystack checkout.
    Note: The Next.js webhook handles the actual subscription creation.
    This endpoint just confirms payment status for the mobile app.
    """
    try:
        user_id = current_user["user_id"]
        
        # Verify with Paystack
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{PAYSTACK_BASE_URL}/transaction/verify/{reference}",
                headers={
                    "Authorization": f"Bearer {PAYSTACK_SECRET_KEY}"
                }
            )
        
        if response.status_code != 200:
            logger.error(f"Paystack verification failed: {response.text}")
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
        
        # Verify this payment belongs to current user
        if data.get("metadata", {}).get("userId") != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Unauthorized access"
            )
        
        # Get subscription created by webhook
        subscription_response = supabase.table("UserSubscriptions").select(
            "*, SubscriptionPlans!inner(*)"
        ).eq("userId", user_id).order(
            "createdAt", desc=True
        ).limit(1).execute()
        
        return {
            "status": data["status"],
            "reference": reference,
            "amount": data["amount"] / 100,
            "currency": data["currency"],
            "paid_at": data.get("paid_at"),
            "subscription": subscription_response.data[0] if subscription_response.data else None,
            "message": "Payment successful" if data["status"] == "success" else "Payment pending"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error verifying subscription payment: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to verify payment"
        )