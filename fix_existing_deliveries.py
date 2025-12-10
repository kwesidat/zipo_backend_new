"""
Fix existing deliveries to include latitude/longitude and missing contact info
"""
import os
from dotenv import load_dotenv
from app.database import supabase
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()


def fix_existing_deliveries():
    """Update existing deliveries to include lat/long and fix missing contact info"""
    try:
        # Get all deliveries
        logger.info("Fetching all deliveries...")
        deliveries_response = supabase.table("Delivery").select("*").execute()
        deliveries = deliveries_response.data or []

        logger.info(f"Found {len(deliveries)} deliveries to check")

        updated_count = 0
        skipped_count = 0

        for delivery in deliveries:
            delivery_id = delivery["id"]
            order_id = delivery["order_id"]
            needs_update = False
            update_data = {}

            # Check if delivery_address needs lat/long
            delivery_address = delivery.get("delivery_address", {})
            if not delivery_address.get("latitude") or not delivery_address.get("longitude"):
                # Get order to fetch shippingAddress
                order_response = supabase.table("Order").select("shippingAddress, userId").eq("id", order_id).execute()

                if order_response.data:
                    order = order_response.data[0]
                    shipping_address = order.get("shippingAddress", {})

                    # Update delivery address with lat/long from shipping address
                    if shipping_address.get("latitude") and shipping_address.get("longitude"):
                        delivery_address.update({
                            "address": shipping_address.get("address", delivery_address.get("address", "")),
                            "city": shipping_address.get("city", delivery_address.get("city", "")),
                            "country": shipping_address.get("country", delivery_address.get("country", "")),
                            "latitude": shipping_address.get("latitude"),
                            "longitude": shipping_address.get("longitude"),
                            "additional_info": shipping_address.get("additionalInfo", delivery_address.get("additional_info", ""))
                        })
                        update_data["delivery_address"] = delivery_address
                        needs_update = True
                        logger.info(f"  - Updated delivery_address with lat/long for delivery {delivery_id}")

                    # Fix missing delivery_contact_phone
                    if not delivery.get("delivery_contact_phone") and shipping_address.get("phone"):
                        update_data["delivery_contact_phone"] = shipping_address.get("phone")
                        needs_update = True
                        logger.info(f"  - Added delivery_contact_phone for delivery {delivery_id}")

                    # Fix missing delivery_contact_name
                    if not delivery.get("delivery_contact_name") and shipping_address.get("name"):
                        update_data["delivery_contact_name"] = shipping_address.get("name")
                        needs_update = True
                        logger.info(f"  - Added delivery_contact_name for delivery {delivery_id}")

            # Check if pickup_address needs lat/long
            pickup_address = delivery.get("pickup_address", {})
            if not pickup_address.get("latitude") or not pickup_address.get("longitude"):
                # Get vendor/seller info from order items
                order_items_response = supabase.table("OrderItem").select("sellerId").eq("orderId", order_id).limit(1).execute()

                if order_items_response.data:
                    seller_id = order_items_response.data[0]["sellerId"]

                    # Get seller's address with lat/long
                    seller_response = supabase.table("users").select(
                        "address, city, country, latitude, longitude, name, phone_number"
                    ).eq("user_id", seller_id).execute()

                    if seller_response.data:
                        seller = seller_response.data[0]

                        # Update pickup address with vendor's lat/long
                        if seller.get("latitude") and seller.get("longitude"):
                            pickup_address.update({
                                "address": seller.get("address", pickup_address.get("address", "")),
                                "city": seller.get("city", pickup_address.get("city", "")),
                                "country": seller.get("country", pickup_address.get("country", "")),
                                "latitude": seller.get("latitude"),
                                "longitude": seller.get("longitude"),
                                "additional_info": pickup_address.get("additional_info", f"Vendor: {seller.get('name', 'Unknown')}")
                            })
                            update_data["pickup_address"] = pickup_address
                            needs_update = True
                            logger.info(f"  - Updated pickup_address with vendor lat/long for delivery {delivery_id}")

                        # Fix missing pickup_contact_phone
                        if not delivery.get("pickup_contact_phone") and seller.get("phone_number"):
                            update_data["pickup_contact_phone"] = seller.get("phone_number")
                            needs_update = True
                            logger.info(f"  - Added pickup_contact_phone for delivery {delivery_id}")

                        # Fix missing pickup_contact_name
                        if not delivery.get("pickup_contact_name") and seller.get("name"):
                            update_data["pickup_contact_name"] = seller.get("name")
                            needs_update = True
                            logger.info(f"  - Added pickup_contact_name for delivery {delivery_id}")

            # Update the delivery if changes were made
            if needs_update:
                logger.info(f"Updating delivery {delivery_id}...")
                supabase.table("Delivery").update(update_data).eq("id", delivery_id).execute()
                updated_count += 1
            else:
                skipped_count += 1

        logger.info(f"\n✅ Migration complete!")
        logger.info(f"   Updated: {updated_count} deliveries")
        logger.info(f"   Skipped: {skipped_count} deliveries (already have lat/long)")

    except Exception as e:
        logger.error(f"❌ Error during migration: {str(e)}")
        raise


if __name__ == "__main__":
    logger.info("Starting delivery migration...")
    fix_existing_deliveries()
