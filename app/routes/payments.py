import re
from fastapi import APIRouter, HTTPException, status, Depends, Query
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
import phonenumbers

logger = logging.getLogger(__name__)

router = APIRouter()
security = HTTPBearer(auto_error=False)

# Paystack configuration
PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY")
PAYSTACK_BASE_URL = "https://api.paystack.co"
NEXT_PUBLIC_BASE_URL = os.getenv("NEXT_PUBLIC_BASE_URL", "https://zipohubonline.com")

def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)):
    """Get current authenticated user (optional for some endpoints)"""
    if not credentials:
        return None

    try:
        user_data = AuthUtils.verify_supabase_token(credentials.credentials)
        return user_data
    except Exception as e:
        logger.error(f"Token verification failed: {str(e)}")
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
        logger.error(f"Authentication failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed"
        )

# ========== PYDANTIC MODELS ==========

class SubscribeRequest(BaseModel):
    subscriptionPlanId: str  # This matches your React Native code
    referralCode: Optional[str] = None


class SubscriptionStatusResponse(BaseModel):
    has_subscription: bool
    can_create_product: bool
    max_products: Optional[int]
    current_products: int
    expires_at: Optional[str]
    plan: Optional[dict]
    message: str


class SubaccountRequest(BaseModel):
    businessName: str
    bankCode: str
    accountNumber: str
    email: str
    name: str
    phone: str


class BankResponse(BaseModel):
    id: int
    name: str
    slug: str
    code: str
    active: bool
    type: str


class SubaccountStatusResponse(BaseModel):
    hasSubaccount: bool
    subaccount: Optional[dict] = None


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
        logger.info(f"Fetching plans - Region: {region}, Tier: {tier}, Interval: {interval}")
        
        query = supabase.table("SubscriptionPlans").select("*")
        
        if tier:
            query = query.eq("subscriptionTier", tier)
        if region:
            query = query.eq("region", region)
        if interval:
            query = query.eq("interval", interval)
        
        # Only return active plans
        query = query.eq("isActive", True)
        
        response = query.execute()
        
        logger.info(f"Found {len(response.data) if response.data else 0} plans")
        
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
        
        logger.info(f"Fetching subscription status for user: {user_id}")
        
        # Get active subscriptions with plan details
        # ✅ FIX: Correct Supabase relationship syntax
        subscription_response = supabase.table("UserSubscriptions").select(
            "*, plan:subscriptionPlanId(*)"
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
        plan = subscription.get("plan")
        
        if not plan:
            logger.error(f"Plan data not found for subscription: {subscription.get('id')}")
            return {
                "has_subscription": False,
                "can_create_product": False,
                "max_products": 0,
                "current_products": current_products,
                "expires_at": None,
                "plan": None,
                "message": "Subscription plan data unavailable."
            }
        
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
    The Next.js webhook will handle subscription creation.
    """
    try:
        user_id = current_user["user_id"]
        user_email = current_user.get("email")
        
        logger.info(f"=== SUBSCRIPTION REQUEST ===")
        logger.info(f"User ID: {user_id}")
        logger.info(f"User Email: {user_email}")
        logger.info(f"Plan ID: {request.subscriptionPlanId}")
        logger.info(f"Referral Code: {request.referralCode or 'None'}")
        
        if not user_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User email is required"
            )
        
        # ✅ Check for active (non-expired) subscriptions FIRST
        from datetime import datetime

        active_subs = supabase.table("UserSubscriptions").select(
            "id, expiresAt, plan:subscriptionPlanId(name, region, subscriptionTier)"
        ).eq("userId", user_id).execute()

        # Filter for active subscriptions (not expired)
        if active_subs.data and len(active_subs.data) > 0:
            now = datetime.utcnow()

            for sub in active_subs.data:
                expires_at = datetime.fromisoformat(sub["expiresAt"].replace('Z', '+00:00'))

                # Check if subscription is still active
                if expires_at > now:
                    plan_name = sub.get("plan", {}).get("name", "Unknown Plan")
                    logger.warning(f"User {user_id} already has active subscription: {plan_name}")
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"You already have an active subscription ({plan_name}) that expires on {expires_at.strftime('%B %d, %Y')}. Please wait for it to expire before subscribing to a new plan."
                    )

        logger.info(f"✅ User {user_id} has no active subscription - can proceed")
        
        # Get subscription plan
        plan_response = supabase.table("SubscriptionPlans").select("*").eq(
            "id", request.subscriptionPlanId
        ).eq("region", "GHANA").execute()
        
        if not plan_response.data:
            logger.error(f"Plan not found: {request.subscriptionPlanId}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Subscription plan not found or is inactive"
            )
        
        plan = plan_response.data[0]
        
        # ✅ FIX: Validate planCode exists
        if not plan.get("planCode"):
            logger.error(f"Plan {plan['id']} missing planCode")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Subscription plan is not properly configured. Missing Paystack plan code."
            )
        
        # Convert amount to kobo (Paystack smallest unit)
        amount_in_kobo = int(float(plan["amount"]))
        
        logger.info(f"Plan Details: {plan['name']} - {amount_in_kobo} kobo ({amount_in_kobo/100} GHS)")
        
        # ✅ CRITICAL: Match Next.js metadata structure EXACTLY
        metadata = {
            "userId": user_id,
            "subscriptionId": plan["id"],
            "transactionType": "subscription",
            "email": user_email,
        }
        
        # Include referral code if provided
        if request.referralCode:
            metadata["referralCode"] = request.referralCode
            logger.info(f"✅ Referral code included: {request.referralCode}")
        
        # Callback URL for mobile
        callback_url = f"{NEXT_PUBLIC_BASE_URL}/api/payment-callback"
        
        logger.info(f"Callback URL: {callback_url}")
        
        # Initialize payment with Paystack
        paystack_data = {
            "email": user_email,
            "plan": plan["planCode"],
            "amount": amount_in_kobo,
            "callback_url": callback_url,
            "channels": ["card", "bank", "ussd", "qr", "mobile_money", "bank_transfer"],
            "metadata": metadata
        }
        
        logger.info(f"Calling Paystack API...")
        
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
        
        logger.info(f"Paystack response status: {response.status_code}")
        
        if response.status_code != 200:
            logger.error(f"Paystack initialization failed: {response.text}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to initialize payment with Paystack"
            )
        
        paystack_response = response.json()
        
        if not paystack_response.get("status"):
            logger.error(f"Paystack returned error: {paystack_response}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=paystack_response.get("message", "Payment initialization failed")
            )
        
        data = paystack_response["data"]
        
        logger.info(f"✅ Payment initialized successfully!")
        logger.info(f"Reference: {data['reference']}")
        logger.info(f"Authorization URL: {data['authorization_url']}")
        
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
        logger.error(f"💥 Error initializing subscription: {str(e)}")
        logger.exception(e)  # Full stack trace
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process subscription"
        )


# ========== VERIFY SUBSCRIPTION PAYMENT ==========

@router.post("/subscription/verify")
async def verify_subscription_payment(
    reference: str = Query(..., description="Payment reference from Paystack"),  # ✅ FIX: Query parameter
    current_user = Depends(get_required_user)
):
    """
    Verify subscription payment after user completes Paystack checkout.
    Note: The Next.js webhook handles the actual subscription creation.
    This endpoint just confirms payment status for the mobile app.
    """
    try:
        user_id = current_user["user_id"]
        
        logger.info(f"=== PAYMENT VERIFICATION ===")
        logger.info(f"User ID: {user_id}")
        logger.info(f"Reference: {reference}")
        
        # Verify with Paystack
        logger.info("Calling Paystack verification API...")
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{PAYSTACK_BASE_URL}/transaction/verify/{reference}",
                headers={
                    "Authorization": f"Bearer {PAYSTACK_SECRET_KEY}"
                },
                timeout=30.0
            )
        
        logger.info(f"Paystack verification response status: {response.status_code}")
        
        if response.status_code != 200:
            logger.error(f"Paystack verification failed: {response.text}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to verify payment with Paystack"
            )
        
        paystack_response = response.json()
        
        if not paystack_response.get("status"):
            logger.error(f"Paystack verification returned error: {paystack_response}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Payment verification failed"
            )
        
        data = paystack_response["data"]
        
        logger.info(f"Payment Status: {data['status']}")
        logger.info(f"Amount: {data['amount']} kobo")
        logger.info(f"Currency: {data['currency']}")
        
        # Extract metadata from payment data
        metadata = data.get("metadata", {})
        metadata_user_id = metadata.get("userId")

        if metadata_user_id != user_id:
            logger.error(f"User mismatch! Expected: {user_id}, Got: {metadata_user_id}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Unauthorized: This payment does not belong to you"
            )

        logger.info("✅ User verification passed")

        # Get subscription plan ID from metadata
        subscription_plan_id = metadata.get("subscriptionId")

        if not subscription_plan_id:
            logger.warning("No subscription plan ID in payment metadata")
            result = {
                "status": data["status"],
                "reference": reference,
                "amount": data["amount"] / 100,
                "currency": data["currency"],
                "paid_at": data.get("paid_at"),
                "subscription": None,
                "message": "Payment successful but no subscription data found"
            }
            return result

        logger.info(f"Subscription Plan ID: {subscription_plan_id}")

        # Check if subscription already exists
        existing_subscription = supabase.table("UserSubscriptions").select(
            "*, plan:subscriptionPlanId(*)"
        ).eq("userId", user_id).eq("subscriptionPlanId", subscription_plan_id).execute()

        subscription = None

        if existing_subscription.data and len(existing_subscription.data) > 0:
            subscription = existing_subscription.data[0]
            logger.info(f"✅ Existing subscription found: {subscription['id']}")
        else:
            # Create new subscription since webhook didn't create it
            logger.info("🆕 Creating new subscription (webhook didn't create it)...")

            # Get plan details to calculate expiry
            plan_response = supabase.table("SubscriptionPlans").select("*").eq(
                "id", subscription_plan_id
            ).execute()

            if not plan_response.data:
                logger.error(f"❌ Subscription plan not found: {subscription_plan_id}")
                result = {
                    "status": data["status"],
                    "reference": reference,
                    "amount": data["amount"] / 100,
                    "currency": data["currency"],
                    "paid_at": data.get("paid_at"),
                    "subscription": None,
                    "message": "Payment successful but subscription plan not found"
                }
                return result

            plan = plan_response.data[0]
            logger.info(f"📋 Plan: {plan['name']} - {plan['interval']}")

            # Calculate expiry date based on interval
            from datetime import datetime, timedelta

            now = datetime.utcnow()
            interval = plan["interval"]

            if interval == "DAILY":
                expires_at = now + timedelta(days=1)
            elif interval == "WEEKLY":
                expires_at = now + timedelta(weeks=1)
            elif interval == "MONTHLY":
                expires_at = now + timedelta(days=30)
            elif interval == "QUARTERLY":
                expires_at = now + timedelta(days=90)
            elif interval == "BIANNUALLY":
                expires_at = now + timedelta(days=180)
            elif interval == "ANNUALLY":
                expires_at = now + timedelta(days=365)
            else:
                expires_at = now + timedelta(days=30)  # Default to monthly

            logger.info(f"📅 Calculated expiry: {expires_at.isoformat()}")

            # Create subscription record
            subscription_data = {
                "id": str(uuid.uuid4()),
                "userId": user_id,
                "subscriptionPlanId": subscription_plan_id,
                "expiresAt": expires_at.isoformat(),
                "createdAt": now.isoformat(),
                "updatedAt": now.isoformat()
            }

            try:
                create_response = supabase.table("UserSubscriptions").insert(
                    subscription_data
                ).execute()

                if create_response.data and len(create_response.data) > 0:
                    # Fetch the created subscription with plan details
                    subscription_response = supabase.table("UserSubscriptions").select(
                        "*, plan:subscriptionPlanId(*)"
                    ).eq("id", create_response.data[0]["id"]).execute()

                    if subscription_response.data:
                        subscription = subscription_response.data[0]
                        logger.info(f"✅ Subscription created successfully: {subscription['id']}")
                        logger.info(f"   Expires at: {subscription['expiresAt']}")

                        # Create success notification
                        try:
                            notification_data = {
                                "userId": user_id,
                                "title": "Subscription Activated",
                                "notificationType": "SUCCESS",
                                "body": f"Your {plan['name']} subscription has been activated successfully! Enjoy your benefits until {expires_at.strftime('%B %d, %Y')}.",
                                "dismissed": False,
                                "createdAt": now.isoformat(),
                                "expiresAt": (now + timedelta(days=30)).isoformat()  # Notification expires in 30 days
                            }

                            notification_response = supabase.table("Notification").insert(
                                notification_data
                            ).execute()

                            if notification_response.data:
                                logger.info(f"✅ Success notification created for user {user_id}")
                            else:
                                logger.warning("⚠️ Failed to create success notification")

                        except Exception as notif_error:
                            logger.error(f"❌ Error creating notification: {str(notif_error)}")
                            # Don't fail the whole operation if notification fails

                        # Process agent commission (only once per seller subscription)
                        try:
                            logger.info("🔍 Checking for agent commission eligibility...")

                            # Check if seller is registered by an agent
                            agent_relation = supabase.table("AgentRegisteredSeller").select(
                                "agent_id, Agent!inner(id, user_id, agent_code, commission_rate)"
                            ).eq("seller_id", user_id).eq("is_active", True).execute()

                            if agent_relation.data and len(agent_relation.data) > 0:
                                agent_data = agent_relation.data[0]
                                agent_record = agent_data["Agent"]
                                agent_uuid = agent_record["id"]
                                agent_user_id = agent_record["user_id"]

                                logger.info(f"✅ Found agent: {agent_uuid} for seller {user_id}")

                                # Calculate commission (10% of subscription amount)
                                commission_rate = 0.1
                                amount_in_kobo = int(plan["amount"])  # Plan amount is already in kobo
                                commission_amount = round(amount_in_kobo * commission_rate)

                                logger.info(f"💰 Commission: {commission_amount} kobo (GHS {(commission_amount / 100):.2f})")

                                # Check if commission already paid for this subscription
                                reference_id = f"subscription_{subscription['id']}"
                                existing_commission = supabase.table("CommissionTransaction").select("id").eq(
                                    "agent_id", agent_uuid
                                ).eq("reference_id", reference_id).eq("reference_type", "SUBSCRIPTION").execute()

                                if existing_commission.data and len(existing_commission.data) > 0:
                                    logger.info("⚠️ Commission already paid for this subscription")
                                else:
                                    # Create commission transaction
                                    commission_data = {
                                        "agent_id": agent_uuid,
                                        "amount": commission_amount / 100,  # Store in cedis
                                        "transaction_type": "EARNING",
                                        "reference_id": reference_id,
                                        "reference_type": "SUBSCRIPTION",
                                        "status": "COMPLETED",
                                        "created_at": now.isoformat(),
                                        "processed_at": now.isoformat()
                                    }

                                    commission_response = supabase.table("CommissionTransaction").insert(
                                        commission_data
                                    ).execute()

                                    if commission_response.data:
                                        logger.info(f"✅ Commission transaction created: {commission_response.data[0]['id']}")

                                        # Update agent balances
                                        agent_update = supabase.rpc("increment_agent_balance", {
                                            "p_agent_id": agent_uuid,
                                            "p_amount": commission_amount / 100
                                        }).execute()

                                        logger.info(f"✅ Agent balance updated")

                                        # Create agent activity log
                                        activity_data = {
                                            "agent_id": agent_uuid,
                                            "activity_type": "COMMISSION_EARNED",
                                            "description": f"Earned GHS {(commission_amount / 100):.2f} from seller subscription",
                                            "metadata": {
                                                "seller_id": user_id,
                                                "subscription_id": subscription["id"],
                                                "plan_name": plan["name"],
                                                "commission_amount_kobo": commission_amount,
                                                "commission_amount_ghs": commission_amount / 100,
                                                "original_amount_kobo": amount_in_kobo,
                                                "original_amount_ghs": amount_in_kobo / 100,
                                                "commission_rate": commission_rate,
                                                "reference_id": reference_id,
                                                "payment_reference": reference
                                            },
                                            "created_at": now.isoformat(),
                                            "is_read": False
                                        }

                                        activity_response = supabase.table("AgentActivity").insert(
                                            activity_data
                                        ).execute()

                                        if activity_response.data:
                                            logger.info(f"✅ Agent activity logged")

                                        # Send notification to agent
                                        agent_notification = {
                                            "id": str(uuid.uuid4()),
                                            "userId": agent_user_id,
                                            "title": "Commission Earned",
                                            "notificationType": "SUCCESS",
                                            "body": f"You earned GHS {(commission_amount / 100):.2f} commission from your registered seller's subscription to {plan['name']}.",
                                            "dismissed": False,
                                            "createdAt": now.isoformat(),
                                            "expiresAt": (now + timedelta(days=30)).isoformat()
                                        }

                                        agent_notif_response = supabase.table("Notification").insert(
                                            agent_notification
                                        ).execute()

                                        if agent_notif_response.data:
                                            logger.info(f"✅ Agent notification sent")

                                        logger.info(f"✅ Commission processing completed successfully")
                                    else:
                                        logger.error("❌ Failed to create commission transaction")
                            else:
                                logger.info("ℹ️ No agent found for this seller - no commission to process")

                        except Exception as commission_error:
                            logger.error(f"❌ Error processing agent commission: {str(commission_error)}")
                            logger.exception(commission_error)
                            # Don't fail the whole operation if commission fails
                    else:
                        subscription = create_response.data[0]
                else:
                    logger.error("❌ Failed to create subscription - no data returned")

            except Exception as create_error:
                logger.error(f"❌ Error creating subscription: {str(create_error)}")
                logger.exception(create_error)

        result = {
            "status": data["status"],
            "reference": reference,
            "amount": data["amount"] / 100,  # Convert kobo to cedis
            "currency": data["currency"],
            "paid_at": data.get("paid_at"),
            "subscription": subscription,
            "message": "Payment successful" if data["status"] == "success" else "Payment pending"
        }

        logger.info(f"✅ Verification complete: {result['message']}")

        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"💥 Error verifying subscription payment: {str(e)}")
        logger.exception(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to verify payment"
        )


# ========== GET SUPPORTED GHANAIAN BANKS ==========

@router.get("/banks/ghana")
async def get_supported_ghanaian_banks():
    """
    Get list of supported Ghanaian banks and mobile money providers from Paystack
    """
    try:
        logger.info("Fetching supported Ghanaian banks from Paystack...")

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{PAYSTACK_BASE_URL}/bank",
                headers={
                    "Authorization": f"Bearer {PAYSTACK_SECRET_KEY}",
                    "Content-Type": "application/json"
                },
                params={
                    "country": "ghana",
                    "perPage": 100
                },
                timeout=30.0
            )

        if response.status_code != 200:
            logger.error(f"Paystack banks fetch failed: {response.text}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to fetch banks from Paystack"
            )

        data = response.json()

        if not data.get("status"):
            logger.error(f"Paystack returned error: {data}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to fetch banks"
            )

        banks = data.get("data", [])
        logger.info(f"✅ Retrieved {len(banks)} banks from Paystack")

        return banks

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"💥 Error fetching banks: {str(e)}")
        logger.exception(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch banks"
        )


# ========== CREATE PAYSTACK SUBACCOUNT ==========


@router.post("/paystack/subaccounts")
async def create_paystack_subaccount(
    request: SubaccountRequest,
    current_user = Depends(get_required_user)
):
    """
    Create a Paystack subaccount for a seller to receive payments.
    Requires an active Ghanaian subscription.
    """
    user_id = current_user["user_id"]

    logger.info(f"=== SUBACCOUNT CREATION REQUEST ===")
    logger.info(f"User ID: {user_id}")
    logger.info(f"Business Name: {request.businessName}")
    logger.info(f"Bank Code: {request.bankCode}")
    logger.info(f"Account Number: {request.accountNumber}")
    logger.info(f"Phone: {request.phone}")

    # Basic phone number validation - just ensure it's not empty and has reasonable length
    clean_phone = re.sub(r'[^\d]', '', request.phone)
    if not clean_phone or len(clean_phone) < 9 or len(clean_phone) > 13:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid contact phone number format"
        )

    # Check user type to determine if subscription is required
    user_check = supabase.table("users").select("user_type, role").eq("user_id", user_id).execute()

    is_courier = False
    platform_cut = 0

    if user_check.data and len(user_check.data) > 0:
        user_type = user_check.data[0].get("user_type")
        role = user_check.data[0].get("role")
        is_courier = user_type == "COURIER" or role == "COURIER"
        logger.info(f"User type: {user_type}, Role: {role}, Is courier: {is_courier}")

    # Couriers don't need subscriptions to create subaccounts
    if not is_courier:
        # Check for active Ghanaian subscription
        active_subscription = supabase.table("UserSubscriptions").select(
            "*, plan:subscriptionPlanId(*)"
        ).eq("userId", user_id).gt("expiresAt", datetime.utcnow().isoformat()).execute()

        if not active_subscription.data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User has no active subscription"
            )

        subscription = active_subscription.data[0]
        plan = subscription.get("plan")

        if not plan or plan.get("region") != "GHANA":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User has no active Ghanaian subscription"
            )

        logger.info(f"✅ Active subscription verified: {plan['name']}")
        platform_cut = plan.get("platformCut", 0)
    else:
        logger.info(f"✅ Courier user - no subscription required")
        # For couriers, platform cut is 0 (they keep all earnings)
        platform_cut = 0

    # Check if user already has a subaccount
    existing_subaccount = supabase.table("PaystackSubaccount").select("*").eq(
        "userId", user_id
    ).execute()

    if existing_subaccount.data:
        logger.warning(f"User {user_id} already has a subaccount")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a subaccount"
        )

    logger.info(f"Platform cut: {platform_cut}%")

    # Define mobile money provider codes based on Paystack's actual response
    MOBILE_MONEY_PROVIDERS = {'MTN', 'ATL', 'VOD'}  # MTN, AirtelTigo, Vodafone
    is_mobile_money = request.bankCode.upper() in MOBILE_MONEY_PROVIDERS

    # For mobile money, ensure account number is in LOCAL Ghana format (024...)
    account_number = request.accountNumber
    
    if is_mobile_money:
        # Clean the account number (remove any non-digit characters)
        clean_account = re.sub(r'[^\d]', '', account_number)
        
        # Convert to local Ghana format (024...)
        if clean_account.startswith('233') and len(clean_account) == 12:
            # Convert from international to local format
            clean_account = '0' + clean_account[3:]
        elif clean_account.startswith('0') and len(clean_account) == 10:
            # Already in local format, keep as-is
            pass
        elif len(clean_account) == 9:
            # Local format without leading 0, add it
            clean_account = '0' + clean_account
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Mobile money account number must be a valid Ghanaian phone number (e.g., 0241234567)"
            )
        
        account_number = clean_account

    # Create subaccount with Paystack
    subaccount_data = {
        "business_name": request.businessName,
        "bank_code": request.bankCode,
        "account_number": account_number,  # This will be 024... for mobile money
        "percentage_charge": platform_cut,
        "primary_contact_email": request.email,
        "primary_contact_name": request.name,
        "primary_contact_phone": request.phone,  # Send as-is
    }

    logger.info(f"Sending to Paystack: {subaccount_data}")

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

    logger.info(f"Paystack response status: {response.status_code}")
    logger.info(f"Paystack response: {response.text}")

    if response.status_code not in [200, 201]:
        error_data = response.json()
        logger.error(f"Paystack subaccount creation failed: {response.text}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_data.get("message", "Failed to create subaccount with Paystack")
        )

    paystack_response = response.json()

    if not paystack_response.get("status"):
        logger.error(f"Paystack returned error: {paystack_response}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=paystack_response.get("message", "Subaccount creation failed")
        )

    subaccount_code = paystack_response["data"]["subaccount_code"]
    logger.info(f"✅ Paystack subaccount created: {subaccount_code}")

    # Save subaccount to database - include updatedAt field for Supabase
    current_time = datetime.utcnow().isoformat()
    db_subaccount = supabase.table("PaystackSubaccount").insert({
        "userId": user_id,
        "subaccountId": subaccount_code,
        "updatedAt": current_time
    }).execute()

    if not db_subaccount.data:
        logger.error("Failed to save subaccount to database")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save subaccount"
        )

    created_subaccount = db_subaccount.data[0]
    logger.info(f"✅ Subaccount saved to database: {created_subaccount['id']}")

    return {
        "id": created_subaccount["id"],
        "subAccountId": created_subaccount["subaccountId"],
        "message": "Subaccount created successfully"
    }

# ========== CHECK SUBACCOUNT STATUS ==========

@router.get("/paystack/subaccounts/status", response_model=SubaccountStatusResponse)
async def check_subaccount_status(current_user = Depends(get_required_user)):
    """
    Check if the authenticated user has already created a Paystack subaccount.
    """
    try:
        user_id = current_user["user_id"]

        logger.info(f"Checking subaccount status for user: {user_id}")

        # Check if user has a subaccount
        subaccount_response = supabase.table("PaystackSubaccount").select("*").eq(
            "userId", user_id
        ).execute()

        if not subaccount_response.data:
            logger.info(f"User {user_id} has no subaccount")
            return {
                "hasSubaccount": False,
                "subaccount": None
            }

        subaccount = subaccount_response.data[0]

        logger.info(f"✅ User {user_id} has subaccount: {subaccount['subaccountId']}")

        return {
            "hasSubaccount": True,
            "subaccount": {
                "id": subaccount["id"],
                "subaccountId": subaccount["subaccountId"],
                "createdAt": subaccount["createdAt"],
                "updatedAt": subaccount["updatedAt"]
            }
        }

    except Exception as e:
        logger.error(f"💥 Error checking subaccount status: {str(e)}")
        logger.exception(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to check subaccount status"
        )