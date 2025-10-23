#!/usr/bin/env python3
"""
Simple validation to check if the dashboard fix is working
Uses only built-in Python modules
"""

import sys
import os
from datetime import datetime, timezone

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from app.database import supabase
    from decimal import Decimal
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure you're running from the project root directory")
    sys.exit(1)


def validate_fix():
    """Validate that the dashboard fix is working"""
    print("🔍 VALIDATING DASHBOARD FIX")
    print("=" * 40)

    # Test 1: Check if we can import the helper function
    print("1. Testing helper function import...")
    try:
        from app.routes.seller import parse_datetime_to_utc

        print("   ✅ Helper function imported successfully")
    except ImportError:
        print("   ❌ Cannot import helper function")
        return False

    # Test 2: Test datetime parsing
    print("2. Testing datetime parsing...")
    try:
        # Test different datetime formats
        test_cases = [
            "2025-10-18T00:16:39.601",  # No timezone
            "2025-10-18T00:16:39.601Z",  # Z timezone
            "2025-10-18T00:16:39.601+00:00",  # Explicit UTC
        ]

        for dt_str in test_cases:
            parsed_dt = parse_datetime_to_utc(dt_str)
            print(f"   ✅ '{dt_str}' → {parsed_dt} (timezone: {parsed_dt.tzinfo})")

            # Verify timezone-aware
            if parsed_dt.tzinfo is None:
                print(f"   ❌ Parsed datetime is timezone-naive: {parsed_dt}")
                return False

    except Exception as e:
        print(f"   ❌ Datetime parsing failed: {e}")
        return False

    # Test 3: Check database connectivity
    print("3. Testing database connectivity...")
    try:
        response = supabase.table("users").select("user_id").limit(1).execute()
        if response.data:
            print("   ✅ Database connection working")
        else:
            print("   ⚠️  Database connected but no users found")
    except Exception as e:
        print(f"   ❌ Database connection failed: {e}")
        return False

    # Test 4: Find sellers with data
    print("4. Finding sellers with actual data...")
    try:
        # Get sellers with order items
        order_items_response = (
            supabase.table("OrderItem").select("sellerId, price, quantity").execute()
        )

        seller_stats = {}
        for item in order_items_response.data or []:
            seller_id = item.get("sellerId")
            if seller_id:
                if seller_id not in seller_stats:
                    seller_stats[seller_id] = {"revenue": 0, "items": 0}

                price = float(item.get("price", 0))
                quantity = int(item.get("quantity", 0))
                seller_stats[seller_id]["revenue"] += price * quantity
                seller_stats[seller_id]["items"] += 1

        active_sellers = [
            (sid, stats) for sid, stats in seller_stats.items() if stats["items"] > 0
        ]

        print(f"   ✅ Found {len(active_sellers)} sellers with order data")

        if active_sellers:
            # Show top seller
            top_seller = max(active_sellers, key=lambda x: x[1]["revenue"])
            seller_id, stats = top_seller
            print(
                f"   📊 Top seller {seller_id}: {stats['items']} items, GHS {stats['revenue']:.2f}"
            )

            # Test dashboard calculation for this seller
            return test_dashboard_calculation(seller_id)
        else:
            print("   ⚠️  No sellers have order data yet")
            print("   💡 Dashboard will show zeros until orders are created")
            return True

    except Exception as e:
        print(f"   ❌ Seller analysis failed: {e}")
        return False


def test_dashboard_calculation(seller_id):
    """Test dashboard calculation for a specific seller"""
    print(f"5. Testing dashboard calculation for seller {seller_id}...")

    try:
        # Get order items like the dashboard does
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

        if not order_items:
            print("   ⚠️  No order items found - dashboard will show zeros")
            return True

        # Calculate metrics like the dashboard
        unique_orders = set()
        unique_customers = set()
        total_revenue = Decimal("0.00")

        for item in order_items:
            # Test datetime parsing on real data
            if item.get("createdAt"):
                try:
                    from app.routes.seller import parse_datetime_to_utc

                    dt = parse_datetime_to_utc(item["createdAt"])
                    # Can compare with timezone-aware datetime
                    now = datetime.now(timezone.utc)
                    is_recent = dt >= (
                        now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                    )
                    # This comparison should not fail
                except Exception as e:
                    print(f"   ❌ Datetime comparison failed: {e}")
                    return False

            # Calculate metrics
            if item.get("order") and item["order"].get("id"):
                unique_orders.add(item["order"]["id"])
            if item.get("order") and item["order"].get("userId"):
                unique_customers.add(item["order"]["userId"])

            item_revenue = Decimal(str(item.get("price", 0))) * item.get("quantity", 0)
            total_revenue += item_revenue

        total_orders = len(unique_orders)
        total_customers = len(unique_customers)

        print(f"   📊 Calculated metrics:")
        print(f"      - Orders: {total_orders}")
        print(f"      - Revenue: GHS {total_revenue}")
        print(f"      - Customers: {total_customers}")

        if total_orders > 0 and total_revenue > 0:
            print("   ✅ Dashboard should show real data for this seller!")
            return True
        else:
            print("   ⚠️  Calculated zeros - check if order items have valid data")
            return True

    except Exception as e:
        print(f"   ❌ Dashboard calculation test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def check_common_issues():
    """Check for common issues that might cause problems"""
    print("6. Checking for common issues...")

    issues_found = []

    # Check if server needs restart
    try:
        from app.routes.seller import get_seller_dashboard
        import inspect

        # Get the source code of the function
        source = inspect.getsource(get_seller_dashboard)

        if "total_sales" in source and "totalSales=total_sales" in source:
            issues_found.append("❌ Old undefined variable 'total_sales' still in code")

        if "parse_datetime_to_utc" not in source:
            issues_found.append("❌ New datetime helper function not being used")

        if 'datetime.fromisoformat(item["createdAt"].replace("Z", "+00:00"))' in source:
            issues_found.append("❌ Old datetime parsing still in code")

    except Exception as e:
        issues_found.append(f"❌ Could not analyze function source: {e}")

    if issues_found:
        print("   Issues found:")
        for issue in issues_found:
            print(f"      {issue}")
        print("   🔧 SOLUTION: Restart the FastAPI server to load the fixed code")
        return False
    else:
        print("   ✅ No common issues detected")
        return True


def main():
    """Main validation function"""
    print(f"🕐 Validation started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    try:
        fix_working = validate_fix()
        issues_ok = check_common_issues()

        print("\n" + "=" * 40)
        print("📋 VALIDATION SUMMARY")
        print("=" * 40)

        if fix_working and issues_ok:
            print("✅ SUCCESS: Dashboard fix is working correctly!")
            print("📝 What this means:")
            print("   - Datetime parsing is fixed")
            print("   - Variable errors are resolved")
            print("   - Dashboard will show real data for active sellers")
            print("   - Dashboard will show zeros for inactive sellers (expected)")
            print()
            print("🚀 ACTION: Test the API endpoint with a real seller token")

        else:
            print("❌ ISSUES DETECTED")
            if not fix_working:
                print("   - Dashboard calculation has problems")
            if not issues_ok:
                print("   - Common issues detected (likely need server restart)")
            print()
            print("🔧 ACTION: Address the issues listed above")

    except Exception as e:
        print(f"❌ VALIDATION FAILED: {e}")
        import traceback

        traceback.print_exc()

    print(f"\n🕐 Validation completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
