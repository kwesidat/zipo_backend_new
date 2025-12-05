"""
Delivery Fee Calculation Utilities

This module handles delivery fee calculations based on:
- Product free_delivery status
- Distance between vendor and customer (using lat/long)
- Rate: GHS 20 per kilometer
"""

import math
from decimal import Decimal
from typing import Optional, Tuple
import logging

logger = logging.getLogger(__name__)

# Delivery fee configuration
DELIVERY_RATE_PER_KM = Decimal("20.00")  # GHS 20 per kilometer


def calculate_distance_haversine(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """
    Calculate distance between two points on Earth using Haversine formula.

    Args:
        lat1: Latitude of point 1 (vendor)
        lon1: Longitude of point 1 (vendor)
        lat2: Latitude of point 2 (customer)
        lon2: Longitude of point 2 (customer)

    Returns:
        Distance in kilometers
    """
    # Earth's radius in kilometers
    R = 6371.0

    # Convert degrees to radians
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)

    # Differences
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad

    # Haversine formula
    a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    distance = R * c

    return round(distance, 2)


def calculate_delivery_fee_for_product(
    product_free_delivery: bool,
    vendor_lat: Optional[float],
    vendor_lon: Optional[float],
    customer_lat: Optional[float],
    customer_lon: Optional[float],
) -> Tuple[Decimal, Optional[float]]:
    """
    Calculate delivery fee for a single product.

    Rules:
    - If product has free_delivery = True, delivery fee is GHS 0
    - If product has free_delivery = False, calculate based on distance
    - Rate: GHS 20 per kilometer

    Args:
        product_free_delivery: Whether product offers free delivery
        vendor_lat: Vendor's latitude
        vendor_lon: Vendor's longitude
        customer_lat: Customer's latitude
        customer_lon: Customer's longitude

    Returns:
        Tuple of (delivery_fee, distance_km)
    """
    # If product offers free delivery, no fee
    if product_free_delivery:
        logger.info("Product offers free delivery - no delivery fee")
        return Decimal("0.00"), 0.0

    # Validate coordinates
    if not all([vendor_lat, vendor_lon, customer_lat, customer_lon]):
        logger.warning(
            "Missing coordinates for delivery calculation. "
            f"Vendor: ({vendor_lat}, {vendor_lon}), Customer: ({customer_lat}, {customer_lon})"
        )
        # Return default fee if coordinates missing
        return Decimal("40.00"), None  # Default ~2km distance

    try:
        # Calculate distance
        distance_km = calculate_distance_haversine(
            vendor_lat, vendor_lon, customer_lat, customer_lon
        )

        # Calculate fee: GHS 20 per km
        delivery_fee = Decimal(str(distance_km)) * DELIVERY_RATE_PER_KM

        # Round to 2 decimal places
        delivery_fee = delivery_fee.quantize(Decimal("0.01"))

        logger.info(
            f"Calculated delivery fee: GHS {delivery_fee} for {distance_km} km"
        )

        return delivery_fee, distance_km

    except Exception as e:
        logger.error(f"Error calculating delivery fee: {str(e)}")
        # Return default fee on error
        return Decimal("40.00"), None


def calculate_order_delivery_fees(
    cart_items: list,
    customer_lat: Optional[float],
    customer_lon: Optional[float],
) -> dict:
    """
    Calculate delivery fees for all items in cart/order.
    Groups items by seller and calculates per-seller delivery fees.

    Args:
        cart_items: List of cart items with product and seller details
        customer_lat: Customer's delivery latitude
        customer_lon: Customer's delivery longitude

    Returns:
        Dictionary with total delivery fee and breakdown per seller
    """
    sellers_delivery = {}  # {seller_id: {fee, distance, items}}
    total_delivery_fee = Decimal("0.00")

    for item in cart_items:
        seller_id = item.get("sellerId")
        product_free_delivery = item.get("freeDelivery", True)
        vendor_lat = item.get("vendor_latitude")
        vendor_lon = item.get("vendor_longitude")

        # Skip if seller already calculated
        if seller_id in sellers_delivery:
            sellers_delivery[seller_id]["items"].append(item)
            continue

        # Calculate delivery fee for this seller
        delivery_fee, distance = calculate_delivery_fee_for_product(
            product_free_delivery=product_free_delivery,
            vendor_lat=vendor_lat,
            vendor_lon=vendor_lon,
            customer_lat=customer_lat,
            customer_lon=customer_lon,
        )

        sellers_delivery[seller_id] = {
            "delivery_fee": float(delivery_fee),
            "distance_km": distance,
            "free_delivery": product_free_delivery,
            "items": [item],
            "seller_name": item.get("sellerName", "Unknown Seller"),
        }

        total_delivery_fee += delivery_fee

    return {
        "total_delivery_fee": float(total_delivery_fee),
        "sellers_breakdown": sellers_delivery,
        "currency": "GHS",
    }


def get_vendor_location_from_db(supabase_client, seller_id: str) -> Tuple[Optional[float], Optional[float]]:
    """
    Fetch vendor's latitude and longitude from database.

    Args:
        supabase_client: Supabase client instance
        seller_id: Vendor/seller user ID

    Returns:
        Tuple of (latitude, longitude) or (None, None) if not found
    """
    try:
        response = (
            supabase_client.table("users")
            .select("latitude, longitude")
            .eq("user_id", seller_id)
            .execute()
        )

        if response.data and len(response.data) > 0:
            vendor = response.data[0]
            lat = vendor.get("latitude")
            lon = vendor.get("longitude")

            if lat is not None and lon is not None:
                return float(lat), float(lon)

        logger.warning(f"No location found for vendor {seller_id}")
        return None, None

    except Exception as e:
        logger.error(f"Error fetching vendor location: {str(e)}")
        return None, None


def validate_coordinates(lat: Optional[float], lon: Optional[float]) -> bool:
    """
    Validate latitude and longitude values.

    Args:
        lat: Latitude value
        lon: Longitude value

    Returns:
        True if valid, False otherwise
    """
    if lat is None or lon is None:
        return False

    # Check ranges: latitude [-90, 90], longitude [-180, 180]
    if not (-90 <= lat <= 90):
        return False
    if not (-180 <= lon <= 180):
        return False

    return True
