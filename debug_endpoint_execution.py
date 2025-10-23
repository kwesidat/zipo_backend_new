#!/usr/bin/env python3
"""
Simulate exact endpoint execution to find the specific error in top-products
"""

import sys
import os
from decimal import Decimal
from typing import Dict, Any, List

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from app.database import supabase
    from app.models.seller import TopSellingProduct
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)


def simulate_top_products_endpoint():
    """Simulate the exact execution of get_top_selling_products endpoint"""
    print("🧪 SIMULATING TOP PRODUCTS ENDPOINT EXECUTION")
    print("=" * 60)

    # Use the same seller we know has data
    seller_id = "91f01f31-23ea-4658-ac45-0b679c49ae19"  # Glenn Nana
    limit = 5

    print(f"📝 Input Parameters:")
    print(f"   - seller_id: {seller_id}")
    print(f"   - limit: {limit}")

    try:
        print("\n1. Executing database query...")

        # Execute the exact query from the endpoint
        purchases_response = (
            supabase.table("ProductPurchase")
            .select(
                "productId, quantity, totalAmount, product:productId(id, name, photos)"
            )
            .eq("product.sellerId", seller_id)
            .execute()
        )

        print(f"   ✅ Query executed successfully")
        print(
            f"   📦 Raw response data count: {len(purchases_response.data) if purchases_response.data else 0}"
        )

        if not purchases_response.data:
            print("   ⚠️  Query returned empty data - endpoint would return []")
            return []

        print(f"   📋 Raw data sample:")
        for i, purchase in enumerate(purchases_response.data[:2]):
            print(f"      [{i}]: {purchase}")

        print("\n2. Processing data aggregation...")

        # Aggregate by product (exact logic from endpoint)
        product_stats: Dict[str, Dict[str, Any]] = {}

        for purchase in purchases_response.data:
            print(f"\n   Processing purchase: {purchase.get('productId', 'N/A')}")

            product_id = purchase.get("productId")
            if not product_id:
                print(f"     ⚠️  Skipping - no productId")
                continue

            print(f"     ✅ Product ID: {product_id}")

            if product_id not in product_stats:
                product_data = purchase.get("product", {})
                print(f"     📦 Product data: {product_data}")

                if isinstance(product_data, list):
                    product_data = product_data[0] if product_data else {}
                    print(f"     🔄 Converted list to dict: {product_data}")

                product_stats[product_id] = {
                    "productId": product_id,
                    "productName": product_data.get("name", "Unknown Product"),
                    "photos": product_data.get("photos", []),
                    "totalSold": 0,
                    "totalRevenue": Decimal("0.00"),
                }
                print(f"     ➕ Created new product entry")

            # Update totals
            quantity = purchase.get("quantity", 0)
            total_amount = purchase.get("totalAmount", 0)

            print(f"     📊 Adding: quantity={quantity}, amount={total_amount}")

            product_stats[product_id]["totalSold"] += quantity
            product_stats[product_id]["totalRevenue"] += Decimal(str(total_amount))

            print(
                f"     📈 New totals: sold={product_stats[product_id]['totalSold']}, revenue={product_stats[product_id]['totalRevenue']}"
            )

        print(f"\n3. Sorting and limiting results...")
        print(f"   📊 Product stats collected:")
        for product_id, stats in product_stats.items():
            print(
                f"      {product_id}: {stats['productName']} - {stats['totalSold']} sold, ${stats['totalRevenue']}"
            )

        # Sort by total sold and get top N
        top_products = sorted(
            product_stats.values(), key=lambda x: x["totalSold"], reverse=True
        )[:limit]

        print(f"   📋 Top {limit} products after sorting:")
        for i, product in enumerate(top_products, 1):
            print(f"      {i}. {product['productName']}: {product['totalSold']} sold")

        print(f"\n4. Creating response objects...")

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
                print(
                    f"   ✅ Created: {top_product.productName} ({top_product.productId})"
                )

            except Exception as e:
                print(f"   ❌ Error creating TopSellingProduct: {e}")
                print(f"      Data: {product}")
                raise

        print(f"\n5. Final result:")
        print(f"   📦 Total products returned: {len(result)}")
        for i, product in enumerate(result, 1):
            print(
                f"      {i}. {product.productName}: {product.totalSold} sold, ${product.totalRevenue} revenue"
            )

        # Test JSON serialization
        print(f"\n6. Testing JSON serialization...")
        try:
            # Convert to dict like FastAPI would
            json_data = []
            for product in result:
                product_dict = {
                    "productId": product.productId,
                    "productName": product.productName,
                    "totalSold": product.totalSold,
                    "totalRevenue": float(
                        product.totalRevenue
                    ),  # This is what Config does
                    "photos": product.photos,
                }
                json_data.append(product_dict)

            print(f"   ✅ JSON serialization successful")
            print(f"   📄 JSON sample: {json_data[0] if json_data else 'No data'}")

        except Exception as e:
            print(f"   ❌ JSON serialization failed: {e}")
            raise

        return result

    except Exception as e:
        print(f"\n❌ SIMULATION FAILED: {str(e)}")
        import traceback

        print("📋 Full traceback:")
        traceback.print_exc()

        # This is what the endpoint would do
        print(
            f"\n🔥 This would cause a 500 error with message: 'Failed to fetch top selling products'"
        )
        return None


def compare_with_orderitem_approach():
    """Show what the results would be using OrderItem table instead"""
    print(f"\n" + "=" * 60)
    print("📊 COMPARISON: OrderItem-based approach (like dashboard)")
    print("=" * 60)

    seller_id = "91f01f31-23ea-4658-ac45-0b679c49ae19"

    try:
        # Query OrderItem table instead
        order_items_response = (
            supabase.table("OrderItem")
            .select("id, productId, quantity, price, sellerId, title")
            .eq("sellerId", seller_id)
            .execute()
        )

        order_items = order_items_response.data if order_items_response.data else []
        print(f"📦 OrderItem records found: {len(order_items)}")

        # Aggregate by product
        product_stats = {}
        for item in order_items:
            product_id = item.get("productId")
            if not product_id:
                continue

            if product_id not in product_stats:
                product_stats[product_id] = {
                    "productId": product_id,
                    "productName": item.get("title", "Unknown Product"),
                    "totalSold": 0,
                    "totalRevenue": Decimal("0.00"),
                }

            product_stats[product_id]["totalSold"] += item.get("quantity", 0)
            item_revenue = Decimal(str(item.get("price", 0))) * item.get("quantity", 0)
            product_stats[product_id]["totalRevenue"] += item_revenue

        # Sort and show results
        top_products = sorted(
            product_stats.values(), key=lambda x: x["totalSold"], reverse=True
        )[:5]

        print(f"🏆 Top products using OrderItem data:")
        for i, product in enumerate(top_products, 1):
            print(
                f"   {i}. {product['productName']}: {product['totalSold']} sold, ${product['totalRevenue']} revenue"
            )

        return len(top_products) > 0

    except Exception as e:
        print(f"❌ OrderItem approach failed: {e}")
        return False


def main():
    """Main debug function"""
    print("🚀 TOP PRODUCTS ENDPOINT DEBUG")
    print(
        "🕐 Started at:",
        __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )

    # Simulate the actual endpoint
    result = simulate_top_products_endpoint()

    # Compare with alternative approach
    orderitem_works = compare_with_orderitem_approach()

    # Summary
    print(f"\n" + "=" * 60)
    print("📋 DEBUG SUMMARY")
    print("=" * 60)

    if result is not None:
        print("✅ ProductPurchase-based endpoint simulation: SUCCESS")
        print(f"   Returns {len(result)} products")
        print("💡 The endpoint logic is working correctly")
        print("❓ If you're still getting 500 errors, check:")
        print("   1. Server restart needed")
        print("   2. Authentication issues")
        print("   3. Database connection problems")

    else:
        print("❌ ProductPurchase-based endpoint simulation: FAILED")
        print("💡 This explains the 500 error you're seeing")

    if orderitem_works:
        print("✅ OrderItem-based approach: Would work better")
        print("💡 Consider updating endpoint to use OrderItem for consistency")
    else:
        print("❌ OrderItem-based approach: Also has issues")

    print(f"\n🔧 RECOMMENDATIONS:")
    if result is not None:
        print("   1. Restart the FastAPI server")
        print("   2. Test with proper authentication")
        print("   3. Endpoint should work as-is")
    else:
        print("   1. Fix the specific error found above")
        print("   2. Consider switching to OrderItem-based logic")
        print("   3. Ensure data consistency between tables")


if __name__ == "__main__":
    main()
