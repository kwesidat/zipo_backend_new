from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.models.cart import (
    CartItemAdd, CartItemUpdate, CartItemResponse,
    CartResponse, CartSummary
)
from app.database import supabase
from app.utils.auth_utils import AuthUtils
from typing import Optional
from datetime import datetime
from decimal import Decimal
import logging
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

def calculate_cart_totals(items: list) -> dict:
    """Calculate cart totals from items"""
    subtotal = Decimal('0')
    item_count = 0

    for item in items:
        subtotal += Decimal(str(item["price"])) * item["quantity"]
        item_count += item["quantity"]

    # Tax calculation (example: 10%)
    tax = subtotal * Decimal('0.10')
    total = subtotal + tax

    return {
        "subtotal": subtotal,
        "itemCount": item_count,
        "tax": tax,
        "total": total
    }

@router.post("/cart/items", response_model=CartResponse, status_code=status.HTTP_201_CREATED)
async def add_to_cart(
    item: CartItemAdd,
    current_user = Depends(get_required_user)
):
    """Add a product to the cart"""
    try:
        user_id = current_user["user_id"]

        # Get product details
        product_response = supabase.table("products").select("""
            id, name, price, currency, condition, photos, quantity,
            country, sellerId, users!products_sellerId_fkey(name, business_name)
        """).eq("id", item.productId).execute()

        if not product_response.data or len(product_response.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product not found"
            )

        product = product_response.data[0]

        # Check if product is available
        if product["quantity"] < item.quantity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Only {product['quantity']} items available"
            )

        # Get or create cart
        cart_response = supabase.table("Cart").select("*").eq("userId", user_id).execute()

        if not cart_response.data or len(cart_response.data) == 0:
            # Create new cart
            cart_data = {
                "id": str(uuid.uuid4()),
                "userId": user_id,
                "currency": product["currency"],
                "subtotal": "0.00",
                "tax": "0.00",
                "total": "0.00",
                "discountAmount": "0.00",
                "itemCount": 0,
                "createdAt": datetime.utcnow().isoformat(),
                "updatedAt": datetime.utcnow().isoformat()
            }
            cart_response = supabase.table("Cart").insert(cart_data).execute()
            if not cart_response.data:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to create cart"
                )
            cart = cart_response.data[0]
        else:
            cart = cart_response.data[0]

        cart_id = cart["id"]

        # Check if item already exists in cart
        existing_item_response = supabase.table("CartItem").select("*").eq("cartId", cart_id).eq("productId", item.productId).execute()

        seller_name = product.get("users", {}).get("business_name") or product.get("users", {}).get("name")

        if existing_item_response.data and len(existing_item_response.data) > 0:
            # Update quantity
            existing_item = existing_item_response.data[0]
            new_quantity = existing_item["quantity"] + item.quantity

            if new_quantity > product["quantity"]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot add more. Only {product['quantity']} items available"
                )

            update_data = {
                "quantity": new_quantity,
                "updatedAt": datetime.utcnow().isoformat()
            }
            supabase.table("CartItem").update(update_data).eq("id", existing_item["id"]).execute()
        else:
            # Create new cart item
            cart_item_data = {
                "id": str(uuid.uuid4()),
                "cartId": cart_id,
                "productId": item.productId,
                "quantity": item.quantity,
                "price": str(product["price"]),
                "condition": product.get("condition"),
                "image": product.get("photos", [None])[0] if product.get("photos") else None,
                "location": product.get("country"),
                "maxQuantity": product.get("quantity"),
                "sellerId": product.get("sellerId"),
                "sellerName": seller_name,
                "title": product.get("name"),
                "createdAt": datetime.utcnow().isoformat(),
                "updatedAt": datetime.utcnow().isoformat()
            }
            supabase.table("CartItem").insert(cart_item_data).execute()

        # Get updated cart with items
        cart_items_response = supabase.table("CartItem").select("*").eq("cartId", cart_id).execute()
        cart_items = cart_items_response.data

        # Calculate totals
        totals = calculate_cart_totals(cart_items)

        # Update cart totals
        cart_update = {
            "itemCount": totals["itemCount"],
            "subtotal": str(totals["subtotal"]),
            "tax": str(totals["tax"]),
            "total": str(totals["total"]),
            "updatedAt": datetime.utcnow().isoformat()
        }
        supabase.table("Cart").update(cart_update).eq("id", cart_id).execute()

        # Get final cart state
        return await get_cart(current_user)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding to cart: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add item to cart"
        )

@router.get("/cart", response_model=CartResponse)
async def get_cart(current_user = Depends(get_required_user)):
    """Get user's cart"""
    try:
        user_id = current_user["user_id"]

        # Get cart
        cart_response = supabase.table("Cart").select("*").eq("userId", user_id).execute()

        if not cart_response.data or len(cart_response.data) == 0:
            # Return empty cart
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cart is empty"
            )

        cart = cart_response.data[0]

        # Get cart items
        cart_items_response = supabase.table("CartItem").select("*").eq("cartId", cart["id"]).execute()
        cart_items = cart_items_response.data

        # Convert items to response format
        items = [
            CartItemResponse(
                id=item["id"],
                cartId=item["cartId"],
                productId=item["productId"],
                quantity=item["quantity"],
                price=Decimal(str(item["price"])),
                condition=item.get("condition"),
                image=item.get("image"),
                location=item.get("location"),
                maxQuantity=item.get("maxQuantity"),
                sellerId=item.get("sellerId"),
                sellerName=item.get("sellerName"),
                title=item.get("title"),
                createdAt=item["createdAt"],
                updatedAt=item["updatedAt"]
            )
            for item in cart_items
        ]

        return CartResponse(
            id=cart["id"],
            userId=cart["userId"],
            currency=cart["currency"],
            discountAmount=Decimal(str(cart["discountAmount"])),
            itemCount=cart["itemCount"],
            subtotal=Decimal(str(cart["subtotal"])),
            tax=Decimal(str(cart["tax"])),
            total=Decimal(str(cart["total"])),
            items=items,
            createdAt=cart["createdAt"],
            updatedAt=cart["updatedAt"]
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting cart: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get cart"
        )

@router.put("/cart/items/{item_id}", response_model=CartResponse)
async def update_cart_item_quantity(
    item_id: str,
    update: CartItemUpdate,
    current_user = Depends(get_required_user)
):
    """Update cart item quantity"""
    try:
        user_id = current_user["user_id"]

        # Get cart item
        cart_item_response = supabase.table("CartItem").select("*, Cart!inner(userId)").eq("id", item_id).execute()

        logger.info(f"Cart item response data: {cart_item_response.data}")

        if not cart_item_response.data or len(cart_item_response.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cart item not found"
            )

        cart_item = cart_item_response.data[0]

        # Verify cart belongs to user
        cart_user_id = cart_item.get("Cart", {}).get("userId") if isinstance(cart_item.get("Cart"), dict) else None
        if not cart_user_id or cart_user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot update another user's cart"
            )

        # Check product availability
        product_response = supabase.table("products").select("quantity").eq("id", cart_item["productId"]).execute()

        if not product_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product not found"
            )

        product_quantity = product_response.data[0]["quantity"]

        if update.quantity > product_quantity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Only {product_quantity} items available"
            )

        # Update cart item
        update_data = {
            "quantity": update.quantity,
            "updatedAt": datetime.utcnow().isoformat()
        }
        supabase.table("CartItem").update(update_data).eq("id", item_id).execute()

        # Recalculate cart totals
        cart_id = cart_item["cartId"]
        cart_items_response = supabase.table("CartItem").select("*").eq("cartId", cart_id).execute()
        cart_items = cart_items_response.data

        totals = calculate_cart_totals(cart_items)

        cart_update = {
            "itemCount": totals["itemCount"],
            "subtotal": str(totals["subtotal"]),
            "tax": str(totals["tax"]),
            "total": str(totals["total"]),
            "updatedAt": datetime.utcnow().isoformat()
        }
        supabase.table("Cart").update(cart_update).eq("id", cart_id).execute()

        # Return updated cart
        return await get_cart(current_user)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating cart item: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update cart item"
        )

@router.delete("/cart/items/{item_id}", response_model=CartResponse)
async def remove_cart_item(
    item_id: str,
    current_user = Depends(get_required_user)
):
    """Remove item from cart"""
    try:
        user_id = current_user["user_id"]

        # Get cart item
        cart_item_response = supabase.table("CartItem").select("*, Cart!inner(userId)").eq("id", item_id).execute()

        if not cart_item_response.data or len(cart_item_response.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cart item not found"
            )

        cart_item = cart_item_response.data[0]

        # Verify cart belongs to user
        cart_user_id = cart_item.get("Cart", {}).get("userId") if isinstance(cart_item.get("Cart"), dict) else None
        if not cart_user_id or cart_user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot modify another user's cart"
            )

        cart_id = cart_item["cartId"]

        # Delete cart item
        supabase.table("CartItem").delete().eq("id", item_id).execute()

        # Recalculate cart totals
        cart_items_response = supabase.table("CartItem").select("*").eq("cartId", cart_id).execute()
        cart_items = cart_items_response.data

        if cart_items:
            totals = calculate_cart_totals(cart_items)

            cart_update = {
                "itemCount": totals["itemCount"],
                "subtotal": str(totals["subtotal"]),
                "tax": str(totals["tax"]),
                "total": str(totals["total"]),
                "updatedAt": datetime.utcnow().isoformat()
            }
            supabase.table("Cart").update(cart_update).eq("id", cart_id).execute()
        else:
            # Reset cart if empty
            cart_update = {
                "itemCount": 0,
                "subtotal": "0",
                "tax": "0",
                "total": "0",
                "updatedAt": datetime.utcnow().isoformat()
            }
            supabase.table("Cart").update(cart_update).eq("id", cart_id).execute()

        # Return updated cart
        return await get_cart(current_user)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing cart item: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to remove cart item"
        )

@router.delete("/cart", status_code=status.HTTP_204_NO_CONTENT)
async def clear_cart(current_user = Depends(get_required_user)):
    """Clear all items from cart"""
    try:
        user_id = current_user["user_id"]

        # Get cart
        cart_response = supabase.table("Cart").select("id").eq("userId", user_id).execute()

        if not cart_response.data or len(cart_response.data) == 0:
            return

        cart_id = cart_response.data[0]["id"]

        # Delete all cart items
        supabase.table("CartItem").delete().eq("cartId", cart_id).execute()

        # Reset cart totals
        cart_update = {
            "itemCount": 0,
            "subtotal": "0",
            "tax": "0",
            "total": "0",
            "discountAmount": "0",
            "updatedAt": datetime.utcnow().isoformat()
        }
        supabase.table("Cart").update(cart_update).eq("id", cart_id).execute()

    except Exception as e:
        logger.error(f"Error clearing cart: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to clear cart"
        )

@router.get("/cart/summary", response_model=CartSummary)
async def get_cart_summary(current_user = Depends(get_required_user)):
    """Get cart summary (totals only)"""
    try:
        user_id = current_user["user_id"]

        # Get cart
        cart_response = supabase.table("Cart").select(
            "itemCount, subtotal, tax, discountAmount, total, currency"
        ).eq("userId", user_id).execute()

        if not cart_response.data or len(cart_response.data) == 0:
            # Return empty summary
            return CartSummary(
                itemCount=0,
                subtotal=Decimal('0'),
                tax=Decimal('0'),
                discountAmount=Decimal('0'),
                total=Decimal('0'),
                currency="GHS"
            )

        cart = cart_response.data[0]

        return CartSummary(
            itemCount=cart["itemCount"],
            subtotal=Decimal(str(cart["subtotal"])),
            tax=Decimal(str(cart["tax"])),
            discountAmount=Decimal(str(cart["discountAmount"])),
            total=Decimal(str(cart["total"])),
            currency=cart["currency"]
        )

    except Exception as e:
        logger.error(f"Error getting cart summary: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get cart summary"
        )