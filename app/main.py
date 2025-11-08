from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from app.database import connect_db, disconnect_db
from app.routes.auth import router as auth_router
from app.routes.categories import router as categories_router
from app.routes.products import router as products_router
from app.routes.subscriptions import router as subscriptions_router
from app.routes.cart import router as cart_router
from app.routes.files import router as files_router
from app.routes.payments import router as payments_router
from app.routes.webhooks import router as webhooks_router
from app.routes.discounts import router as discounts_router
from app.routes.orders import router as orders_router
from app.routes.notifications import router as notifications_router
from app.routes.seller import router as seller_router
from app.routes.courier import router as courier_router
from app.middleware.mobile_auth import (
    MobileAuthMiddleware,
    RateLimitMiddleware,
    RequestLoggingMiddleware,
)

import logging
import time
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up ZipoHub API...")
    try:
        await connect_db()
    except Exception as e:
        logger.warning(f"Database startup warning: {e}")
    yield
    logger.info("Shutting down ZipoHub API...")
    try:
        await disconnect_db()
    except Exception as e:
        logger.warning(f"Database shutdown warning: {e}")


app = FastAPI(
    title="ZipoHub API",
    version="1.0.0",
    description="ZipoHub E-commerce API with Supabase Authentication",
    lifespan=lifespan,
)

# Add middleware in order (last added = first executed)
# Request Logging Middleware
app.add_middleware(RequestLoggingMiddleware)

# Rate Limiting Middleware
app.add_middleware(RateLimitMiddleware, requests_per_minute=100)

# Mobile Auth Middleware
app.add_middleware(
    MobileAuthMiddleware,
    excluded_paths=[
        "/docs",
        "/redoc",
        "/openapi.json",
        "/api/auth/signup",
        "/api/auth/login",
        "/api/auth/refresh",
        "/api/auth/mobile/signup",
        "/api/auth/mobile/login",
        "/api/auth/mobile/refresh",
        "/api/auth/password-reset/request",
        "/api/auth/password-reset/verify",
        "/api/auth/password-reset/verify-otp",
        "/api/auth/password-reset/complete",
        "/api/auth/confirm",
        "/api/auth/resend-verification",
        "/api/auth/status",
        "/api/auth/logout",
        "/api/auth/mobile/status",
        "/api/auth/mobile/logout",
        "/api/courier/signup",
        "/api/categories",
        "/api/subcategories",
        "/api/categories-tree",
        "/api/products",
        "/api/products/featured",
        "/api/products/stats",
        "/api/subscription-plans",
        "/api/webhooks/paystack",
        "/api/webhooks/paystack/health",
        "/health",
        "/",
        "/api/auth/",
    ],
)

# CORS Middleware - unrestricted
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,  # must be False when allow_origins=["*"]
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception handler for mobile-friendly error responses
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global exception: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": "An unexpected error occurred",
            "timestamp": time.time(),
        },
    )


# Include routers
app.include_router(auth_router, prefix="/api/auth", tags=["authentication"])
app.include_router(categories_router, prefix="/api", tags=["categories"])
app.include_router(products_router, prefix="/api", tags=["products"])
app.include_router(subscriptions_router, prefix="/api", tags=["subscriptions"])
app.include_router(payments_router, prefix="/api", tags=["payments"])
app.include_router(cart_router, prefix="/api", tags=["cart"])
app.include_router(orders_router, prefix="/api", tags=["orders"])
app.include_router(files_router, prefix="/api", tags=["files"])
app.include_router(webhooks_router, prefix="/api/webhooks", tags=["webhooks"])
app.include_router(discounts_router, prefix="/api", tags=["discounts"])
app.include_router(notifications_router, prefix="/api", tags=["notifications"])
app.include_router(seller_router, prefix="/api", tags=["seller"])
app.include_router(courier_router, prefix="/api/courier", tags=["courier"])


# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": time.time(), "version": "1.0.0"}


@app.get("/")
async def root():
    return {
        "message": "ZipoHub API is running",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }


# API Info endpoint for mobile apps
@app.get("/api/info")
async def api_info():
    return {
        "name": "ZipoHub API",
        "version": "1.0.0",
        "endpoints": {
            "auth": "/api/auth",
            "categories": "/api/categories",
            "subcategories": "/api/subcategories",
            "categories_tree": "/api/categories-tree",
            "products": "/api/products",
            "featured_products": "/api/products/featured",
            "my_products": "/api/products/my-products",
            "product_stats": "/api/products/stats",
            "subscription_plans": "/api/subscription-plans",
            "cart": "/api/cart",
            "add_to_cart": "/api/cart/items",
            "cart_summary": "/api/cart/summary",
            "apply_discount_to_cart": "/api/cart/discount",
            "buy_now": "/api/buy-now",
            "checkout": "/api/checkout",
            "verify_payment": "/api/verify-payment",
            "my_orders": "/api/orders",
            "discounts": "/api/discounts",
            "my_discounts": "/api/discounts/my-discounts",
            "notifications": "/api/notifications",
            "notification_stats": "/api/notifications/stats",
            "seller_dashboard": "/api/seller/dashboard",
            "seller_analytics": "/api/seller/analytics",
            "seller_events": "/api/seller/events",
            "seller_invoices": "/api/seller/invoices",
            "seller_top_products": "/api/seller/top-products",
            "seller_orders": "/api/seller/orders",
            "user_invoices": "/api/user/invoices",
            "health": "/health",
            "docs": "/docs",
        },
        "features": [
            "Supabase Authentication",
            "JWT Tokens",
            "Mobile Optimized",
            "Rate Limited",
            "CORS Enabled",
            "Categories & Subcategories",
            "Product Management",
            "Product Search & Filtering",
            "Pagination & Sorting",
            "Featured Products",
            "Shopping Cart",
            "Cart Management",
            "Product Discounts",
            "Discount Management",
            "Buy Now Payments",
            "Cart Checkout",
            "Order Management",
            "Payment Verification",
            "Seller Dashboard",
            "Seller Analytics",
            "Seller Events & Notifications",
            "Invoice Management",
        ],
    }
