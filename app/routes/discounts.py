from fastapi import APIRouter, HTTPException, status, Query, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.models.discounts import (
    DiscountCreate, DiscountUpdate, DiscountResponse, DiscountListItem,
    DiscountsListResponse, DiscountStatus, DiscountStatusUpdate,
    DiscountProductsRequest, DiscountProductsResponse, DiscountCreateResponse,
    DiscountProductItem
)
from app.database import supabase
from app.utils.auth_utils import AuthUtils
from typing import Optional
from datetime import datetime
import logging
import math
import uuid

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

@router.post("/discounts", response_model=DiscountCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_discount(
    discount: DiscountCreate,
    current_user = Depends(get_required_user)
):
    """Create a new discount and apply it to selected products"""
    try:
        # Check if discount code already exists for this user
        existing = supabase.table("Discount").select("id").eq("userId", current_user["user_id"]).eq("code", discount.code).execute()
        if existing.data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Discount code '{discount.code}' already exists"
            )

        # Verify all products exist and belong to the user
        products_response = supabase.table("products").select("id, sellerId").in_("id", discount.productIds).execute()

        if len(products_response.data) != len(discount.productIds):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="One or more product IDs are invalid"
            )

        # Check all products belong to the seller
        for product in products_response.data:
            if product["sellerId"] != current_user["user_id"]:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only create discounts for your own products"
                )

        # Create the discount
        discount_id = str(uuid.uuid4())
        discount_data = {
            "id": discount_id,
            "code": discount.code,
            "percentage": discount.percentage,
            "description": discount.description,
            "limit": discount.limit,
            "showOnPlatform": discount.showOnPlatform,
            "expiresAt": discount.expiresAt.isoformat() if discount.expiresAt else None,
            "status": DiscountStatus.ENABLED.value,
            "userId": current_user["user_id"],
            "createdAt": datetime.utcnow().isoformat(),
            "updatedAt": datetime.utcnow().isoformat()
        }

        response = supabase.table("Discount").insert(discount_data).execute()

        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create discount"
            )

        created_discount = response.data[0]

        # Apply discount to products
        discount_products = []
        for product_id in discount.productIds:
            discount_products.append({
                "productId": product_id,
                "discountId": discount_id,
                "appliedAt": datetime.utcnow().isoformat()
            })

        supabase.table("DiscountOnProduct").insert(discount_products).execute()

        return DiscountCreateResponse(
            id=created_discount["id"],
            code=created_discount["code"],
            percentage=created_discount["percentage"],
            description=created_discount.get("description"),
            expiresAt=created_discount.get("expiresAt"),
            limit=created_discount.get("limit"),
            showOnPlatform=created_discount["showOnPlatform"],
            status=DiscountStatus(created_discount["status"]),
            userId=created_discount["userId"],
            createdAt=created_discount["createdAt"],
            updatedAt=created_discount["updatedAt"],
            appliedProducts=len(discount.productIds)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating discount: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create discount: {str(e)}"
        )

@router.get("/discounts/my-discounts", response_model=DiscountsListResponse)
async def get_my_discounts(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    status_filter: Optional[DiscountStatus] = Query(None, description="Filter by status"),
    current_user = Depends(get_required_user)
):
    """Get discounts created by the current user"""
    try:
        # Build query
        query = supabase.table("Discount").select("*").eq("userId", current_user["user_id"])

        if status_filter:
            query = query.eq("status", status_filter.value)

        query = query.order("createdAt", desc=True)

        # Get total count
        count_query = supabase.table("Discount").select("id", count="exact").eq("userId", current_user["user_id"])
        if status_filter:
            count_query = count_query.eq("status", status_filter.value)

        count_response = count_query.execute()
        total_count = count_response.count or 0

        # Apply pagination
        offset = (page - 1) * page_size
        query = query.range(offset, offset + page_size - 1)

        response = query.execute()

        if not response.data:
            return DiscountsListResponse(
                discounts=[],
                total_count=total_count,
                page=page,
                page_size=page_size,
                total_pages=0,
                has_next=False,
                has_previous=page > 1
            )

        # Get product counts and usage counts for each discount
        discount_ids = [d["id"] for d in response.data]

        # Get applied products count
        products_count = {}
        if discount_ids:
            products_response = supabase.table("DiscountOnProduct").select("discountId").in_("discountId", discount_ids).execute()
            for item in products_response.data:
                discount_id = item["discountId"]
                products_count[discount_id] = products_count.get(discount_id, 0) + 1

        # Get usage count
        usage_count = {}
        if discount_ids:
            usage_response = supabase.table("ProductPurchase").select("discountId").in_("discountId", discount_ids).execute()
            for item in usage_response.data:
                discount_id = item["discountId"]
                usage_count[discount_id] = usage_count.get(discount_id, 0) + 1

        discounts_list = []
        for discount in response.data:
            discounts_list.append(DiscountListItem(
                id=discount["id"],
                code=discount["code"],
                percentage=discount["percentage"],
                description=discount.get("description"),
                status=DiscountStatus(discount["status"]),
                limit=discount.get("limit"),
                usedCount=usage_count.get(discount["id"], 0),
                showOnPlatform=discount["showOnPlatform"],
                expiresAt=discount.get("expiresAt"),
                createdAt=discount["createdAt"],
                appliedProductsCount=products_count.get(discount["id"], 0)
            ))

        total_pages = math.ceil(total_count / page_size) if total_count > 0 else 0

        return DiscountsListResponse(
            discounts=discounts_list,
            total_count=total_count,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_previous=page > 1
        )

    except Exception as e:
        logger.error(f"Error fetching discounts: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch discounts"
        )

@router.get("/discounts/{discount_id}", response_model=DiscountResponse)
async def get_discount_by_id(
    discount_id: str,
    current_user = Depends(get_required_user)
):
    """Get discount details with applied products"""
    try:
        # Get discount
        discount_response = supabase.table("Discount").select("*").eq("id", discount_id).execute()

        if not discount_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Discount not found"
            )

        discount = discount_response.data[0]

        # Check ownership
        if discount["userId"] != current_user["user_id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view your own discounts"
            )

        # Get applied products
        products_response = supabase.table("DiscountOnProduct").select("""
            appliedAt,
            product:products(id, name, price, currency, photos)
        """).eq("discountId", discount_id).execute()

        products_list = []
        for item in products_response.data:
            product = item.get("product")
            if product:
                products_list.append(DiscountProductItem(
                    id=product["id"],
                    name=product["name"],
                    price=float(product["price"]),
                    currency=product["currency"],
                    photos=product.get("photos", []),
                    appliedAt=item["appliedAt"]
                ))

        # Get usage count
        usage_response = supabase.table("ProductPurchase").select("id", count="exact").eq("discountId", discount_id).execute()
        usage_count = usage_response.count or 0

        return DiscountResponse(
            id=discount["id"],
            code=discount["code"],
            percentage=discount["percentage"],
            description=discount.get("description"),
            status=DiscountStatus(discount["status"]),
            limit=discount.get("limit"),
            usedCount=usage_count,
            showOnPlatform=discount["showOnPlatform"],
            expiresAt=discount.get("expiresAt"),
            createdAt=discount["createdAt"],
            updatedAt=discount["updatedAt"],
            products=products_list
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching discount {discount_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch discount details"
        )

@router.put("/discounts/{discount_id}", response_model=DiscountResponse)
async def update_discount(
    discount_id: str,
    discount_update: DiscountUpdate,
    current_user = Depends(get_required_user)
):
    """Update discount details"""
    try:
        # Check if discount exists and belongs to user
        existing = supabase.table("Discount").select("*").eq("id", discount_id).execute()

        if not existing.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Discount not found"
            )

        if existing.data[0]["userId"] != current_user["user_id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only update your own discounts"
            )

        # Build update data
        update_data = {}
        if discount_update.description is not None:
            update_data["description"] = discount_update.description
        if discount_update.percentage is not None:
            update_data["percentage"] = discount_update.percentage
        if discount_update.limit is not None:
            update_data["limit"] = discount_update.limit
        if discount_update.showOnPlatform is not None:
            update_data["showOnPlatform"] = discount_update.showOnPlatform
        if discount_update.expiresAt is not None:
            update_data["expiresAt"] = discount_update.expiresAt.isoformat()

        update_data["updatedAt"] = datetime.utcnow().isoformat()

        # Update discount
        response = supabase.table("Discount").update(update_data).eq("id", discount_id).execute()

        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update discount"
            )

        # Fetch updated discount with products
        return await get_discount_by_id(discount_id, current_user)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating discount {discount_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update discount"
        )

@router.post("/discounts/{discount_id}/products", response_model=DiscountProductsResponse)
async def add_products_to_discount(
    discount_id: str,
    request: DiscountProductsRequest,
    current_user = Depends(get_required_user)
):
    """Add products to an existing discount"""
    try:
        # Check discount ownership
        discount = supabase.table("Discount").select("userId").eq("id", discount_id).execute()

        if not discount.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Discount not found"
            )

        if discount.data[0]["userId"] != current_user["user_id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only modify your own discounts"
            )

        # Verify products exist and belong to user
        products = supabase.table("products").select("id, sellerId").in_("id", request.productIds).execute()

        if len(products.data) != len(request.productIds):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="One or more product IDs are invalid"
            )

        for product in products.data:
            if product["sellerId"] != current_user["user_id"]:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only add your own products to discounts"
                )

        # Check which products are already applied
        existing = supabase.table("DiscountOnProduct").select("productId").eq("discountId", discount_id).in_("productId", request.productIds).execute()
        existing_product_ids = {item["productId"] for item in existing.data}

        # Add only new products
        new_products = [pid for pid in request.productIds if pid not in existing_product_ids]

        if new_products:
            discount_products = [
                {
                    "productId": pid,
                    "discountId": discount_id,
                    "appliedAt": datetime.utcnow().isoformat()
                }
                for pid in new_products
            ]
            supabase.table("DiscountOnProduct").insert(discount_products).execute()

        # Get total count
        total = supabase.table("DiscountOnProduct").select("productId", count="exact").eq("discountId", discount_id).execute()

        return DiscountProductsResponse(
            message="Products added to discount",
            addedCount=len(new_products),
            totalProducts=total.count or 0
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding products to discount: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add products to discount"
        )

@router.delete("/discounts/{discount_id}/products")
async def remove_products_from_discount(
    discount_id: str,
    request: DiscountProductsRequest,
    current_user = Depends(get_required_user)
):
    """Remove products from a discount"""
    try:
        # Check discount ownership
        discount = supabase.table("Discount").select("userId").eq("id", discount_id).execute()

        if not discount.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Discount not found"
            )

        if discount.data[0]["userId"] != current_user["user_id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only modify your own discounts"
            )

        # Remove products
        for product_id in request.productIds:
            supabase.table("DiscountOnProduct").delete().eq("discountId", discount_id).eq("productId", product_id).execute()

        return {"message": "Products removed from discount", "removedCount": len(request.productIds)}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing products from discount: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to remove products from discount"
        )

@router.patch("/discounts/{discount_id}/status", response_model=DiscountResponse)
async def update_discount_status(
    discount_id: str,
    status_update: DiscountStatusUpdate,
    current_user = Depends(get_required_user)
):
    """Enable or disable a discount"""
    try:
        # Check discount ownership
        discount = supabase.table("Discount").select("userId, status").eq("id", discount_id).execute()

        if not discount.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Discount not found"
            )

        if discount.data[0]["userId"] != current_user["user_id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only modify your own discounts"
            )

        # Don't allow enabling expired discounts
        if discount.data[0]["status"] == DiscountStatus.EXPIRED.value and status_update.status == DiscountStatus.ENABLED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot enable an expired discount"
            )

        # Update status
        update_data = {
            "status": status_update.status.value,
            "updatedAt": datetime.utcnow().isoformat()
        }

        if status_update.status == DiscountStatus.DISABLED:
            update_data["disabledAt"] = datetime.utcnow().isoformat()

        supabase.table("Discount").update(update_data).eq("id", discount_id).execute()

        # Return updated discount
        return await get_discount_by_id(discount_id, current_user)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating discount status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update discount status"
        )

@router.delete("/discounts/{discount_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_discount(
    discount_id: str,
    current_user = Depends(get_required_user)
):
    """Delete a discount"""
    try:
        # Check discount ownership
        discount = supabase.table("Discount").select("userId").eq("id", discount_id).execute()

        if not discount.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Discount not found"
            )

        if discount.data[0]["userId"] != current_user["user_id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only delete your own discounts"
            )

        # Delete discount (cascade will remove DiscountOnProduct entries)
        supabase.table("Discount").delete().eq("id", discount_id).execute()

        return None

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting discount: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete discount"
        )
