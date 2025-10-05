from app.database import supabase
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


async def check_user_subscription(user_id: str) -> dict:
    """
    Check if a user has an active subscription.

    Returns:
        dict with keys:
        - has_subscription: bool
        - subscription: dict or None
        - max_products: int or None
        - can_create_product: bool
    """
    # Subscription plan limits mapping
    SUBSCRIPTION_LIMITS = {
        "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11": {"name": "Basic Seller", "max_products": 5},
        "a1eebc99-9c0b-4ef8-bb6d-6bb9bd380a11": {"name": "Professional Seller", "max_products": 10},
        "a2eebc99-9c0b-4ef8-bb6d-6bb9bd380a11": {"name": "Enterprise Seller", "max_products": None},  # Unlimited
    }

    try:
        # Check if UserSubscription table exists and get active subscription
        subscription_response = supabase.table("UserSubscriptions").select("*").eq("userId", user_id).execute()

        logger.info(f"Subscription response for user {user_id}: {subscription_response.data}")

        if not subscription_response.data or len(subscription_response.data) == 0:
            return {
                "has_subscription": False,
                "subscription": None,
                "max_products": 0,
                "can_create_product": False,
                "message": "No active subscription found. Please subscribe to create products."
            }

        # Find the most recent non-expired subscription
        subscription = None
        current_time = datetime.utcnow()

        # Sort subscriptions by expiresAt descending to get the latest first
        sorted_subscriptions = sorted(
            subscription_response.data,
            key=lambda x: x.get("expiresAt", ""),
            reverse=True
        )

        for sub in sorted_subscriptions:
            if sub.get("expiresAt"):
                end_date = datetime.fromisoformat(sub["expiresAt"].replace("Z", "+00:00"))
                # Convert current_time to the same timezone
                if end_date.tzinfo:
                    current_time_tz = datetime.now(end_date.tzinfo)
                else:
                    current_time_tz = datetime.utcnow()

                if end_date >= current_time_tz:
                    subscription = sub
                    logger.info(f"Found active subscription: {subscription}")
                    break

        # If no active subscription found, all are expired
        if not subscription:
            logger.info("All subscriptions are expired")
            return {
                "has_subscription": False,
                "subscription": sorted_subscriptions[0] if sorted_subscriptions else None,
                "max_products": 0,
                "can_create_product": False,
                "message": "Your subscription has expired. Please renew to create products."
            }

        # Get subscription plan ID and limits
        plan_id = subscription.get("subscriptionPlanId")
        logger.info(f"Plan ID from subscription: {plan_id}")
        plan_limits = SUBSCRIPTION_LIMITS.get(plan_id)

        if not plan_limits:
            logger.warning(f"Unknown subscription plan ID: {plan_id}. Available plans: {list(SUBSCRIPTION_LIMITS.keys())}")
            return {
                "has_subscription": True,
                "subscription": subscription,
                "max_products": 0,
                "can_create_product": False,
                "message": f"Invalid subscription plan ({plan_id}). Please contact support."
            }

        max_products = plan_limits["max_products"]

        if max_products is None:
            # Unlimited products (Enterprise)
            return {
                "has_subscription": True,
                "subscription": subscription,
                "max_products": None,
                "can_create_product": True,
                "message": "Unlimited products allowed"
            }

        # Check current product count
        product_count_response = supabase.table("products").select("id", count="exact").eq("sellerId", user_id).execute()
        current_product_count = product_count_response.count or 0

        can_create = current_product_count < max_products

        return {
            "has_subscription": True,
            "subscription": subscription,
            "max_products": max_products,
            "current_products": current_product_count,
            "can_create_product": can_create,
            "message": f"You have {current_product_count}/{max_products} products" if not can_create else "Can create product"
        }

    except Exception as e:
        logger.error(f"Error checking user subscription: {str(e)}")
        # If table doesn't exist or other error, allow product creation (graceful fallback)
        logger.warning("UserSubscription table may not exist. Allowing product creation.")
        return {
            "has_subscription": True,
            "subscription": None,
            "max_products": None,
            "can_create_product": True,
            "message": "Subscription check unavailable, allowing creation"
        }
