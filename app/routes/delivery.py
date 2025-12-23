from fastapi import APIRouter, HTTPException, status, Depends, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.database import supabase
from app.utils.auth_utils import AuthUtils
from app.models.delivery import (
    ScheduleDeliveryRequest,
    DeliveryResponse,
    AvailableDeliveryResponse,
    AcceptDeliveryRequest,
    UpdateDeliveryStatusRequest,
    DeliveryListResponse,
    AvailableDeliveryListResponse,
    DeliveryStatus,
    DeliveryPriority,
    UserType,
    CalculateDeliveryFeeRequest,
)
from typing import Optional, List
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import logging
import uuid
import math
import os
import httpx

logger = logging.getLogger(__name__)

router = APIRouter()
security = HTTPBearer()


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


def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate distance between two points in kilometers using Haversine formula
    """
    from math import radians, cos, sin, asin, sqrt

    # Convert decimal degrees to radians
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])

    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))

    # Radius of earth in kilometers
    r = 6371

    return c * r


def calculate_delivery_fee(
    pickup_lat: Optional[float] = None,
    pickup_lon: Optional[float] = None,
    delivery_lat: Optional[float] = None,
    delivery_lon: Optional[float] = None,
    priority: str = "STANDARD",
    distance_km: Optional[float] = None
) -> Decimal:
    """
    Calculate delivery fee based on distance and priority
    Formula: distance_km × 15.00 × priority_multiplier
    """
    # Calculate distance if coordinates provided
    if distance_km is None and all([pickup_lat, pickup_lon, delivery_lat, delivery_lon]):
        distance_km = calculate_distance(pickup_lat, pickup_lon, delivery_lat, delivery_lon)

    # Default to 2km if no distance available
    if distance_km is None:
        distance_km = 2.0

    # Base rate per kilometer
    base_rate_per_km = Decimal("15.00")

    # Priority multipliers
    priority_multipliers = {
        "STANDARD": Decimal("1.0"),
        "EXPRESS": Decimal("1.5"),
        "URGENT": Decimal("2.0"),
    }

    # Get multiplier (default to STANDARD if not found)
    multiplier = priority_multipliers.get(priority, Decimal("1.0"))

    # Calculate fee: distance × 15 × priority_multiplier
    delivery_fee = Decimal(str(distance_km)) * base_rate_per_km * multiplier

    # Round to 2 decimal places
    return delivery_fee.quantize(Decimal("0.01"))


def calculate_courier_and_platform_fees(delivery_fee: Decimal) -> tuple[Decimal, Decimal]:
    """Calculate courier fee (70%) and platform fee (30%) from delivery fee"""
    courier_fee = (delivery_fee * Decimal("0.70")).quantize(Decimal("0.01"))
    platform_fee = (delivery_fee * Decimal("0.30")).quantize(Decimal("0.01"))
    return courier_fee, platform_fee


def safe_decimal_convert(value, default: Decimal = Decimal("0")) -> Decimal:
    """Safely convert a value to Decimal, handling None, empty strings, and invalid values"""
    if value is None or value == "":
        return default
    try:
        return Decimal(str(value))
    except (ValueError, TypeError, Exception):
        logger.warning(f"Invalid decimal conversion for value: {value}, using default {default}")
        return default


# ========== CASE 2: CUSTOMER SCHEDULES STANDALONE DELIVERY (ZipoExpress) ==========


@router.post("/schedule", response_model=DeliveryResponse)
async def schedule_delivery(
    request: ScheduleDeliveryRequest, current_user=Depends(get_current_user)
):
    """
    Case 2: Customer schedules a standalone delivery/errand (ZipoExpress).
    Customer provides pickup and delivery addresses.
    Couriers can see this delivery and offer to take it.
    """
    try:
        user_id = current_user["user_id"]
        user_type = current_user.get("user_type", "CUSTOMER")

        logger.info(f"Customer {user_id} scheduling standalone delivery")

        # Create a placeholder order for this delivery
        # This is a delivery-only order (no product purchase)
        order_id = str(uuid.uuid4())

        # Calculate delivery fee using coordinates
        delivery_fee = calculate_delivery_fee(
            pickup_lat=request.pickup_address.latitude,
            pickup_lon=request.pickup_address.longitude,
            delivery_lat=request.delivery_address.latitude,
            delivery_lon=request.delivery_address.longitude,
            priority=request.priority.value
        )
        courier_fee, platform_fee = calculate_courier_and_platform_fees(delivery_fee)

        # Calculate actual distance for storage
        distance_km = None
        if all([request.pickup_address.latitude, request.pickup_address.longitude,
                request.delivery_address.latitude, request.delivery_address.longitude]):
            distance_km = calculate_distance(
                request.pickup_address.latitude,
                request.pickup_address.longitude,
                request.delivery_address.latitude,
                request.delivery_address.longitude
            )

        # Create order for tracking purposes
        order_data = {
            "id": order_id,
            "userId": user_id,
            "subtotal": 0,
            "discountAmount": 0,
            "tax": 0,
            "deliveryFee": float(delivery_fee),
            "total": float(delivery_fee),
            "status": "PENDING",
            "paymentStatus": "PENDING",
            "currency": "GHS",
            "shippingAddress": request.delivery_address.dict(),
            "useCourierService": True,  # Standalone deliveries always use courier service
            "courierServiceStatus": "PENDING",
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "updatedAt": datetime.now(timezone.utc).isoformat(),
        }

        order_response = supabase.table("Order").insert(order_data).execute()

        if not order_response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create order",
            )

        # Create delivery record
        delivery_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        delivery_data = {
            "id": delivery_id,
            "order_id": order_id,
            "pickup_address": request.pickup_address.dict(),
            "delivery_address": request.delivery_address.dict(),
            "pickup_contact_name": request.pickup_contact_name,
            "pickup_contact_phone": request.pickup_contact_phone,
            "delivery_contact_name": request.delivery_contact_name,
            "delivery_contact_phone": request.delivery_contact_phone,
            "scheduled_by_user": user_id,
            "scheduled_by_type": user_type,
            "delivery_fee": float(delivery_fee),
            "courier_fee": float(courier_fee),
            "platform_fee": float(platform_fee),
            "distance_km": distance_km,
            "status": "PENDING",
            "priority": request.priority.value,
            "scheduled_date": request.scheduled_date.isoformat() if request.scheduled_date else None,
            "notes": request.notes,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }

        delivery_response = supabase.table("Delivery").insert(delivery_data).execute()

        if not delivery_response.data:
            # Rollback order creation
            supabase.table("Order").delete().eq("id", order_id).execute()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create delivery",
            )

        delivery = delivery_response.data[0]

        logger.info(f"✅ Delivery {delivery_id} created successfully for customer {user_id}")

        return DeliveryResponse(
            id=delivery["id"],
            order_id=delivery["order_id"],
            courier_id=delivery.get("courier_id"),
            pickup_address=delivery["pickup_address"],
            delivery_address=delivery["delivery_address"],
            pickup_contact_name=delivery.get("pickup_contact_name"),
            pickup_contact_phone=delivery.get("pickup_contact_phone"),
            delivery_contact_name=delivery.get("delivery_contact_name"),
            delivery_contact_phone=delivery.get("delivery_contact_phone"),
            scheduled_by_user=delivery["scheduled_by_user"],
            scheduled_by_type=UserType(delivery["scheduled_by_type"]),
            delivery_fee=safe_decimal_convert(delivery.get("delivery_fee")),
            courier_fee=safe_decimal_convert(delivery.get("courier_fee")),
            platform_fee=safe_decimal_convert(delivery.get("platform_fee")),
            distance_km=delivery.get("distance_km"),
            status=DeliveryStatus(delivery["status"]),
            priority=DeliveryPriority(delivery["priority"]),
            scheduled_date=delivery.get("scheduled_date"),
            estimated_pickup_time=delivery.get("estimated_pickup_time"),
            estimated_delivery_time=delivery.get("estimated_delivery_time"),
            actual_pickup_time=delivery.get("actual_pickup_time"),
            actual_delivery_time=delivery.get("actual_delivery_time"),
            notes=delivery.get("notes"),
            courier_notes=delivery.get("courier_notes"),
            cancellation_reason=delivery.get("cancellation_reason"),
            proof_of_delivery=delivery.get("proof_of_delivery", []),
            customer_signature=delivery.get("customer_signature"),
            rating=delivery.get("rating"),
            review=delivery.get("review"),
            created_at=delivery["created_at"],
            updated_at=delivery["updated_at"],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error scheduling delivery: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to schedule delivery",
        )


# ========== PAYMENT: INITIALIZE DELIVERY PAYMENT ==========


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

        # Calculate delivery fee using coordinates
        delivery_fee = calculate_delivery_fee(
            pickup_lat=request.pickup_address.latitude,
            pickup_lon=request.pickup_address.longitude,
            delivery_lat=request.delivery_address.latitude,
            delivery_lon=request.delivery_address.longitude,
            priority=request.priority.value
        )
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


# ========== PAYMENT: VERIFY AND SCHEDULE DELIVERY ==========


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

        # Create order with COMPLETED payment status
        order_data = {
            "id": order_id,
            "userId": user_id,
            "subtotal": 0,
            "discountAmount": 0,
            "tax": 0,
            "deliveryFee": float(delivery_fee),
            "total": float(delivery_fee),
            "status": "PENDING",
            "paymentStatus": "COMPLETED",  # ✅ Mark as COMPLETED
            "paymentMethod": "PAYSTACK",
            "paymentGateway": "PAYSTACK",
            "currency": "GHS",
            "shippingAddress": delivery_data["delivery_address"],
            "useCourierService": True,  # Standalone deliveries always use courier service
            "courierServiceStatus": "PENDING",
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "updatedAt": datetime.now(timezone.utc).isoformat(),
        }

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
            "scheduled_date": delivery_data.get("scheduled_date") or None,
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


# ========== COURIER: VIEW AVAILABLE DELIVERIES ==========


@router.get("/available", response_model=AvailableDeliveryListResponse)
async def get_available_deliveries(
    current_user=Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    priority: Optional[str] = None,
):
    """
    Get all available deliveries that couriers can accept within 5-mile radius.
    Shows deliveries with status PENDING (not yet assigned to any courier).
    Only shows orders where useCourierService = true and within proximity.
    """
    try:
        user_id = current_user["user_id"]
        user_type = current_user.get("user_type")

        # Verify user is a courier
        if user_type != "COURIER":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only couriers can view available deliveries",
            )

        logger.info(f"Courier {user_id} fetching available deliveries, page {page}")

        # Get courier's current location from users table
        courier_location_response = (
            supabase.table("users")
            .select("latitude, longitude")
            .eq("user_id", user_id)
            .execute()
        )

        if not courier_location_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Courier profile not found",
            )

        courier_data = courier_location_response.data[0]
        courier_lat = courier_data.get("latitude")
        courier_lon = courier_data.get("longitude")

        # Convert to float if they are strings
        if courier_lat is not None:
            courier_lat = float(courier_lat)
        if courier_lon is not None:
            courier_lon = float(courier_lon)

        # Check if courier has location set
        if courier_lat is None or courier_lon is None:
            logger.warning(f"Courier {user_id} has no location set")
            # Return empty list if courier hasn't broadcasted location yet
            return AvailableDeliveryListResponse(
                deliveries=[],
                total_count=0,
                page=page,
                page_size=page_size,
                total_pages=0,
                has_next=False,
                has_previous=False,
            )

        logger.info(f"Courier location: lat={courier_lat}, lon={courier_lon}")

        # Calculate offset
        offset = (page - 1) * page_size

        # Build query - get PENDING deliveries with order details
        query = supabase.table("Delivery").select(
            "*, order:order_id(id, useCourierService, courierServiceStatus, subtotal, total, currency, paymentStatus)",
            count="exact"
        ).eq("status", "PENDING")

        # Filter by priority if provided
        if priority:
            query = query.eq("priority", priority)

        # Order by priority (URGENT first) and creation date
        query = query.order("priority", desc=True).order("created_at", desc=False)
        # Don't apply pagination limit yet - we need to filter by proximity first

        response = query.execute()

        deliveries_data = response.data or []

        # Filter deliveries by:
        # 1. useCourierService = true
        # 2. courierServiceStatus != ACCEPTED
        # 3. Within 5-mile (8.05 km) radius from courier's current location
        RADIUS_KM = 8.05  # 5 miles in kilometers

        filtered_deliveries = []
        for delivery in deliveries_data:
            order_data = delivery.get("order")

            # Handle case where order might be a list or dict
            if isinstance(order_data, list):
                order_data = order_data[0] if order_data else None

            # Check order has useCourierService = true and is available
            if not (order_data and order_data.get("useCourierService") == True):
                continue

            courier_status = order_data.get("courierServiceStatus")
            if courier_status == "ACCEPTED":
                continue

            # Check proximity - calculate distance from courier to pickup location
            pickup_address = delivery.get("pickup_address", {})
            pickup_lat = pickup_address.get("latitude")
            pickup_lon = pickup_address.get("longitude")

            # Skip if pickup location not set
            if pickup_lat is None or pickup_lon is None:
                logger.warning(f"Delivery {delivery['id']} has no pickup coordinates")
                continue

            # Convert to float if they are strings
            try:
                pickup_lat = float(pickup_lat)
                pickup_lon = float(pickup_lon)
            except (ValueError, TypeError) as e:
                logger.warning(f"Delivery {delivery['id']} has invalid pickup coordinates: {e}")
                continue

            # Calculate distance using Haversine formula
            distance_km = calculate_distance(
                courier_lat, courier_lon,
                pickup_lat, pickup_lon
            )

            # Only include deliveries within 10-mile radius
            if distance_km <= RADIUS_KM:
                # Add distance info for sorting/display
                delivery["distance_to_pickup_km"] = round(distance_km, 2)
                filtered_deliveries.append(delivery)
                logger.info(f"Delivery {delivery['id']} within range: {distance_km:.2f} km")
            else:
                logger.debug(f"Delivery {delivery['id']} out of range: {distance_km:.2f} km > {RADIUS_KM} km")

        # Sort by distance (closest first)
        filtered_deliveries.sort(key=lambda d: d.get("distance_to_pickup_km", float('inf')))

        total_count = len(filtered_deliveries)

        # Apply pagination to filtered results
        paginated_deliveries = filtered_deliveries[offset:offset + page_size]

        # Transform data
        deliveries = []
        for delivery in paginated_deliveries:
            # Fetch order items for this delivery
            order_summary = None
            order_id = delivery["order_id"]

            try:
                # Get order items
                order_items_response = (
                    supabase.table("OrderItem")
                    .select("*")
                    .eq("orderId", order_id)
                    .execute()
                )

                order_items_data = order_items_response.data or []

                # Get order data
                order_data = delivery.get("order")
                if isinstance(order_data, list):
                    order_data = order_data[0] if order_data else None

                if order_data and order_items_data:
                    # Build order item summaries
                    order_items = []
                    seller_ids = set()

                    for item in order_items_data:
                        # Handle None or invalid price values
                        price = safe_decimal_convert(item.get("price"))

                        order_items.append({
                            "id": item["id"],
                            "product_id": item["productId"],
                            "title": item["title"],
                            "image": item.get("image"),
                            "quantity": item["quantity"],
                            "price": price,
                            "seller_id": item["sellerId"],
                            "seller_name": item["sellerName"],
                            "condition": item.get("condition"),
                        })
                        seller_ids.add(item["sellerId"])

                    # Check if multi-vendor
                    is_multi_vendor = len(seller_ids) > 1

                    # Safely convert subtotal and total
                    subtotal = safe_decimal_convert(order_data.get("subtotal"))
                    total = safe_decimal_convert(order_data.get("total"))

                    order_summary = {
                        "id": order_data["id"],
                        "subtotal": subtotal,
                        "total": total,
                        "currency": order_data.get("currency", "GHS"),
                        "payment_status": order_data.get("paymentStatus", "PENDING"),
                        "items": order_items,
                        "item_count": len(order_items),
                        "is_multi_vendor": is_multi_vendor,
                    }
            except Exception as e:
                logger.error(f"Failed to fetch order items for delivery {delivery['id']}: {str(e)}")
                order_summary = None

            # Safely convert delivery fees
            delivery_fee = safe_decimal_convert(delivery.get("delivery_fee"))
            courier_fee = safe_decimal_convert(delivery.get("courier_fee"))

            deliveries.append(
                AvailableDeliveryResponse(
                    id=delivery["id"],
                    order_id=delivery["order_id"],
                    pickup_address=delivery["pickup_address"],
                    delivery_address=delivery["delivery_address"],
                    pickup_contact_name=delivery.get("pickup_contact_name"),
                    pickup_contact_phone=delivery.get("pickup_contact_phone"),
                    delivery_contact_name=delivery.get("delivery_contact_name"),
                    delivery_contact_phone=delivery.get("delivery_contact_phone"),
                    delivery_fee=delivery_fee,
                    courier_fee=courier_fee,
                    distance_km=delivery.get("distance_km"),
                    priority=DeliveryPriority(delivery["priority"]),
                    scheduled_date=delivery.get("scheduled_date"),
                    estimated_pickup_time=delivery.get("estimated_pickup_time"),
                    estimated_delivery_time=delivery.get("estimated_delivery_time"),
                    notes=delivery.get("notes"),
                    created_at=delivery["created_at"],
                    order=order_summary,
                )
            )

        # Calculate pagination info
        total_pages = math.ceil(total_count / page_size) if total_count > 0 else 1
        has_next = page < total_pages
        has_previous = page > 1

        logger.info(f"✅ Retrieved {len(deliveries)} available deliveries (with useCourierService=true) for courier {user_id}")

        return AvailableDeliveryListResponse(
            deliveries=deliveries,
            total_count=total_count,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            has_next=has_next,
            has_previous=has_previous,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error fetching available deliveries: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch available deliveries",
        )


# ========== COURIER: ACCEPT DELIVERY ==========


@router.post("/accept", response_model=DeliveryResponse)
async def accept_delivery(
    request: AcceptDeliveryRequest, current_user=Depends(get_current_user)
):
    """
    Courier accepts a delivery request.
    Updates delivery status to ACCEPTED and assigns courier.
    """
    try:
        user_id = current_user["user_id"]
        user_type = current_user.get("user_type")

        # Verify user is a courier
        if user_type != "COURIER":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only couriers can accept deliveries",
            )

        logger.info(f"Courier {user_id} attempting to accept delivery {request.delivery_id}")

        # Get courier profile
        courier_response = (
            supabase.table("Courier")
            .select("*")
            .eq("user_id", user_id)
            .execute()
        )

        if not courier_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Courier profile not found",
            )

        courier = courier_response.data[0]
        courier_id = courier["id"]

        # Check courier's current active deliveries count
        # Active statuses: ACCEPTED, PICKED_UP, IN_TRANSIT (not PENDING, DELIVERED, CANCELLED, FAILED)
        active_deliveries_response = (
            supabase.table("Delivery")
            .select("id, status")
            .eq("courier_id", courier_id)
            .in_("status", ["ACCEPTED", "PICKED_UP", "IN_TRANSIT"])
            .execute()
        )

        active_count = len(active_deliveries_response.data) if active_deliveries_response.data else 0

        logger.info(f"Courier {courier_id} has {active_count} active deliveries")

        # Enforce maximum 2 active orders limit
        MAX_ACTIVE_ORDERS = 2
        if active_count >= MAX_ACTIVE_ORDERS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot accept delivery. You have reached the maximum limit of {MAX_ACTIVE_ORDERS} active orders. Please complete or cancel existing orders before accepting new ones.",
            )

        # Get delivery
        delivery_response = (
            supabase.table("Delivery")
            .select("*")
            .eq("id", request.delivery_id)
            .execute()
        )

        if not delivery_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Delivery not found",
            )

        delivery = delivery_response.data[0]

        # Verify delivery is within proximity (10-mile radius)
        # Get courier's current location
        courier_user_response = (
            supabase.table("users")
            .select("latitude, longitude")
            .eq("user_id", user_id)
            .execute()
        )

        if courier_user_response.data:
            courier_data = courier_user_response.data[0]
            courier_lat = courier_data.get("latitude")
            courier_lon = courier_data.get("longitude")

            pickup_address = delivery.get("pickup_address", {})
            pickup_lat = pickup_address.get("latitude")
            pickup_lon = pickup_address.get("longitude")

            # If both courier and pickup locations are available, verify proximity
            if all([courier_lat, courier_lon, pickup_lat, pickup_lon]):
                distance_km = calculate_distance(
                    courier_lat, courier_lon,
                    pickup_lat, pickup_lon
                )
                RADIUS_KM = 8.05  # 5 miles

                if distance_km > RADIUS_KM:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Delivery is out of range. Distance: {distance_km:.2f} km (max {RADIUS_KM} km / 5 miles)",
                    )

                logger.info(f"Delivery {request.delivery_id} is within range: {distance_km:.2f} km")

        # Check if delivery is still available
        if delivery["status"] != "PENDING":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Delivery is not available. Current status: {delivery['status']}",
            )

        # Check if delivery is already assigned
        if delivery.get("courier_id"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Delivery has already been assigned to another courier",
            )

        # Update delivery with courier assignment
        now = datetime.now(timezone.utc)
        update_data = {
            "courier_id": courier_id,
            "status": "ACCEPTED",
            "updated_at": now.isoformat(),
        }

        if request.estimated_pickup_time:
            update_data["estimated_pickup_time"] = request.estimated_pickup_time.isoformat()

        if request.estimated_delivery_time:
            update_data["estimated_delivery_time"] = request.estimated_delivery_time.isoformat()

        updated_delivery = (
            supabase.table("Delivery")
            .update(update_data)
            .eq("id", request.delivery_id)
            .execute()
        )

        if not updated_delivery.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to accept delivery",
            )

        delivery = updated_delivery.data[0]

        # Update the related Order's courierServiceStatus to ACCEPTED
        order_id = delivery["order_id"]
        order_update = supabase.table("Order").update({
            "courierServiceStatus": "ACCEPTED",
            "updatedAt": now.isoformat()
        }).eq("id", order_id).execute()

        if order_update.data:
            logger.info(f"✅ Order {order_id} courierServiceStatus updated to ACCEPTED")
        else:
            logger.warning(f"⚠️ Failed to update Order courierServiceStatus for order {order_id}")

        # Create status history
        status_history_data = {
            "id": str(uuid.uuid4()),
            "delivery_id": request.delivery_id,
            "status": "ACCEPTED",
            "notes": f"Delivery accepted by courier {courier['courier_code']}",
            "created_at": now.isoformat(),
        }
        supabase.table("DeliveryStatusHistory").insert(status_history_data).execute()

        # Update courier stats
        supabase.table("Courier").update({
            "total_deliveries": courier.get("total_deliveries", 0) + 1,
            "updated_at": now.isoformat(),
        }).eq("id", courier_id).execute()

        # Create notification for customer
        try:
            notification_expiry = now + timedelta(days=7)
            scheduled_info = ""
            if delivery.get("scheduled_date"):
                scheduled_info = f" scheduled for {delivery['scheduled_date']}"

            customer_notification = {
                "id": str(uuid.uuid4()),
                "userId": delivery["scheduled_by_user"],
                "title": "Courier Accepted Your Delivery!",
                "notificationType": "SUCCESS",
                "body": f"A courier ({courier.get('courier_code')}) has accepted your delivery{scheduled_info}. You will receive updates as your delivery progresses.",
                "dismissed": False,
                "createdAt": now.isoformat(),
                "expiresAt": notification_expiry.isoformat(),
            }
            supabase.table("Notification").insert(customer_notification).execute()
            logger.info(f"✅ Customer notification sent for delivery {request.delivery_id}")
        except Exception as notif_error:
            logger.error(f"⚠️ Failed to create customer notification: {str(notif_error)}")

        logger.info(f"✅ Courier {user_id} accepted delivery {request.delivery_id}")

        return DeliveryResponse(
            id=delivery["id"],
            order_id=delivery["order_id"],
            courier_id=delivery.get("courier_id"),
            pickup_address=delivery["pickup_address"],
            delivery_address=delivery["delivery_address"],
            pickup_contact_name=delivery.get("pickup_contact_name"),
            pickup_contact_phone=delivery.get("pickup_contact_phone"),
            delivery_contact_name=delivery.get("delivery_contact_name"),
            delivery_contact_phone=delivery.get("delivery_contact_phone"),
            scheduled_by_user=delivery["scheduled_by_user"],
            scheduled_by_type=UserType(delivery["scheduled_by_type"]),
            delivery_fee=safe_decimal_convert(delivery.get("delivery_fee")),
            courier_fee=safe_decimal_convert(delivery.get("courier_fee")),
            platform_fee=safe_decimal_convert(delivery.get("platform_fee")),
            distance_km=delivery.get("distance_km"),
            status=DeliveryStatus(delivery["status"]),
            priority=DeliveryPriority(delivery["priority"]),
            scheduled_date=delivery.get("scheduled_date"),
            estimated_pickup_time=delivery.get("estimated_pickup_time"),
            estimated_delivery_time=delivery.get("estimated_delivery_time"),
            actual_pickup_time=delivery.get("actual_pickup_time"),
            actual_delivery_time=delivery.get("actual_delivery_time"),
            notes=delivery.get("notes"),
            courier_notes=delivery.get("courier_notes"),
            cancellation_reason=delivery.get("cancellation_reason"),
            proof_of_delivery=delivery.get("proof_of_delivery", []),
            customer_signature=delivery.get("customer_signature"),
            rating=delivery.get("rating"),
            review=delivery.get("review"),
            created_at=delivery["created_at"],
            updated_at=delivery["updated_at"],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error accepting delivery: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to accept delivery",
        )


# ========== COURIER: UPDATE DELIVERY STATUS ==========


@router.put("/{delivery_id}/status", response_model=DeliveryResponse)
async def update_delivery_status(
    delivery_id: str,
    request: UpdateDeliveryStatusRequest,
    current_user=Depends(get_current_user),
):
    """
    Courier updates delivery status (PICKED_UP, IN_TRANSIT, DELIVERED, etc.)
    """
    try:
        user_id = current_user["user_id"]
        user_type = current_user.get("user_type")

        # Verify user is a courier
        if user_type != "COURIER":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only couriers can update delivery status",
            )

        # Get courier profile
        courier_response = (
            supabase.table("Courier")
            .select("*")
            .eq("user_id", user_id)
            .execute()
        )

        if not courier_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Courier profile not found",
            )

        courier = courier_response.data[0]
        courier_id = courier["id"]

        # Get delivery
        delivery_response = (
            supabase.table("Delivery")
            .select("*")
            .eq("id", delivery_id)
            .execute()
        )

        if not delivery_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Delivery not found",
            )

        delivery = delivery_response.data[0]

        # Verify courier is assigned to this delivery
        if delivery.get("courier_id") != courier_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not assigned to this delivery",
            )

        # Update delivery status
        now = datetime.now(timezone.utc)
        update_data = {
            "status": request.status.value,
            "updated_at": now.isoformat(),
        }

        if request.notes:
            update_data["courier_notes"] = request.notes

        # Update actual times based on status
        if request.status == DeliveryStatus.PICKED_UP and not delivery.get("actual_pickup_time"):
            update_data["actual_pickup_time"] = now.isoformat()
        elif request.status == DeliveryStatus.DELIVERED and not delivery.get("actual_delivery_time"):
            update_data["actual_delivery_time"] = now.isoformat()

        # Add proof of delivery if provided
        if request.proof_of_delivery_urls:
            update_data["proof_of_delivery"] = request.proof_of_delivery_urls

        if request.customer_signature:
            update_data["customer_signature"] = request.customer_signature

        updated_delivery = (
            supabase.table("Delivery")
            .update(update_data)
            .eq("id", delivery_id)
            .execute()
        )

        if not updated_delivery.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update delivery status",
            )

        delivery = updated_delivery.data[0]

        # Update the related Order's courierServiceStatus to match delivery status
        order_id = delivery["order_id"]
        order_courier_status_map = {
            "ACCEPTED": "ACCEPTED",
            "PICKED_UP": "PICKED_UP",
            "IN_TRANSIT": "IN_TRANSIT",
            "DELIVERED": "DELIVERED",
            "CANCELLED": "CANCELLED",
            "FAILED": "FAILED",
        }

        new_courier_status = order_courier_status_map.get(request.status.value)
        if new_courier_status:
            order_update = supabase.table("Order").update({
                "courierServiceStatus": new_courier_status,
                "updatedAt": now.isoformat()
            }).eq("id", order_id).execute()

            if order_update.data:
                logger.info(f"✅ Order {order_id} courierServiceStatus updated to {new_courier_status}")
            else:
                logger.warning(f"⚠️ Failed to update Order courierServiceStatus for order {order_id}")

        # Create status history
        status_history_data = {
            "id": str(uuid.uuid4()),
            "delivery_id": delivery_id,
            "status": request.status.value,
            "notes": request.notes,
            "location": request.location,
            "created_at": now.isoformat(),
        }
        supabase.table("DeliveryStatusHistory").insert(status_history_data).execute()

        # Create notifications for all parties involved
        try:
            notification_expiry = now + timedelta(days=7)

            # Status-specific notification messages
            status_messages = {
                "PICKED_UP": {
                    "customer_title": "Order Picked Up",
                    "customer_body": f"Your order has been picked up by the courier and is on its way!",
                    "seller_title": "Order Picked Up",
                    "seller_body": f"Courier has picked up the order and delivery is in progress.",
                    "type": "INFO"
                },
                "IN_TRANSIT": {
                    "customer_title": "Order In Transit",
                    "customer_body": f"Your order is currently in transit and will arrive soon.",
                    "seller_title": "Order In Transit",
                    "seller_body": f"The order is in transit to the customer.",
                    "type": "INFO"
                },
                "DELIVERED": {
                    "customer_title": "Order Delivered Successfully!",
                    "customer_body": f"Your order has been delivered. Thank you for choosing our service!",
                    "seller_title": "Order Delivered Successfully",
                    "seller_body": f"The order has been successfully delivered to the customer.",
                    "type": "SUCCESS"
                },
                "CANCELLED": {
                    "customer_title": "Delivery Cancelled",
                    "customer_body": f"Your delivery has been cancelled. {request.notes or 'Please contact support for more details.'}",
                    "seller_title": "Delivery Cancelled",
                    "seller_body": f"The delivery has been cancelled by the courier. {request.notes or ''}",
                    "type": "ERROR"
                },
                "FAILED": {
                    "customer_title": "Delivery Failed",
                    "customer_body": f"Delivery attempt failed. {request.notes or 'Our team will contact you shortly.'}",
                    "seller_title": "Delivery Failed",
                    "seller_body": f"Delivery attempt failed. {request.notes or 'Customer will be contacted.'}",
                    "type": "ERROR"
                }
            }

            status_info = status_messages.get(request.status.value)

            if status_info:
                # Notify customer (scheduled_by_user)
                customer_notification = {
                    "id": str(uuid.uuid4()),
                    "userId": delivery["scheduled_by_user"],
                    "title": status_info["customer_title"],
                    "notificationType": status_info["type"],
                    "body": status_info["customer_body"],
                    "dismissed": False,
                    "createdAt": now.isoformat(),
                    "expiresAt": notification_expiry.isoformat(),
                }
                supabase.table("Notification").insert(customer_notification).execute()
                logger.info(f"✅ Customer notification sent for delivery {delivery_id} status {request.status.value}")

                # Get order items to notify sellers
                order_id = delivery["order_id"]
                order_items_response = (
                    supabase.table("OrderItem")
                    .select("sellerId")
                    .eq("orderId", order_id)
                    .execute()
                )

                if order_items_response.data:
                    # Get unique seller IDs
                    seller_ids = set(item["sellerId"] for item in order_items_response.data if item.get("sellerId"))

                    # Notify each seller
                    for seller_id in seller_ids:
                        seller_notification = {
                            "id": str(uuid.uuid4()),
                            "userId": seller_id,
                            "title": status_info["seller_title"],
                            "notificationType": status_info["type"],
                            "body": status_info["seller_body"],
                            "dismissed": False,
                            "createdAt": now.isoformat(),
                            "expiresAt": notification_expiry.isoformat(),
                        }
                        supabase.table("Notification").insert(seller_notification).execute()

                    logger.info(f"✅ Seller notifications sent to {len(seller_ids)} sellers for delivery {delivery_id}")

        except Exception as notif_error:
            logger.error(f"⚠️ Failed to create notifications for delivery status update: {str(notif_error)}")

        # Update courier completed deliveries if status is DELIVERED
        if request.status == DeliveryStatus.DELIVERED:
            supabase.table("Courier").update({
                "completed_deliveries": courier.get("completed_deliveries", 0) + 1,
                "updated_at": now.isoformat(),
            }).eq("id", courier_id).execute()

            # Create courier earning record
            courier_fee = safe_decimal_convert(delivery.get("courier_fee"))
            if courier_fee > 0:
                earning_data = {
                    "id": str(uuid.uuid4()),
                    "courier_id": courier_id,
                    "delivery_id": delivery_id,
                    "amount": float(courier_fee),
                    "type": "DELIVERY_FEE",
                    "description": f"Delivery fee for order {delivery['order_id'][:8]}",
                    "status": "PENDING",
                    "created_at": now.isoformat(),
                }
                supabase.table("CourierEarning").insert(earning_data).execute()

        logger.info(f"✅ Delivery {delivery_id} status updated to {request.status.value}")

        return DeliveryResponse(
            id=delivery["id"],
            order_id=delivery["order_id"],
            courier_id=delivery.get("courier_id"),
            pickup_address=delivery["pickup_address"],
            delivery_address=delivery["delivery_address"],
            pickup_contact_name=delivery.get("pickup_contact_name"),
            pickup_contact_phone=delivery.get("pickup_contact_phone"),
            delivery_contact_name=delivery.get("delivery_contact_name"),
            delivery_contact_phone=delivery.get("delivery_contact_phone"),
            scheduled_by_user=delivery["scheduled_by_user"],
            scheduled_by_type=UserType(delivery["scheduled_by_type"]),
            delivery_fee=safe_decimal_convert(delivery.get("delivery_fee")),
            courier_fee=safe_decimal_convert(delivery.get("courier_fee")),
            platform_fee=safe_decimal_convert(delivery.get("platform_fee")),
            distance_km=delivery.get("distance_km"),
            status=DeliveryStatus(delivery["status"]),
            priority=DeliveryPriority(delivery["priority"]),
            scheduled_date=delivery.get("scheduled_date"),
            estimated_pickup_time=delivery.get("estimated_pickup_time"),
            estimated_delivery_time=delivery.get("estimated_delivery_time"),
            actual_pickup_time=delivery.get("actual_pickup_time"),
            actual_delivery_time=delivery.get("actual_delivery_time"),
            notes=delivery.get("notes"),
            courier_notes=delivery.get("courier_notes"),
            cancellation_reason=delivery.get("cancellation_reason"),
            proof_of_delivery=delivery.get("proof_of_delivery", []),
            customer_signature=delivery.get("customer_signature"),
            rating=delivery.get("rating"),
            review=delivery.get("review"),
            created_at=delivery["created_at"],
            updated_at=delivery["updated_at"],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error updating delivery status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update delivery status",
        )


# ========== COURIER: GET MY ACCEPTED DELIVERIES ==========


@router.get("/courier/my-deliveries", response_model=DeliveryListResponse)
async def get_courier_deliveries(
    current_user=Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    delivery_status: Optional[str] = None,
):
    """
    Get all deliveries assigned to the current courier.
    Shows deliveries that the courier has accepted.
    """
    try:
        user_id = current_user["user_id"]
        user_type = current_user.get("user_type")

        # Verify user is a courier
        if user_type != "COURIER":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only couriers can view their deliveries",
            )

        logger.info(f"Courier {user_id} fetching their deliveries, page {page}")

        # Get courier profile
        courier_response = (
            supabase.table("Courier")
            .select("id")
            .eq("user_id", user_id)
            .execute()
        )

        if not courier_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Courier profile not found",
            )

        courier_id = courier_response.data[0]["id"]

        # Calculate offset
        offset = (page - 1) * page_size

        # Build query - get deliveries assigned to this courier
        query = supabase.table("Delivery").select("*", count="exact").eq("courier_id", courier_id)

        # Filter by status if provided
        if delivery_status:
            query = query.eq("status", delivery_status)

        # Order by updated date (most recent first)
        query = query.order("updated_at", desc=True)
        query = query.range(offset, offset + page_size - 1)

        response = query.execute()

        total_count = response.count or 0
        deliveries_data = response.data or []

        # Transform data
        deliveries = []
        for delivery in deliveries_data:
            deliveries.append(
                DeliveryResponse(
                    id=delivery["id"],
                    order_id=delivery["order_id"],
                    courier_id=delivery.get("courier_id"),
                    pickup_address=delivery["pickup_address"],
                    delivery_address=delivery["delivery_address"],
                    pickup_contact_name=delivery.get("pickup_contact_name"),
                    pickup_contact_phone=delivery.get("pickup_contact_phone"),
                    delivery_contact_name=delivery.get("delivery_contact_name"),
                    delivery_contact_phone=delivery.get("delivery_contact_phone"),
                    scheduled_by_user=delivery["scheduled_by_user"],
                    scheduled_by_type=UserType(delivery["scheduled_by_type"]),
                    delivery_fee=safe_decimal_convert(delivery.get("delivery_fee")),
                    courier_fee=safe_decimal_convert(delivery.get("courier_fee")),
                    platform_fee=safe_decimal_convert(delivery.get("platform_fee")),
                    distance_km=delivery.get("distance_km"),
                    status=DeliveryStatus(delivery["status"]),
                    priority=DeliveryPriority(delivery["priority"]),
                    scheduled_date=delivery.get("scheduled_date"),
                    estimated_pickup_time=delivery.get("estimated_pickup_time"),
                    estimated_delivery_time=delivery.get("estimated_delivery_time"),
                    actual_pickup_time=delivery.get("actual_pickup_time"),
                    actual_delivery_time=delivery.get("actual_delivery_time"),
                    notes=delivery.get("notes"),
                    courier_notes=delivery.get("courier_notes"),
                    cancellation_reason=delivery.get("cancellation_reason"),
                    proof_of_delivery=delivery.get("proof_of_delivery", []),
                    customer_signature=delivery.get("customer_signature"),
                    rating=delivery.get("rating"),
                    review=delivery.get("review"),
                    created_at=delivery["created_at"],
                    updated_at=delivery["updated_at"],
                )
            )

        # Calculate pagination info
        total_pages = math.ceil(total_count / page_size) if total_count > 0 else 1
        has_next = page < total_pages
        has_previous = page > 1

        logger.info(f"✅ Retrieved {len(deliveries)} deliveries for courier {user_id}")

        return DeliveryListResponse(
            deliveries=deliveries,
            total_count=total_count,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            has_next=has_next,
            has_previous=has_previous,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error fetching courier deliveries: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch courier deliveries",
        )


# ========== GET USER'S SCHEDULED DELIVERIES ==========


@router.get("/my-deliveries", response_model=DeliveryListResponse)
async def get_my_deliveries(
    current_user=Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    delivery_status: Optional[str] = None,
):
    """
    Get all deliveries scheduled by the current user.
    Shows deliveries with their current status and details.
    """
    try:
        user_id = current_user["user_id"]

        logger.info(f"User {user_id} fetching their scheduled deliveries, page {page}")

        # Calculate offset
        offset = (page - 1) * page_size

        # Build query - get deliveries scheduled by this user
        query = supabase.table("Delivery").select("*", count="exact").eq("scheduled_by_user", user_id)

        # Filter by status if provided
        if delivery_status:
            query = query.eq("status", delivery_status)

        # Order by creation date (most recent first)
        query = query.order("created_at", desc=True)
        query = query.range(offset, offset + page_size - 1)

        response = query.execute()

        total_count = response.count or 0
        deliveries_data = response.data or []

        # Transform data
        deliveries = []
        for delivery in deliveries_data:
            deliveries.append(
                DeliveryResponse(
                    id=delivery["id"],
                    order_id=delivery["order_id"],
                    courier_id=delivery.get("courier_id"),
                    pickup_address=delivery["pickup_address"],
                    delivery_address=delivery["delivery_address"],
                    pickup_contact_name=delivery.get("pickup_contact_name"),
                    pickup_contact_phone=delivery.get("pickup_contact_phone"),
                    delivery_contact_name=delivery.get("delivery_contact_name"),
                    delivery_contact_phone=delivery.get("delivery_contact_phone"),
                    scheduled_by_user=delivery["scheduled_by_user"],
                    scheduled_by_type=UserType(delivery["scheduled_by_type"]),
                    delivery_fee=safe_decimal_convert(delivery.get("delivery_fee")),
                    courier_fee=safe_decimal_convert(delivery.get("courier_fee")),
                    platform_fee=safe_decimal_convert(delivery.get("platform_fee")),
                    distance_km=delivery.get("distance_km"),
                    status=DeliveryStatus(delivery["status"]),
                    priority=DeliveryPriority(delivery["priority"]),
                    scheduled_date=delivery.get("scheduled_date"),
                    estimated_pickup_time=delivery.get("estimated_pickup_time"),
                    estimated_delivery_time=delivery.get("estimated_delivery_time"),
                    actual_pickup_time=delivery.get("actual_pickup_time"),
                    actual_delivery_time=delivery.get("actual_delivery_time"),
                    notes=delivery.get("notes"),
                    courier_notes=delivery.get("courier_notes"),
                    cancellation_reason=delivery.get("cancellation_reason"),
                    proof_of_delivery=delivery.get("proof_of_delivery", []),
                    customer_signature=delivery.get("customer_signature"),
                    rating=delivery.get("rating"),
                    review=delivery.get("review"),
                    created_at=delivery["created_at"],
                    updated_at=delivery["updated_at"],
                )
            )

        # Calculate pagination info
        total_pages = math.ceil(total_count / page_size) if total_count > 0 else 1
        has_next = page < total_pages
        has_previous = page > 1

        logger.info(f"✅ Retrieved {len(deliveries)} scheduled deliveries for user {user_id}")

        return DeliveryListResponse(
            deliveries=deliveries,
            total_count=total_count,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            has_next=has_next,
            has_previous=has_previous,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error fetching user's scheduled deliveries: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch scheduled deliveries",
        )


# ========== GET DELIVERY BY ID ==========


@router.get("/{delivery_id}", response_model=DeliveryResponse)
async def get_delivery(delivery_id: str, current_user=Depends(get_current_user)):
    """Get delivery details by ID with courier information"""
    try:
        user_id = current_user["user_id"]

        delivery_response = (
            supabase.table("Delivery")
            .select("*")
            .eq("id", delivery_id)
            .execute()
        )

        if not delivery_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Delivery not found",
            )

        delivery = delivery_response.data[0]

        # Verify user has access (customer who scheduled it or assigned courier)
        if current_user.get("user_type") == "COURIER":
            courier_response = (
                supabase.table("Courier")
                .select("id")
                .eq("user_id", user_id)
                .execute()
            )
            if courier_response.data:
                courier_id = courier_response.data[0]["id"]
                if delivery.get("courier_id") != courier_id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="You don't have access to this delivery",
                    )
        elif delivery["scheduled_by_user"] != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this delivery",
            )

        return DeliveryResponse(
            id=delivery["id"],
            order_id=delivery["order_id"],
            courier_id=delivery.get("courier_id"),
            pickup_address=delivery["pickup_address"],
            delivery_address=delivery["delivery_address"],
            pickup_contact_name=delivery.get("pickup_contact_name"),
            pickup_contact_phone=delivery.get("pickup_contact_phone"),
            delivery_contact_name=delivery.get("delivery_contact_name"),
            delivery_contact_phone=delivery.get("delivery_contact_phone"),
            scheduled_by_user=delivery["scheduled_by_user"],
            scheduled_by_type=UserType(delivery["scheduled_by_type"]),
            delivery_fee=safe_decimal_convert(delivery.get("delivery_fee")),
            courier_fee=safe_decimal_convert(delivery.get("courier_fee")),
            platform_fee=safe_decimal_convert(delivery.get("platform_fee")),
            distance_km=delivery.get("distance_km"),
            status=DeliveryStatus(delivery["status"]),
            priority=DeliveryPriority(delivery["priority"]),
            scheduled_date=delivery.get("scheduled_date"),
            estimated_pickup_time=delivery.get("estimated_pickup_time"),
            estimated_delivery_time=delivery.get("estimated_delivery_time"),
            actual_pickup_time=delivery.get("actual_pickup_time"),
            actual_delivery_time=delivery.get("actual_delivery_time"),
            notes=delivery.get("notes"),
            courier_notes=delivery.get("courier_notes"),
            cancellation_reason=delivery.get("cancellation_reason"),
            proof_of_delivery=delivery.get("proof_of_delivery", []),
            customer_signature=delivery.get("customer_signature"),
            rating=delivery.get("rating"),
            review=delivery.get("review"),
            created_at=delivery["created_at"],
            updated_at=delivery["updated_at"],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error fetching delivery: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch delivery",
        )


# ========== CALCULATE DELIVERY FEE ==========


@router.post("/delivery/calculate-fee")
async def calculate_delivery_fee_endpoint(
    request: CalculateDeliveryFeeRequest,
    current_user=Depends(get_current_user)
):
    """Calculate delivery fee before payment"""
    try:
        distance_km = request.distance_km

        fee = calculate_delivery_fee(
            distance_km=distance_km,
            priority=request.priority.value
        )
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


# ========== GET COURIER DETAILS FOR A DELIVERY ==========


@router.get("/{delivery_id}/courier")
async def get_delivery_courier_details(delivery_id: str, current_user=Depends(get_current_user)):
    """
    Get courier details for a specific delivery.
    Only accessible by the user who scheduled the delivery.
    """
    try:
        user_id = current_user["user_id"]

        # Get delivery
        delivery_response = (
            supabase.table("Delivery")
            .select("courier_id, scheduled_by_user")
            .eq("id", delivery_id)
            .execute()
        )

        if not delivery_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Delivery not found",
            )

        delivery = delivery_response.data[0]

        # Verify user scheduled this delivery
        if delivery["scheduled_by_user"] != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this delivery",
            )

        # Check if courier is assigned
        if not delivery.get("courier_id"):
            return {
                "delivery_id": delivery_id,
                "courier_assigned": False,
                "message": "No courier has accepted this delivery yet"
            }

        # Get courier details
        courier_response = (
            supabase.table("Courier")
            .select("*, users!inner(name, phone_number)")
            .eq("id", delivery["courier_id"])
            .execute()
        )

        if not courier_response.data:
            return {
                "delivery_id": delivery_id,
                "courier_assigned": False,
                "message": "Courier information not available"
            }

        courier = courier_response.data[0]
        user_info = courier.get("users", {})

        return {
            "delivery_id": delivery_id,
            "courier_assigned": True,
            "courier": {
                "courier_id": courier["id"],
                "courier_code": courier.get("courier_code"),
                "name": user_info.get("name"),
                "phone_number": user_info.get("phone_number"),
                "vehicle_type": courier.get("vehicle_type"),
                "vehicle_number": courier.get("vehicle_number"),
                "rating": courier.get("rating", 0),
                "total_deliveries": courier.get("total_deliveries", 0),
                "completed_deliveries": courier.get("completed_deliveries", 0),
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error fetching courier details: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch courier details",
        )


# ========== COURIER: DASHBOARD OVERVIEW ==========


@router.get("/courier/dashboard")
async def get_courier_dashboard(current_user=Depends(get_current_user)):
    """
    Get courier dashboard overview with statistics:
    - Total earnings (from completed deliveries)
    - Total deliveries (all time)
    - Completed deliveries count
    - Pending deliveries count
    - Active deliveries count (ACCEPTED, PICKED_UP, IN_TRANSIT)
    - Average rating
    - Available balance
    - Recent deliveries
    """
    try:
        user_id = current_user["user_id"]
        user_type = current_user.get("user_type")

        # Verify user is a courier
        if user_type != "COURIER":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only couriers can view dashboard",
            )

        logger.info(f"Courier {user_id} fetching dashboard")

        # Get courier profile
        courier_response = (
            supabase.table("Courier")
            .select("*")
            .eq("user_id", user_id)
            .execute()
        )

        if not courier_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Courier profile not found",
            )

        courier = courier_response.data[0]
        courier_id = courier["id"]

        # Get all deliveries for this courier
        all_deliveries = (
            supabase.table("Delivery")
            .select("*")
            .eq("courier_id", courier_id)
            .execute()
        )

        deliveries_data = all_deliveries.data or []

        # Calculate statistics
        total_deliveries = len(deliveries_data)
        completed_deliveries = len([d for d in deliveries_data if d["status"] == "DELIVERED"])
        pending_deliveries = len([d for d in deliveries_data if d["status"] == "PENDING"])
        active_deliveries = len([
            d for d in deliveries_data
            if d["status"] in ["ACCEPTED", "PICKED_UP", "IN_TRANSIT"]
        ])

        # Get earnings from CourierEarning table
        earnings_response = (
            supabase.table("CourierEarning")
            .select("amount, status, type")
            .eq("courier_id", courier_id)
            .execute()
        )

        earnings_data = earnings_response.data or []

        # Calculate total earnings from completed deliveries
        total_earnings = sum(
            safe_decimal_convert(earning.get("amount"))
            for earning in earnings_data
            if earning["type"] == "DELIVERY_FEE"
        )

        # Calculate available balance (pending + completed but not withdrawn)
        available_balance = sum(
            safe_decimal_convert(earning.get("amount"))
            for earning in earnings_data
            if earning["status"] in ["PENDING", "COMPLETED"]
        )

        # Get recent deliveries (last 5)
        recent_deliveries = (
            supabase.table("Delivery")
            .select("*")
            .eq("courier_id", courier_id)
            .order("updated_at", desc=True)
            .limit(5)
            .execute()
        )

        recent_deliveries_data = recent_deliveries.data or []

        # Transform recent deliveries
        recent_deliveries_list = []
        for delivery in recent_deliveries_data:
            recent_deliveries_list.append({
                "id": delivery["id"],
                "order_id": delivery["order_id"],
                "delivery_address": delivery["delivery_address"],
                "delivery_fee": float(safe_decimal_convert(delivery.get("delivery_fee"))),
                "courier_fee": float(safe_decimal_convert(delivery.get("courier_fee"))),
                "status": delivery["status"],
                "priority": delivery["priority"],
                "created_at": delivery["created_at"],
                "updated_at": delivery["updated_at"],
            })

        # Delivery status breakdown
        status_breakdown = {
            "pending": pending_deliveries,
            "active": active_deliveries,
            "completed": completed_deliveries,
            "cancelled": len([d for d in deliveries_data if d["status"] == "CANCELLED"]),
            "failed": len([d for d in deliveries_data if d["status"] == "FAILED"]),
        }

        logger.info(f"✅ Dashboard loaded for courier {user_id}")

        return {
            "courier_info": {
                "courier_id": courier["id"],
                "courier_code": courier.get("courier_code"),
                "vehicle_type": courier.get("vehicle_type"),
                "rating": courier.get("rating", 0),
                "is_available": courier.get("is_available", True),
                "is_verified": courier.get("verified", False),
            },
            "statistics": {
                "total_deliveries": total_deliveries,
                "completed_deliveries": completed_deliveries,
                "pending_deliveries": pending_deliveries,
                "active_deliveries": active_deliveries,
                "total_earnings": float(total_earnings),
                "available_balance": float(available_balance),
                "average_rating": courier.get("rating", 0),
            },
            "status_breakdown": status_breakdown,
            "recent_deliveries": recent_deliveries_list,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error fetching courier dashboard: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch courier dashboard",
        )
