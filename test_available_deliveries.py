"""
Test script to debug the available deliveries endpoint
"""
import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

# Initialize Supabase
supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_ROLE_KEY")
)

print("=" * 80)
print("Testing Available Deliveries Query")
print("=" * 80)

# Test 1: Get all deliveries with PENDING status
print("\n1. All PENDING deliveries:")
pending_deliveries = supabase.table("Delivery").select(
    "id, order_id, status, created_at"
).eq("status", "PENDING").execute()

print(f"Found {len(pending_deliveries.data)} PENDING deliveries:")
for delivery in pending_deliveries.data:
    print(f"  - Delivery ID: {delivery['id'][:8]}..., Order ID: {delivery['order_id'][:8]}...")

# Test 2: Get deliveries with order details (exactly as in the endpoint)
print("\n2. PENDING deliveries with order details:")
deliveries_with_order = supabase.table("Delivery").select(
    "*, order:order_id(id, useCourierService, courierServiceStatus)"
).eq("status", "PENDING").execute()

print(f"Found {len(deliveries_with_order.data)} deliveries:")
for delivery in deliveries_with_order.data:
    order_data = delivery.get("order")
    print(f"\n  Delivery ID: {delivery['id'][:8]}...")
    print(f"  Order ID: {delivery['order_id'][:8]}...")
    print(f"  Order data type: {type(order_data)}")
    print(f"  Order data: {order_data}")

    # Handle case where order might be a list or dict
    if isinstance(order_data, list):
        order_data = order_data[0] if order_data else None

    if order_data:
        print(f"  useCourierService: {order_data.get('useCourierService')}")
        print(f"  courierServiceStatus: {order_data.get('courierServiceStatus')}")
    else:
        print(f"  ⚠️ No order data found!")

# Test 3: Check all orders with useCourierService = true
print("\n3. All orders with useCourierService = true:")
courier_orders = supabase.table("Order").select(
    "id, useCourierService, courierServiceStatus, status"
).eq("useCourierService", True).execute()

print(f"Found {len(courier_orders.data)} orders with useCourierService=true:")
for order in courier_orders.data:
    print(f"  - Order ID: {order['id'][:8]}..., Status: {order.get('status')}, Courier Status: {order.get('courierServiceStatus')}")

# Test 4: Find deliveries for these courier orders
print("\n4. Deliveries for courier service orders:")
if courier_orders.data:
    order_ids = [order['id'] for order in courier_orders.data]
    deliveries_for_orders = supabase.table("Delivery").select(
        "id, order_id, status"
    ).in_("order_id", order_ids).execute()

    print(f"Found {len(deliveries_for_orders.data)} deliveries:")
    for delivery in deliveries_for_orders.data:
        print(f"  - Delivery ID: {delivery['id'][:8]}..., Order ID: {delivery['order_id'][:8]}..., Status: {delivery['status']}")
else:
    print("  No courier service orders found!")

print("\n" + "=" * 80)
print("Test Complete")
print("=" * 80)
