"""
Fix standalone delivery orders to have useCourierService = true
These are orders with subtotal = 0 (delivery-only orders)
"""
import os
from dotenv import load_dotenv
from supabase import create_client
from datetime import datetime, timezone

load_dotenv()

# Initialize Supabase
supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_ROLE_KEY")
)

print("=" * 80)
print("Fixing Standalone Delivery Orders")
print("=" * 80)

# Get all orders with subtotal = 0 (standalone deliveries)
standalone_orders = supabase.table("Order").select("*").eq("subtotal", 0).execute()

print(f"\nFound {len(standalone_orders.data)} orders with subtotal=0 (standalone deliveries)")

for order in standalone_orders.data:
    order_id = order["id"]
    use_courier = order.get("useCourierService")
    courier_status = order.get("courierServiceStatus")

    print(f"\nOrder {order_id[:8]}...")
    print(f"  Current useCourierService: {use_courier}")
    print(f"  Current courierServiceStatus: {courier_status}")

    # Update if needed
    if use_courier != True or courier_status is None:
        update_data = {
            "useCourierService": True,
            "courierServiceStatus": courier_status or "PENDING",
            "updatedAt": datetime.now(timezone.utc).isoformat()
        }

        result = supabase.table("Order").update(update_data).eq("id", order_id).execute()

        if result.data:
            print(f"  [UPDATED] Set useCourierService=True, courierServiceStatus={update_data['courierServiceStatus']}")
        else:
            print(f"  [FAILED] Could not update order")
    else:
        print(f"  [OK] Already has correct flags")

print("\n" + "=" * 80)
print("Script Complete")
print("=" * 80)
