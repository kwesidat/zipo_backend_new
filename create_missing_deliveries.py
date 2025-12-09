"""
Script to create Delivery records for existing orders that have useCourierService=true
but don't have a corresponding Delivery record yet.
"""
import os
from dotenv import load_dotenv
from supabase import create_client
from datetime import datetime, timezone
from decimal import Decimal
import uuid

load_dotenv()

# Initialize Supabase
supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_ROLE_KEY")
)

def calculate_delivery_fee(distance_km, priority="STANDARD"):
    """Calculate delivery fee based on distance and priority"""
    base_fee = Decimal("10.00")  # Base fee in GHS

    if distance_km:
        distance_fee = Decimal(str(distance_km)) * Decimal("2.00")
    else:
        distance_fee = Decimal("20.00")

    priority_multipliers = {
        "STANDARD": Decimal("1.0"),
        "EXPRESS": Decimal("1.5"),
        "URGENT": Decimal("2.0"),
    }

    multiplier = priority_multipliers.get(priority, Decimal("1.0"))
    total_fee = (base_fee + distance_fee) * multiplier

    return total_fee.quantize(Decimal("0.01"))


def calculate_courier_and_platform_fees(delivery_fee):
    """Calculate courier fee (70%) and platform fee (30%) from delivery fee"""
    courier_fee = (delivery_fee * Decimal("0.70")).quantize(Decimal("0.01"))
    platform_fee = (delivery_fee * Decimal("0.30")).quantize(Decimal("0.01"))
    return courier_fee, platform_fee


print("=" * 80)
print("Creating Missing Delivery Records")
print("=" * 80)

# Get all orders with useCourierService = true
courier_orders = supabase.table("Order").select(
    "*,items:OrderItem(*)"
).eq("useCourierService", True).execute()

print(f"\nFound {len(courier_orders.data)} orders with useCourierService=true")

# Check which ones already have delivery records
for order in courier_orders.data:
    order_id = order["id"]

    # Check if delivery exists
    existing_delivery = supabase.table("Delivery").select("id").eq("order_id", order_id).execute()

    if existing_delivery.data:
        print(f"\n[OK] Order {order_id[:8]}... already has delivery record")
        continue

    print(f"\n[CREATING] Creating delivery for order {order_id[:8]}...")

    try:
        # Get order items
        order_items = order.get("items", [])

        # Get seller location as pickup address (first item's seller)
        pickup_address = {}
        pickup_contact_name = ""
        pickup_contact_phone = ""

        if order_items:
            first_item = order_items[0]
            seller_response = supabase.table("users").select("*").eq("user_id", first_item["sellerId"]).execute()
            if seller_response.data:
                seller = seller_response.data[0]
                pickup_address = {
                    "street": seller.get("address", ""),
                    "city": seller.get("city", ""),
                    "country": seller.get("country", ""),
                }
                pickup_contact_name = seller.get("name", "")
                pickup_contact_phone = seller.get("phone_number", "")

        # Get delivery address from order
        shipping_address = order.get("shippingAddress", {})
        delivery_metadata = shipping_address.get("deliveryMetadata", {}) if isinstance(shipping_address, dict) else {}

        delivery_address = {
            "street": shipping_address.get("street", "") if isinstance(shipping_address, dict) else "",
            "city": shipping_address.get("city", "") if isinstance(shipping_address, dict) else "",
            "country": shipping_address.get("country", "") if isinstance(shipping_address, dict) else "",
        }

        delivery_contact_name = shipping_address.get("fullName", "") if isinstance(shipping_address, dict) else ""
        delivery_contact_phone = shipping_address.get("phoneNumber", "") if isinstance(shipping_address, dict) else ""

        # Calculate delivery fee
        delivery_fee = Decimal(str(order.get("deliveryFee", 0)))
        if delivery_fee == 0:
            delivery_fee = calculate_delivery_fee(None, delivery_metadata.get("priority", "STANDARD"))

        courier_fee, platform_fee = calculate_courier_and_platform_fees(delivery_fee)

        # Create delivery record
        delivery_id = str(uuid.uuid4())
        delivery_data = {
            "id": delivery_id,
            "order_id": order_id,
            "pickup_address": pickup_address,
            "delivery_address": delivery_address,
            "pickup_contact_name": pickup_contact_name,
            "pickup_contact_phone": pickup_contact_phone,
            "delivery_contact_name": delivery_contact_name,
            "delivery_contact_phone": delivery_contact_phone,
            "scheduled_by_user": order["userId"],
            "scheduled_by_type": "CUSTOMER",
            "delivery_fee": float(delivery_fee),
            "courier_fee": float(courier_fee),
            "platform_fee": float(platform_fee),
            "distance_km": delivery_metadata.get("distance_km"),
            "status": "PENDING",
            "priority": delivery_metadata.get("priority", "STANDARD"),
            "scheduled_date": delivery_metadata.get("scheduled_date"),
            "notes": delivery_metadata.get("deliveryNotes"),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        delivery_response = supabase.table("Delivery").insert(delivery_data).execute()

        if delivery_response.data:
            print(f"   [SUCCESS] Created delivery {delivery_id[:8]}... for order {order_id[:8]}...")
        else:
            print(f"   [FAILED] Failed to create delivery for order {order_id[:8]}...")

    except Exception as e:
        print(f"   [ERROR] Error creating delivery: {str(e)}")

print("\n" + "=" * 80)
print("Script Complete")
print("=" * 80)
