from fastapi import APIRouter, HTTPException, status, Depends, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.database import supabase
from app.utils.auth_utils import AuthUtils
from app.models.payments import (
    BuyNowRequest,
    CheckoutRequest,
    PaymentInitResponse,
    OrderResponse,
    PaymentVerificationResponse,
    PaymentGateway,
    OrderStatus,
    PaymentStatus,
)
from app.models.seller import (
    InvoiceStatus,
    InvoiceWithPurchaseDetails,
    InvoicesListResponse,
)
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import logging
import httpx
import os
import uuid
import math

logger = logging.getLogger(__name__)

router = APIRouter()
security = HTTPBearer()

# Paystack configuration
PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY")
PAYSTACK_BASE_URL = "https://api.paystack.co"
NEXT_PUBLIC_BASE_URL = os.getenv("NEXT_PUBLIC_BASE_URL", "https://zipohubonline.com")


def generate_invoice_number():
    """Generate unique invoice number"""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    random_suffix = str(uuid.uuid4())[:4].upper()
    return f"INV-{timestamp}-{random_suffix}"


def calculate_delivery_fee(distance_km: Optional[float], priority: str) -> Decimal:
    """Calculate delivery fee based on distance and priority"""
    base_fee = Decimal("10.00")  # Base fee in GHS

    if distance_km:
        # Add GHS 2 per km
        distance_fee = Decimal(str(distance_km)) * Decimal("2.00")
    else:
        # Default distance fee if no distance provided
        distance_fee = Decimal("20.00")

    # Priority multipliers
    priority_multipliers = {
        "STANDARD": Decimal("1.0"),
        "EXPRESS": Decimal("1.5"),
        "URGENT": Decimal("2.0"),
    }

    multiplier = priority_multipliers.get(priority, Decimal("1.0"))
    total_fee = (base_fee + distance_fee) * multiplier

    return total_fee.quantize(Decimal("0.01"))


def create_delivery_for_order(order: dict, order_items: List[dict]) -> Optional[dict]:
    """Create delivery record for order if courier delivery was requested"""
    try:
        shipping_address = order.get("shippingAddress", {})
        delivery_metadata = shipping_address.get("deliveryMetadata")

        # Check if courier delivery was requested
        if not delivery_metadata or not delivery_metadata.get("enableCourierDelivery"):
            logger.info(f"Order {order['id']} does not require courier delivery")
            return None

        logger.info(f"Creating delivery for order {order['id']}")

        # Get seller address from first item (for multi-seller orders, this handles first seller)
        # TODO: Handle multi-seller orders with multiple deliveries
        seller_id = order_items[0]["sellerId"]
        seller_response = (
            supabase.table("users")
            .select("address, city, country, phone_number, name")
            .eq("user_id", seller_id)
            .execute()
        )

        if not seller_response.data:
            logger.error(f"Seller {seller_id} not found for delivery creation")
            return None

        seller = seller_response.data[0]

        # Prepare pickup address (seller's address)
        pickup_address = {
            "address": seller.get("address", ""),
            "city": seller.get("city", ""),
            "country": seller.get("country", ""),
            "additional_info": f"Seller: {seller.get('name', 'Unknown')}"
        }

        # Prepare delivery address (customer's shipping address)
        delivery_address = {
            "address": shipping_address.get("address", ""),
            "city": shipping_address.get("city", ""),
            "country": shipping_address.get("country", ""),
            "additional_info": shipping_address.get("additionalInfo", "")
        }

        # Calculate delivery fee
        priority = delivery_metadata.get("deliveryPriority", "STANDARD")
        distance_km = None  # Can integrate Google Maps API here
        delivery_fee = calculate_delivery_fee(distance_km, priority)
        courier_fee = (delivery_fee * Decimal("0.70")).quantize(Decimal("0.01"))
        platform_fee = (delivery_fee * Decimal("0.30")).quantize(Decimal("0.01"))

        # Create delivery record
        delivery_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        delivery_data = {
            "id": delivery_id,
            "order_id": order["id"],
            "pickup_address": pickup_address,
            "delivery_address": delivery_address,
            "pickup_contact_name": seller.get("name"),
            "pickup_contact_phone": seller.get("phone_number"),
            "delivery_contact_name": shipping_address.get("name"),
            "delivery_contact_phone": shipping_address.get("phone"),
            "scheduled_by_user": order["userId"],
            "scheduled_by_type": "CUSTOMER",
            "delivery_fee": float(delivery_fee),
            "courier_fee": float(courier_fee),
            "platform_fee": float(platform_fee),
            "distance_km": distance_km,
            "status": "PENDING",
            "priority": priority,
            "notes": delivery_metadata.get("deliveryNotes"),
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }

        delivery_response = supabase.table("Delivery").insert(delivery_data).execute()

        if delivery_response.data:
            logger.info(f"✅ Delivery {delivery_id} created for order {order['id']}")
            return delivery_response.data[0]
        else:
            logger.error(f"❌ Failed to create delivery for order {order['id']}")
            return None

    except Exception as e:
        logger.error(f"❌ Error creating delivery for order: {str(e)}")
        return None


def create_invoice_for_purchase(purchase_data: dict, order: dict):
    """Create invoice for a product purchase"""
    try:
        invoice_number = generate_invoice_number()

        invoice_data = {
            "id": str(uuid.uuid4()),
            "invoiceNumber": invoice_number,
            "purchaseId": purchase_data["id"],
            "sellerId": purchase_data["sellerId"],
            "customerEmail": purchase_data.get("email", order["userId"]),
            "customerName": purchase_data.get("customerName", "Customer"),
            "subtotal": float(purchase_data["totalAmount"]),
            "tax": 0.0,
            "discount": float(purchase_data.get("discountAmount", 0)),
            "total": float(purchase_data["totalAmount"]),
            "currency": order["currency"],
            "status": "PAID",
            "sentAt": datetime.now(timezone.utc).isoformat(),
            "paidAt": datetime.now(timezone.utc).isoformat(),
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "updatedAt": datetime.now(timezone.utc).isoformat(),
        }

        response = supabase.table("Invoice").insert(invoice_data).execute()

        if response.data:
            logger.info(
                f"✅ Invoice {invoice_number} created for purchase {purchase_data['id']}"
            )
            return response.data[0]
        else:
            logger.error(
                f"❌ Failed to create invoice for purchase {purchase_data['id']}"
            )
            return None

    except Exception as e:
        logger.error(f"❌ Error creating invoice: {str(e)}")
        return None


def update_seller_analytics(
    seller_id: str, order_items: List[dict], order_total: Decimal
):
    """Update seller analytics after successful order"""
    try:
        # Calculate seller's portion of the order
        seller_items = [item for item in order_items if item["sellerId"] == seller_id]
        seller_total = sum(
            Decimal(str(item["price"])) * item["quantity"] for item in seller_items
        )

        # Get existing analytics or create new
        analytics_response = (
            supabase.table("SellerAnalytics")
            .select("*")
            .eq("sellerId", seller_id)
            .execute()
        )

        now = datetime.now(timezone.utc).isoformat()

        if analytics_response.data:
            # Update existing analytics
            analytics = analytics_response.data[0]

            new_total_sales = (
                Decimal(str(analytics.get("totalSales", 0))) + seller_total
            )
            new_total_orders = analytics.get("totalOrders", 0) + 1
            new_average_order_value = (
                new_total_sales / new_total_orders
                if new_total_orders > 0
                else seller_total
            )

            # Get unique customer count (simplified - just increment)
            new_total_customers = analytics.get("totalCustomers", 0) + 1

            update_data = {
                "totalSales": float(new_total_sales),
                "totalOrders": new_total_orders,
                "totalCustomers": new_total_customers,
                "averageOrderValue": float(new_average_order_value),
                "lastSaleDate": now,
                "updatedAt": now,
            }

            supabase.table("SellerAnalytics").update(update_data).eq(
                "sellerId", seller_id
            ).execute()
            logger.info(f"✅ Updated analytics for seller {seller_id}")

        else:
            # Create new analytics
            analytics_data = {
                "id": str(uuid.uuid4()),
                "sellerId": seller_id,
                "totalSales": float(seller_total),
                "totalOrders": 1,
                "totalCustomers": 1,
                "averageOrderValue": float(seller_total),
                "lastSaleDate": now,
                "updatedAt": now,
            }

            supabase.table("SellerAnalytics").insert(analytics_data).execute()
            logger.info(f"✅ Created analytics for seller {seller_id}")

    except Exception as e:
        logger.error(f"❌ Error updating seller analytics: {str(e)}")


def create_seller_event(
    seller_id: str,
    event_type: str,
    order_id: str,
    order_items: List[dict],
    order_total: Decimal,
):
    """Create seller event for new order"""
    try:
        # Calculate seller's items
        seller_items = [item for item in order_items if item["sellerId"] == seller_id]
        items_count = len(seller_items)

        # Create event title and description
        items_summary = ", ".join(
            [f"{item['quantity']}x {item['title']}" for item in seller_items[:2]]
        )
        if items_count > 2:
            items_summary += f" and {items_count - 2} more"

        event_data = {
            "id": str(uuid.uuid4()),
            "sellerId": seller_id,
            "type": event_type,
            "title": f"New Order Received - #{order_id[:8]}",
            "description": f"Order with {items_count} item(s): {items_summary}",
            "metadata": {
                "orderId": order_id,
                "itemsCount": items_count,
                "totalAmount": float(order_total),
                "items": seller_items,
            },
            "priority": "HIGH",
            "status": "PENDING",
            "dueDate": (datetime.now(timezone.utc) + timedelta(days=2)).isoformat(),
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "updatedAt": datetime.now(timezone.utc).isoformat(),
        }

        response = supabase.table("SellerEvent").insert(event_data).execute()

        if response.data:
            logger.info(f"✅ Created event for seller {seller_id}")
            return response.data[0]
        else:
            logger.error(f"❌ Failed to create event for seller {seller_id}")
            return None

    except Exception as e:
        logger.error(f"❌ Error creating seller event: {str(e)}")
        return None


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get current authenticated user"""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required"
        )

    try:
        user_data = AuthUtils.verify_supabase_token(credentials.credentials)
        if not user_data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            )
        return user_data
    except Exception as e:
        logger.error(f"Authentication failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication failed"
        )


def validate_product_for_purchase(product: dict, quantity: int, buyer_user_id: str):
    """Validate product can be purchased"""
    # Check if product accepts online payment
    if not product.get("allowPurchaseOnPlatform"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This product does not accept online payments",
        )

    # Check if seller has subaccount
    seller = product.get("user", {})

    # Handle case where seller might be a list
    if isinstance(seller, list):
        seller = seller[0] if seller else {}

    # Get PaystackSubaccount data
    paystack_data = seller.get("PaystackSubaccount")

    # Handle case where PaystackSubaccount might be a list, dict, or None
    if isinstance(paystack_data, list):
        paystack_data = paystack_data[0] if paystack_data else None

    # Check if subaccount exists and has subaccountId
    if not paystack_data or not isinstance(paystack_data, dict) or not paystack_data.get("subaccountId"):
        logger.error(f"Seller validation failed - product: {product.get('id')}, seller: {seller.get('user_id')}, paystack_data: {paystack_data}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Seller has not set up their payment account. Cannot purchase this product.",
        )

    # Check if user is trying to buy their own product
    if product.get("sellerId") == buyer_user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot purchase your own products",
        )

    # Check stock availability
    if product.get("quantity", 0) < quantity:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Insufficient stock. Only {product.get('quantity', 0)} items available",
        )


def validate_discount(discount_code: str, product_ids: List[str]) -> Optional[dict]:
    """Validate and return discount if applicable"""
    if not discount_code:
        return None

    # Get discount
    discount_response = (
        supabase.table("Discount")
        .select("*, products:DiscountOnProduct(productId)")
        .eq("code", discount_code.upper())
        .execute()
    )

    if not discount_response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Invalid discount code"
        )

    discount = discount_response.data[0]

    # Check if discount is enabled
    if discount["status"] != "ENABLED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This discount code is not active",
        )

    # Check if discount is expired
    if discount.get("expiresAt"):
        expires_at = datetime.fromisoformat(
            discount["expiresAt"].replace("Z", "+00:00")
        )
        if expires_at <= datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This discount code has expired",
            )

    # Check if any products are eligible for this discount
    discount_product_ids = [prod["productId"] for prod in discount.get("products", [])]
    eligible_products = set(product_ids) & set(discount_product_ids)

    if not eligible_products:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This discount is not applicable to the selected product(s)",
        )

    return discount


def calculate_discount_amount(items: List[dict], discount: Optional[dict]) -> Decimal:
    """Calculate total discount amount for items"""
    if not discount:
        return Decimal("0.00")

    discount_product_ids = [prod["productId"] for prod in discount.get("products", [])]
    discount_percentage = Decimal(str(discount["percentage"])) / 100
    total_discount = Decimal("0.00")

    for item in items:
        if item["productId"] in discount_product_ids:
            item_total = Decimal(str(item["price"])) * item["quantity"]
            total_discount += item_total * discount_percentage

    return total_discount


# ========== BUY NOW (Single Product Purchase) ==========


@router.post("/buy-now", response_model=PaymentInitResponse)
async def buy_now(request: BuyNowRequest, current_user=Depends(get_current_user)):
    """
    Initialize payment for a single product purchase (Buy Now).
    Validates: product availability, seller subaccount, online payment enabled, user cannot buy own products.
    """
    try:
        user_id = current_user["user_id"]
        user_email = current_user.get("email")

        logger.info(
            f"Buy Now request from user {user_id} for product {request.productId}"
        )

        # Get product with seller details
        product_response = (
            supabase.table("products")
            .select(
                """
            id, name, price, currency, quantity, sellerId, allowPurchaseOnPlatform, photos, condition, country,
            user:sellerId(
                user_id, name, business_name,
                PaystackSubaccount(subaccountId)
            )
            """
            )
            .eq("id", request.productId)
            .execute()
        )

        if not product_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Product not found"
            )

        product = product_response.data[0]

        # Validate product for purchase
        validate_product_for_purchase(product, request.quantity, user_id)

        # Validate discount if provided
        discount = (
            validate_discount(request.discountCode, [request.productId])
            if request.discountCode
            else None
        )

        # Calculate totals
        subtotal = Decimal(str(product["price"])) * request.quantity
        discount_amount = calculate_discount_amount(
            [
                {
                    "productId": request.productId,
                    "price": product["price"],
                    "quantity": request.quantity,
                }
            ],
            discount,
        )
        tax = Decimal("0.00")  # Can be calculated based on business logic
        total = subtotal - discount_amount + tax

        # Create order
        order_id = str(uuid.uuid4())
        seller_data = product.get("user", {})

        # Handle case where user might be a list or dict
        if isinstance(seller_data, list):
            seller = seller_data[0] if seller_data else {}
        elif isinstance(seller_data, dict):
            seller = seller_data
        else:
            seller = {}

        # Store delivery preferences in metadata for later use
        delivery_metadata = None
        if request.enableCourierDelivery:
            delivery_metadata = {
                "enableCourierDelivery": True,
                "deliveryPriority": request.deliveryPriority or "STANDARD",
                "deliveryNotes": request.deliveryNotes,
            }

        order_data = {
            "id": order_id,
            "userId": user_id,
            "subtotal": float(subtotal),
            "discountAmount": float(discount_amount),
            "tax": float(tax),
            "total": float(total),
            "status": "PENDING",
            "paymentStatus": "PENDING",
            "currency": product["currency"],
            "shippingAddress": {**request.shippingAddress.dict(), "deliveryMetadata": delivery_metadata},
            "paymentGateway": request.paymentGateway.value,
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "updatedAt": datetime.now(timezone.utc).isoformat(),
        }

        order_response = supabase.table("Order").insert(order_data).execute()

        if not order_response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create order",
            )

        # Create order item
        order_item_data = {
            "id": str(uuid.uuid4()),
            "orderId": order_id,
            "productId": request.productId,
            "quantity": request.quantity,
            "price": float(product["price"]),
            "title": product["name"],
            "image": product.get("photos", [])[0] if product.get("photos") else None,
            "condition": product.get("condition"),
            "location": product.get("country"),
            "sellerId": product["sellerId"],
            "sellerName": seller.get("business_name") or seller.get("name"),
        }

        supabase.table("OrderItem").insert(order_item_data).execute()

        # Create discount record if applicable
        if discount:
            discount_record = {
                "orderId": order_id,
                "discountId": discount["id"],
                "code": discount["code"],
                "percentage": discount["percentage"],
                "amount": float(discount_amount),
                "description": discount.get("description"),
            }
            supabase.table("OrderDiscount").insert(discount_record).execute()

        # Initialize Paystack payment
        # Handle case where PaystackSubaccount might be a list or dict
        paystack_data = seller.get("PaystackSubaccount")
        if isinstance(paystack_data, list):
            paystack_data = paystack_data[0] if paystack_data else {}
        elif not isinstance(paystack_data, dict):
            paystack_data = {}

        subaccount_id = paystack_data.get("subaccountId")

        # Convert amount to kobo
        amount_in_kobo = int(total * 100)

        metadata = {
            "orderId": order_id,
            "userId": user_id,
            "transactionType": "product_purchase",
            "email": user_email,
            "productId": request.productId,
            "quantity": request.quantity,
        }

        callback_url = f"{NEXT_PUBLIC_BASE_URL}/api/payment-callback"

        paystack_data = {
            "email": user_email,
            "amount": amount_in_kobo,
            "currency": product["currency"],
            "callback_url": callback_url,
            "metadata": metadata,
            "subaccount": subaccount_id,
            "transaction_charge": 0,  # Platform takes its cut via subaccount split
            "channels": ["card", "bank", "ussd", "qr", "mobile_money", "bank_transfer"],
        }

        logger.info(f"Initializing Paystack payment: {amount_in_kobo} kobo")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{PAYSTACK_BASE_URL}/transaction/initialize",
                json=paystack_data,
                headers={
                    "Authorization": f"Bearer {PAYSTACK_SECRET_KEY}",
                    "Content-Type": "application/json",
                },
                timeout=30.0,
            )

        if response.status_code != 200:
            logger.error(f"Paystack initialization failed: {response.text}")
            # Delete the order since payment initialization failed
            supabase.table("Order").delete().eq("id", order_id).execute()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to initialize payment",
            )

        paystack_response = response.json()

        if not paystack_response.get("status"):
            logger.error(f"Paystack returned error: {paystack_response}")
            supabase.table("Order").delete().eq("id", order_id).execute()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=paystack_response.get(
                    "message", "Payment initialization failed"
                ),
            )

        data = paystack_response["data"]

        logger.info(f"Payment initialized successfully. Reference: {data['reference']}")

        return {
            "authorization_url": data["authorization_url"],
            "access_code": data["access_code"],
            "reference": data["reference"],
            "order_id": order_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in buy now: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process buy now request",
        )


# ========== CHECKOUT (Cart Purchase) ==========


@router.post("/checkout", response_model=PaymentInitResponse)
async def checkout_cart(
    request: CheckoutRequest, current_user=Depends(get_current_user)
):
    """
    Checkout cart and initialize payment.
    Validates: all items available, sellers have subaccounts, products accept online payment, same currency.
    """
    try:
        user_id = current_user["user_id"]
        user_email = current_user.get("email")

        logger.info(f"Checkout request from user {user_id}")

        # Get cart
        cart_response = (
            supabase.table("Cart")
            .select("*")
            .eq("userId", user_id)
            .execute()
        )

        if not cart_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Cart not found"
            )

        cart = cart_response.data[0]

        if cart["itemCount"] == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot checkout an empty cart",
            )

        # Get cart items
        logger.info(f"Fetching cart items for cartId: {cart['id']}")
        cart_items_response = (
            supabase.table("CartItem")
            .select("*")
            .eq("cartId", cart["id"])
            .execute()
        )

        cart_items = cart_items_response.data or []
        logger.info(f"Found {len(cart_items)} cart items")

        # Fetch product details for each cart item
        for item in cart_items:
            # First get the product
            product_response = (
                supabase.table("products")
                .select("*")
                .eq("id", item["productId"])
                .execute()
            )

            if product_response.data and len(product_response.data) > 0:
                product_data = product_response.data[0]

                # Now fetch the seller's user data and PaystackSubaccount separately
                seller_id = product_data.get("sellerId")
                if seller_id:
                    seller_response = (
                        supabase.table("users")
                        .select("user_id, name, business_name, PaystackSubaccount(subaccountId)")
                        .eq("user_id", seller_id)
                        .execute()
                    )

                    if seller_response.data and len(seller_response.data) > 0:
                        product_data["user"] = seller_response.data[0]
                        logger.info(f"🔍 Seller data for product {item['productId']}: {seller_response.data[0]}")
                    else:
                        logger.error(f"❌ No seller found for sellerId: {seller_id}")
                        product_data["user"] = None
                else:
                    logger.error(f"❌ Product {item['productId']} has no sellerId")
                    product_data["user"] = None

                item["product"] = product_data
            else:
                item["product"] = None

        if not cart_items or len(cart_items) == 0:
            logger.error(f"No cart items found for cartId {cart['id']}, but cart.itemCount={cart['itemCount']}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cart is empty. Cannot checkout an empty cart.",
            )

        # Validate all cart items
        cart_currency = cart["currency"]
        product_ids = []

        for item in cart_items:
            product = item.get("product")
            logger.info(f"Processing cart item: productId={item.get('productId')}, product data type: {type(product)}")

            if not product or not isinstance(product, dict):
                logger.error(f"Product data invalid for item {item.get('productId')}: {product}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Product {item.get('productId', 'unknown')} not found or is invalid",
                )

            # Validate each product
            logger.info(f"Validating product {product.get('id')} for purchase. Seller data: {product.get('user')}")
            validate_product_for_purchase(product, item["quantity"], user_id)

            # Ensure all products are in the same currency (already validated in cart, but double-check)
            if product["currency"] != cart_currency:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="All products must be in the same currency",
                )

            product_ids.append(product["id"])

        # Validate discount if provided
        discount = (
            validate_discount(request.discountCode, product_ids)
            if request.discountCode
            else None
        )

        # Calculate totals
        subtotal = Decimal(str(cart["subtotal"]))

        # Recalculate discount if new code provided
        if request.discountCode:
            items_for_discount = [
                {
                    "productId": item.get("productId"),
                    "price": item.get("price"),
                    "quantity": item.get("quantity"),
                }
                for item in cart_items
            ]
            discount_amount = calculate_discount_amount(items_for_discount, discount)
        else:
            discount_amount = Decimal(str(cart.get("discountAmount", 0)))

        tax = Decimal(str(cart.get("tax", 0)))
        total = subtotal - discount_amount + tax

        # Create order
        order_id = str(uuid.uuid4())

        # Store delivery preferences in metadata for later use
        delivery_metadata = None
        if request.enableCourierDelivery:
            delivery_metadata = {
                "enableCourierDelivery": True,
                "deliveryPriority": request.deliveryPriority or "STANDARD",
                "deliveryNotes": request.deliveryNotes,
            }

        order_data = {
            "id": order_id,
            "userId": user_id,
            "subtotal": float(subtotal),
            "discountAmount": float(discount_amount),
            "tax": float(tax),
            "total": float(total),
            "status": "PENDING",
            "paymentStatus": "PENDING",
            "currency": cart_currency,
            "shippingAddress": {**request.shippingAddress.dict(), "deliveryMetadata": delivery_metadata},
            "paymentGateway": request.paymentGateway.value,
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "updatedAt": datetime.now(timezone.utc).isoformat(),
        }

        order_response = supabase.table("Order").insert(order_data).execute()

        if not order_response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create order",
            )

        # Create order items
        for item in cart_items:
            product = item.get("product", {})
            seller_data = product.get("user")

            # Handle case where user might be a list or dict
            if isinstance(seller_data, list):
                seller = seller_data[0] if seller_data else {}
            elif isinstance(seller_data, dict):
                seller = seller_data
            else:
                seller = {}

            order_item_data = {
                "id": str(uuid.uuid4()),
                "orderId": order_id,
                "productId": item.get("productId"),
                "quantity": item.get("quantity"),
                "price": float(item.get("price", 0)),
                "title": product.get("name", "Unknown Product"),
                "image": product.get("photos", [])[0]
                if product.get("photos")
                else None,
                "condition": product.get("condition"),
                "location": product.get("country"),
                "sellerId": product.get("sellerId"),
                "sellerName": seller.get("business_name")
                or seller.get("name", "Unknown Seller"),
            }

            supabase.table("OrderItem").insert(order_item_data).execute()

        # Create discount record if applicable
        if discount:
            discount_record = {
                "orderId": order_id,
                "discountId": discount["id"],
                "code": discount["code"],
                "percentage": discount["percentage"],
                "amount": float(discount_amount),
                "description": discount.get("description"),
            }
            supabase.table("OrderDiscount").insert(discount_record).execute()

        # For multi-seller carts, we'll use split payment
        # Get unique sellers and their subaccounts
        seller_subaccounts = {}
        for item in cart_items:
            product = item.get("product", {})
            seller_id = product.get("sellerId")

            if not seller_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Product {item.get('productId')} has no seller information",
                )

            if seller_id not in seller_subaccounts:
                user_data = product.get("user")
                # Handle case where user might be a list or dict
                if isinstance(user_data, list):
                    user_data = user_data[0] if user_data else {}
                elif not isinstance(user_data, dict):
                    user_data = {}

                paystack_data = user_data.get("PaystackSubaccount")
                if isinstance(paystack_data, list):
                    paystack_data = paystack_data[0] if paystack_data else {}
                elif not isinstance(paystack_data, dict):
                    paystack_data = {}

                subaccount_id = paystack_data.get("subaccountId")

                if not subaccount_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Seller for product {product.get('name', 'unknown')} has not set up payment account",
                    )

                seller_subaccounts[seller_id] = subaccount_id

        # For now, use the first seller's subaccount (for single-seller carts)
        # TODO: Implement proper split payment for multi-seller carts
        primary_subaccount = list(seller_subaccounts.values())[0]

        # Convert amount to kobo
        amount_in_kobo = int(total * 100)

        metadata = {
            "orderId": order_id,
            "userId": user_id,
            "transactionType": "cart_checkout",
            "email": user_email,
            "itemCount": cart["itemCount"],
        }

        callback_url = f"{NEXT_PUBLIC_BASE_URL}/api/payment-callback"

        paystack_data = {
            "email": user_email,
            "amount": amount_in_kobo,
            "currency": cart_currency,
            "callback_url": callback_url,
            "metadata": metadata,
            "subaccount": primary_subaccount,
            "transaction_charge": 0,
            "channels": ["card", "bank", "ussd", "qr", "mobile_money", "bank_transfer"],
        }

        logger.info(f"Initializing Paystack payment: {amount_in_kobo} kobo")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{PAYSTACK_BASE_URL}/transaction/initialize",
                json=paystack_data,
                headers={
                    "Authorization": f"Bearer {PAYSTACK_SECRET_KEY}",
                    "Content-Type": "application/json",
                },
                timeout=30.0,
            )

        if response.status_code != 200:
            logger.error(f"Paystack initialization failed: {response.text}")
            supabase.table("Order").delete().eq("id", order_id).execute()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to initialize payment",
            )

        paystack_response = response.json()

        if not paystack_response.get("status"):
            logger.error(f"Paystack returned error: {paystack_response}")
            supabase.table("Order").delete().eq("id", order_id).execute()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=paystack_response.get(
                    "message", "Payment initialization failed"
                ),
            )

        data = paystack_response["data"]

        logger.info(f"Payment initialized successfully. Reference: {data['reference']}")

        # NOTE: Cart will be cleared after successful payment verification
        # We don't clear it here in case user cancels payment or payment fails

        return {
            "authorization_url": data["authorization_url"],
            "access_code": data["access_code"],
            "reference": data["reference"],
            "order_id": order_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in checkout: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process checkout",
        )


# ========== VERIFY PAYMENT ==========


@router.post("/verify-payment", response_model=PaymentVerificationResponse)
async def verify_payment(
    reference: str = Query(..., description="Payment reference from Paystack"),
    current_user=Depends(get_current_user),
):
    """Verify payment and update order status"""
    try:
        user_id = current_user["user_id"]

        logger.info(f"Verifying payment: {reference} for user {user_id}")

        # Verify with Paystack
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{PAYSTACK_BASE_URL}/transaction/verify/{reference}",
                headers={"Authorization": f"Bearer {PAYSTACK_SECRET_KEY}"},
                timeout=30.0,
            )

        if response.status_code != 200:
            logger.error(f"Paystack verification failed: {response.text}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to verify payment",
            )

        paystack_response = response.json()

        if not paystack_response.get("status"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Payment verification failed",
            )

        data = paystack_response["data"]
        metadata = data.get("metadata", {})
        order_id = metadata.get("orderId")

        if not order_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid payment reference",
            )

        # Get order
        order_response = (
            supabase.table("Order")
            .select(
                """
            *,
            items:OrderItem(*),
            appliedDiscounts:OrderDiscount(*)
            """
            )
            .eq("id", order_id)
            .execute()
        )

        if not order_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Order not found"
            )

        order = order_response.data[0]

        # Verify ownership
        if order["userId"] != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Unauthorized access to this order",
            )

        # Update order based on payment status
        if data["status"] == "success":
            # Update product quantities
            order_items = order.get("items") or order.get("OrderItem") or []
            for item in order_items:
                # Fetch current product quantity
                product_response = (
                    supabase.table("products")
                    .select("quantity")
                    .eq("id", item["productId"])
                    .execute()
                )
                if product_response.data:
                    current_quantity = product_response.data[0]["quantity"]
                    new_quantity = max(0, current_quantity - item["quantity"])
                    supabase.table("products").update({"quantity": new_quantity}).eq(
                        "id", item["productId"]
                    ).execute()

            # Update order status
            supabase.table("Order").update(
                {
                    "paymentStatus": "COMPLETED",
                    "status": "CONFIRMED",
                    "paymentMethod": data.get("channel"),
                    "updatedAt": datetime.now(timezone.utc).isoformat(),
                }
            ).eq("id", order_id).execute()

            # Refresh order data
            order_response = (
                supabase.table("Order")
                .select(
                    """
                *,
                items:OrderItem(*),
                appliedDiscounts:OrderDiscount(*)
                """
                )
                .eq("id", order_id)
                .execute()
            )
            order = order_response.data[0]
            order_items = order.get("items") or order.get("OrderItem") or []

            # Create notifications for buyer and sellers
            now = datetime.now(timezone.utc)
            notification_expiry = now + timedelta(days=30)

            # Get unique sellers from order items
            sellers = {}
            for item in order_items:
                seller_id = item["sellerId"]
                if seller_id not in sellers:
                    sellers[seller_id] = {
                        "id": seller_id,
                        "name": item["sellerName"],
                        "items": [],
                        "total": Decimal("0.00"),
                    }
                sellers[seller_id]["items"].append(item)
                sellers[seller_id]["total"] += (
                    Decimal(str(item["price"])) * item["quantity"]
                )

            # 1. Create notification for BUYER
            buyer_items_text = ", ".join(
                [f"{item['quantity']}x {item['title']}" for item in order_items[:3]]
            )
            if len(order_items) > 3:
                buyer_items_text += f" and {len(order_items) - 3} more items"

            buyer_notification = {
                "id": str(uuid.uuid4()),
                "userId": order["userId"],
                "title": "Order Confirmed!",
                "notificationType": "SUCCESS",
                "body": f"Your order #{order_id[:8]} has been confirmed! Items: {buyer_items_text}. Total: {order['currency']} {order['total']}. You will be notified when your order is shipped.",
                "dismissed": False,
                "createdAt": now.isoformat(),
                "expiresAt": notification_expiry.isoformat(),
            }

            try:
                supabase.table("Notification").insert(buyer_notification).execute()
                logger.info(f"✅ Buyer notification created for user {order['userId']}")
            except Exception as notif_error:
                logger.error(
                    f"❌ Failed to create buyer notification: {str(notif_error)}"
                )

            # 2. Create notifications for each SELLER
            for seller_id, seller_info in sellers.items():
                items_count = len(seller_info["items"])
                items_text = ", ".join(
                    [
                        f"{item['quantity']}x {item['title']}"
                        for item in seller_info["items"][:2]
                    ]
                )
                if items_count > 2:
                    items_text += f" and {items_count - 2} more"

                seller_notification = {
                    "id": str(uuid.uuid4()),
                    "userId": seller_id,
                    "title": "New Order Received!",
                    "notificationType": "SUCCESS",
                    "body": f"You have a new order! Order #{order_id[:8]} - {items_count} item(s): {items_text}. Amount: {order['currency']} {float(seller_info['total']):.2f}. Please prepare the items for shipping.",
                    "dismissed": False,
                    "createdAt": now.isoformat(),
                    "expiresAt": notification_expiry.isoformat(),
                }

                try:
                    supabase.table("Notification").insert(seller_notification).execute()
                    logger.info(f"✅ Seller notification created for user {seller_id}")
                except Exception as notif_error:
                    logger.error(
                        f"❌ Failed to create seller notification: {str(notif_error)}"
                    )

            # ========== CREATE PRODUCT PURCHASES AND INVOICES ==========
            logger.info("Creating ProductPurchase records and Invoices...")

            # Extract customer details from order
            shipping_address = order.get("shippingAddress", {})
            customer_name = (
                shipping_address.get("fullName", "")
                if isinstance(shipping_address, dict)
                else f"Customer {order['userId'][:8]}"
            )
            customer_phone = (
                shipping_address.get("phoneNumber", "")
                if isinstance(shipping_address, dict)
                else ""
            )

            # Create ProductPurchase and Invoice for each order item
            for item in order_items:
                try:
                    # 3. Create ProductPurchase record
                    purchase_data = {
                        "id": str(uuid.uuid4()),
                        "userId": order["userId"],
                        "email": current_user.get("email", ""),
                        "productId": item["productId"],
                        "paymentGateway": "PAYSTACK",
                        "customerName": customer_name,
                        "customerPhone": customer_phone,
                        "shippingAddress": shipping_address,
                        "quantity": item["quantity"],
                        "totalAmount": float(
                            Decimal(str(item["price"])) * item["quantity"]
                        ),
                        "unitPrice": float(item["price"]),
                        "createdAt": now.isoformat(),
                        "updatedAt": now.isoformat(),
                    }

                    purchase_response = (
                        supabase.table("ProductPurchase")
                        .insert(purchase_data)
                        .execute()
                    )

                    if purchase_response.data:
                        purchase = purchase_response.data[0]
                        logger.info(f"✅ ProductPurchase created: {purchase['id']}")

                        # 4. Create Invoice for this purchase
                        invoice_number = f"INV-{int(datetime.now().timestamp())}-{purchase['id'][:8]}"

                        invoice_data = {
                            "id": str(uuid.uuid4()),
                            "invoiceNumber": invoice_number,
                            "purchaseId": purchase["id"],
                            "sellerId": item["sellerId"],
                            "customerEmail": current_user.get("email", ""),
                            "customerName": customer_name
                            or f"Customer {order['userId'][:8]}",
                            "subtotal": float(item["price"]) * item["quantity"],
                            "tax": 0.00,  # Can be calculated based on business rules
                            "discount": 0.00,  # Can be calculated from applied discounts
                            "total": float(item["price"]) * item["quantity"],
                            "currency": order["currency"],
                            "status": "PAID",  # Since payment is already verified
                            "sentAt": now.isoformat(),
                            "paidAt": now.isoformat(),
                            "createdAt": now.isoformat(),
                            "updatedAt": now.isoformat(),
                        }

                        invoice_response = (
                            supabase.table("Invoice").insert(invoice_data).execute()
                        )

                        if invoice_response.data:
                            invoice = invoice_response.data[0]
                            logger.info(
                                f"✅ Invoice created: {invoice['invoiceNumber']}"
                            )
                        else:
                            logger.error(
                                f"❌ Failed to create invoice for purchase {purchase['id']}"
                            )

                    else:
                        logger.error(
                            f"❌ Failed to create ProductPurchase for item {item['id']}"
                        )

                except Exception as purchase_error:
                    logger.error(
                        f"❌ Error creating ProductPurchase/Invoice: {str(purchase_error)}"
                    )
                    # Continue with other items even if one fails

            # ========== UPDATE SELLER ANALYTICS ==========
            logger.info("Updating SellerAnalytics for each seller")

            for seller_id, seller_info in sellers.items():
                try:
                    seller_revenue = float(seller_info["total"])
                    seller_orders = 1  # This order

                    # Get existing analytics or create default
                    analytics_response = (
                        supabase.table("SellerAnalytics")
                        .select("*")
                        .eq("sellerId", seller_id)
                        .execute()
                    )

                    if analytics_response.data:
                        # Update existing analytics
                        analytics = analytics_response.data[0]
                        new_total_sales = (
                            float(analytics.get("totalSales", 0)) + seller_revenue
                        )
                        new_total_orders = (
                            analytics.get("totalOrders", 0) + seller_orders
                        )
                        new_avg_order_value = (
                            new_total_sales / new_total_orders
                            if new_total_orders > 0
                            else 0
                        )
                        current_customers = analytics.get("totalCustomers", 0)
                        # Get unique customers count (simplified - just increment)
                        new_customers = (
                            current_customers + 1
                        )  # Increment by 1 for this order

                        update_data = {
                            "totalSales": new_total_sales,
                            "totalOrders": new_total_orders,
                            "totalCustomers": new_customers,
                            "averageOrderValue": new_avg_order_value,
                            "lastSaleDate": now.isoformat(),
                            "updatedAt": now.isoformat(),
                        }

                        supabase.table("SellerAnalytics").update(update_data).eq(
                            "sellerId", seller_id
                        ).execute()

                        logger.info(f"✅ Updated analytics for seller {seller_id}")
                    else:
                        # Create new analytics record
                        analytics_data = {
                            "id": str(uuid.uuid4()),
                            "sellerId": seller_id,
                            "totalSales": seller_revenue,
                            "totalOrders": seller_orders,
                            "totalCustomers": 1,
                            "averageOrderValue": seller_revenue,
                            "lastSaleDate": now.isoformat(),
                            "customerRetentionRate": 0.0,
                            "createdAt": now.isoformat(),
                            "updatedAt": now.isoformat(),
                        }

                        supabase.table("SellerAnalytics").insert(
                            analytics_data
                        ).execute()

                        logger.info(f"✅ Created analytics for seller {seller_id}")

                except Exception as analytics_error:
                    logger.error(
                        f"❌ Error updating analytics for seller {seller_id}: {str(analytics_error)}"
                    )

            # ========== CREATE DELIVERY IF COURIER DELIVERY WAS REQUESTED ==========
            try:
                delivery = create_delivery_for_order(order, order_items)
                if delivery:
                    logger.info(f"✅ Delivery created for order {order_id}")
            except Exception as delivery_error:
                # Don't fail the whole transaction if delivery creation fails
                logger.error(f"⚠️ Failed to create delivery: {str(delivery_error)}")

            # ========== CREATE INVOICES, UPDATE ANALYTICS & CREATE EVENTS ==========

            # Group items by seller for processing
            sellers_data = {}
            for item in order_items:
                seller_id = item["sellerId"]
                if seller_id not in sellers_data:
                    sellers_data[seller_id] = {
                        "id": seller_id,
                        "name": item["sellerName"],
                        "items": [],
                        "total": Decimal("0.00"),
                    }
                sellers_data[seller_id]["items"].append(item)
                sellers_data[seller_id]["total"] += (
                    Decimal(str(item["price"])) * item["quantity"]
                )

            # Process each seller
            for seller_id, seller_data in sellers_data.items():
                # 1. Create ProductPurchase records and Invoices
                for item in seller_data["items"]:
                    try:
                        # Create ProductPurchase record
                        purchase_data = {
                            "id": str(uuid.uuid4()),
                            "userId": order["userId"],
                            "email": order.get("shippingAddress", {}).get("email"),
                            "productId": item["productId"],
                            "paymentGateway": order.get("paymentGateway", "PAYSTACK"),
                            "quantity": item["quantity"],
                            "unitPrice": float(item["price"]),
                            "totalAmount": float(
                                Decimal(str(item["price"])) * item["quantity"]
                            ),
                            "customerName": order.get("shippingAddress", {}).get(
                                "fullName", "Customer"
                            ),
                            "customerPhone": order.get("shippingAddress", {}).get(
                                "phone"
                            ),
                            "shippingAddress": order.get("shippingAddress"),
                            "createdAt": datetime.now(timezone.utc).isoformat(),
                            "updatedAt": datetime.now(timezone.utc).isoformat(),
                        }

                        purchase_response = (
                            supabase.table("ProductPurchase")
                            .insert(purchase_data)
                            .execute()
                        )

                        if purchase_response.data:
                            purchase = purchase_response.data[0]
                            # Add sellerId to purchase data for invoice creation
                            purchase["sellerId"] = seller_id

                            # Create Invoice for this purchase
                            create_invoice_for_purchase(purchase, order)

                    except Exception as purchase_error:
                        logger.error(
                            f"❌ Error creating purchase/invoice for item {item['productId']}: {str(purchase_error)}"
                        )

                # 2. Update Seller Analytics
                try:
                    update_seller_analytics(
                        seller_id, order_items, seller_data["total"]
                    )
                except Exception as analytics_error:
                    logger.error(
                        f"❌ Error updating analytics for seller {seller_id}: {str(analytics_error)}"
                    )

                # 3. Create Seller Event
                try:
                    create_seller_event(
                        seller_id=seller_id,
                        event_type="PAYMENT_RECEIVED",
                        order_id=order_id,
                        order_items=order_items,
                        order_total=seller_data["total"],
                    )
                except Exception as event_error:
                    logger.error(
                        f"❌ Error creating event for seller {seller_id}: {str(event_error)}"
                    )

            # Clear user's cart after successful payment (only for cart checkouts)
            transaction_type = metadata.get("transactionType")
            if transaction_type == "cart_checkout":
                try:
                    # Get user's cart
                    cart_response = (
                        supabase.table("Cart")
                        .select("id")
                        .eq("userId", user_id)
                        .execute()
                    )

                    if cart_response.data:
                        cart_id = cart_response.data[0]["id"]

                        # Delete all cart items
                        supabase.table("CartItem").delete().eq(
                            "cartId", cart_id
                        ).execute()

                        # Reset cart totals
                        supabase.table("Cart").update(
                            {
                                "itemCount": 0,
                                "subtotal": 0,
                                "discountAmount": 0,
                                "tax": 0,
                                "total": 0,
                                "updatedAt": datetime.now(timezone.utc).isoformat(),
                            }
                        ).eq("id", cart_id).execute()

                        logger.info(
                            f"✅ Cart cleared for user {user_id} after successful payment"
                        )
                except Exception as cart_error:
                    # Don't fail the whole transaction if cart clearing fails
                    logger.error(f"⚠️ Failed to clear cart: {str(cart_error)}")

            message = "Payment successful. Your order has been confirmed."
        else:
            supabase.table("Order").update(
                {
                    "paymentStatus": "FAILED",
                    "updatedAt": datetime.now(timezone.utc).isoformat(),
                }
            ).eq("id", order_id).execute()
            message = "Payment pending or failed"

        # Format order response
        order_items_raw = order.get("items") or order.get("OrderItem") or []
        order_items = [
            {
                "id": item["id"],
                "productId": item["productId"],
                "title": item["title"],
                "image": item.get("image"),
                "quantity": item["quantity"],
                "price": Decimal(str(item["price"])),
                "subtotal": Decimal(str(item["price"])) * item["quantity"],
                "sellerId": item["sellerId"],
                "sellerName": item["sellerName"],
                "condition": item.get("condition"),
                "location": item.get("location"),
            }
            for item in order_items_raw
        ]

        return {
            "status": data["status"],
            "reference": reference,
            "amount": data["amount"] / 100,
            "currency": data["currency"],
            "paid_at": data.get("paid_at"),
            "order": {
                "id": order["id"],
                "userId": order["userId"],
                "subtotal": Decimal(str(order["subtotal"])),
                "discountAmount": Decimal(str(order["discountAmount"])),
                "tax": Decimal(str(order["tax"])),
                "total": Decimal(str(order["total"])),
                "status": order["status"],
                "paymentStatus": order["paymentStatus"],
                "currency": order["currency"],
                "shippingAddress": order["shippingAddress"],
                "trackingNumber": order.get("trackingNumber"),
                "paymentMethod": order.get("paymentMethod"),
                "paymentGateway": order.get("paymentGateway"),
                "createdAt": order["createdAt"],
                "updatedAt": order["updatedAt"],
                "items": order_items,
                "appliedDiscounts": order.get("appliedDiscounts", []),
            },
            "message": message,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error verifying payment: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to verify payment",
        )


# ========== GET USER ORDERS ==========


@router.get("/orders", response_model=List[OrderResponse])
async def get_user_orders(
    current_user=Depends(get_current_user),
    order_status: Optional[str] = None,
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
):
    """Get user's orders with optional status filter"""
    try:
        user_id = current_user["user_id"]

        query = (
            supabase.table("Order")
            .select("*")
            .eq("userId", user_id)
        )

        if order_status:
            query = query.eq("status", order_status)

        query = query.order("createdAt", desc=True).range(offset, offset + limit - 1)

        response = query.execute()

        orders = []
        for order in response.data:
            # Fetch order items separately
            items_response = (
                supabase.table("OrderItem")
                .select("*")
                .eq("orderId", order["id"])
                .execute()
            )

            # Fetch order discounts separately
            discounts_response = (
                supabase.table("OrderDiscount")
                .select("*")
                .eq("orderId", order["id"])
                .execute()
            )

            order_items = [
                {
                    "id": item["id"],
                    "productId": item["productId"],
                    "title": item["title"],
                    "image": item.get("image"),
                    "quantity": item["quantity"],
                    "price": Decimal(str(item["price"])),
                    "subtotal": Decimal(str(item["price"])) * item["quantity"],
                    "sellerId": item["sellerId"],
                    "sellerName": item["sellerName"],
                    "condition": item.get("condition"),
                    "location": item.get("location"),
                }
                for item in (items_response.data or [])
            ]

            orders.append(
                {
                    "id": order["id"],
                    "userId": order["userId"],
                    "subtotal": Decimal(str(order["subtotal"])),
                    "discountAmount": Decimal(str(order["discountAmount"])),
                    "tax": Decimal(str(order["tax"])),
                    "total": Decimal(str(order["total"])),
                    "status": order["status"],
                    "paymentStatus": order["paymentStatus"],
                    "currency": order["currency"],
                    "shippingAddress": order["shippingAddress"],
                    "trackingNumber": order.get("trackingNumber"),
                    "paymentMethod": order.get("paymentMethod"),
                    "paymentGateway": order.get("paymentGateway"),
                    "createdAt": order["createdAt"],
                    "updatedAt": order["updatedAt"],
                    "items": order_items,
                    "appliedDiscounts": discounts_response.data or [],
                }
            )

        return orders

    except Exception as e:
        logger.error(f"Error fetching orders: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch orders",
        )


# ========== GET SINGLE ORDER ==========


@router.get("/orders/{order_id}", response_model=OrderResponse)
async def get_order(order_id: str, current_user=Depends(get_current_user)):
    """Get a single order by ID"""
    try:
        user_id = current_user["user_id"]

        order_response = (
            supabase.table("Order")
            .select("*")
            .eq("id", order_id)
            .eq("userId", user_id)
            .execute()
        )

        if not order_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Order not found"
            )

        order = order_response.data[0]

        # Fetch order items separately
        items_response = (
            supabase.table("OrderItem")
            .select("*")
            .eq("orderId", order["id"])
            .execute()
        )

        # Fetch order discounts separately
        discounts_response = (
            supabase.table("OrderDiscount")
            .select("*")
            .eq("orderId", order["id"])
            .execute()
        )

        order_items = [
            {
                "id": item["id"],
                "productId": item["productId"],
                "title": item["title"],
                "image": item.get("image"),
                "quantity": item["quantity"],
                "price": Decimal(str(item["price"])),
                "subtotal": Decimal(str(item["price"])) * item["quantity"],
                "sellerId": item["sellerId"],
                "sellerName": item["sellerName"],
                "condition": item.get("condition"),
                "location": item.get("location"),
            }
            for item in (items_response.data or [])
        ]

        return {
            "id": order["id"],
            "userId": order["userId"],
            "subtotal": Decimal(str(order["subtotal"])),
            "discountAmount": Decimal(str(order["discountAmount"])),
            "tax": Decimal(str(order["tax"])),
            "total": Decimal(str(order["total"])),
            "status": order["status"],
            "paymentStatus": order["paymentStatus"],
            "currency": order["currency"],
            "shippingAddress": order["shippingAddress"],
            "trackingNumber": order.get("trackingNumber"),
            "paymentMethod": order.get("paymentMethod"),
            "paymentGateway": order.get("paymentGateway"),
            "createdAt": order["createdAt"],
            "updatedAt": order["updatedAt"],
            "items": order_items,
            "appliedDiscounts": discounts_response.data or [],
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching order: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch order",
        )


# ========== DELETE ORDER ==========


@router.delete("/orders/{order_id}")
async def delete_order(order_id: str, current_user=Depends(get_current_user)):
    """
    Delete an order. Only orders with PENDING payment status can be deleted.
    Completed/paid orders cannot be deleted.
    """
    try:
        user_id = current_user["user_id"]

        logger.info(f"Delete order request from user {user_id} for order {order_id}")

        # Get order to verify ownership and status
        order_response = (
            supabase.table("Order")
            .select("*, items:OrderItem(*)")
            .eq("id", order_id)
            .eq("userId", user_id)
            .execute()
        )

        if not order_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found or you don't have permission to delete it",
            )

        order = order_response.data[0]

        # Only allow deletion of pending orders (not paid/completed)
        if order["paymentStatus"] not in ["PENDING", "FAILED"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete orders that have been paid. Only pending or failed orders can be deleted.",
            )

        # Delete related records first (due to foreign key constraints)

        # 1. Delete OrderDiscount records
        supabase.table("OrderDiscount").delete().eq("orderId", order_id).execute()
        logger.info(f"Deleted discount records for order {order_id}")

        # 2. Delete OrderItem records
        supabase.table("OrderItem").delete().eq("orderId", order_id).execute()
        logger.info(f"Deleted order items for order {order_id}")

        # 3. Delete the Order itself
        delete_response = supabase.table("Order").delete().eq("id", order_id).execute()

        if not delete_response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete order",
            )

        logger.info(f"✅ Order {order_id} deleted successfully by user {user_id}")

        return {
            "success": True,
            "message": "Order deleted successfully",
            "orderId": order_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting order: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete order",
        )


# ========== CANCEL ORDER ==========


@router.post("/orders/{order_id}/cancel")
async def cancel_order(order_id: str, current_user=Depends(get_current_user)):
    """
    Cancel an order. Only orders that are PENDING or CONFIRMED can be cancelled.
    Orders that are SHIPPED or DELIVERED cannot be cancelled.
    """
    try:
        user_id = current_user["user_id"]

        logger.info(f"Cancel order request from user {user_id} for order {order_id}")

        # Get order to verify ownership and status
        order_response = (
            supabase.table("Order")
            .select("*, items:OrderItem(*)")
            .eq("id", order_id)
            .eq("userId", user_id)
            .execute()
        )

        if not order_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found or you don't have permission to cancel it",
            )

        order = order_response.data[0]

        # Check if order can be cancelled
        if order["status"] in ["SHIPPED", "DELIVERED", "CANCELLED"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot cancel order with status: {order['status']}",
            )

        # Update order status to CANCELLED
        update_response = (
            supabase.table("Order")
            .update(
                {
                    "status": "CANCELLED",
                    "updatedAt": datetime.now(timezone.utc).isoformat(),
                }
            )
            .eq("id", order_id)
            .execute()
        )

        if not update_response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to cancel order",
            )

        # If payment was completed, restore product quantities
        if order["paymentStatus"] == "COMPLETED":
            for item in order["items"]:
                try:
                    # Fetch current product quantity
                    product_response = (
                        supabase.table("products")
                        .select("quantity")
                        .eq("id", item["productId"])
                        .execute()
                    )
                    if product_response.data:
                        current_quantity = product_response.data[0]["quantity"]
                        new_quantity = current_quantity + item["quantity"]
                        supabase.table("products").update(
                            {"quantity": new_quantity}
                        ).eq("id", item["productId"]).execute()
                        logger.info(
                            f"Restored {item['quantity']} units to product {item['productId']}"
                        )
                except Exception as restore_error:
                    logger.error(
                        f"Failed to restore quantity for product {item['productId']}: {str(restore_error)}"
                    )

        # Create cancellation notifications
        now = datetime.now(timezone.utc)
        notification_expiry = now + timedelta(days=30)

        # Notify buyer
        buyer_notification = {
            "id": str(uuid.uuid4()),
            "userId": order["userId"],
            "title": "Order Cancelled",
            "notificationType": "INFO",
            "body": f"Your order #{order_id[:8]} has been cancelled successfully. If you were charged, a refund will be processed within 5-7 business days.",
            "dismissed": False,
            "createdAt": now.isoformat(),
            "expiresAt": notification_expiry.isoformat(),
        }

        try:
            supabase.table("Notification").insert(buyer_notification).execute()
            logger.info(f"✅ Cancellation notification sent to buyer {order['userId']}")
        except Exception as notif_error:
            logger.error(f"❌ Failed to create buyer notification: {str(notif_error)}")

        # Notify sellers
        sellers = {}
        for item in order["items"]:
            seller_id = item["sellerId"]
            if seller_id not in sellers:
                sellers[seller_id] = {
                    "name": item["sellerName"],
                    "items": [],
                }
            sellers[seller_id]["items"].append(item)

        for seller_id, seller_info in sellers.items():
            items_count = len(seller_info["items"])
            items_text = ", ".join(
                [
                    f"{item['quantity']}x {item['title']}"
                    for item in seller_info["items"][:2]
                ]
            )
            if items_count > 2:
                items_text += f" and {items_count - 2} more"

            seller_notification = {
                "id": str(uuid.uuid4()),
                "userId": seller_id,
                "title": "Order Cancelled",
                "notificationType": "WARNING",
                "body": f"Order #{order_id[:8]} has been cancelled by the customer. Items: {items_text}.",
                "dismissed": False,
                "createdAt": now.isoformat(),
                "expiresAt": notification_expiry.isoformat(),
            }

            try:
                supabase.table("Notification").insert(seller_notification).execute()
                logger.info(f"✅ Cancellation notification sent to seller {seller_id}")
            except Exception as notif_error:
                logger.error(
                    f"❌ Failed to create seller notification: {str(notif_error)}"
                )

        logger.info(f"✅ Order {order_id} cancelled successfully by user {user_id}")

        return {
            "success": True,
            "message": "Order cancelled successfully",
            "orderId": order_id,
            "status": "CANCELLED",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling order: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel order",
        )


# ========== USER INVOICE ENDPOINTS ==========


@router.get("/user/invoices", response_model=InvoicesListResponse)
async def get_user_invoices(
    current_user=Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[InvoiceStatus] = None,
):
    """
    Get all invoices for the current user (buyer) with pagination.
    Invoices are generated after successful product purchases.
    """
    try:
        user_id = current_user["user_id"]
        user_email = current_user.get("email", "")

        logger.info(
            f"Fetching invoices for user {user_id}, page {page}, page_size {page_size}"
        )

        # Calculate offset
        offset = (page - 1) * page_size

        # Build query - get invoices where customer email matches user's email
        query = supabase.table("Invoice").select(
            """
            *,
            purchase:purchaseId(
                quantity,
                unitPrice,
                shippingAddress,
                product:productId(name)
            )
            """,
            count="exact",
        )

        # Filter by customer email (since invoices are linked to purchases by email)
        if user_email:
            query = query.eq("customerEmail", user_email)
        else:
            # Fallback: try to find invoices through ProductPurchase table
            query = query.in_("purchaseId", [])  # This will return empty results

        # Filter by status if provided
        if status:
            query = query.eq("status", status.value)

        # Order by creation date (newest first) and apply pagination
        query = query.order("createdAt", desc=True).range(
            offset, offset + page_size - 1
        )

        response = query.execute()

        total_count = response.count or 0
        invoices_data = response.data or []

        # Transform data
        invoices = []
        for invoice in invoices_data:
            purchase_data = invoice.get("purchase", {})
            if isinstance(purchase_data, list):
                purchase_data = purchase_data[0] if purchase_data else {}

            product_data = purchase_data.get("product", {})
            if isinstance(product_data, list):
                product_data = product_data[0] if product_data else {}

            invoices.append(
                InvoiceWithPurchaseDetails(
                    id=invoice["id"],
                    invoiceNumber=invoice["invoiceNumber"],
                    purchaseId=invoice["purchaseId"],
                    sellerId=invoice["sellerId"],
                    customerEmail=invoice["customerEmail"],
                    customerName=invoice.get("customerName"),
                    subtotal=Decimal(str(invoice["subtotal"])),
                    tax=Decimal(str(invoice.get("tax", 0))),
                    discount=Decimal(str(invoice.get("discount", 0))),
                    total=Decimal(str(invoice["total"])),
                    currency=invoice["currency"],
                    status=InvoiceStatus(invoice["status"]),
                    sentAt=invoice.get("sentAt"),
                    paidAt=invoice.get("paidAt"),
                    createdAt=invoice["createdAt"],
                    updatedAt=invoice["updatedAt"],
                    # Purchase details
                    productName=product_data.get("name"),
                    quantity=purchase_data.get("quantity"),
                    unitPrice=Decimal(str(purchase_data.get("unitPrice", 0)))
                    if purchase_data.get("unitPrice")
                    else None,
                    shippingAddress=purchase_data.get("shippingAddress"),
                )
            )

        # Calculate pagination info
        total_pages = math.ceil(total_count / page_size) if total_count > 0 else 1
        has_next = page < total_pages
        has_previous = page > 1

        logger.info(f"✅ Retrieved {len(invoices)} invoices for user {user_id}")

        return InvoicesListResponse(
            invoices=invoices,
            total_count=total_count,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            has_next=has_next,
            has_previous=has_previous,
        )

    except Exception as e:
        logger.error(f"❌ Error fetching user invoices: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch invoices",
        )


@router.get("/user/invoices/{invoice_id}", response_model=InvoiceWithPurchaseDetails)
async def get_user_invoice(invoice_id: str, current_user=Depends(get_current_user)):
    """Get a specific invoice by ID for the current user (buyer)"""
    try:
        user_id = current_user["user_id"]
        user_email = current_user.get("email", "")

        # Get invoice with purchase details
        invoice_response = (
            supabase.table("Invoice")
            .select(
                """
                *,
                purchase:purchaseId(
                    quantity,
                    unitPrice,
                    shippingAddress,
                    product:productId(name)
                )
                """
            )
            .eq("id", invoice_id)
            .execute()
        )

        if not invoice_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found"
            )

        invoice = invoice_response.data[0]

        # Verify the invoice belongs to the current user
        if invoice["customerEmail"] != user_email:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to view this invoice",
            )

        purchase_data = invoice.get("purchase", {})
        if isinstance(purchase_data, list):
            purchase_data = purchase_data[0] if purchase_data else {}

        product_data = purchase_data.get("product", {})
        if isinstance(product_data, list):
            product_data = product_data[0] if product_data else {}

        return InvoiceWithPurchaseDetails(
            id=invoice["id"],
            invoiceNumber=invoice["invoiceNumber"],
            purchaseId=invoice["purchaseId"],
            sellerId=invoice["sellerId"],
            customerEmail=invoice["customerEmail"],
            customerName=invoice.get("customerName"),
            subtotal=Decimal(str(invoice["subtotal"])),
            tax=Decimal(str(invoice.get("tax", 0))),
            discount=Decimal(str(invoice.get("discount", 0))),
            total=Decimal(str(invoice["total"])),
            currency=invoice["currency"],
            status=InvoiceStatus(invoice["status"]),
            sentAt=invoice.get("sentAt"),
            paidAt=invoice.get("paidAt"),
            createdAt=invoice["createdAt"],
            updatedAt=invoice["updatedAt"],
            # Purchase details
            productName=product_data.get("name"),
            quantity=purchase_data.get("quantity"),
            unitPrice=Decimal(str(purchase_data.get("unitPrice", 0)))
            if purchase_data.get("unitPrice")
            else None,
            shippingAddress=purchase_data.get("shippingAddress"),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error fetching user invoice {invoice_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch invoice",
        )
