from fastapi import APIRouter, HTTPException, Request, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, Dict, Any, Literal
from datetime import datetime, timedelta
import logging
import hmac
import hashlib
import os
from app.database import supabase, get_prisma
from decimal import Decimal

logger = logging.getLogger(__name__)

router = APIRouter()

# Paystack configuration
PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY")

# ===== PYDANTIC MODELS =====


class PaystackMetadata(BaseModel):
    userId: str
    productId: Optional[str] = None
    email: Optional[str] = None
    discountCode: Optional[str] = None
    customerName: Optional[str] = None
    customerPhone: Optional[str] = None
    subscriptionId: Optional[str] = None
    subscriptionCode: Optional[str] = None
    planCode: Optional[str] = None
    transactionType: Optional[Literal["subscription", "product", "one-time"]] = None
    referralCode: Optional[str] = None


class PaystackWebhookData(BaseModel):
    id: int
    domain: str
    status: str
    reference: str
    amount: int  # in kobo
    message: Optional[str] = None
    gateway_response: str
    paid_at: Optional[str] = None
    created_at: str
    channel: str
    currency: str
    ip_address: Optional[str] = None
    metadata: PaystackMetadata
    fees: Optional[int] = None
    customer: Optional[Dict[str, Any]] = None
    plan: Optional[Dict[str, Any]] = None


# ===== WEBHOOK EVENT TYPES =====
WEBHOOK_EVENTS = {
    "CHARGE_SUCCESS": "charge.success",
    "CHARGE_FAILED": "charge.failed",
    "SUBSCRIPTION_CREATE": "subscription.create",
    "SUBSCRIPTION_NOT_RENEW": "subscription.not_renew",
    "SUBSCRIPTION_DISABLE": "subscription.disable",
    "INVOICE_CREATE": "invoice.create",
    "INVOICE_UPDATE": "invoice.update",
    "INVOICE_PAYMENT_FAILED": "invoice.payment_failed",
}


# ===== AGENT COMMISSION SERVICE =====
class AgentCommissionService:
    COMMISSION_RATE = 0.1  # 10%
    MIN_COMMISSION_AMOUNT = 100  # 1 GHS in kobo

    @staticmethod
    async def process_referral_commission(
        user_id: str,
        amount: int,  # Amount in kobo
        referral_code: str,
        reference_id: str,
        reference_type: str = "SUBSCRIPTION",
    ):
        """Process referral commission for new users using referral codes"""
        try:
            logger.info(
                f"🔗 STEP 2: Processing referral commission for user: {user_id}"
            )
            logger.info(f"💰 Payment amount: {amount} kobo (GHS {amount / 100:.2f})")
            logger.info(f"🎯 Referral code: {referral_code}")

            # Skip commission for very small amounts
            if amount < AgentCommissionService.MIN_COMMISSION_AMOUNT:
                logger.warning(
                    f"⚠️ Amount too small for referral commission: {amount} kobo"
                )
                return None

            # Check if seller is already registered by an agent
            existing_agent_relation = (
                supabase.table("AgentRegisteredSeller")
                .select("*")
                .eq("seller_id", user_id)
                .eq("is_active", True)
                .execute()
            )

            if existing_agent_relation.data:
                logger.info(
                    f"❌ Seller {user_id} already registered by agent - skipping referral commission"
                )
                return None

            logger.info(
                "✅ Seller not registered by any agent - eligible for referral commission"
            )

            # Validate referral code exists and is active
            logger.info(f"🔍 Validating referral code: {referral_code}")
            referral_link = (
                supabase.table("agent_referral_links")
                .select("*, Agent!inner(id, user_id, agent_code)")
                .eq("referral_code", referral_code)
                .eq("is_active", True)
                .execute()
            )

            if not referral_link.data:
                logger.warning(f"❌ Invalid or inactive referral code: {referral_code}")
                return None

            referral_link_data = referral_link.data[0]
            agent_id = referral_link_data["agent_id"]
            agent_data = referral_link_data.get("Agent")

            if not agent_data:
                logger.error(f"❌ Agent not found for referral link: {referral_code}")
                return None

            agent_record_id = agent_data["id"]
            logger.info(f"✅ Valid referral link found for agent: {agent_id}")

            # Check for duplicate referral conversion
            existing_conversion = (
                supabase.table("referral_conversions")
                .select("*")
                .eq("referral_link_id", referral_link_data["id"])
                .eq("seller_id", user_id)
                .execute()
            )

            if existing_conversion.data:
                logger.warning(
                    f"❌ Seller already converted via this referral: {user_id}"
                )
                return None

            logger.info("✅ No duplicate conversion found")

            # Check for duplicate commission transactions
            existing_transaction = (
                supabase.table("CommissionTransaction")
                .select("*")
                .eq("agent_id", agent_record_id)
                .eq("reference_id", reference_id)
                .eq("reference_type", reference_type)
                .execute()
            )

            if existing_transaction.data:
                logger.warning(
                    f"❌ Commission already processed for reference: {reference_id}"
                )
                return existing_transaction.data[0]

            logger.info("✅ No duplicate transaction found")

            # Calculate 10% commission
            commission_amount = int(amount * AgentCommissionService.COMMISSION_RATE)
            logger.info(f"💵 Commission calculation:")
            logger.info(f"   Original amount: {amount} kobo (GHS {amount / 100:.2f})")
            logger.info(
                f"   Commission rate: {AgentCommissionService.COMMISSION_RATE * 100}%"
            )
            logger.info(
                f"   Commission amount: {commission_amount} kobo (GHS {commission_amount / 100:.2f})"
            )

            # Get seller info
            seller = (
                supabase.table("users").select("email").eq("user_id", user_id).execute()
            )

            # Process commission (store in cedis)
            commission_in_cedis = commission_amount / 100

            # Create commission transaction
            transaction = (
                supabase.table("CommissionTransaction")
                .insert(
                    {
                        "agent_id": agent_record_id,
                        "amount": commission_in_cedis,
                        "transaction_type": "EARNING",
                        "reference_id": reference_id,
                        "reference_type": reference_type,
                        "status": "COMPLETED",
                        "created_at": datetime.utcnow().isoformat(),
                        "processed_at": datetime.utcnow().isoformat(),
                    }
                )
                .execute()
            )

            # Update agent balances
            agent_update = supabase.rpc(
                "increment_agent_balances",
                {"p_user_id": agent_id, "p_amount": commission_in_cedis},
            ).execute()

            # Record referral conversion
            conversion = (
                supabase.table("referral_conversions")
                .insert(
                    {
                        "referral_link_id": referral_link_data["id"],
                        "agent_id": agent_id,
                        "seller_id": user_id,
                        "seller_email": seller.data[0]["email"]
                        if seller.data
                        else None,
                        "converted_at": datetime.utcnow().isoformat(),
                        "commission_earned": commission_in_cedis,
                    }
                )
                .execute()
            )

            # Update referral link stats
            supabase.table("agent_referral_links").update(
                {
                    "conversion_count": referral_link_data.get("conversion_count", 0)
                    + 1,
                    "click_count": referral_link_data.get("click_count", 0) + 1,
                    "updated_at": datetime.utcnow().isoformat(),
                }
            ).eq("id", referral_link_data["id"]).execute()

            # Create activity log
            supabase.table("AgentActivity").insert(
                {
                    "agent_id": agent_record_id,
                    "activity_type": "COMMISSION_EARNED",
                    "description": f"Earned GHS {commission_in_cedis:.2f} from referral conversion (standalone referral)",
                    "metadata": {
                        "amount_kobo": commission_amount,
                        "amount_ghs": commission_in_cedis,
                        "reference_id": reference_id,
                        "reference_type": reference_type,
                        "transaction_id": transaction.data[0]["id"]
                        if transaction.data
                        else None,
                        "seller_id": user_id,
                        "referral_code": referral_code,
                        "original_amount_kobo": amount,
                        "original_amount_ghs": amount / 100,
                        "commission_rate": AgentCommissionService.COMMISSION_RATE,
                        "currency": "GHS",
                        "commission_type": "REFERRAL_ONLY",
                    },
                    "created_at": datetime.utcnow().isoformat(),
                }
            ).execute()

            logger.info(f"✅ Referral commission processed successfully!")
            logger.info(
                f"   Agent {agent_id} earned GHS {commission_in_cedis:.2f} (referral only)"
            )

            return {
                "transaction": transaction.data[0] if transaction.data else None,
                "conversion": conversion.data[0] if conversion.data else None,
                "commission_amount": commission_amount,
            }

        except Exception as error:
            logger.error(f"❌ Error processing referral commission: {error}")
            return None

    @staticmethod
    async def process_commission(
        user_id: str,
        amount: int,  # Amount in kobo
        reference_id: str,
        reference_type: str = "SUBSCRIPTION",
    ):
        """Process regular agent commission for registered sellers"""
        try:
            logger.info(f"🔍 Processing commission for user: {user_id}")
            logger.info(f"💰 Payment amount: {amount} kobo (GHS {amount / 100:.2f})")

            # Skip commission for very small amounts
            if amount < AgentCommissionService.MIN_COMMISSION_AMOUNT:
                logger.warning(f"⚠️ Amount too small for commission: {amount} kobo")
                return None

            # Find the agent for this user
            agent_relation = (
                supabase.table("AgentRegisteredSeller")
                .select("agent_id, Agent!inner(id, user_id)")
                .eq("seller_id", user_id)
                .eq("is_active", True)
                .execute()
            )

            if not agent_relation.data:
                logger.info(f"❌ No active agent found for user {user_id}")
                return None

            agent_id = agent_relation.data[0]["agent_id"]
            agent_record_id = agent_relation.data[0]["Agent"]["id"]

            logger.info(f"🔍 Agent ID: {agent_id}")

            # Calculate commission in kobo
            commission_amount = int(amount * AgentCommissionService.COMMISSION_RATE)

            logger.info(f"💵 Commission calculation:")
            logger.info(f"   Original amount: {amount} kobo (GHS {amount / 100:.2f})")
            logger.info(
                f"   Commission rate: {AgentCommissionService.COMMISSION_RATE * 100}%"
            )
            logger.info(
                f"   Commission amount: {commission_amount} kobo (GHS {commission_amount / 100:.2f})"
            )

            # Check for duplicate transactions
            existing_transaction = (
                supabase.table("CommissionTransaction")
                .select("*")
                .eq("agent_id", agent_record_id)
                .eq("reference_id", reference_id)
                .eq("reference_type", reference_type)
                .execute()
            )

            if existing_transaction.data:
                logger.warning(
                    f"⚠️ Commission already processed for reference: {reference_id}"
                )
                return existing_transaction.data[0]

            # Store in cedis
            commission_in_cedis = commission_amount / 100

            # Create commission transaction
            transaction = (
                supabase.table("CommissionTransaction")
                .insert(
                    {
                        "agent_id": agent_record_id,
                        "amount": commission_in_cedis,
                        "transaction_type": "EARNING",
                        "reference_id": reference_id,
                        "reference_type": reference_type,
                        "status": "COMPLETED",
                        "created_at": datetime.utcnow().isoformat(),
                        "processed_at": datetime.utcnow().isoformat(),
                    }
                )
                .execute()
            )

            # Update agent balances
            agent_update = supabase.rpc(
                "increment_agent_balances",
                {"p_user_id": agent_id, "p_amount": commission_in_cedis},
            ).execute()

            # Create activity log
            supabase.table("AgentActivity").insert(
                {
                    "agent_id": agent_record_id,
                    "activity_type": "COMMISSION_EARNED",
                    "description": f"Earned GHS {commission_in_cedis:.2f} for registered user transaction",
                    "metadata": {
                        "amount_kobo": commission_amount,
                        "amount_ghs": commission_in_cedis,
                        "reference_id": reference_id,
                        "reference_type": reference_type,
                        "transaction_id": transaction.data[0]["id"]
                        if transaction.data
                        else None,
                        "user_id": user_id,
                        "original_amount_kobo": amount,
                        "original_amount_ghs": amount / 100,
                        "commission_rate": AgentCommissionService.COMMISSION_RATE,
                        "currency": "GHS",
                    },
                    "created_at": datetime.utcnow().isoformat(),
                }
            ).execute()

            logger.info(f"✅ Commission processed successfully!")
            logger.info(f"   Agent {agent_id} earned GHS {commission_in_cedis:.2f}")

            return transaction.data[0] if transaction.data else None

        except Exception as error:
            logger.error(f"❌ Error processing agent commission: {error}")
            return None


# ===== UTILITY FUNCTIONS =====


def verify_paystack_signature(raw_body: bytes, signature: str) -> bool:
    """Verify Paystack webhook signature"""
    try:
        hash_obj = hmac.new(
            PAYSTACK_SECRET_KEY.encode("utf-8"), raw_body, hashlib.sha512
        )
        expected_signature = hash_obj.hexdigest()
        return hmac.compare_digest(expected_signature, signature)
    except Exception as error:
        logger.error(f"❌ Signature verification error: {error}")
        return False


def add_interval_to_date(date: datetime, interval: str) -> datetime:
    """Add subscription interval to date"""
    interval_map = {
        "DAILY": timedelta(days=1),
        "WEEKLY": timedelta(weeks=1),
        "MONTHLY": timedelta(days=30),
        "QUARTERLY": timedelta(days=90),
        "BIANNUALLY": timedelta(days=180),
        "ANNUALLY": timedelta(days=365),
    }
    return date + interval_map.get(interval, timedelta(days=30))


def get_referral_code_from_metadata(metadata: PaystackMetadata) -> Optional[str]:
    """Extract referral code from payment metadata"""
    try:
        logger.info("🔍 STEP 3: Checking for referral code in payment metadata")
        referral_code = metadata.referralCode

        if referral_code:
            logger.info(
                f"✅ STEP 3 FOUND: Referral code {referral_code} in payment metadata"
            )
            return referral_code

        logger.info("ℹ️ STEP 3 NO REFERRAL: No referral code found in payment metadata")
        return None
    except Exception as error:
        logger.error(
            f"❌ STEP 3 ERROR: Error checking referral code in metadata: {error}"
        )
        return None


# ===== EVENT HANDLERS =====


async def handle_charge_success(data: PaystackWebhookData):
    """Handle successful payment charge"""
    logger.info("💳 Processing charge success")
    logger.info(f"💰 Amount: {data.amount} kobo (GHS {data.amount / 100:.2f})")
    logger.info(f"🔖 Reference: {data.reference}")

    metadata = data.metadata

    if not metadata.userId:
        logger.warning("⚠️ Missing userId in charge success metadata")
        return

    # Validate user exists
    user = supabase.table("users").select("*").eq("user_id", metadata.userId).execute()

    if not user.data:
        logger.error(f"❌ User not found: {metadata.userId}")
        return

    logger.info(f"👤 User: {user.data[0]['email']} ({metadata.userId})")

    # Determine transaction type
    transaction_type = metadata.transactionType or (
        "product"
        if metadata.productId
        else "subscription"
        if metadata.subscriptionId
        else "one-time"
    )

    logger.info(f"🏷️ Transaction type: {transaction_type}")

    # Handle different transaction types
    if transaction_type == "product" and metadata.productId:
        await handle_product_purchase(data, metadata)
    elif transaction_type == "subscription" and metadata.subscriptionId:
        await handle_subscription_payment(data, metadata)
    else:
        await handle_one_time_payment(data, metadata)


async def handle_product_purchase(
    data: PaystackWebhookData, metadata: PaystackMetadata
):
    """Handle product purchase payment"""
    logger.info("🛒 Processing product purchase")
    logger.info(f"📦 Product ID: {metadata.productId}")

    try:
        # Validate user
        user = (
            supabase.table("users").select("*").eq("user_id", metadata.userId).execute()
        )

        if not user.data:
            logger.error(f"❌ User not found: {metadata.userId}")
            return

        logger.info(f"👤 User found: {user.data[0]['email']} ({metadata.userId})")

        # Get product details
        product = (
            supabase.table("products")
            .select("*")
            .eq("id", metadata.productId)
            .execute()
        )

        if not product.data:
            logger.error(f"❌ Product not found: {metadata.productId}")
            return

        product_data = product.data[0]
        logger.info(f"📦 Product: {product_data['name']}")

        # Check for duplicate purchase
        existing_purchase = (
            supabase.table("ProductPurchase")
            .select("*")
            .eq("userId", metadata.userId)
            .eq("productId", metadata.productId)
            .execute()
        )

        if existing_purchase.data:
            logger.warning(f"⚠️ Duplicate purchase detected")
            return

        # Calculate pricing (convert kobo to cedis)
        unit_price_in_cedis = data.amount / 100
        total_amount = unit_price_in_cedis

        logger.info(f"💵 Pricing: Unit price: {unit_price_in_cedis:.2f} GHS")

        # Update product quantity
        supabase.table("products").update(
            {
                "quantity": product_data["quantity"] - 1,
                "updated_at": datetime.utcnow().isoformat(),
            }
        ).eq("id", metadata.productId).execute()

        # Create purchase record
        purchase_data = {
            "id": str(uuid.uuid4()),
            "userId": metadata.userId,
            "productId": metadata.productId,
            "paymentGateway": "PAYSTACK",
            "quantity": 1,
            "totalAmount": total_amount,
            "unitPrice": unit_price_in_cedis,
            "customerName": user.data[0].get("name", ""),
            "email": user.data[0].get("email", ""),
            "createdAt": datetime.utcnow().isoformat(),
            "updatedAt": datetime.utcnow().isoformat(),
        }

        purchase = supabase.table("ProductPurchase").insert(purchase_data).execute()

        if not purchase.data:
            logger.error("❌ Failed to create ProductPurchase record")
            return

        purchase_record = purchase.data[0]
        logger.info(f"✅ Purchase record created: {purchase_record['id']}")

        # Create invoice for the purchase
        invoice_number = (
            f"INV-{int(datetime.utcnow().timestamp())}-{purchase_record['id'][:8]}"
        )

        invoice_data = {
            "id": str(uuid.uuid4()),
            "invoiceNumber": invoice_number,
            "purchaseId": purchase_record["id"],
            "sellerId": product_data["sellerId"],
            "customerEmail": user.data[0].get("email", ""),
            "customerName": user.data[0].get("name", "")
            or f"Customer {metadata.userId[:8]}",
            "subtotal": total_amount,
            "tax": 0.00,
            "discount": 0.00,
            "total": total_amount,
            "currency": "GHS",
            "status": "PAID",
            "sentAt": datetime.utcnow().isoformat(),
            "paidAt": datetime.utcnow().isoformat(),
            "createdAt": datetime.utcnow().isoformat(),
            "updatedAt": datetime.utcnow().isoformat(),
        }

        invoice = supabase.table("Invoice").insert(invoice_data).execute()

        if invoice.data:
            logger.info(f"✅ Invoice created: {invoice.data[0]['invoiceNumber']}")
        else:
            logger.error(
                f"❌ Failed to create invoice for purchase {purchase_record['id']}"
            )

        # Process agent commission
        reference_id = (
            f"product_{purchase_record['id']}_{int(datetime.utcnow().timestamp())}"
        )
        await AgentCommissionService.process_commission(
            metadata.userId, data.amount, reference_id, "SUBSCRIPTION"
        )

        logger.info("✅ Product purchase processed successfully")

    except Exception as error:
        logger.error(f"❌ Failed to process product purchase: {error}")
        raise


async def handle_subscription_payment(
    data: PaystackWebhookData, metadata: PaystackMetadata
):
    """Handle subscription payment with referral support"""
    logger.info("💰 Processing subscription payment with referral support")

    try:
        plan_id = metadata.subscriptionId
        user_id = metadata.userId
        payment_amount = data.amount  # Amount in kobo

        logger.info(f"📋 Subscription details:")
        logger.info(f"   Plan ID: {plan_id}")
        logger.info(f"   User ID: {user_id}")
        logger.info(
            f"   Payment: {payment_amount} kobo (GHS {payment_amount / 100:.2f})"
        )

        # Get plan details - try both table names
        plan = (
            supabase.table("SubscriptionPlans").select("*").eq("id", plan_id).execute()
        )
        if not plan.data:
            plan = (
                supabase.table("SubscriptionPlan")
                .select("*")
                .eq("id", plan_id)
                .execute()
            )

        if not plan.data:
            logger.error(f"❌ Subscription plan not found: {plan_id}")
            return

        plan_data = plan.data[0]
        logger.info(f"📋 Plan found: {plan_data['name']} - {plan_data['interval']}")

        # Check for recent duplicate
        recent_subscription = (
            supabase.table("UserSubscriptions")
            .select("*")
            .eq("userId", user_id)
            .eq("subscriptionPlanId", plan_id)
            .gte("createdAt", (datetime.utcnow() - timedelta(minutes=5)).isoformat())
            .execute()
        )

        # Find existing subscription (including expired ones)
        existing_subscription = (
            supabase.table("UserSubscriptions")
            .select("*")
            .eq("userId", user_id)
            .eq("subscriptionPlanId", plan_id)
            .execute()
        )

        if existing_subscription.data and not recent_subscription.data:
            # Check if expired or active
            current_expiry = datetime.fromisoformat(
                existing_subscription.data[0]["expiresAt"].replace("Z", "+00:00")
            )
            now = datetime.utcnow()

            # If expired, renew from now, otherwise extend from current expiry
            if current_expiry <= now:
                logger.info("🔄 Renewing expired subscription from now")
                new_expiry_date = add_interval_to_date(now, plan_data["interval"])
            else:
                logger.info("🔄 Extending active subscription from current expiry")
                new_expiry_date = add_interval_to_date(
                    current_expiry, plan_data["interval"]
                )

            supabase.table("UserSubscriptions").update(
                {
                    "expiresAt": new_expiry_date.isoformat(),
                    "updatedAt": datetime.utcnow().isoformat(),
                }
            ).eq("id", existing_subscription.data[0]["id"]).execute()

            logger.info(f"✅ Subscription renewed until: {new_expiry_date.isoformat()}")

            # Process commission for renewal
            reference_id = (
                f"renewal_{existing_subscription.data[0]['id']}_{data.reference}"
            )
            await AgentCommissionService.process_commission(
                user_id, payment_amount, reference_id, "SUBSCRIPTION"
            )

        elif not recent_subscription.data:
            # New subscription
            logger.info("🆕 Creating new subscription")
            expiry_date = add_interval_to_date(datetime.utcnow(), plan_data["interval"])

            new_subscription = (
                supabase.table("UserSubscriptions")
                .insert(
                    {
                        "subscriptionPlanId": plan_id,
                        "userId": user_id,
                        "expiresAt": expiry_date.isoformat(),
                        "createdAt": datetime.utcnow().isoformat(),
                        "updatedAt": datetime.utcnow().isoformat(),
                    }
                )
                .execute()
            )

            subscription_id = (
                new_subscription.data[0]["id"] if new_subscription.data else None
            )
            logger.info(f"✅ New subscription created: {subscription_id}")

            # Process regular commission for new subscription
            reference_id = f"new_sub_{subscription_id}_{data.reference}"
            await AgentCommissionService.process_commission(
                user_id, payment_amount, reference_id, "SUBSCRIPTION"
            )

            # Check for referral commission
            logger.info("🔄 STEP 6: Checking for referral commission...")
            referral_code = get_referral_code_from_metadata(metadata)

            if referral_code:
                logger.info(f"🎯 STEP 6: Found referral code: {referral_code}")
                referral_reference_id = (
                    f"referral_subscription_{subscription_id}_{data.reference}"
                )
                await AgentCommissionService.process_referral_commission(
                    user_id,
                    payment_amount,
                    referral_code,
                    referral_reference_id,
                    "SUBSCRIPTION",
                )
            else:
                logger.info(
                    "ℹ️ STEP 6: No referral code found - skipping referral commission"
                )

        else:
            logger.warning(f"⚠️ Recent subscription already processed")

    except Exception as error:
        logger.error(f"❌ Failed to process subscription payment: {error}")
        raise


async def handle_one_time_payment(
    data: PaystackWebhookData, metadata: PaystackMetadata
):
    """Handle one-time payment"""
    logger.info("💳 Processing one-time payment")

    try:
        logger.info(f"💰 One-time payment: GHS {data.amount / 100:.2f}")

        # Process agent commission
        reference_id = f"onetime_{data.reference}_{int(datetime.utcnow().timestamp())}"
        await AgentCommissionService.process_commission(
            metadata.userId, data.amount, reference_id, "SUBSCRIPTION"
        )

        logger.info("✅ One-time payment processed successfully")

    except Exception as error:
        logger.error(f"❌ Failed to process one-time payment: {error}")
        raise


# ===== WEBHOOK ENDPOINT =====


@router.post("/paystack")
async def paystack_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Paystack webhook endpoint - handles all Paystack payment events
    Supports subscriptions, products, and referral commissions
    """
    start_time = datetime.utcnow()
    logger.info(f"🔄 Webhook received at: {start_time.isoformat()}")

    try:
        # Get raw body and signature
        raw_body = await request.body()
        signature = request.headers.get("x-paystack-signature", "")
        user_agent = request.headers.get("user-agent", "")

        logger.info("📝 Request details:")
        logger.info(f"   Body length: {len(raw_body)}")
        logger.info(f"   Signature: {'Present' if signature else 'Missing'}")
        logger.info(f"   User Agent: {user_agent}")

        # Verify signature
        if not verify_paystack_signature(raw_body, signature):
            logger.error("❌ Invalid Paystack signature")
            raise HTTPException(status_code=401, detail="Invalid signature")

        logger.info("✅ Signature verified")

        # Parse body
        try:
            import json

            body = json.loads(raw_body.decode("utf-8"))
        except Exception as parse_error:
            logger.error(f"❌ Failed to parse webhook body: {parse_error}")
            raise HTTPException(status_code=400, detail="Invalid JSON")

        if not body.get("event") or not body.get("data"):
            logger.error("❌ Invalid webhook payload structure")
            raise HTTPException(status_code=400, detail="Invalid payload")

        event = body["event"]
        logger.info(f"📨 Processing event: {event}")

        # Process event in background
        background_tasks.add_task(process_webhook_event, body)

        processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        logger.info(f"⚡ Webhook acknowledged in {processing_time:.0f}ms")

        return {
            "received": True,
            "event": event,
            "processingTime": processing_time,
            "timestamp": datetime.utcnow().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as error:
        processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        logger.error(f"❌ Webhook processing error: {error}")
        logger.error(f"⏱️  Failed after {processing_time:.0f}ms")
        raise HTTPException(status_code=500, detail="Server error")


async def process_webhook_event(body: dict):
    """Process webhook event in background"""
    event_start_time = datetime.utcnow()

    try:
        logger.info(f"🔄 Processing {body['event']} event")
        logger.info(f"📊 Event processing started at: {event_start_time.isoformat()}")

        event = body["event"]
        data_dict = body["data"]

        # Convert to Pydantic model
        try:
            data = PaystackWebhookData(**data_dict)
        except Exception as validation_error:
            logger.error(f"❌ Webhook data validation error: {validation_error}")
            return

        # Route to appropriate handler
        if event == WEBHOOK_EVENTS["CHARGE_SUCCESS"]:
            await handle_charge_success(data)
        elif event == WEBHOOK_EVENTS["SUBSCRIPTION_CREATE"]:
            await handle_subscription_payment(data, data.metadata)
        elif event == WEBHOOK_EVENTS["INVOICE_UPDATE"]:
            if data.status == "success" and data.metadata.subscriptionId:
                await handle_subscription_payment(data, data.metadata)
        else:
            logger.info(f"⚠️ Unhandled event type: {event}")

        processing_time = (datetime.utcnow() - event_start_time).total_seconds() * 1000
        logger.info(
            f"✅ Event {event} processed successfully in {processing_time:.0f}ms"
        )

    except Exception as error:
        processing_time = (datetime.utcnow() - event_start_time).total_seconds() * 1000
        logger.error(
            f"❌ Event {body['event']} processing failed after {processing_time:.0f}ms: {error}"
        )


# ===== HEALTH CHECK =====


@router.get("/paystack/health")
async def webhook_health_check():
    """Health check endpoint for webhook"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "webhook_events": list(WEBHOOK_EVENTS.values()),
        "version": "2.0.0",
    }
