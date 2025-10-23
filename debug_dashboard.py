#!/usr/bin/env python3
"""
Debug script to identify the exact datetime comparison error in seller dashboard
"""

import sys
import os
from datetime import datetime, timezone, timedelta
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import supabase


def parse_datetime_to_utc(datetime_str: str) -> datetime:
    """Helper function to parse datetime strings to UTC timezone-aware datetime"""
    if not datetime_str:
        return None

    # Add timezone if missing
    if "+" not in datetime_str and "Z" not in datetime_str:
        datetime_str += "+00:00"
    else:
        datetime_str = datetime_str.replace("Z", "+00:00")

    dt = datetime.fromisoformat(datetime_str)

    # Ensure timezone-aware
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return dt


def debug_datetime_issue():
    """Debug the datetime comparison issue"""
    print("🔍 DEBUGGING DATETIME COMPARISON ISSUE")
    print("=" * 50)

    try:
        # Get a seller with actual orders
        seller_id = "f5fe9d34-a804-4365-b5e0-eab5a9aee819"  # Flaco - has 1 order
        print(f"Using seller ID: {seller_id}")

        # Get order items like the dashboard does
        print("\n1. Fetching order items...")
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
        print(f"Found {len(order_items)} order items")

        if not order_items:
            print("❌ No order items found for this seller")
            return

        # Show raw datetime data
        print("\n2. Examining datetime data...")
        for i, item in enumerate(order_items):
            print(f"Item {i + 1}:")
            print(
                f"  createdAt: {item.get('createdAt')} (type: {type(item.get('createdAt'))})"
            )
            if item.get("order"):
                print(
                    f"  order.createdAt: {item['order'].get('createdAt')} (type: {type(item['order'].get('createdAt'))})"
                )

        # Test datetime conversion
        print("\n3. Testing datetime conversion...")
        now = datetime.now(timezone.utc)
        print(f"Current time (UTC): {now}")

        for i, item in enumerate(order_items):
            created_at_str = item.get("createdAt")
            if created_at_str:
                try:
                    # Try the new helper function
                    created_at_dt = parse_datetime_to_utc(created_at_str)
                    print(
                        f"Item {i + 1} datetime: {created_at_dt} (timezone: {created_at_dt.tzinfo})"
                    )

                    # Test comparison with now
                    print(f"  Can compare with now: {created_at_dt < now}")

                except Exception as e:
                    print(f"❌ Error converting datetime for item {i + 1}: {e}")

        # Test period calculations that might be causing issues
        print("\n4. Testing period calculations...")

        try:
            # Today's metrics calculation
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            print(f"Today start: {today_start} (timezone: {today_start.tzinfo})")

            today_items = []
            for item in order_items:
                if item.get("createdAt"):
                    try:
                        item_dt = parse_datetime_to_utc(item["createdAt"])
                        if item_dt >= today_start:
                            today_items.append(item)
                            print(
                                f"  Item matches today filter: {item_dt} >= {today_start}"
                            )
                    except Exception as e:
                        print(f"❌ Error in today comparison: {e}")

            print(f"Today items count: {len(today_items)}")

        except Exception as e:
            print(f"❌ Error in today calculation: {e}")

        try:
            # Week calculation
            week_start = now - timedelta(days=now.weekday())
            week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
            print(f"Week start: {week_start} (timezone: {week_start.tzinfo})")

            week_items = []
            for item in order_items:
                if item.get("createdAt"):
                    try:
                        item_dt = parse_datetime_to_utc(item["createdAt"])
                        if item_dt >= week_start:
                            week_items.append(item)
                            print(
                                f"  Item matches week filter: {item_dt} >= {week_start}"
                            )
                    except Exception as e:
                        print(f"❌ Error in week comparison: {e}")

            print(f"Week items count: {len(week_items)}")

        except Exception as e:
            print(f"❌ Error in week calculation: {e}")

        try:
            # Month calculation
            month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            print(f"Month start: {month_start} (timezone: {month_start.tzinfo})")

            month_items = []
            for item in order_items:
                if item.get("createdAt"):
                    try:
                        item_dt = parse_datetime_to_utc(item["createdAt"])
                        if item_dt >= month_start:
                            month_items.append(item)
                            print(
                                f"  Item matches month filter: {item_dt} >= {month_start}"
                            )
                    except Exception as e:
                        print(f"❌ Error in month comparison: {e}")

            print(f"Month items count: {len(month_items)}")

        except Exception as e:
            print(f"❌ Error in month calculation: {e}")

        # Test more complex calculations
        print("\n5. Testing complex period calculations...")

        try:
            # Previous month calculation (this might be the problematic one)
            prev_month_start = (month_start - timedelta(days=1)).replace(day=1)
            prev_month_end = month_start - timedelta(seconds=1)
            print(
                f"Prev month start: {prev_month_start} (timezone: {prev_month_start.tzinfo})"
            )
            print(
                f"Prev month end: {prev_month_end} (timezone: {prev_month_end.tzinfo})"
            )

            prev_month_items = []
            for item in order_items:
                if item.get("createdAt"):
                    try:
                        item_dt = parse_datetime_to_utc(item["createdAt"])
                        if prev_month_start <= item_dt <= prev_month_end:
                            prev_month_items.append(item)
                            print(
                                f"  Item matches prev month: {prev_month_start} <= {item_dt} <= {prev_month_end}"
                            )
                    except Exception as e:
                        print(f"❌ Error in prev month comparison: {e}")
                        return  # This might be where the error occurs

            print(f"Prev month items count: {len(prev_month_items)}")

        except Exception as e:
            print(f"❌ Error in prev month calculation: {e}")
            print("🎯 This might be the source of the datetime comparison error!")

        # Test revenue by month calculation
        print("\n6. Testing revenue by month calculation...")
        try:
            for i in range(2, -1, -1):  # Test last 3 months only
                period_start = (now - timedelta(days=30 * i)).replace(
                    day=1, hour=0, minute=0, second=0, microsecond=0
                )
                if i == 0:
                    period_end = now
                else:
                    next_month = period_start.replace(day=28) + timedelta(days=4)
                    period_end = next_month.replace(day=1) - timedelta(seconds=1)

                print(f"Period {i}: {period_start} to {period_end}")
                print(
                    f"  Start timezone: {period_start.tzinfo}, End timezone: {period_end.tzinfo}"
                )

                period_items = []
                for item in order_items:
                    if item.get("createdAt"):
                        try:
                            item_dt = parse_datetime_to_utc(item["createdAt"])
                            if period_start <= item_dt <= period_end:
                                period_items.append(item)
                        except Exception as e:
                            print(f"❌ Error in period comparison: {e}")
                            return

                print(f"  Items in period: {len(period_items)}")

        except Exception as e:
            print(f"❌ Error in revenue by month: {e}")
            print("🎯 This might be another source of the error!")

        print("\n✅ Datetime debugging complete")

    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    debug_datetime_issue()
