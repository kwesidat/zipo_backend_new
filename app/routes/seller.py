from fastapi import APIRouter, HTTPException, status, Depends, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.database import supabase
from app.utils.auth_utils import AuthUtils
from app.models.seller import (
    SellerAnalyticsResponse,
    SellerEventResponse,
    SellerEventsListResponse,
    InvoiceResponse,
    InvoiceWithPurchaseDetails,
    InvoicesListResponse,
    SellerDashboardResponse,
    EventUpdateRequest,
    EventStatus,
    EventPriority,
    EventType,
    InvoiceStatus,
    RevenueData,
    ProductPerformance,
    RecentOrder,
    InventoryAlert,
    TopSellingProduct,
    SellerCustomer,
    SellerCustomersListResponse,
    CustomerDetailResponse,
    CustomerOrder,
    SellerOrder,
    SellerOrderItem,
    SellerOrdersListResponse,
)
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import logging
import math

logger = logging.getLogger(__name__)

router = APIRouter()
security = HTTPBearer()


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get current authenticated user"""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required"
        )

    try:
        user_data = AuthUtils.verify_supabase_token(credentials.credentials)
        if not user_data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            )
        return user_data
    except Exception as e:
        logger.error(f"Authentication failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication failed"
        )


# ========== SELLER ANALYTICS ENDPOINTS ==========


@router.get("/seller/compare-products")
async def compare_products_endpoints(current_user=Depends(get_current_user)):
    """
    Compare results from different product queries to identify the issue
    """
    try:
        seller_id = current_user["user_id"]
        logger.info(f"=== COMPARING PRODUCT QUERIES for seller: {seller_id} ===")

        # Query 1: Dashboard style (minimal fields)
        dashboard_query = (
            supabase.table("products")
            .select("id, quantity")
            .eq("sellerId", seller_id)
            .execute()
        )

        # Query 2: My Products style (full fields)
        my_products_query = (
            supabase.table("products")
            .select("""
                id, name, price, currency, country, condition, photos, featured,
                quantity, allowPurchaseOnPlatform, created_at, sellerId,
                categoryId, subCategoryId
            """)
            .eq("sellerId", seller_id)
            .execute()
        )

        # Query 3: Simple all products
        all_products_query = (
            supabase.table("products").select("id, sellerId").limit(10).execute()
        )

        return {
            "seller_id": seller_id,
            "comparison": {
                "dashboard_query": {
                    "count": len(dashboard_query.data) if dashboard_query.data else 0,
                    "data": dashboard_query.data if dashboard_query.data else [],
                },
                "my_products_query": {
                    "count": len(my_products_query.data)
                    if my_products_query.data
                    else 0,
                    "sample": my_products_query.data[:2]
                    if my_products_query.data
                    else [],
                },
                "all_products_sample": {
                    "count": len(all_products_query.data)
                    if all_products_query.data
                    else 0,
                    "data": all_products_query.data if all_products_query.data else [],
                },
            },
            "analysis": {
                "queries_match": (
                    len(dashboard_query.data) if dashboard_query.data else 0
                )
                == (len(my_products_query.data) if my_products_query.data else 0),
                "products_exist_for_seller": (
                    len(dashboard_query.data) if dashboard_query.data else 0
                )
                > 0,
                "products_exist_in_db": (
                    len(all_products_query.data) if all_products_query.data else 0
                )
                > 0,
            },
            "message": "If queries_match is False, there's a query issue. If products_exist_for_seller is False but products_exist_in_db is True, sellerId mismatch.",
        }

    except Exception as e:
        logger.error(f"Comparison error: {str(e)}")
        import traceback

        return {
            "error": str(e),
            "traceback": traceback.format_exc(),
        }


@router.get("/seller/debug-products")
async def debug_seller_products(current_user=Depends(get_current_user)):
    """
    Debug endpoint to check product queries and diagnose issues.
    Call this endpoint to see:
    - Your current user_id
    - Products with your sellerId
    - Sample of all products (to verify sellerId format)
    """
    try:
        seller_id = current_user["user_id"]

        logger.info(f"=== DEBUG: Testing product queries for seller: {seller_id} ===")

        # Query 1: Get products for this seller
        query1 = (
            supabase.table("products")
            .select("id, name, sellerId, quantity")
            .eq("sellerId", seller_id)
            .execute()
        )
        logger.info(
            f"Query 1 result: {len(query1.data) if query1.data else 0} products found"
        )

        # Query 2: Count query
        query2 = (
            supabase.table("products")
            .select("id", count="exact")
            .eq("sellerId", seller_id)
            .execute()
        )

        # Query 3: Get all products (up to 10) to see what sellerIds exist
        query3 = (
            supabase.table("products").select("id, name, sellerId").limit(10).execute()
        )
        logger.info(
            f"Query 3: Found {len(query3.data) if query3.data else 0} total products in database"
        )

        # Query 4: Get user info
        user_info = (
            supabase.table("users")
            .select("user_id, name, email, role, user_type")
            .eq("user_id", seller_id)
            .execute()
        )

        return {
            "debug_info": {
                "your_user_id": seller_id,
                "your_user_info": user_info.data[0] if user_info.data else None,
            },
            "products_for_you": {
                "count": len(query1.data) if query1.data else 0,
                "count_from_exact_query": query2.count,
                "sample_products": query1.data[:3] if query1.data else [],
                "full_list": query1.data if query1.data else [],
            },
            "all_products_sample": {
                "count": len(query3.data) if query3.data else 0,
                "sample": query3.data if query3.data else [],
            },
            "diagnosis": {
                "products_found": len(query1.data) > 0 if query1.data else False,
                "possible_issues": [
                    (
                        "No products created yet"
                        if not query1.data or len(query1.data) == 0
                        else None
                    ),
                    (
                        "sellerId mismatch - check if products were created with different user_id"
                        if query3.data
                        and len(query3.data) > 0
                        and (not query1.data or len(query1.data) == 0)
                        else None
                    ),
                    "Database connection issue" if not query3.data else None,
                ],
            },
            "instructions": "1. Check 'your_user_id' - this is your current logged-in user ID. 2. Check 'products_for_you' to see products with your sellerId. 3. Check 'all_products_sample' to see if products exist with different sellerIds. 4. When creating products, ensure the sellerId matches your user_id.",
        }

    except Exception as e:
        logger.error(f"Debug error: {str(e)}")
        import traceback

        return {
            "error": str(e),
            "traceback": traceback.format_exc(),
        }


@router.get("/seller/analytics", response_model=SellerAnalyticsResponse)
async def get_seller_analytics(current_user=Depends(get_current_user)):
    """
    Get seller analytics overview.
    Returns total sales, orders, customers, average order value, and more.
    """
    try:
        seller_id = current_user["user_id"]

        # Get seller analytics
        analytics_response = (
            supabase.table("SellerAnalytics")
            .select("*")
            .eq("sellerId", seller_id)
            .execute()
        )

        if not analytics_response.data:
            # Return default analytics if not found
            return SellerAnalyticsResponse(
                id="",
                sellerId=seller_id,
                totalSales=Decimal("0.00"),
                totalOrders=0,
                totalCustomers=0,
                averageOrderValue=Decimal("0.00"),
                topSellingProductId=None,
                lastSaleDate=None,
                monthlyRevenue=None,
                customerRetentionRate=0.0,
                updatedAt=datetime.now(timezone.utc),
            )

        analytics = analytics_response.data[0]

        return SellerAnalyticsResponse(
            id=analytics["id"],
            sellerId=analytics["sellerId"],
            totalSales=Decimal(str(analytics.get("totalSales", 0))),
            totalOrders=analytics.get("totalOrders", 0),
            totalCustomers=analytics.get("totalCustomers", 0),
            averageOrderValue=Decimal(str(analytics.get("averageOrderValue", 0))),
            topSellingProductId=analytics.get("topSellingProductId"),
            lastSaleDate=analytics.get("lastSaleDate"),
            monthlyRevenue=analytics.get("monthlyRevenue"),
            customerRetentionRate=analytics.get("customerRetentionRate", 0.0),
            updatedAt=analytics["updatedAt"],
        )

    except Exception as e:
        logger.error(f"Error fetching seller analytics: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch seller analytics",
        )


@router.get("/seller/top-products", response_model=List[TopSellingProduct])
async def get_top_selling_products(
    current_user=Depends(get_current_user), limit: int = Query(5, ge=1, le=20)
):
    """
    Get top selling products for the seller.
    Returns products sorted by total quantity sold based on actual order data.
    """
    try:
        seller_id = current_user["user_id"]

        # Get order items for this seller (consistent with dashboard logic)
        order_items_response = (
            supabase.table("OrderItem")
            .select("id, productId, quantity, price, title")
            .eq("sellerId", seller_id)
            .execute()
        )

        order_items = order_items_response.data if order_items_response.data else []

        if not order_items:
            return []

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

        # Aggregate by product
        product_stats: Dict[str, Dict[str, Any]] = {}

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

        return [
            TopSellingProduct(
                productId=product["productId"],
                productName=product["productName"],
                totalSold=product["totalSold"],
                totalRevenue=product["totalRevenue"],
                photos=product["photos"],
            )
            for product in top_products
        ]

    except Exception as e:
        logger.error(f"Error fetching top products: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch top selling products",
        )


# ========== SELLER EVENTS ENDPOINTS ==========


@router.get("/seller/events", response_model=SellerEventsListResponse)
async def get_seller_events(
    current_user=Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[EventStatus] = None,
    priority: Optional[EventPriority] = None,
    event_type: Optional[EventType] = None,
):
    """
    Get seller events with filtering and pagination.
    Events include notifications about orders, low stock, payments, etc.
    """
    try:
        seller_id = current_user["user_id"]

        # Build query
        query = supabase.table("SellerEvent").select("*").eq("sellerId", seller_id)

        # Apply filters
        if status:
            query = query.eq("status", status.value)

        if priority:
            query = query.eq("priority", priority.value)

        if event_type:
            query = query.eq("type", event_type.value)

        # Get total count
        count_query = (
            supabase.table("SellerEvent")
            .select("id", count="exact")
            .eq("sellerId", seller_id)
        )

        if status:
            count_query = count_query.eq("status", status.value)
        if priority:
            count_query = count_query.eq("priority", priority.value)
        if event_type:
            count_query = count_query.eq("type", event_type.value)

        count_response = count_query.execute()
        total_count = count_response.count or 0

        # Apply sorting and pagination
        offset = (page - 1) * page_size
        query = query.order("createdAt", desc=True).range(
            offset, offset + page_size - 1
        )

        response = query.execute()

        events = []
        for event in response.data:
            events.append(
                SellerEventResponse(
                    id=event["id"],
                    sellerId=event["sellerId"],
                    type=EventType(event["type"]),
                    title=event["title"],
                    description=event.get("description"),
                    metadata=event.get("metadata"),
                    priority=EventPriority(event["priority"]),
                    status=EventStatus(event["status"]),
                    dueDate=event.get("dueDate"),
                    createdAt=event["createdAt"],
                    updatedAt=event["updatedAt"],
                )
            )

        total_pages = math.ceil(total_count / page_size) if total_count > 0 else 0

        return SellerEventsListResponse(
            events=events,
            total_count=total_count,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_previous=page > 1,
        )

    except Exception as e:
        logger.error(f"Error fetching seller events: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch seller events",
        )


@router.get("/seller/events/{event_id}", response_model=SellerEventResponse)
async def get_seller_event(event_id: str, current_user=Depends(get_current_user)):
    """Get a specific seller event by ID"""
    try:
        seller_id = current_user["user_id"]

        event_response = (
            supabase.table("SellerEvent")
            .select("*")
            .eq("id", event_id)
            .eq("sellerId", seller_id)
            .execute()
        )

        if not event_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Event not found"
            )

        event = event_response.data[0]

        return SellerEventResponse(
            id=event["id"],
            sellerId=event["sellerId"],
            type=EventType(event["type"]),
            title=event["title"],
            description=event.get("description"),
            metadata=event.get("metadata"),
            priority=EventPriority(event["priority"]),
            status=EventStatus(event["status"]),
            dueDate=event.get("dueDate"),
            createdAt=event["createdAt"],
            updatedAt=event["updatedAt"],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching event {event_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch event",
        )


@router.put("/seller/events/{event_id}", response_model=SellerEventResponse)
async def update_seller_event(
    event_id: str,
    update_data: EventUpdateRequest,
    current_user=Depends(get_current_user),
):
    """Update a seller event (e.g., mark as completed, change priority)"""
    try:
        seller_id = current_user["user_id"]

        # Verify event exists and belongs to seller
        event_response = (
            supabase.table("SellerEvent")
            .select("*")
            .eq("id", event_id)
            .eq("sellerId", seller_id)
            .execute()
        )

        if not event_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Event not found"
            )

        # Build update dict
        update_dict = {"updatedAt": datetime.now(timezone.utc).isoformat()}

        if update_data.status:
            update_dict["status"] = update_data.status.value

        if update_data.priority:
            update_dict["priority"] = update_data.priority.value

        if update_data.description is not None:
            update_dict["description"] = update_data.description

        if update_data.dueDate is not None:
            update_dict["dueDate"] = update_data.dueDate.isoformat()

        # Update event
        updated_response = (
            supabase.table("SellerEvent")
            .update(update_dict)
            .eq("id", event_id)
            .execute()
        )

        if not updated_response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update event",
            )

        event = updated_response.data[0]

        return SellerEventResponse(
            id=event["id"],
            sellerId=event["sellerId"],
            type=EventType(event["type"]),
            title=event["title"],
            description=event.get("description"),
            metadata=event.get("metadata"),
            priority=EventPriority(event["priority"]),
            status=EventStatus(event["status"]),
            dueDate=event.get("dueDate"),
            createdAt=event["createdAt"],
            updatedAt=event["updatedAt"],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating event {event_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update event",
        )


@router.delete("/seller/events/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_seller_event(event_id: str, current_user=Depends(get_current_user)):
    """Delete a seller event"""
    try:
        seller_id = current_user["user_id"]

        # Verify event exists and belongs to seller
        event_response = (
            supabase.table("SellerEvent")
            .select("id")
            .eq("id", event_id)
            .eq("sellerId", seller_id)
            .execute()
        )

        if not event_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Event not found"
            )

        # Delete event
        supabase.table("SellerEvent").delete().eq("id", event_id).execute()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting event {event_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete event",
        )


# ========== SELLER INVOICES ENDPOINTS ==========


@router.get("/seller/invoices", response_model=InvoicesListResponse)
async def get_seller_invoices(
    current_user=Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[InvoiceStatus] = None,
):
    """
    Get all invoices for the seller with pagination.
    Invoices are generated after successful product purchases.
    """
    try:
        seller_id = current_user["user_id"]

        # Build query
        query = (
            supabase.table("Invoice")
            .select(
                "*, purchase:purchaseId(quantity, unitPrice, shippingAddress, product:productId(name))"
            )
            .eq("sellerId", seller_id)
        )

        # Apply status filter
        if status:
            query = query.eq("status", status.value)

        # Get total count
        count_query = (
            supabase.table("Invoice")
            .select("id", count="exact")
            .eq("sellerId", seller_id)
        )
        if status:
            count_query = count_query.eq("status", status.value)

        count_response = count_query.execute()
        total_count = count_response.count or 0

        # Apply pagination
        offset = (page - 1) * page_size
        query = query.order("createdAt", desc=True).range(
            offset, offset + page_size - 1
        )

        response = query.execute()

        invoices = []
        for invoice in response.data:
            purchase_data = invoice.get("purchase", {})
            if isinstance(purchase_data, list):
                purchase_data = purchase_data[0] if purchase_data else {}

            product_data = purchase_data.get("product", {})
            if isinstance(product_data, list):
                product_data = product_data[0] if product_data else {}

            invoices.append(
                InvoiceWithPurchaseDetails(
                    id=invoice["id"],
                    invoiceNumber=invoice["invoiceNumber"],
                    purchaseId=invoice["purchaseId"],
                    sellerId=invoice["sellerId"],
                    customerEmail=invoice["customerEmail"],
                    customerName=invoice.get("customerName"),
                    subtotal=Decimal(str(invoice["subtotal"])),
                    tax=Decimal(str(invoice.get("tax", 0))),
                    discount=Decimal(str(invoice.get("discount", 0))),
                    total=Decimal(str(invoice["total"])),
                    currency=invoice["currency"],
                    status=InvoiceStatus(invoice["status"]),
                    sentAt=invoice.get("sentAt"),
                    paidAt=invoice.get("paidAt"),
                    createdAt=invoice["createdAt"],
                    updatedAt=invoice["updatedAt"],
                    productName=product_data.get("name"),
                    quantity=purchase_data.get("quantity"),
                    unitPrice=Decimal(str(purchase_data.get("unitPrice", 0)))
                    if purchase_data.get("unitPrice")
                    else None,
                    shippingAddress=purchase_data.get("shippingAddress"),
                )
            )

        total_pages = math.ceil(total_count / page_size) if total_count > 0 else 0

        return InvoicesListResponse(
            invoices=invoices,
            total_count=total_count,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_previous=page > 1,
        )

    except Exception as e:
        logger.error(f"Error fetching seller invoices: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch seller invoices",
        )


@router.get("/seller/invoices/{invoice_id}", response_model=InvoiceWithPurchaseDetails)
async def get_seller_invoice(invoice_id: str, current_user=Depends(get_current_user)):
    """Get a specific invoice by ID"""
    try:
        seller_id = current_user["user_id"]

        invoice_response = (
            supabase.table("Invoice")
            .select(
                "*, purchase:purchaseId(quantity, unitPrice, shippingAddress, product:productId(name))"
            )
            .eq("id", invoice_id)
            .eq("sellerId", seller_id)
            .execute()
        )

        if not invoice_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found"
            )

        invoice = invoice_response.data[0]
        purchase_data = invoice.get("purchase", {})
        if isinstance(purchase_data, list):
            purchase_data = purchase_data[0] if purchase_data else {}

        product_data = purchase_data.get("product", {})
        if isinstance(product_data, list):
            product_data = product_data[0] if product_data else {}

        return InvoiceWithPurchaseDetails(
            id=invoice["id"],
            invoiceNumber=invoice["invoiceNumber"],
            purchaseId=invoice["purchaseId"],
            sellerId=invoice["sellerId"],
            customerEmail=invoice["customerEmail"],
            customerName=invoice.get("customerName"),
            subtotal=Decimal(str(invoice["subtotal"])),
            tax=Decimal(str(invoice.get("tax", 0))),
            discount=Decimal(str(invoice.get("discount", 0))),
            total=Decimal(str(invoice["total"])),
            currency=invoice["currency"],
            status=InvoiceStatus(invoice["status"]),
            sentAt=invoice.get("sentAt"),
            paidAt=invoice.get("paidAt"),
            createdAt=invoice["createdAt"],
            updatedAt=invoice["updatedAt"],
            productName=product_data.get("name"),
            quantity=purchase_data.get("quantity"),
            unitPrice=Decimal(str(purchase_data.get("unitPrice", 0)))
            if purchase_data.get("unitPrice")
            else None,
            shippingAddress=purchase_data.get("shippingAddress"),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching invoice {invoice_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch invoice",
        )


# ========== SELLER DASHBOARD ENDPOINT ==========


def parse_datetime_to_utc(datetime_str: str) -> datetime:
    """Helper function to parse datetime strings to UTC timezone-aware datetime"""
    if not datetime_str:
        raise ValueError("datetime_str cannot be empty")

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


@router.get("/seller/dashboard", response_model=SellerDashboardResponse)
async def get_seller_dashboard(current_user=Depends(get_current_user)):
    """
    Get comprehensive seller dashboard with all key metrics based on actual orders.
    Shows orders received for seller's products, revenue, customers, and recent activity.
    """
    try:
        seller_id = current_user["user_id"]
        now = datetime.now(timezone.utc)
        logger.info(f"=== DASHBOARD: Fetching data for seller: {seller_id} ===")

        # ========== 1. Get All Orders for Seller's Products ==========
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
        logger.info(f"Found {len(order_items)} order items for seller {seller_id}")

        # Get unique orders (not order items) to count actual orders
        unique_orders = set()
        for item in order_items:
            if item.get("order") and item["order"].get("id"):
                unique_orders.add(item["order"]["id"])

        total_orders = len(unique_orders)
        total_revenue = sum(
            Decimal(str(item.get("price", 0))) * item.get("quantity", 0)
            for item in order_items
        )

        # Get unique customers (users who bought from this seller)
        unique_customers = set()
        for item in order_items:
            if item.get("order") and item["order"].get("userId"):
                unique_customers.add(item["order"]["userId"])
        total_customers = len(unique_customers)

        # Calculate average order value per unique order
        average_order_value = (
            total_revenue / total_orders if total_orders > 0 else Decimal("0.00")
        )

        logger.info(
            f"Metrics - Orders: {total_orders}, Revenue: {total_revenue}, Customers: {total_customers}"
        )

        # ========== 2. Get Product Statistics ==========
        products_response = (
            supabase.table("products")
            .select("id, quantity, name, price")
            .eq("sellerId", seller_id)
            .execute()
        )

        products = products_response.data if products_response.data else []
        total_products = len(products)
        active_products = len([p for p in products if p.get("quantity", 0) > 0])
        low_stock_products = len([p for p in products if 0 < p.get("quantity", 0) <= 5])
        out_of_stock_products = len([p for p in products if p.get("quantity", 0) == 0])

        logger.info(f"Products: {total_products}, Active: {active_products}")

        # ========== 3. Calculate Period Metrics ==========
        # Today's metrics
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_items = [
            item
            for item in order_items
            if item.get("createdAt")
            and parse_datetime_to_utc(item["createdAt"]) >= today_start
        ]
        today_revenue = sum(
            Decimal(str(item.get("price", 0))) * item.get("quantity", 0)
            for item in today_items
        )
        today_orders = len(today_items)

        # This week's metrics
        week_start = now - timedelta(days=now.weekday())
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        week_items = [
            item
            for item in order_items
            if item.get("createdAt")
            and parse_datetime_to_utc(item["createdAt"]) >= week_start
        ]
        week_revenue = sum(
            Decimal(str(item.get("price", 0))) * item.get("quantity", 0)
            for item in week_items
        )
        week_orders = len(week_items)

        # This month's metrics
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        month_items = [
            item
            for item in order_items
            if item.get("createdAt")
            and parse_datetime_to_utc(item["createdAt"]) >= month_start
        ]
        month_revenue = sum(
            Decimal(str(item.get("price", 0))) * item.get("quantity", 0)
            for item in month_items
        )
        month_orders = len(month_items)

        # Previous month for comparison
        prev_month_start = (month_start - timedelta(days=1)).replace(day=1)
        prev_month_end = month_start - timedelta(seconds=1)
        prev_month_items = [
            item
            for item in order_items
            if item.get("createdAt")
            and prev_month_start
            <= parse_datetime_to_utc(item["createdAt"])
            <= prev_month_end
        ]
        prev_month_revenue = sum(
            Decimal(str(item.get("price", 0))) * item.get("quantity", 0)
            for item in prev_month_items
        )
        prev_month_orders = len(prev_month_items)

        # Calculate growth rates
        revenue_growth = (
            float((month_revenue - prev_month_revenue) / prev_month_revenue * 100)
            if prev_month_revenue > 0
            else 0.0
        )
        orders_growth = (
            float((month_orders - prev_month_orders) / prev_month_orders * 100)
            if prev_month_orders > 0
            else 0.0
        )

        # ========== 4. Revenue by Month (Last 12 months) ==========
        revenue_by_month = []
        for i in range(11, -1, -1):
            period_start = (now - timedelta(days=30 * i)).replace(
                day=1, hour=0, minute=0, second=0, microsecond=0
            )
            if i == 0:
                period_end = now
            else:
                next_month = period_start.replace(day=28) + timedelta(days=4)
                period_end = next_month.replace(day=1) - timedelta(seconds=1)

            period_items = [
                item
                for item in order_items
                if item.get("createdAt")
                and period_start
                <= parse_datetime_to_utc(item["createdAt"])
                <= period_end
            ]

            period_revenue = sum(
                Decimal(str(item.get("price", 0))) * item.get("quantity", 0)
                for item in period_items
            )
            period_orders = len(period_items)

            revenue_by_month.append(
                RevenueData(
                    period=period_start.strftime("%Y-%m"),
                    revenue=Decimal(str(period_revenue)),
                    orders=period_orders,
                )
            )

        # ========== 5. Revenue by Week (Last 8 weeks) ==========
        revenue_by_week = []
        for i in range(7, -1, -1):
            week_start_date = now - timedelta(weeks=i)
            week_start_date = week_start_date - timedelta(
                days=week_start_date.weekday()
            )
            week_start_date = week_start_date.replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            week_end_date = week_start_date + timedelta(
                days=6, hours=23, minutes=59, seconds=59
            )

            week_period_items = [
                item
                for item in order_items
                if item.get("createdAt")
                and week_start_date
                <= parse_datetime_to_utc(item["createdAt"])
                <= week_end_date
            ]
            week_revenue = sum(
                Decimal(str(item.get("price", 0))) * item.get("quantity", 0)
                for item in week_period_items
            )
            week_orders_count = len(week_period_items)

            revenue_by_week.append(
                RevenueData(
                    period=f"Week {week_start_date.strftime('%U')}",
                    revenue=Decimal(str(week_revenue)),
                    orders=week_orders_count,
                )
            )

        # ========== 6. Top Selling Products ==========
        # Group order items by product to calculate performance
        product_performance_dict: Dict[str, Dict[str, Any]] = {}
        for order_item in order_items:
            product_id = order_item.get("productId")
            if not product_id:
                continue

            if product_id not in product_performance_dict:
                # Find product details
                product_info = next(
                    (p for p in products if p.get("id") == product_id),
                    {"name": "Unknown Product", "quantity": 0},
                )

                product_performance_dict[product_id] = {
                    "productId": product_id,
                    "productName": product_info.get("name", "Unknown Product"),
                    "photos": product_info.get("photos", []),
                    "stockRemaining": product_info.get("quantity", 0),
                    "totalSold": 0,
                    "totalRevenue": Decimal("0.00"),
                    "prices": [],
                }

            quantity = order_item.get("quantity", 0)
            price = Decimal(str(order_item.get("price", 0)))

            product_performance_dict[product_id]["totalSold"] += quantity
            product_performance_dict[product_id]["totalRevenue"] += price * quantity
            product_performance_dict[product_id]["prices"].append(price)

        top_selling_products = []
        for product_data in sorted(
            product_performance_dict.values(),
            key=lambda x: x["totalSold"],
            reverse=True,
        )[:5]:
            avg_price = (
                sum(product_data["prices"]) / len(product_data["prices"])
                if product_data["prices"]
                else Decimal("0.00")
            )

            top_selling_products.append(
                ProductPerformance(
                    productId=product_data["productId"],
                    productName=product_data["productName"],
                    totalSold=product_data["totalSold"],
                    totalRevenue=product_data["totalRevenue"],
                    averagePrice=Decimal(str(avg_price)),
                    stockRemaining=product_data["stockRemaining"],
                    photos=product_data["photos"],
                )
            )

        # ========== 7. Recent Orders (from OrderItem table) ==========
        # Group order items by order ID for recent orders
        orders_dict: Dict[str, Dict[str, Any]] = {}
        for item in order_items:
            order_data = item.get("order", {})
            if not order_data or not order_data.get("id"):
                continue

            order_id = order_data["id"]

            if order_id not in orders_dict:
                shipping_address = order_data.get("shippingAddress", {})
                customer_name = (
                    shipping_address.get("fullName", "Customer")
                    if isinstance(shipping_address, dict)
                    else "Customer"
                )

                orders_dict[order_id] = {
                    "orderId": order_id,
                    "orderDate": order_data.get("createdAt"),
                    "customerName": customer_name,
                    "totalAmount": Decimal(str(order_data.get("total", 0))),
                    "itemCount": 0,
                    "status": order_data.get("status", "PENDING"),
                    "paymentStatus": order_data.get("paymentStatus", "PENDING"),
                    "sellerRevenue": Decimal("0.00"),
                }

            # Count items for this seller in this order
            orders_dict[order_id]["itemCount"] += 1
            # Add seller's revenue from this item
            item_revenue = Decimal(str(item.get("price", 0))) * item.get("quantity", 0)
            orders_dict[order_id]["sellerRevenue"] += item_revenue

        # Sort by date and take recent 5 orders
        recent_orders = []
        sorted_orders = sorted(
            orders_dict.values(),
            key=lambda x: x["orderDate"] if x["orderDate"] else "",
            reverse=True,
        )[:5]

        for order in sorted_orders:
            recent_orders.append(
                RecentOrder(
                    orderId=order["orderId"],
                    orderDate=order["orderDate"],
                    customerName=order["customerName"],
                    totalAmount=order[
                        "sellerRevenue"
                    ],  # Use seller's portion instead of total order
                    itemCount=order["itemCount"],
                    status=order["status"],
                    paymentStatus=order["paymentStatus"],
                )
            )

        # ========== 8. Pending Events ==========
        pending_events_response = (
            supabase.table("SellerEvent")
            .select("*")
            .eq("sellerId", seller_id)
            .in_("status", ["PENDING", "IN_PROGRESS"])
            .order("priority", desc=True)
            .order("createdAt", desc=True)
            .limit(5)
            .execute()
        )

        pending_events = [
            SellerEventResponse(
                id=event["id"],
                sellerId=event["sellerId"],
                type=EventType(event["type"]),
                title=event["title"],
                description=event.get("description"),
                metadata=event.get("metadata"),
                priority=EventPriority(event["priority"]),
                status=EventStatus(event["status"]),
                dueDate=event.get("dueDate"),
                createdAt=event["createdAt"],
                updatedAt=event["updatedAt"],
            )
            for event in pending_events_response.data
        ]

        # ========== 9. Inventory Alerts ==========
        inventory_alerts = []
        for product in products:
            quantity = product.get("quantity", 0)
            if quantity == 0:
                inventory_alerts.append(
                    InventoryAlert(
                        productId=product["id"],
                        productName=product["name"],
                        currentStock=0,
                        status="OUT_OF_STOCK",
                        photos=product.get("photos", []),
                    )
                )
            elif 0 < quantity <= 5:
                inventory_alerts.append(
                    InventoryAlert(
                        productId=product["id"],
                        productName=product["name"],
                        currentStock=quantity,
                        status="LOW_STOCK",
                        photos=product.get("photos", []),
                    )
                )

        # ========== 10. Invoice Statistics ==========
        invoices_response = (
            supabase.table("Invoice")
            .select("id, status")
            .eq("sellerId", seller_id)
            .execute()
        )

        total_invoices = len(invoices_response.data)
        paid_invoices = len(
            [inv for inv in invoices_response.data if inv.get("status") == "PAID"]
        )
        pending_invoices = len(
            [
                inv
                for inv in invoices_response.data
                if inv.get("status") in ["SENT", "DRAFT"]
            ]
        )

        # ========== Return Dashboard Response ==========
        return SellerDashboardResponse(
            # Summary Statistics
            totalSales=Decimal(str(total_revenue)),
            totalOrders=total_orders,
            totalCustomers=total_customers,
            averageOrderValue=Decimal(str(average_order_value)),
            totalProducts=total_products,
            activeProducts=active_products,
            lowStockProducts=low_stock_products,
            outOfStockProducts=out_of_stock_products,
            # Revenue & Growth
            todayRevenue=Decimal(str(today_revenue)),
            weekRevenue=Decimal(str(week_revenue)),
            monthRevenue=Decimal(str(month_revenue)),
            revenueGrowth=revenue_growth,
            ordersGrowth=orders_growth,
            # Charts
            revenueByMonth=revenue_by_month,
            revenueByWeek=revenue_by_week,
            # Top Products
            topSellingProducts=top_selling_products,
            # Recent Activity
            recentOrders=recent_orders,
            pendingEvents=pending_events,
            # Inventory
            inventoryAlerts=inventory_alerts,
            # Analytics
            lastSaleDate=None,  # Will be calculated from order items
            customerRetentionRate=0.0,  # Will be calculated based on repeat customers
            totalInvoices=total_invoices,
            paidInvoices=paid_invoices,
            pendingInvoices=pending_invoices,
        )

    except Exception as e:
        logger.error(f"Error fetching seller dashboard: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch seller dashboard",
        )


# ========== SELLER CUSTOMERS ENDPOINTS ==========


@router.get("/seller/customers", response_model=SellerCustomersListResponse)
async def get_seller_customers(
    current_user=Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = Query("recent", description="Sort by: recent, spending, orders"),
):
    """
    Get all customers who have purchased from this seller.
    Customers are identified by their orders containing the seller's products.
    """
    try:
        seller_id = current_user["user_id"]

        # Get all order items for this seller
        order_items_response = (
            supabase.table("OrderItem")
            .select(
                "*, order:orderId(id, userId, createdAt, total, status, paymentStatus, shippingAddress)"
            )
            .eq("sellerId", seller_id)
            .execute()
        )

        if not order_items_response.data:
            return SellerCustomersListResponse(
                customers=[],
                total_count=0,
                page=page,
                page_size=page_size,
                total_pages=0,
                has_next=False,
                has_previous=page > 1,
            )

        # Group by customer (userId or email from shipping address)
        customers_dict: Dict[str, Dict[str, Any]] = {}

        for item in order_items_response.data:
            order_data = item.get("order", {})
            if isinstance(order_data, list):
                order_data = order_data[0] if order_data else {}

            if not order_data:
                continue

            # Get customer identifier
            user_id = order_data.get("userId")
            shipping_address = order_data.get("shippingAddress", {})

            if not isinstance(shipping_address, dict):
                shipping_address = {}

            customer_email = shipping_address.get("email", "unknown@example.com")
            customer_name = shipping_address.get("fullName", "Unknown Customer")
            customer_phone = shipping_address.get("phone")

            # Use userId as primary key, fallback to email
            customer_key = user_id if user_id else customer_email

            if customer_key not in customers_dict:
                customers_dict[customer_key] = {
                    "userId": user_id,
                    "customerName": customer_name,
                    "customerEmail": customer_email,
                    "customerPhone": customer_phone,
                    "totalOrders": 0,
                    "totalSpent": Decimal("0.00"),
                    "orderIds": set(),
                    "orders": [],
                    "firstOrderDate": None,
                    "lastOrderDate": None,
                    "shippingAddress": shipping_address,
                }

            # Track unique orders
            order_id = order_data.get("id")
            if order_id and order_id not in customers_dict[customer_key]["orderIds"]:
                customers_dict[customer_key]["orderIds"].add(order_id)
                customers_dict[customer_key]["totalOrders"] += 1

                order_date = order_data.get("createdAt")
                if order_date:
                    order_date_dt = datetime.fromisoformat(
                        order_date.replace("Z", "+00:00")
                    )

                    if not customers_dict[customer_key]["firstOrderDate"]:
                        customers_dict[customer_key]["firstOrderDate"] = order_date_dt
                    else:
                        customers_dict[customer_key]["firstOrderDate"] = min(
                            customers_dict[customer_key]["firstOrderDate"],
                            order_date_dt,
                        )

                    if not customers_dict[customer_key]["lastOrderDate"]:
                        customers_dict[customer_key]["lastOrderDate"] = order_date_dt
                    else:
                        customers_dict[customer_key]["lastOrderDate"] = max(
                            customers_dict[customer_key]["lastOrderDate"], order_date_dt
                        )

                # Add order to customer's orders list
                customers_dict[customer_key]["orders"].append(
                    {
                        "orderId": order_id,
                        "orderDate": order_date_dt
                        if order_date
                        else datetime.now(timezone.utc),
                        "totalAmount": Decimal(str(order_data.get("total", 0))),
                        "status": order_data.get("status", "UNKNOWN"),
                        "paymentStatus": order_data.get("paymentStatus", "UNKNOWN"),
                        "itemCount": 1,  # Will be counted properly below
                    }
                )

            # Add to total spent (only for seller's items)
            item_total = Decimal(str(item.get("price", 0))) * item.get("quantity", 0)
            customers_dict[customer_key]["totalSpent"] += item_total

        # Convert to list and calculate averages
        customers_list = []
        for customer_data in customers_dict.values():
            if customer_data["totalOrders"] == 0:
                continue

            avg_order_value = (
                customer_data["totalSpent"] / customer_data["totalOrders"]
                if customer_data["totalOrders"] > 0
                else Decimal("0.00")
            )

            # Get recent orders (last 3)
            recent_orders = sorted(
                customer_data["orders"], key=lambda x: x["orderDate"], reverse=True
            )[:3]

            recent_orders_list = [
                CustomerOrder(
                    orderId=order["orderId"],
                    orderDate=order["orderDate"],
                    totalAmount=order["totalAmount"],
                    itemCount=order["itemCount"],
                    status=order["status"],
                    paymentStatus=order["paymentStatus"],
                )
                for order in recent_orders
            ]

            customers_list.append(
                {
                    "userId": customer_data["userId"],
                    "customerName": customer_data["customerName"],
                    "customerEmail": customer_data["customerEmail"],
                    "customerPhone": customer_data["customerPhone"],
                    "totalOrders": customer_data["totalOrders"],
                    "totalSpent": customer_data["totalSpent"],
                    "firstOrderDate": customer_data["firstOrderDate"],
                    "lastOrderDate": customer_data["lastOrderDate"],
                    "averageOrderValue": avg_order_value,
                    "shippingAddress": customer_data["shippingAddress"],
                    "recentOrders": recent_orders_list,
                }
            )

        # Sort customers
        if sort_by == "spending":
            customers_list.sort(key=lambda x: x["totalSpent"], reverse=True)
        elif sort_by == "orders":
            customers_list.sort(key=lambda x: x["totalOrders"], reverse=True)
        else:  # recent
            customers_list.sort(key=lambda x: x["lastOrderDate"], reverse=True)

        # Paginate
        total_count = len(customers_list)
        total_pages = math.ceil(total_count / page_size) if total_count > 0 else 0
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_customers = customers_list[start_idx:end_idx]

        # Convert to response models
        customer_responses = [
            SellerCustomer(
                userId=customer["userId"],
                customerName=customer["customerName"],
                customerEmail=customer["customerEmail"],
                customerPhone=customer["customerPhone"],
                totalOrders=customer["totalOrders"],
                totalSpent=customer["totalSpent"],
                firstOrderDate=customer["firstOrderDate"],
                lastOrderDate=customer["lastOrderDate"],
                averageOrderValue=customer["averageOrderValue"],
                shippingAddress=customer["shippingAddress"],
                recentOrders=customer["recentOrders"],
            )
            for customer in paginated_customers
        ]

        return SellerCustomersListResponse(
            customers=customer_responses,
            total_count=total_count,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_previous=page > 1,
        )

    except Exception as e:
        logger.error(f"Error fetching seller customers: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch seller customers",
        )


@router.get(
    "/seller/customers/{customer_identifier}", response_model=CustomerDetailResponse
)
async def get_seller_customer_detail(
    customer_identifier: str,
    current_user=Depends(get_current_user),
):
    """
    Get detailed information about a specific customer.
    Customer can be identified by userId or email.
    """
    try:
        seller_id = current_user["user_id"]

        # Get all order items for this seller and customer
        # First try by userId
        order_items_response = (
            supabase.table("OrderItem")
            .select(
                "*, order:orderId(id, userId, createdAt, total, status, paymentStatus, shippingAddress)"
            )
            .eq("sellerId", seller_id)
            .execute()
        )

        if not order_items_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Customer not found",
            )

        # Filter for this specific customer
        customer_orders = []
        customer_info = None
        products_ordered_set = set()

        for item in order_items_response.data:
            order_data = item.get("order", {})
            if isinstance(order_data, list):
                order_data = order_data[0] if order_data else {}

            if not order_data:
                continue

            user_id = order_data.get("userId")
            shipping_address = order_data.get("shippingAddress", {})

            if not isinstance(shipping_address, dict):
                shipping_address = {}

            customer_email = shipping_address.get("email", "")

            # Check if this order belongs to the customer we're looking for
            if customer_identifier != user_id and customer_identifier != customer_email:
                continue

            # This is the customer we're looking for
            if not customer_info:
                customer_info = {
                    "userId": user_id,
                    "customerName": shipping_address.get(
                        "fullName", "Unknown Customer"
                    ),
                    "customerEmail": customer_email,
                    "customerPhone": shipping_address.get("phone"),
                    "shippingAddress": shipping_address,
                }

            # Add to products ordered
            products_ordered_set.add(item.get("productId"))

            # Track orders
            order_id = order_data.get("id")
            order_date = order_data.get("createdAt")

            # Check if order already added
            existing_order = next(
                (o for o in customer_orders if o["orderId"] == order_id), None
            )
            if existing_order:
                existing_order["itemCount"] += 1
            else:
                customer_orders.append(
                    {
                        "orderId": order_id,
                        "orderDate": datetime.fromisoformat(
                            order_date.replace("Z", "+00:00")
                        )
                        if order_date
                        else datetime.now(timezone.utc),
                        "totalAmount": Decimal(str(order_data.get("total", 0))),
                        "status": order_data.get("status", "UNKNOWN"),
                        "paymentStatus": order_data.get("paymentStatus", "UNKNOWN"),
                        "itemCount": 1,
                    }
                )

        if not customer_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Customer not found",
            )

        # Calculate stats
        total_orders = len(customer_orders)
        total_spent = sum(order["totalAmount"] for order in customer_orders)
        avg_order_value = (
            total_spent / total_orders if total_orders > 0 else Decimal("0.00")
        )

        # Sort orders by date
        customer_orders.sort(key=lambda x: x["orderDate"], reverse=True)

        first_order_date = (
            customer_orders[-1]["orderDate"]
            if customer_orders
            else datetime.now(timezone.utc)
        )
        last_order_date = (
            customer_orders[0]["orderDate"]
            if customer_orders
            else datetime.now(timezone.utc)
        )

        # Convert orders to response models
        orders_list = [
            CustomerOrder(
                orderId=order["orderId"],
                orderDate=order["orderDate"],
                totalAmount=order["totalAmount"],
                itemCount=order["itemCount"],
                status=order["status"],
                paymentStatus=order["paymentStatus"],
            )
            for order in customer_orders
        ]

        return CustomerDetailResponse(
            userId=customer_info["userId"],
            customerName=customer_info["customerName"],
            customerEmail=customer_info["customerEmail"],
            customerPhone=customer_info["customerPhone"],
            totalOrders=total_orders,
            totalSpent=Decimal(str(total_spent)),
            firstOrderDate=first_order_date,
            lastOrderDate=last_order_date,
            averageOrderValue=Decimal(str(avg_order_value)),
            shippingAddress=customer_info["shippingAddress"],
            orders=orders_list,
            productsOrdered=len(products_ordered_set),
            favoriteProducts=None,  # Can be implemented later
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching customer detail: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch customer details",
        )


# ========== SELLER ORDERS ENDPOINT ==========


@router.get("/seller/orders", response_model=SellerOrdersListResponse)
async def get_seller_orders(
    current_user=Depends(get_current_user),
    status: Optional[str] = Query(None, description="Filter by order status"),
    payment_status: Optional[str] = Query(None, description="Filter by payment status"),
    limit: int = Query(20, ge=1, le=100, description="Number of orders per page"),
    offset: int = Query(0, ge=0, description="Number of orders to skip"),
):
    """
    Get orders that contain the seller's products.
    Returns orders with seller-specific information including only the seller's items and revenue.
    """
    try:
        seller_id = current_user["user_id"]
        logger.info(f"=== SELLER ORDERS: Fetching orders for seller: {seller_id} ===")

        # Get order items for this seller with full order details
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
        )

        # Apply filters if provided
        if status:
            query = query.eq("order.status", status)
        if payment_status:
            query = query.eq("order.paymentStatus", payment_status)

        # Order by most recent first
        query = query.order("createdAt", desc=True)

        response = query.execute()
        order_items = response.data if response.data else []

        logger.info(f"Found {len(order_items)} order items for seller")

        if not order_items:
            return SellerOrdersListResponse(
                orders=[], total=0, page=offset // limit + 1, limit=limit, totalPages=0
            )

        # Group order items by order
        orders_dict: Dict[str, Dict[str, Any]] = {}

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

        # Convert to list and sort by creation date
        orders_list = list(orders_dict.values())
        orders_list.sort(
            key=lambda x: x["order_data"].get("createdAt", ""), reverse=True
        )

        # Apply pagination
        total_orders = len(orders_list)
        paginated_orders = orders_list[offset : offset + limit]

        # Build response objects
        seller_orders = []
        for order in paginated_orders:
            order_data = order["order_data"]

            seller_order_items = [
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
                for item in order["items"]
            ]

            seller_orders.append(
                SellerOrder(
                    id=order_data["id"],
                    userId=order_data["userId"],
                    customerName=order["customer_name"],
                    customerEmail=order["customer_email"],
                    customerPhone=order["customer_phone"],
                    subtotal=Decimal(str(order_data.get("subtotal", 0))),
                    discountAmount=Decimal(str(order_data.get("discountAmount", 0))),
                    tax=Decimal(str(order_data.get("tax", 0))),
                    total=Decimal(str(order_data.get("total", 0))),
                    sellerRevenue=order["seller_revenue"],
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
                    itemCount=order["item_count"],
                )
            )

        total_pages = math.ceil(total_orders / limit) if total_orders > 0 else 0

        logger.info(f"Returning {len(seller_orders)} orders for seller")

        return SellerOrdersListResponse(
            orders=seller_orders,
            total=total_orders,
            page=offset // limit + 1,
            limit=limit,
            totalPages=total_pages,
        )

    except Exception as e:
        logger.error(f"Error fetching seller orders: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch seller orders",
        )
