#!/usr/bin/env python3
"""
Debug script to identify issues with the top products endpoint
"""

import sys
import os
from decimal import Decimal

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from app.database import supabase
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)


def debug_top_products():
    """Debug the top products endpoint issue"""
    print("🔍 DEBUGGING TOP PRODUCTS ENDPOINT")
    print("=" * 50)

    # Get an active seller ID from our previous analysis
    seller_id = "91f01f31-23ea-4658-ac45-0b679c49ae19"  # Glenn Nana
    print(f"🧪 Testing with seller: {seller_id}")

    # 1. Check ProductPurchase table (what endpoint currently uses)
    print("\n1. Checking ProductPurchase table (current endpoint logic)...")
    try:
        purchases_response = (
            supabase.table("ProductPurchase")
            .select(
                "productId, quantity, totalAmount, product:productId(id, name, photos, sellerId)"
            )
            .execute()
        )

        all_purchases = purchases_response.data if purchases_response.data else []
        print(f"   📦 Total ProductPurchase records: {len(all_purchases)}")

        if all_purchases:
            print("   Sample records:")
            for i, purchase in enumerate(all_purchases[:3]):
                product_info = purchase.get("product", {})
                print(
                    f"     - Product {purchase.get('productId', 'N/A')}: {purchase.get('quantity', 0)} units, {purchase.get('totalAmount', 0)} amount"
                )
                if product_info:
                    print(
                        f"       Name: {product_info.get('name', 'N/A')}, Seller: {product_info.get('sellerId', 'N/A')}"
                    )

        # Filter for our test seller
        seller_purchases = []
        for purchase in all_purchases:
            product = purchase.get("product", {})
            if isinstance(product, list):
                product = product[0] if product else {}

            if product.get("sellerId") == seller_id:
                seller_purchases.append(purchase)

        print(f"   👤 ProductPurchase records for test seller: {len(seller_purchases)}")

        if len(seller_purchases) == 0:
            print("   ❌ ISSUE FOUND: No ProductPurchase records for active seller!")
            print("   💡 This explains why top-products endpoint returns empty/fails")

    except Exception as e:
        print(f"   ❌ Error querying ProductPurchase: {e}")

    # 2. Check OrderItem table (where actual sales data is)
    print("\n2. Checking OrderItem table (actual sales data)...")
    try:
        order_items_response = (
            supabase.table("OrderItem")
            .select("id, productId, quantity, price, sellerId, title")
            .eq("sellerId", seller_id)
            .execute()
        )

        order_items = order_items_response.data if order_items_response.data else []
        print(f"   📦 OrderItem records for test seller: {len(order_items)}")

        if order_items:
            print("   Sample order items:")
            for item in order_items[:3]:
                print(
                    f"     - Product {item.get('productId', 'N/A')}: {item.get('quantity', 0)} units @ ${item.get('price', 0)} each"
                )
                print(f"       Title: {item.get('title', 'N/A')}")

            # Calculate what top products should show
            product_stats = {}
            for item in order_items:
                product_id = item.get("productId")
                if not product_id:
                    continue

                if product_id not in product_stats:
                    product_stats[product_id] = {
                        "productId": product_id,
                        "title": item.get("title", "Unknown"),
                        "totalSold": 0,
                        "totalRevenue": Decimal("0.00"),
                    }

                product_stats[product_id]["totalSold"] += item.get("quantity", 0)
                item_revenue = Decimal(str(item.get("price", 0))) * item.get(
                    "quantity", 0
                )
                product_stats[product_id]["totalRevenue"] += item_revenue

            print(f"   📊 Top products from OrderItem data:")
            sorted_products = sorted(
                product_stats.values(), key=lambda x: x["totalSold"], reverse=True
            )
            for i, product in enumerate(sorted_products[:5], 1):
                print(
                    f"     {i}. {product['title']}: {product['totalSold']} sold, ${product['totalRevenue']} revenue"
                )

    except Exception as e:
        print(f"   ❌ Error querying OrderItem: {e}")

    # 3. Check products table structure
    print("\n3. Checking products table structure...")
    try:
        products_response = (
            supabase.table("products")
            .select("id, name, sellerId, photos")
            .eq("sellerId", seller_id)
            .execute()
        )

        products = products_response.data if products_response.data else []
        print(f"   📦 Products for test seller: {len(products)}")

        if products:
            print("   Sample products:")
            for product in products[:3]:
                print(
                    f"     - {product.get('name', 'N/A')} (ID: {product.get('id', 'N/A')})"
                )

    except Exception as e:
        print(f"   ❌ Error querying products: {e}")

    # 4. Test the problematic query from the endpoint
    print("\n4. Testing the endpoint's current query...")
    try:
        # This is the exact query from the endpoint
        test_response = (
            supabase.table("ProductPurchase")
            .select(
                "productId, quantity, totalAmount, product:productId(id, name, photos)"
            )
            .eq("product.sellerId", seller_id)
            .execute()
        )

        print(
            f"   📦 Query result count: {len(test_response.data if test_response.data else [])}"
        )

        if test_response.data:
            print("   Sample results:")
            for purchase in test_response.data[:2]:
                print(f"     - Product {purchase.get('productId')}: {purchase}")
        else:
            print("   ❌ Query returned no results!")
            print("   💡 This confirms why the endpoint fails - no matching data")

    except Exception as e:
        print(f"   ❌ Endpoint query failed: {e}")
        print("   💡 This is likely the cause of the 500 error")

    # 5. Diagnosis and recommendations
    print("\n" + "=" * 50)
    print("📋 DIAGNOSIS")
    print("=" * 50)

    print("🔍 Root Cause Analysis:")
    print("   1. The endpoint queries ProductPurchase table")
    print("   2. But actual sales data is in OrderItem table")
    print("   3. ProductPurchase may be empty or have different structure")
    print("   4. This causes the endpoint to return empty results or fail")

    print("\n💡 Recommended Fix:")
    print("   1. Update top-products endpoint to use OrderItem table")
    print("   2. Use same logic as dashboard for consistency")
    print("   3. Join with products table to get product details")
    print("   4. Aggregate by productId from OrderItem records")

    print("\n🔧 Alternative Solutions:")
    print("   1. Ensure ProductPurchase is properly populated when orders are created")
    print("   2. Create a view/query that combines both tables")
    print("   3. Use OrderItem as primary source (recommended)")


if __name__ == "__main__":
    debug_top_products()
