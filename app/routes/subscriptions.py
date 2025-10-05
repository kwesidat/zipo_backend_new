from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import List, Optional
from pydantic import BaseModel
from app.database import supabase
from app.utils.auth_utils import AuthUtils
from app.utils.subscription_utils import check_user_subscription
import logging

logger = logging.getLogger(__name__)

router = APIRouter()
security = HTTPBearer(auto_error=False)


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

# Table name constant
SUBSCRIPTION_PLAN_TABLE = "SubscriptionPlans"


# Pydantic Models
class SubscriptionPlanBase(BaseModel):
    name: str
    description: Optional[str] = None
    subscriptionTier: str
    amount: float
    currency: str = "GHS"
    interval: str
    planCode: Optional[str] = None
    region: str
    platformCut: Optional[float] = None


class SubscriptionPlanResponse(SubscriptionPlanBase):
    id: str
    createdAt: str
    updatedAt: str

    class Config:
        from_attributes = True


class SubscriptionPlanFilter(BaseModel):
    tier: Optional[str] = None
    region: Optional[str] = None
    interval: Optional[str] = None


@router.get(
    "/subscription-plans",
    response_model=List[SubscriptionPlanResponse],
    summary="Get all subscription plans",
    description="Retrieve all available subscription plans with optional filtering"
)
async def get_all_subscription_plans(
    tier: Optional[str] = None,
    region: Optional[str] = None,
    interval: Optional[str] = None
):
    """
    Get all subscription plans with optional filters.

    - **tier**: Filter by subscription tier (LEVEL1, LEVEL2, LEVEL3)
    - **region**: Filter by region (GHANA, INTERNATIONAL)
    - **interval**: Filter by billing interval (DAILY, WEEKLY, MONTHLY, QUARTERLY, BIANNUALLY, ANNUALLY)
    """
    try:
        # Build Supabase query
        query = supabase.table(SUBSCRIPTION_PLAN_TABLE).select("*")

        # Apply filters
        if tier:
            query = query.eq("subscriptionTier", tier)

        if region:
            query = query.eq("region", region)

        if interval:
            query = query.eq("interval", interval)

        # Execute query with ordering
        response = query.order("amount", desc=False).execute()

        if not response.data:
            return []

        # Convert to response format
        result = []
        for plan in response.data:
            result.append({
                "id": plan["id"],
                "name": plan["name"],
                "description": plan.get("description"),
                "subscriptionTier": plan["subscriptionTier"],
                "amount": float(plan["amount"]),
                "currency": plan.get("currency", "GHS"),
                "interval": plan["interval"],
                "planCode": plan.get("planCode"),
                "region": plan["region"],
                "platformCut": plan.get("platformCut"),
                "createdAt": plan["createdAt"],
                "updatedAt": plan["updatedAt"]
            })

        logger.info(f"Retrieved {len(result)} subscription plans")
        return result

    except Exception as e:
        logger.error(f"Error fetching subscription plans: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch subscription plans: {str(e)}"
        )


@router.get(
    "/subscription-plans/{plan_id}",
    response_model=SubscriptionPlanResponse,
    summary="Get subscription plan by ID",
    description="Retrieve a specific subscription plan by its ID"
)
async def get_subscription_plan_by_id(plan_id: str):
    """
    Get a specific subscription plan by ID.

    - **plan_id**: The unique identifier of the subscription plan
    """
    try:
        # Query Supabase
        response = supabase.table(SUBSCRIPTION_PLAN_TABLE).select("*").eq("id", plan_id).execute()

        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Subscription plan with ID {plan_id} not found"
            )

        plan = response.data[0]

        return {
            "id": plan["id"],
            "name": plan["name"],
            "description": plan.get("description"),
            "subscriptionTier": plan["subscriptionTier"],
            "amount": float(plan["amount"]),
            "currency": plan.get("currency", "GHS"),
            "interval": plan["interval"],
            "planCode": plan["planCode"],
            "region": plan["region"],
            "createdAt": plan["createdAt"],
            "updatedAt": plan["updatedAt"]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching subscription plan {plan_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch subscription plan: {str(e)}"
        )


@router.get(
    "/subscription-plans/tier/{tier}",
    response_model=List[SubscriptionPlanResponse],
    summary="Get subscription plans by tier",
    description="Retrieve all subscription plans for a specific tier"
)
async def get_subscription_plans_by_tier(
    tier: str,
    region: Optional[str] = None
):
    """
    Get all subscription plans for a specific tier.

    - **tier**: Subscription tier (LEVEL1, LEVEL2, LEVEL3)
    - **region**: Optional region filter (GHANA, INTERNATIONAL)
    """
    try:
        # Build Supabase query
        query = supabase.table(SUBSCRIPTION_PLAN_TABLE).select("*").eq("subscriptionTier", tier)

        if region:
            query = query.eq("region", region)

        # Execute query with ordering
        response = query.order("amount", desc=False).execute()

        if not response.data:
            return []

        result = []
        for plan in response.data:
            result.append({
                "id": plan["id"],
                "name": plan["name"],
                "description": plan.get("description"),
                "subscriptionTier": plan["subscriptionTier"],
                "amount": float(plan["amount"]),
                "currency": plan.get("currency", "GHS"),
                "interval": plan["interval"],
                "planCode": plan.get("planCode"),
                "region": plan["region"],
                "platformCut": plan.get("platformCut"),
                "createdAt": plan["createdAt"],
                "updatedAt": plan["updatedAt"]
            })

        logger.info(f"Retrieved {len(result)} subscription plans for tier {tier}")
        return result

    except Exception as e:
        logger.error(f"Error fetching subscription plans for tier {tier}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch subscription plans: {str(e)}"
        )


@router.get(
    "/subscription-plans/region/{region}",
    response_model=List[SubscriptionPlanResponse],
    summary="Get subscription plans by region",
    description="Retrieve all subscription plans for a specific region"
)
async def get_subscription_plans_by_region(region: str):
    """
    Get all subscription plans for a specific region.

    - **region**: Region name (GHANA, INTERNATIONAL)
    """
    try:
        # Query Supabase
        response = (supabase.table(SUBSCRIPTION_PLAN_TABLE)
                   .select("*")
                   .eq("region", region)
                   .order("subscriptionTier", desc=False)
                   .order("amount", desc=False)
                   .execute())

        if not response.data:
            return []

        result = []
        for plan in response.data:
            result.append({
                "id": plan["id"],
                "name": plan["name"],
                "description": plan.get("description"),
                "subscriptionTier": plan["subscriptionTier"],
                "amount": float(plan["amount"]),
                "currency": plan.get("currency", "GHS"),
                "interval": plan["interval"],
                "planCode": plan.get("planCode"),
                "region": plan["region"],
                "platformCut": plan.get("platformCut"),
                "createdAt": plan["createdAt"],
                "updatedAt": plan["updatedAt"]
            })

        logger.info(f"Retrieved {len(result)} subscription plans for region {region}")
        return result

    except Exception as e:
        logger.error(f"Error fetching subscription plans for region {region}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch subscription plans: {str(e)}"
        )


@router.get(
    "/subscription/status",
    summary="Get user's current subscription status",
    description="Get the current user's subscription status and details"
)
async def get_user_subscription_status(current_user = Depends(get_required_user)):
    """
    Get the current user's subscription status.

    Returns subscription details including:
    - Active status
    - Plan details
    - Expiry date
    - Product limits
    """
    try:
        user_id = current_user["user_id"]

        # Check subscription using existing utility
        subscription_check = await check_user_subscription(user_id)

        # Get plan details if subscription exists
        plan_details = None
        if subscription_check.get("subscription"):
            plan_id = subscription_check["subscription"].get("subscriptionPlanId")
            if plan_id:
                plan_response = supabase.table(SUBSCRIPTION_PLAN_TABLE).select("*").eq(
                    "id", plan_id
                ).execute()

                if plan_response.data:
                    plan = plan_response.data[0]
                    plan_details = {
                        "id": plan["id"],
                        "name": plan["name"],
                        "description": plan.get("description"),
                        "subscriptionTier": plan["subscriptionTier"],
                        "amount": float(plan["amount"]),
                        "currency": plan.get("currency", "GHS"),
                        "interval": plan["interval"],
                        "region": plan["region"]
                    }

        return {
            "has_subscription": subscription_check["has_subscription"],
            "can_create_product": subscription_check["can_create_product"],
            "max_products": subscription_check.get("max_products"),
            "current_products": subscription_check.get("current_products", 0),
            "expires_at": subscription_check.get("subscription", {}).get("expiresAt") if subscription_check.get("subscription") else None,
            "plan": plan_details,
            "message": subscription_check.get("message")
        }

    except Exception as e:
        logger.error(f"Error fetching user subscription status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch subscription status"
        )