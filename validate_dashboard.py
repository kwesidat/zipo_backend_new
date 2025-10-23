#!/usr/bin/env python3
"""
Simple validation script to check dashboard data sources and diagnose the zero values issue
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import supabase
from decimal import Decimal


def validate_dashboard_data():
    """Validate the dashboard data sources"""
    print("🔍 VALIDATING SELLER DASHBOARD DATA SOURCES")
    print("=" * 60)

    try:
        # 1. Check if we have any sellers (users with role seller)
        print("\n1. Checking for sellers in database...")
        sellers_response = (
            supabase.table("users").select("user_id, name, email, role").execute()
        )

        if not sellers_response.data:
            print("❌ No users found in database")
            return

        sellers = [
            user for user in sellers_response.data if user.get("role") == "seller"
        ]
        print(
            f"✅ Found {len(sellers)} sellers out of {len(sellers_response.data)} total users"
        )

        if not sellers:
            print("❌ No sellers found - all users have different roles")
            print(
                "Available roles:",
                set(user.get("role", "None") for user in sellers_response.data),
            )
            return

        # Use the first seller for testing
        test_seller = sellers[0]
        seller_id = test_seller["user_id"]
        seller_name = test_seller.get("name", "Unknown")

        print(f"🧪 Using test seller: {seller_name} (ID: {seller_id})")

        # 2. Check products for this seller
        print(f"\n2. Checking products for seller {seller_name}...")
        products_response = (
            supabase.table("products")
            .select("id, name, price, quantity, sellerId")
            .eq("sellerId", seller_id)
            .execute()
        )

        products = products_response.data if products_response.data else []
        print(f"✅ Found {len(products)} products for seller")

        if products:
            print("Sample products:")
            for i, product in enumerate(products[:3]):  # Show first 3 products
                print(
                    f"  - {product.get('name', 'Unnamed')}: GHS {product.get('price', 0)}, Stock: {product.get('quantity', 0)}"
                )

        # 3. Check OrderItems for this seller (this is what dashboard uses)
        print(f"\n3. Checking OrderItems for seller {seller_name}...")
        order_items_response = (
            supabase.table("OrderItem")
            .select("""
            id, orderId, productId, quantity, price, createdAt, sellerId,
            order:orderId(
                id, userId, total, status, createdAt, paymentStatus
            )
        """)
            .eq("sellerId", seller_id)
            .execute()
        )

        order_items = order_items_response.data if order_items_response.data else []
        print(
            f"{'✅' if order_items else '❌'} Found {len(order_items)} order items for seller"
        )

        if order_items:
            print("Sample order items:")
            for i, item in enumerate(order_items[:3]):  # Show first 3 items
                order_info = item.get("order", {}) or {}
                print(
                    f"  - Order {order_info.get('id', 'N/A')}: {item.get('quantity', 0)} items @ GHS {item.get('price', 0)} each"
                )
                print(
                    f"    Status: {order_info.get('status', 'N/A')}, Payment: {order_info.get('paymentStatus', 'N/A')}"
                )

        # 4. Calculate what dashboard metrics would show
        print(f"\n4. Calculating dashboard metrics for seller {seller_name}...")

        # Count unique orders
        unique_orders = set()
        unique_customers = set()
        total_revenue = Decimal("0.00")

        for item in order_items:
            order_info = item.get("order", {})
            if order_info and order_info.get("id"):
                unique_orders.add(order_info["id"])
            if order_info and order_info.get("userId"):
                unique_customers.add(order_info["userId"])

            item_revenue = Decimal(str(item.get("price", 0))) * item.get("quantity", 0)
            total_revenue += item_revenue

        total_orders = len(unique_orders)
        total_customers = len(unique_customers)
        total_products = len(products)

        print("\n📊 DASHBOARD METRICS:")
        print(f"  📦 Total Products: {total_products}")
        print(f"  🛒 Total Orders: {total_orders}")
        print(f"  💰 Total Revenue: GHS {total_revenue}")
        print(f"  👥 Total Customers: {total_customers}")
        print(
            f"  📈 Average Order Value: GHS {total_revenue / total_orders if total_orders > 0 else 0}"
        )

        # 5. Diagnosis
        print("\n🩺 DIAGNOSIS:")
        if total_orders == 0:
            print("❌ ISSUE FOUND: No orders found for this seller")
            print("   This explains why dashboard shows zeros!")
            print("   Solutions:")
            print("   1. Ensure OrderItem records have correct sellerId")
            print("   2. Check if orders are being created properly")
            print("   3. Verify the order creation process includes sellerId")
        else:
            print("✅ Orders found - dashboard should show data!")
            if total_revenue == 0:
                print("⚠️  Warning: Orders found but revenue is 0 - check price fields")

        # 6. Check other sellers
        if len(sellers) > 1:
            print(f"\n5. Quick check of other sellers...")
            for other_seller in sellers[1:3]:  # Check 2 more sellers
                other_id = other_seller["user_id"]
                other_name = other_seller.get("name", "Unknown")

                other_items_response = (
                    supabase.table("OrderItem")
                    .select("id")
                    .eq("sellerId", other_id)
                    .execute()
                )
                other_items_count = (
                    len(other_items_response.data) if other_items_response.data else 0
                )

                other_products_response = (
                    supabase.table("products")
                    .select("id")
                    .eq("sellerId", other_id)
                    .execute()
                )
                other_products_count = (
                    len(other_products_response.data)
                    if other_products_response.data
                    else 0
                )

                print(
                    f"  - {other_name}: {other_products_count} products, {other_items_count} order items"
                )

        print("\n" + "=" * 60)
        print("✅ VALIDATION COMPLETE")

        if total_orders > 0:
            print("🎉 Dashboard should now show correct data!")
            print("   The fix to use OrderItem table is working correctly.")
        else:
            print("🔧 Dashboard will show zeros until orders are placed")
            print("   This is expected behavior for sellers with no sales yet.")

    except Exception as e:
        print(f"❌ Error during validation: {str(e)}")
        import traceback

        traceback.print_exc()


def check_active_sellers():
    """Find sellers who actually have products and orders"""
    print("\n🎯 FINDING ACTIVE SELLERS")
    print("=" * 30)

    try:
        # Get all order items with seller info
        order_items_response = (
            supabase.table("OrderItem")
            .select("sellerId, orderId, price, quantity")
            .execute()
        )
        order_items = order_items_response.data if order_items_response.data else []

        # Get all products with seller info
        products_response = (
            supabase.table("products").select("sellerId, name, price").execute()
        )
        products = products_response.data if products_response.data else []

        # Count by seller
        seller_stats = {}

        # Count products per seller
        for product in products:
            seller_id = product.get("sellerId")
            if seller_id:
                if seller_id not in seller_stats:
                    seller_stats[seller_id] = {
                        "products": 0,
                        "order_items": 0,
                        "revenue": 0,
                    }
                seller_stats[seller_id]["products"] += 1

        # Count orders and revenue per seller
        for item in order_items:
            seller_id = item.get("sellerId")
            if seller_id:
                if seller_id not in seller_stats:
                    seller_stats[seller_id] = {
                        "products": 0,
                        "order_items": 0,
                        "revenue": 0,
                    }
                seller_stats[seller_id]["order_items"] += 1
                seller_stats[seller_id]["revenue"] += float(
                    item.get("price", 0)
                ) * item.get("quantity", 0)

        # Get seller names
        active_sellers = []
        for seller_id, stats in seller_stats.items():
            if stats["products"] > 0 or stats["order_items"] > 0:
                seller_response = (
                    supabase.table("users")
                    .select("user_id, name, email")
                    .eq("user_id", seller_id)
                    .execute()
                )
                seller_info = seller_response.data[0] if seller_response.data else {}
                seller_name = seller_info.get("name", "Unknown Seller")

                active_sellers.append(
                    {
                        "id": seller_id,
                        "name": seller_name,
                        "email": seller_info.get("email", ""),
                        "products": stats["products"],
                        "order_items": stats["order_items"],
                        "revenue": stats["revenue"],
                    }
                )

        # Sort by activity (revenue + products)
        active_sellers.sort(
            key=lambda x: x["revenue"] + x["products"] * 10, reverse=True
        )

        print(f"🎉 Found {len(active_sellers)} active sellers:")
        for seller in active_sellers[:5]:  # Show top 5
            print(f"  📊 {seller['name']}")
            print(
                f"     Products: {seller['products']}, Orders: {seller['order_items']}, Revenue: GHS {seller['revenue']:.2f}"
            )
            print(f"     ID: {seller['id']}")
            print()

        if active_sellers:
            print("🧪 Testing dashboard with most active seller...")
            top_seller = active_sellers[0]
            test_seller_dashboard(top_seller["id"], top_seller["name"])

    except Exception as e:
        print(f"❌ Error checking active sellers: {str(e)}")


def test_seller_dashboard(seller_id, seller_name):
    """Test dashboard calculation for a specific seller"""
    print(f"\n🧪 TESTING DASHBOARD FOR {seller_name}")
    print("=" * 50)

    try:
        # Query OrderItems exactly like the dashboard does
        order_items_response = (
            supabase.table("OrderItem")
            .select("""
                id, orderId, productId, quantity, price, createdAt,
                order:orderId(
                    id, userId, total, status, createdAt, paymentStatus
                )
            """)
            .eq("sellerId", seller_id)
            .execute()
        )

        order_items = order_items_response.data if order_items_response.data else []

        # Calculate metrics exactly like dashboard
        unique_orders = set()
        unique_customers = set()
        total_revenue = Decimal("0.00")

        for item in order_items:
            if item.get("order") and item["order"].get("id"):
                unique_orders.add(item["order"]["id"])
            if item.get("order") and item["order"].get("userId"):
                unique_customers.add(item["order"]["userId"])

            item_revenue = Decimal(str(item.get("price", 0))) * item.get("quantity", 0)
            total_revenue += item_revenue

        total_orders = len(unique_orders)
        total_customers = len(unique_customers)

        # Get products
        products_response = (
            supabase.table("products")
            .select("id, quantity, name, price")
            .eq("sellerId", seller_id)
            .execute()
        )
        products = products_response.data if products_response.data else []
        total_products = len(products)

        print(f"📊 DASHBOARD RESULTS for {seller_name}:")
        print(f"  📦 Products: {total_products}")
        print(f"  🛒 Orders: {total_orders}")
        print(f"  💰 Revenue: GHS {total_revenue}")
        print(f"  👥 Customers: {total_customers}")
        print(
            f"  📈 Avg Order Value: GHS {total_revenue / total_orders if total_orders > 0 else 0}"
        )

        if total_orders > 0 and total_revenue > 0:
            print("\n✅ SUCCESS: This seller's dashboard should show real data!")
            print("✅ The dashboard fix is working correctly!")
        else:
            print("\n❌ Issue: Still showing zeros despite having order items")

    except Exception as e:
        print(f"❌ Error testing seller dashboard: {str(e)}")


def check_system_wide_data():
    """Check system-wide data to understand the overall state"""
    print("\n🌐 CHECKING SYSTEM-WIDE DATA")
    print("=" * 40)

    try:
        # Check all products in system
        all_products_response = (
            supabase.table("products").select("id, sellerId, name, price").execute()
        )
        all_products = all_products_response.data if all_products_response.data else []
        print(f"📦 Total products in system: {len(all_products)}")

        if all_products:
            print("Sample products:")
            for i, product in enumerate(all_products[:3]):
                print(
                    f"  - {product.get('name', 'Unnamed')} by seller {product.get('sellerId', 'N/A')}"
                )

        # Check all order items in system
        all_order_items_response = (
            supabase.table("OrderItem")
            .select("id, sellerId, orderId, price, quantity")
            .execute()
        )
        all_order_items = (
            all_order_items_response.data if all_order_items_response.data else []
        )
        print(f"🛒 Total order items in system: {len(all_order_items)}")

        if all_order_items:
            print("Sample order items:")
            for i, item in enumerate(all_order_items[:3]):
                print(
                    f"  - Order {item.get('orderId', 'N/A')} by seller {item.get('sellerId', 'N/A')}: {item.get('quantity', 0)} @ GHS {item.get('price', 0)}"
                )

        # Check all orders in system
        all_orders_response = (
            supabase.table("Order").select("id, userId, total, status").execute()
        )
        all_orders = all_orders_response.data if all_orders_response.data else []
        print(f"📋 Total orders in system: {len(all_orders)}")

        if all_orders:
            print("Sample orders:")
            for i, order in enumerate(all_orders[:3]):
                print(
                    f"  - Order {order.get('id', 'N/A')} by user {order.get('userId', 'N/A')}: GHS {order.get('total', 0)}, Status: {order.get('status', 'N/A')}"
                )

        # Summary
        print(f"\n📊 SYSTEM SUMMARY:")
        print(f"  - Products: {len(all_products)}")
        print(f"  - Orders: {len(all_orders)}")
        print(f"  - Order Items: {len(all_order_items)}")

        if len(all_products) == 0 and len(all_orders) == 0:
            print("\n❗ ROOT CAUSE IDENTIFIED:")
            print("   Your system has no products or orders yet!")
            print("   This is why all seller dashboards show zeros.")
            print("\n💡 To test the dashboard:")
            print("   1. Create some products for sellers")
            print("   2. Create some test orders with those products")
            print("   3. Ensure OrderItems are created with correct sellerId")
        elif len(all_products) > 0 and len(all_order_items) == 0:
            print("\n❗ ISSUE IDENTIFIED:")
            print("   You have products but no orders/sales yet.")
            print("   Dashboard will show zeros until customers make purchases.")
        elif len(all_order_items) > 0:
            # Check if order items have seller IDs
            items_with_seller_id = [
                item for item in all_order_items if item.get("sellerId")
            ]
            print(
                f"\n🔍 Order items with sellerId: {len(items_with_seller_id)}/{len(all_order_items)}"
            )
            if len(items_with_seller_id) == 0:
                print("❗ CRITICAL ISSUE: OrderItems don't have sellerId!")
                print(
                    "   This is why dashboard shows zeros - fix the order creation process."
                )

    except Exception as e:
        print(f"❌ Error checking system data: {str(e)}")


if __name__ == "__main__":
    validate_dashboard_data()
    check_system_wide_data()
    check_active_sellers()
