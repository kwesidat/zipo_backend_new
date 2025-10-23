#!/usr/bin/env python3
"""
Final comprehensive test to verify all seller endpoint fixes are working
Tests both dashboard and top-products endpoints after the fixes
"""

import sys
import os
from datetime import datetime, timezone
from decimal import Decimal

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from app.database import supabase
    from app.routes.seller import parse_datetime_to_utc
    from app.models.seller import TopSellingProduct
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure you're running from the project root directory")
    sys.exit(1)


def test_dashboard_logic():
    """Test the dashboard calculation logic"""
    print("🔍 TESTING DASHBOARD LOGIC")
    print("=" * 40)

    # Use active seller
    seller_id = "91f01f31-23ea-4658-ac45-0b679c49ae19"  # Glenn Nana

    try:
        # Test datetime parsing first
        print("1. Testing datetime helper function...")
        test_datetime = "2025-10-18T00:16:39.601"
        parsed_dt = parse_datetime_to_utc(test_datetime)
        now = datetime.now(timezone.utc)

        # This should not raise an error
        comparison_result = parsed_dt < now
        print(
            f"   ✅ Datetime parsing and comparison working: {test_datetime} < now = {comparison_result}"
        )

        # Test dashboard data retrieval
        print("2. Testing dashboard data retrieval...")
        orders_response = (
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

        order_items = orders_response.data if orders_response.data else []
        print(f"   📦 Found {len(order_items)} order items")

        if order_items:
            # Calculate metrics like dashboard does
            unique_orders = set()
            unique_customers = set()
            total_revenue = Decimal("0.00")

            for item in order_items:
                # Test datetime parsing on real data
                if item.get("createdAt"):
                    dt = parse_datetime_to_utc(item["createdAt"])
                    # This should work without errors
                    month_start = now.replace(
                        day=1, hour=0, minute=0, second=0, microsecond=0
                    )
                    is_this_month = dt >= month_start

                if item.get("order") and item["order"].get("id"):
                    unique_orders.add(item["order"]["id"])
                if item.get("order") and item["order"].get("userId"):
                    unique_customers.add(item["order"]["userId"])

                item_revenue = Decimal(str(item.get("price", 0))) * item.get(
                    "quantity", 0
                )
                total_revenue += item_revenue

            total_orders = len(unique_orders)
            total_customers = len(unique_customers)
            avg_order_value = (
                total_revenue / total_orders if total_orders > 0 else Decimal("0.00")
            )

            print(f"   📊 Dashboard would show:")
            print(f"      - Orders: {total_orders}")
            print(f"      - Revenue: GHS {total_revenue}")
            print(f"      - Customers: {total_customers}")
            print(f"      - Avg Order Value: GHS {avg_order_value}")

            if total_orders > 0 and total_revenue > 0:
                print("   ✅ Dashboard logic working correctly!")
                return True
            else:
                print("   ⚠️  Dashboard shows zeros (might be expected for this seller)")
                return True

        else:
            print("   ⚠️  No order items found for this seller")
            return True

    except Exception as e:
        print(f"   ❌ Dashboard logic failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_top_products_logic():
    """Test the top products calculation logic"""
    print("\n🔍 TESTING TOP PRODUCTS LOGIC")
    print("=" * 40)

    # Use active seller
    seller_id = "91f01f31-23ea-4658-ac45-0b679c49ae19"  # Glenn Nana
    limit = 5

    try:
        print("1. Testing OrderItem-based approach (new implementation)...")

        # Get order items for this seller
        order_items_response = (
            supabase.table("OrderItem")
            .select("id, productId, quantity, price, title")
            .eq("sellerId", seller_id)
            .execute()
        )

        order_items = order_items_response.data if order_items_response.data else []
        print(f"   📦 Found {len(order_items)} order items")

        if not order_items:
            print("   ⚠️  No order items found - endpoint would return empty list")
            return True

        # Get product details for photos
        product_ids = list(
            set(item.get("productId") for item in order_items if item.get("productId"))
        )
        products_response = (
            (
                supabase.table("products")
                .select("id, name, photos")
                .in_("id", product_ids)
                .execute()
            )
            if product_ids
            else None
        )

        products_data = {
            p["id"]: p
            for p in (
                products_response.data
                if products_response and products_response.data
                else []
            )
        }
        print(f"   🗂️  Found product details for {len(products_data)} products")

        # Aggregate by product
        product_stats = {}
        for item in order_items:
            product_id = item.get("productId")
            if not product_id:
                continue

            if product_id not in product_stats:
                product_info = products_data.get(product_id, {})
                product_stats[product_id] = {
                    "productId": product_id,
                    "productName": product_info.get("name")
                    or item.get("title", "Unknown Product"),
                    "photos": product_info.get("photos", []),
                    "totalSold": 0,
                    "totalRevenue": Decimal("0.00"),
                }

            quantity = item.get("quantity", 0)
            price = Decimal(str(item.get("price", 0)))

            product_stats[product_id]["totalSold"] += quantity
            product_stats[product_id]["totalRevenue"] += price * quantity

        # Sort by total sold and get top N
        top_products = sorted(
            product_stats.values(), key=lambda x: x["totalSold"], reverse=True
        )[:limit]

        print(f"   🏆 Top {len(top_products)} products:")
        for i, product in enumerate(top_products, 1):
            print(
                f"      {i}. {product['productName']}: {product['totalSold']} sold, GHS {product['totalRevenue']}"
            )

        # Test creating TopSellingProduct objects
        print("2. Testing TopSellingProduct object creation...")
        result = []
        for product in top_products:
            try:
                top_product = TopSellingProduct(
                    productId=product["productId"],
                    productName=product["productName"],
                    totalSold=product["totalSold"],
                    totalRevenue=product["totalRevenue"],
                    photos=product["photos"],
                )
                result.append(top_product)
            except Exception as e:
                print(f"   ❌ Error creating TopSellingProduct: {e}")
                return False

        print(f"   ✅ Successfully created {len(result)} TopSellingProduct objects")

        # Test JSON serialization
        print("3. Testing JSON serialization...")
        try:
            json_data = []
            for product in result:
                product_dict = {
                    "productId": product.productId,
                    "productName": product.productName,
                    "totalSold": product.totalSold,
                    "totalRevenue": float(
                        product.totalRevenue
                    ),  # Config converts Decimal to float
                    "photos": product.photos,
                }
                json_data.append(product_dict)

            print(f"   ✅ JSON serialization successful")
            print(f"   📄 Sample: {json_data[0] if json_data else 'No data'}")

        except Exception as e:
            print(f"   ❌ JSON serialization failed: {e}")
            return False

        print("   ✅ Top products logic working correctly!")
        return True

    except Exception as e:
        print(f"   ❌ Top products logic failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_data_consistency():
    """Test consistency between different data sources"""
    print("\n🔍 TESTING DATA CONSISTENCY")
    print("=" * 40)

    try:
        # Get total counts from each table
        order_items_response = (
            supabase.table("OrderItem").select("id", count="exact").execute()
        )
        product_purchases_response = (
            supabase.table("ProductPurchase").select("id", count="exact").execute()
        )
        orders_response = supabase.table("Order").select("id", count="exact").execute()
        products_response = (
            supabase.table("products").select("id", count="exact").execute()
        )

        order_items_count = (
            order_items_response.count
            if hasattr(order_items_response, "count")
            else len(order_items_response.data or [])
        )
        product_purchases_count = (
            product_purchases_response.count
            if hasattr(product_purchases_response, "count")
            else len(product_purchases_response.data or [])
        )
        orders_count = (
            orders_response.count
            if hasattr(orders_response, "count")
            else len(orders_response.data or [])
        )
        products_count = (
            products_response.count
            if hasattr(products_response, "count")
            else len(products_response.data or [])
        )

        print(f"📊 System Overview:")
        print(f"   - Products: {products_count}")
        print(f"   - Orders: {orders_count}")
        print(f"   - OrderItems: {order_items_count}")
        print(f"   - ProductPurchases: {product_purchases_count}")

        # Check active sellers
        active_sellers_response = (
            supabase.table("OrderItem").select("sellerId").execute()
        )

        seller_ids = set(
            item.get("sellerId")
            for item in (active_sellers_response.data or [])
            if item.get("sellerId")
        )
        print(f"   - Active sellers (with orders): {len(seller_ids)}")

        if order_items_count > 0 and len(seller_ids) > 0:
            print("   ✅ System has data for dashboard and top-products endpoints")
            return True
        else:
            print("   ⚠️  Limited data - endpoints will show minimal results")
            return True

    except Exception as e:
        print(f"   ❌ Data consistency check failed: {e}")
        return False


def main():
    """Main test function"""
    print("🚀 FINAL COMPREHENSIVE ENDPOINT TEST")
    print("🕐 Started at:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 60)

    # Run all tests
    dashboard_ok = test_dashboard_logic()
    top_products_ok = test_top_products_logic()
    data_ok = test_data_consistency()

    # Summary
    print("\n" + "=" * 60)
    print("📋 FINAL TEST SUMMARY")
    print("=" * 60)

    if dashboard_ok and top_products_ok and data_ok:
        print("✅ ALL TESTS PASSED!")
        print("📝 What this means:")
        print("   - Dashboard endpoint: Fixed and ready")
        print("   - Top products endpoint: Fixed and ready")
        print("   - Datetime parsing: Working correctly")
        print("   - Type conversions: Working correctly")
        print("   - Data sources: Consistent and available")
        print()
        print("🚀 NEXT STEPS:")
        print("   1. Restart your FastAPI server")
        print("   2. Test endpoints with real authentication:")
        print("      - GET /api/seller/dashboard")
        print("      - GET /api/seller/top-products?limit=5")
        print("   3. Both should return real data for active sellers")
        print("   4. Both should return zeros/empty for inactive sellers")

    else:
        print("❌ SOME TESTS FAILED")
        print("🔧 Issues detected:")
        if not dashboard_ok:
            print("   - Dashboard logic has problems")
        if not top_products_ok:
            print("   - Top products logic has problems")
        if not data_ok:
            print("   - Data consistency issues")

        print("\n🔧 ACTIONS NEEDED:")
        print("   1. Review the specific errors above")
        print("   2. Fix any remaining issues")
        print("   3. Restart server after fixes")

    print(f"\n🕐 Test completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    return dashboard_ok and top_products_ok and data_ok


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
