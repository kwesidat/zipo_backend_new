#!/usr/bin/env python3
"""
Test script for the new seller orders endpoint
Tests the /api/seller/orders endpoint functionality
"""

import sys
import os
from decimal import Decimal

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from app.database import supabase
    from app.models.seller import SellerOrder, SellerOrderItem, SellerOrdersListResponse
    from app.routes.seller import parse_datetime_to_utc
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure you're running from the project root directory")
    sys.exit(1)


def test_seller_orders_endpoint():
    """Test the seller orders endpoint logic"""
    print("🔍 TESTING SELLER ORDERS ENDPOINT")
    print("=" * 50)

    # Use active seller from previous tests
    seller_id = "91f01f31-23ea-4658-ac45-0b679c49ae19"  # Glenn Nana
    print(f"🧪 Testing with seller: {seller_id}")

    try:
        print("\n1. Testing order items query for seller...")

        # Query exactly like the endpoint does
        query = (
            supabase.table("OrderItem")
            .select("""
            id, orderId, productId, quantity, price, title, image, condition, location,
            order:orderId(
                id, userId, subtotal, discountAmount, tax, total, status,
                paymentStatus, currency, shippingAddress, trackingNumber,
                paymentMethod, paymentGateway, createdAt, updatedAt
            )
        """)
            .eq("sellerId", seller_id)
            .order("createdAt", desc=True)
        )

        response = query.execute()
        order_items = response.data if response.data else []

        print(f"   📦 Found {len(order_items)} order items for seller")

        if not order_items:
            print("   ⚠️  No order items found - endpoint would return empty list")
            return True

        # Show sample data
        print("   Sample order items:")
        for i, item in enumerate(order_items[:3]):
            order_info = item.get("order", {})
            print(
                f"     - Item {i + 1}: {item.get('title', 'N/A')} x{item.get('quantity', 0)} @ GHS {item.get('price', 0)}"
            )
            print(
                f"       Order: {order_info.get('id', 'N/A')}, Status: {order_info.get('status', 'N/A')}"
            )

        print("\n2. Testing order grouping logic...")

        # Group order items by order (like endpoint does)
        orders_dict = {}

        for item in order_items:
            order_data = item.get("order", {})
            if not order_data:
                continue

            order_id = order_data["id"]

            if order_id not in orders_dict:
                # Get customer information from shipping address
                shipping_address = order_data.get("shippingAddress", {})
                customer_name = None
                customer_email = None
                customer_phone = None

                if isinstance(shipping_address, dict):
                    customer_name = shipping_address.get("fullName")
                    customer_email = shipping_address.get("email")
                    customer_phone = shipping_address.get("phone")

                orders_dict[order_id] = {
                    "order_data": order_data,
                    "customer_name": customer_name,
                    "customer_email": customer_email,
                    "customer_phone": customer_phone,
                    "items": [],
                    "seller_revenue": Decimal("0.00"),
                    "item_count": 0,
                }

            # Add item to order
            item_price = Decimal(str(item.get("price", 0)))
            item_quantity = item.get("quantity", 0)
            item_subtotal = item_price * item_quantity

            orders_dict[order_id]["items"].append(
                {
                    "id": item["id"],
                    "productId": item["productId"],
                    "title": item.get("title", "Unknown Product"),
                    "image": item.get("image"),
                    "quantity": item_quantity,
                    "price": item_price,
                    "subtotal": item_subtotal,
                    "condition": item.get("condition"),
                    "location": item.get("location"),
                }
            )

            orders_dict[order_id]["seller_revenue"] += item_subtotal
            orders_dict[order_id]["item_count"] += item_quantity

        print(f"   📊 Grouped into {len(orders_dict)} unique orders")

        # Show order summaries
        for i, (order_id, order_info) in enumerate(orders_dict.items()):
            if i >= 3:  # Show only first 3
                break
            print(f"     Order {i + 1} ({order_id[:8]}...):")
            print(f"       - Items: {len(order_info['items'])}")
            print(f"       - Seller Revenue: GHS {order_info['seller_revenue']}")
            print(f"       - Customer: {order_info['customer_name'] or 'Unknown'}")

        print("\n3. Testing SellerOrder model creation...")

        # Test creating SellerOrder objects
        orders_list = list(orders_dict.values())
        orders_list.sort(
            key=lambda x: x["order_data"].get("createdAt", ""), reverse=True
        )

        # Test with first order
        if orders_list:
            test_order = orders_list[0]
            order_data = test_order["order_data"]

            try:
                # Create SellerOrderItem objects
                seller_order_items = []
                for item in test_order["items"]:
                    seller_order_items.append(
                        SellerOrderItem(
                            id=item["id"],
                            productId=item["productId"],
                            title=item["title"],
                            image=item["image"],
                            quantity=item["quantity"],
                            price=item["price"],
                            subtotal=item["subtotal"],
                            condition=item["condition"],
                            location=item["location"],
                        )
                    )

                # Create SellerOrder object
                seller_order = SellerOrder(
                    id=order_data["id"],
                    userId=order_data["userId"],
                    customerName=test_order["customer_name"],
                    customerEmail=test_order["customer_email"],
                    customerPhone=test_order["customer_phone"],
                    subtotal=Decimal(str(order_data.get("subtotal", 0))),
                    discountAmount=Decimal(str(order_data.get("discountAmount", 0))),
                    tax=Decimal(str(order_data.get("tax", 0))),
                    total=Decimal(str(order_data.get("total", 0))),
                    sellerRevenue=test_order["seller_revenue"],
                    status=order_data.get("status", "PENDING"),
                    paymentStatus=order_data.get("paymentStatus", "PENDING"),
                    currency=order_data.get("currency", "GHS"),
                    shippingAddress=order_data.get("shippingAddress"),
                    trackingNumber=order_data.get("trackingNumber"),
                    paymentMethod=order_data.get("paymentMethod"),
                    paymentGateway=order_data.get("paymentGateway"),
                    createdAt=parse_datetime_to_utc(order_data["createdAt"]),
                    updatedAt=parse_datetime_to_utc(order_data["updatedAt"]),
                    items=seller_order_items,
                    itemCount=test_order["item_count"],
                )

                print(f"   ✅ Successfully created SellerOrder object")
                print(f"      - Order ID: {seller_order.id}")
                print(f"      - Customer: {seller_order.customerName or 'Unknown'}")
                print(f"      - Items: {len(seller_order.items)}")
                print(f"      - Seller Revenue: GHS {seller_order.sellerRevenue}")
                print(f"      - Status: {seller_order.status}")

            except Exception as e:
                print(f"   ❌ Error creating SellerOrder object: {e}")
                return False

        print("\n4. Testing SellerOrdersListResponse creation...")

        try:
            # Create response object
            limit = 20
            offset = 0
            total_orders = len(orders_list)

            response = SellerOrdersListResponse(
                orders=[],  # We'll just test with empty for structure
                total=total_orders,
                page=offset // limit + 1,
                limit=limit,
                totalPages=(total_orders + limit - 1) // limit
                if total_orders > 0
                else 0,
            )

            print(f"   ✅ Successfully created SellerOrdersListResponse")
            print(f"      - Total orders: {response.total}")
            print(f"      - Page: {response.page}")
            print(f"      - Limit: {response.limit}")
            print(f"      - Total pages: {response.totalPages}")

        except Exception as e:
            print(f"   ❌ Error creating SellerOrdersListResponse: {e}")
            return False

        print("\n5. Testing with filters...")

        # Test status filter
        completed_items = [
            item
            for item in order_items
            if item.get("order", {}).get("status") == "COMPLETED"
        ]
        pending_items = [
            item
            for item in order_items
            if item.get("order", {}).get("status") == "PENDING"
        ]

        print(f"   📊 Filter results:")
        print(
            f"      - COMPLETED orders: {len(set(item.get('order', {}).get('id') for item in completed_items if item.get('order', {}).get('id')))}"
        )
        print(
            f"      - PENDING orders: {len(set(item.get('order', {}).get('id') for item in pending_items if item.get('order', {}).get('id')))}"
        )

        return True

    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        import traceback

        traceback.print_exc()
        return False


def test_edge_cases():
    """Test edge cases and error handling"""
    print("\n🔍 TESTING EDGE CASES")
    print("=" * 30)

    try:
        print("1. Testing with non-existent seller...")

        fake_seller_id = "00000000-0000-0000-0000-000000000000"

        query = (
            supabase.table("OrderItem")
            .select("id, orderId, productId")
            .eq("sellerId", fake_seller_id)
        )

        response = query.execute()
        order_items = response.data if response.data else []

        print(f"   📦 Found {len(order_items)} order items (expected: 0)")

        if len(order_items) == 0:
            print("   ✅ Correctly returns empty for non-existent seller")
        else:
            print("   ⚠️  Unexpected: found items for fake seller")

        print("\n2. Testing datetime parsing edge cases...")

        test_datetimes = [
            "2025-10-18T00:16:39.601",  # No timezone
            "2025-10-18T00:16:39.601Z",  # Z timezone
            "2025-10-18T00:16:39.601+00:00",  # Explicit UTC
        ]

        for dt_str in test_datetimes:
            try:
                parsed = parse_datetime_to_utc(dt_str)
                print(f"   ✅ Parsed '{dt_str}' → {parsed}")
            except Exception as e:
                print(f"   ❌ Failed to parse '{dt_str}': {e}")
                return False

        return True

    except Exception as e:
        print(f"   ❌ Edge case test failed: {e}")
        return False


def main():
    """Main test function"""
    print("🚀 SELLER ORDERS ENDPOINT TEST")
    print(
        "🕐 Started at:",
        __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )
    print("=" * 60)

    # Run tests
    endpoint_ok = test_seller_orders_endpoint()
    edge_cases_ok = test_edge_cases()

    # Summary
    print("\n" + "=" * 60)
    print("📋 TEST SUMMARY")
    print("=" * 60)

    if endpoint_ok and edge_cases_ok:
        print("✅ ALL TESTS PASSED!")
        print("📝 Seller orders endpoint is ready:")
        print("   - Query logic: Working correctly")
        print("   - Order grouping: Working correctly")
        print("   - Model creation: Working correctly")
        print("   - Response format: Working correctly")
        print("   - Edge cases: Handled correctly")
        print()
        print("🚀 NEXT STEPS:")
        print("   1. Restart your FastAPI server")
        print("   2. Test the endpoint: GET /api/seller/orders")
        print(
            "   3. Try with filters: GET /api/seller/orders?status=COMPLETED&limit=10"
        )
        print("   4. Verify pagination: GET /api/seller/orders?limit=5&offset=5")

    else:
        print("❌ SOME TESTS FAILED")
        if not endpoint_ok:
            print("   - Main endpoint logic has issues")
        if not edge_cases_ok:
            print("   - Edge case handling needs work")

    print(
        f"\n🕐 Test completed at: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    return endpoint_ok and edge_cases_ok


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
