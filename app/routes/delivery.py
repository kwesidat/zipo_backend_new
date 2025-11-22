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


def calculate_courier_and_platform_fees(delivery_fee: Decimal) -> tuple[Decimal, Decimal]:
    """Calculate courier fee (70%) and platform fee (30%) from delivery fee"""
    courier_fee = (delivery_fee * Decimal("0.70")).quantize(Decimal("0.01"))
    platform_fee = (delivery_fee * Decimal("0.30")).quantize(Decimal("0.01"))
    return courier_fee, platform_fee


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

        # Calculate delivery fee
        distance_km = None  # You can integrate Google Maps Distance API here
        delivery_fee = calculate_delivery_fee(distance_km, request.priority.value)
        courier_fee, platform_fee = calculate_courier_and_platform_fees(delivery_fee)

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
            delivery_fee=Decimal(str(delivery["delivery_fee"])),
            courier_fee=Decimal(str(delivery.get("courier_fee", 0))),
            platform_fee=Decimal(str(delivery.get("platform_fee", 0))),
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

        # Calculate delivery fee
        distance_km = None  # You can calculate this using addresses if needed
        delivery_fee = calculate_delivery_fee(distance_km, request.priority.value)
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

        # Create order with PAID status
        order_data = {
            "id": order_id,
            "userId": user_id,
            "subtotal": 0,
            "discountAmount": 0,
            "tax": 0,
            "deliveryFee": float(delivery_fee),
            "total": float(delivery_fee),
            "status": "PENDING",
            "paymentStatus": "PAID",  # ✅ Mark as PAID
            "paymentMethod": "PAYSTACK",
            "paymentGateway": "PAYSTACK",
            "currency": "GHS",
            "shippingAddress": delivery_data["delivery_address"],
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
            "scheduled_date": delivery_data.get("scheduled_date"),
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
    Get all available deliveries that couriers can accept.
    Shows deliveries with status PENDING (not yet assigned to any courier).
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

        # Calculate offset
        offset = (page - 1) * page_size

        # Build query - get PENDING deliveries (not assigned to any courier)
        query = supabase.table("Delivery").select("*", count="exact").eq("status", "PENDING")

        # Filter by priority if provided
        if priority:
            query = query.eq("priority", priority)

        # Order by priority (URGENT first) and creation date
        query = query.order("priority", desc=True).order("created_at", desc=False)
        query = query.range(offset, offset + page_size - 1)

        response = query.execute()

        total_count = response.count or 0
        deliveries_data = response.data or []

        # Transform data
        deliveries = []
        for delivery in deliveries_data:
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
                    delivery_fee=Decimal(str(delivery["delivery_fee"])),
                    courier_fee=Decimal(str(delivery.get("courier_fee", 0))),
                    distance_km=delivery.get("distance_km"),
                    priority=DeliveryPriority(delivery["priority"]),
                    scheduled_date=delivery.get("scheduled_date"),
                    estimated_pickup_time=delivery.get("estimated_pickup_time"),
                    estimated_delivery_time=delivery.get("estimated_delivery_time"),
                    notes=delivery.get("notes"),
                    created_at=delivery["created_at"],
                )
            )

        # Calculate pagination info
        total_pages = math.ceil(total_count / page_size) if total_count > 0 else 1
        has_next = page < total_pages
        has_previous = page > 1

        logger.info(f"✅ Retrieved {len(deliveries)} available deliveries for courier {user_id}")

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
            delivery_fee=Decimal(str(delivery["delivery_fee"])),
            courier_fee=Decimal(str(delivery.get("courier_fee", 0))),
            platform_fee=Decimal(str(delivery.get("platform_fee", 0))),
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

        # Update courier completed deliveries if status is DELIVERED
        if request.status == DeliveryStatus.DELIVERED:
            supabase.table("Courier").update({
                "completed_deliveries": courier.get("completed_deliveries", 0) + 1,
                "updated_at": now.isoformat(),
            }).eq("id", courier_id).execute()

            # Create courier earning record
            courier_fee = Decimal(str(delivery.get("courier_fee", 0)))
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
            delivery_fee=Decimal(str(delivery["delivery_fee"])),
            courier_fee=Decimal(str(delivery.get("courier_fee", 0))),
            platform_fee=Decimal(str(delivery.get("platform_fee", 0))),
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
    status: Optional[str] = None,
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
        if status:
            query = query.eq("status", status)

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
                    delivery_fee=Decimal(str(delivery["delivery_fee"])),
                    courier_fee=Decimal(str(delivery.get("courier_fee", 0))),
                    platform_fee=Decimal(str(delivery.get("platform_fee", 0))),
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
    status: Optional[str] = None,
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
        if status:
            query = query.eq("status", status)

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
                    delivery_fee=Decimal(str(delivery["delivery_fee"])),
                    courier_fee=Decimal(str(delivery.get("courier_fee", 0))),
                    platform_fee=Decimal(str(delivery.get("platform_fee", 0))),
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
            delivery_fee=Decimal(str(delivery["delivery_fee"])),
            courier_fee=Decimal(str(delivery.get("courier_fee", 0))),
            platform_fee=Decimal(str(delivery.get("platform_fee", 0))),
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

        fee = calculate_delivery_fee(distance_km, request.priority.value)
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
