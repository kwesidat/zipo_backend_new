from fastapi import (
    APIRouter,
    HTTPException,
    status,
    Query,
    Depends,
    Request,
    UploadFile,
    File,
    Form,
)
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.models.products import (
    ProductCreate,
    ProductUpdate,
    ProductResponse,
    ProductListItem,
    ProductsListResponse,
    ProductSearchFilters,
    FeaturedProductsResponse,
    ProductStats,
    ProductSortBy,
    ProductCondition,
    SupportedCurrencies,
    SellerInfo,
    CategoryInfo,
    SubcategoryInfo,
)
from app.database import supabase
from app.utils.auth_utils import AuthUtils
from app.utils.subscription_utils import check_user_subscription
from typing import Optional, List
from datetime import datetime
from decimal import Decimal
import logging
import math
import uuid
import json
import mimetypes

logger = logging.getLogger(__name__)

router = APIRouter()
security = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    """Get current authenticated user (optional for some endpoints)"""
    if not credentials:
        return None

    try:
        user_data = AuthUtils.verify_supabase_token(credentials.credentials)
        return user_data
    except Exception:
        return None


def get_required_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get current authenticated user (required)"""
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
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication failed"
        )


@router.get("/products/featured", response_model=FeaturedProductsResponse)
async def get_featured_products(
    limit: int = Query(
        10, ge=1, le=50, description="Number of featured products to return"
    ),
    category_id: Optional[str] = Query(None, description="Filter by category ID"),
    current_user=Depends(get_current_user),
):
    """Get featured products"""
    try:
        query = (
            supabase.table("products")
            .select("""
            id, name, price, currency, country, condition, photos, featured,
            quantity, allowPurchaseOnPlatform, created_at, sellerId,
            categoryId, subCategoryId
        """)
            .eq("featured", True)
            .gt("quantity", 0)
        )

        if category_id:
            query = query.eq("categoryId", category_id)

        query = query.order("created_at", desc=True).limit(limit)

        response = query.execute()

        if not response.data:
            return FeaturedProductsResponse(featured_products=[], total_count=0)

        # Get seller and category info
        seller_ids = list(set([p["sellerId"] for p in response.data]))
        category_ids = list(set([p["categoryId"] for p in response.data]))
        subcategory_ids = list(set([p["subCategoryId"] for p in response.data]))

        # Fetch additional info
        sellers_info = {}
        if seller_ids:
            sellers_response = (
                supabase.table("users")
                .select("user_id, name, business_name")
                .in_("user_id", seller_ids)
                .execute()
            )
            for seller in sellers_response.data:
                sellers_info[seller["user_id"]] = (
                    seller["business_name"] or seller["name"]
                )

        categories_info = {}
        if category_ids:
            categories_response = (
                supabase.table("categories")
                .select("id, name")
                .in_("id", category_ids)
                .execute()
            )
            for category in categories_response.data:
                categories_info[category["id"]] = category["name"]

        subcategories_info = {}
        if subcategory_ids:
            subcategories_response = (
                supabase.table("subcategories")
                .select("id, name")
                .in_("id", subcategory_ids)
                .execute()
            )
            for subcategory in subcategories_response.data:
                subcategories_info[subcategory["id"]] = subcategory["name"]

        featured_products = []
        for product in response.data:
            featured_products.append(
                ProductListItem(
                    id=product["id"],
                    name=product["name"],
                    price=product["price"],
                    currency=product["currency"],
                    country=product["country"],
                    condition=product.get("condition"),
                    photos=product.get("photos", []),
                    featured=product.get("featured", False),
                    quantity=product.get("quantity", 0),
                    allowPurchaseOnPlatform=product.get(
                        "allowPurchaseOnPlatform", False
                    ),
                    created_at=product.get("created_at"),
                    seller_name=sellers_info.get(product["sellerId"]),
                    category_name=categories_info.get(product["categoryId"]),
                    subcategory_name=subcategories_info.get(product["subCategoryId"]),
                )
            )

        return FeaturedProductsResponse(
            featured_products=featured_products, total_count=len(featured_products)
        )

    except Exception as e:
        logger.error(f"Error fetching featured products: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch featured products",
        )


@router.get("/products/my-products", response_model=ProductsListResponse)
async def get_my_products(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    sort_by: ProductSortBy = Query(
        ProductSortBy.CREATED_AT, description="Sort products by"
    ),
    current_user=Depends(get_required_user),
):
    """Get products created by the current user"""
    try:
        query = (
            supabase.table("products")
            .select("""
            id, name, price, currency, country, condition, photos, featured,
            quantity, allowPurchaseOnPlatform, created_at, sellerId,
            categoryId, subCategoryId
        """)
            .eq("sellerId", current_user["user_id"])
        )

        # Apply sorting
        if sort_by == ProductSortBy.PRICE_LOW_TO_HIGH:
            query = query.order("price", desc=False)
        elif sort_by == ProductSortBy.PRICE_HIGH_TO_LOW:
            query = query.order("price", desc=True)
        elif sort_by == ProductSortBy.NAME:
            query = query.order("name", desc=False)
        elif sort_by == ProductSortBy.FEATURED:
            query = query.order("featured", desc=True).order("created_at", desc=True)
        else:  # CREATED_AT
            query = query.order("created_at", desc=True)

        # Get total count
        count_response = (
            supabase.table("products")
            .select("id", count="exact")
            .eq("sellerId", current_user["user_id"])
            .execute()
        )
        total_count = count_response.count or 0

        # Apply pagination
        offset = (page - 1) * page_size
        query = query.range(offset, offset + page_size - 1)

        response = query.execute()

        if not response.data:
            return ProductsListResponse(
                products=[],
                total_count=total_count,
                page=page,
                page_size=page_size,
                total_pages=0,
                has_next=False,
                has_previous=page > 1,
            )

        # Get category and subcategory info
        category_ids = list(set([p["categoryId"] for p in response.data]))
        subcategory_ids = list(set([p["subCategoryId"] for p in response.data]))

        categories_info = {}
        if category_ids:
            categories_response = (
                supabase.table("categories")
                .select("id, name")
                .in_("id", category_ids)
                .execute()
            )
            for category in categories_response.data:
                categories_info[category["id"]] = category["name"]

        subcategories_info = {}
        if subcategory_ids:
            subcategories_response = (
                supabase.table("subcategories")
                .select("id, name")
                .in_("id", subcategory_ids)
                .execute()
            )
            for subcategory in subcategories_response.data:
                subcategories_info[subcategory["id"]] = subcategory["name"]

        products_list = []
        for product in response.data:
            products_list.append(
                ProductListItem(
                    id=product["id"],
                    name=product["name"],
                    price=product["price"],
                    currency=product["currency"],
                    country=product["country"],
                    condition=product.get("condition"),
                    photos=product.get("photos", []),
                    featured=product.get("featured", False),
                    quantity=product.get("quantity", 0),
                    allowPurchaseOnPlatform=product.get(
                        "allowPurchaseOnPlatform", False
                    ),
                    created_at=product.get("created_at"),
                    seller_name=None,  # Current user
                    category_name=categories_info.get(product["categoryId"]),
                    subcategory_name=subcategories_info.get(product["subCategoryId"]),
                )
            )

        total_pages = math.ceil(total_count / page_size) if total_count > 0 else 0

        return ProductsListResponse(
            products=products_list,
            total_count=total_count,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_previous=page > 1,
        )

    except Exception as e:
        logger.error(f"Error fetching user products: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch your products",
        )


@router.get("/products/stats", response_model=ProductStats)
async def get_product_stats(current_user=Depends(get_current_user)):
    """Get product statistics"""
    try:
        # Get total products count
        total_response = (
            supabase.table("products").select("id", count="exact").execute()
        )
        total_products = total_response.count or 0

        # Get products by category
        categories_response = (
            supabase.table("products").select("categoryId, categories(name)").execute()
        )
        products_by_category = {}
        for item in categories_response.data:
            category_name = item.get("categories", {}).get("name", "Unknown")
            products_by_category[category_name] = (
                products_by_category.get(category_name, 0) + 1
            )

        # Get products by condition
        conditions_response = supabase.table("products").select("condition").execute()
        products_by_condition = {}
        for item in conditions_response.data:
            condition = item.get("condition", "Unknown")
            products_by_condition[condition] = (
                products_by_condition.get(condition, 0) + 1
            )

        # Get products by currency
        currency_response = supabase.table("products").select("currency").execute()
        products_by_currency = {}
        for item in currency_response.data:
            currency = item.get("currency", "Unknown")
            products_by_currency[currency] = products_by_currency.get(currency, 0) + 1

        # Get featured products count
        featured_response = (
            supabase.table("products")
            .select("id", count="exact")
            .eq("featured", True)
            .execute()
        )
        featured_products_count = featured_response.count or 0

        # Get available products count
        available_response = (
            supabase.table("products")
            .select("id", count="exact")
            .gt("quantity", 0)
            .execute()
        )
        available_products_count = available_response.count or 0

        return ProductStats(
            total_products=total_products,
            products_by_category=products_by_category,
            products_by_condition=products_by_condition,
            products_by_currency=products_by_currency,
            featured_products_count=featured_products_count,
            available_products_count=available_products_count,
        )

    except Exception as e:
        logger.error(f"Error fetching product stats: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch product statistics",
        )


@router.get("/products/search", response_model=ProductsListResponse)
async def search_products(
    q: Optional[str] = Query(
        None,
        description="Search query - searches in name, description, and custom fields",
    ),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    sort_by: ProductSortBy = Query(
        ProductSortBy.CREATED_AT, description="Sort products by"
    ),
    category_id: Optional[str] = Query(None, description="Filter by category ID"),
    subcategory_id: Optional[str] = Query(None, description="Filter by subcategory ID"),
    condition: Optional[ProductCondition] = Query(
        None, description="Filter by condition (NEW, USED, REFURBISHED)"
    ),
    currency: Optional[SupportedCurrencies] = Query(
        None, description="Filter by currency"
    ),
    country: Optional[str] = Query(None, description="Filter by country"),
    min_price: Optional[float] = Query(None, ge=0, description="Minimum price"),
    max_price: Optional[float] = Query(None, ge=0, description="Maximum price"),
    featured_only: bool = Query(False, description="Show only featured products"),
    available_only: bool = Query(True, description="Show only products in stock"),
    current_user=Depends(get_current_user),
):
    """
    Enhanced product search endpoint with comprehensive filtering capabilities.

    Search and filter products by multiple criteria:
    - **q**: Search in product name, description, and custom fields
    - **category_id**: Filter by specific category
    - **subcategory_id**: Filter by specific subcategory
    - **condition**: Filter by product condition (NEW, USED, REFURBISHED)
    - **currency**: Filter by currency (GHS, USD, EUR)
    - **country**: Filter by country name
    - **min_price / max_price**: Price range filtering
    - **featured_only**: Show only featured products
    - **available_only**: Show only products with stock > 0
    - **sort_by**: Sort by created_at, price_asc, price_desc, name, or featured

    Returns paginated results with seller, category, and subcategory information.
    """
    try:
        # Build the query
        query = supabase.table("products").select("""
            id, name, description, price, currency, country, condition, photos, featured,
            quantity, allowPurchaseOnPlatform, created_at, sellerId,
            categoryId, subCategoryId, fields
        """)

        # Apply search query
        if q and q.strip():
            search_term = q.strip()
            # Search in name and description
            query = query.or_(
                f"name.ilike.%{search_term}%,description.ilike.%{search_term}%"
            )

        # Apply filters
        if category_id:
            query = query.eq("categoryId", category_id)

        if subcategory_id:
            query = query.eq("subCategoryId", subcategory_id)

        if condition:
            query = query.eq("condition", condition.value)

        if currency:
            query = query.eq("currency", currency.value)

        if country:
            query = query.ilike("country", f"%{country}%")

        if min_price is not None:
            query = query.gte("price", min_price)

        if max_price is not None:
            query = query.lte("price", max_price)

        if featured_only:
            query = query.eq("featured", True)

        if available_only:
            query = query.gt("quantity", 0)

        # Apply sorting
        if sort_by == ProductSortBy.PRICE_LOW_TO_HIGH:
            query = query.order("price", desc=False)
        elif sort_by == ProductSortBy.PRICE_HIGH_TO_LOW:
            query = query.order("price", desc=True)
        elif sort_by == ProductSortBy.NAME:
            query = query.order("name", desc=False)
        elif sort_by == ProductSortBy.FEATURED:
            query = query.order("featured", desc=True).order("created_at", desc=True)
        else:  # CREATED_AT
            query = query.order("created_at", desc=True)

        # Get total count for pagination
        count_query = supabase.table("products").select("id", count="exact")

        # Apply same filters for count
        if q and q.strip():
            search_term = q.strip()
            count_query = count_query.or_(
                f"name.ilike.%{search_term}%,description.ilike.%{search_term}%"
            )
        if category_id:
            count_query = count_query.eq("categoryId", category_id)
        if subcategory_id:
            count_query = count_query.eq("subCategoryId", subcategory_id)
        if condition:
            count_query = count_query.eq("condition", condition.value)
        if currency:
            count_query = count_query.eq("currency", currency.value)
        if country:
            count_query = count_query.ilike("country", f"%{country}%")
        if min_price is not None:
            count_query = count_query.gte("price", min_price)
        if max_price is not None:
            count_query = count_query.lte("price", max_price)
        if featured_only:
            count_query = count_query.eq("featured", True)
        if available_only:
            count_query = count_query.gt("quantity", 0)

        count_result = count_query.execute()
        total_count = count_result.count or 0

        # Apply pagination
        offset = (page - 1) * page_size
        query = query.range(offset, offset + page_size - 1)

        response = query.execute()

        if not response.data:
            return ProductsListResponse(
                products=[],
                total_count=total_count,
                page=page,
                page_size=page_size,
                total_pages=math.ceil(total_count / page_size)
                if total_count > 0
                else 0,
                has_next=False,
                has_previous=page > 1,
            )

        # Get all unique IDs for batch fetching
        seller_ids = list(
            set([p["sellerId"] for p in response.data if p.get("sellerId")])
        )
        category_ids = list(
            set([p["categoryId"] for p in response.data if p.get("categoryId")])
        )
        subcategory_ids = list(
            set([p["subCategoryId"] for p in response.data if p.get("subCategoryId")])
        )

        # Fetch sellers info
        sellers_info = {}
        if seller_ids:
            sellers_response = (
                supabase.table("users")
                .select("user_id, name, business_name")
                .in_("user_id", seller_ids)
                .execute()
            )
            for seller in sellers_response.data:
                sellers_info[seller["user_id"]] = seller.get(
                    "business_name"
                ) or seller.get("name")

        # Fetch categories info
        categories_info = {}
        if category_ids:
            categories_response = (
                supabase.table("categories")
                .select("id, name")
                .in_("id", category_ids)
                .execute()
            )
            for category in categories_response.data:
                categories_info[category["id"]] = category["name"]

        # Fetch subcategories info
        subcategories_info = {}
        if subcategory_ids:
            subcategories_response = (
                supabase.table("subcategories")
                .select("id, name")
                .in_("id", subcategory_ids)
                .execute()
            )
            for subcategory in subcategories_response.data:
                subcategories_info[subcategory["id"]] = subcategory["name"]

        # Build product list
        products_list = []
        for product in response.data:
            products_list.append(
                ProductListItem(
                    id=product["id"],
                    name=product["name"],
                    price=product["price"],
                    currency=product["currency"],
                    country=product["country"],
                    condition=product.get("condition"),
                    photos=product.get("photos", []),
                    featured=product.get("featured", False),
                    quantity=product.get("quantity", 0),
                    allowPurchaseOnPlatform=product.get(
                        "allowPurchaseOnPlatform", False
                    ),
                    created_at=product.get("created_at"),
                    seller_name=sellers_info.get(product.get("sellerId")),
                    category_name=categories_info.get(product.get("categoryId")),
                    subcategory_name=subcategories_info.get(
                        product.get("subCategoryId")
                    ),
                )
            )

        total_pages = math.ceil(total_count / page_size) if total_count > 0 else 0

        return ProductsListResponse(
            products=products_list,
            total_count=total_count,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_previous=page > 1,
        )

    except Exception as e:
        logger.error(f"Error searching products: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to search products",
        )


@router.get("/products", response_model=ProductsListResponse)
async def get_products(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    sort_by: ProductSortBy = Query(
        ProductSortBy.CREATED_AT, description="Sort products by"
    ),
    category_id: Optional[str] = Query(None, description="Filter by category ID"),
    subcategory_id: Optional[str] = Query(None, description="Filter by subcategory ID"),
    seller_id: Optional[str] = Query(None, description="Filter by seller ID"),
    condition: Optional[ProductCondition] = Query(
        None, description="Filter by condition"
    ),
    currency: Optional[SupportedCurrencies] = Query(
        None, description="Filter by currency"
    ),
    country: Optional[str] = Query(None, description="Filter by country"),
    min_price: Optional[float] = Query(None, ge=0, description="Minimum price"),
    max_price: Optional[float] = Query(None, ge=0, description="Maximum price"),
    featured_only: bool = Query(False, description="Show only featured products"),
    available_only: bool = Query(True, description="Show only available products"),
    search_query: Optional[str] = Query(
        None, description="Search in product names and descriptions"
    ),
    current_user=Depends(get_current_user),
):
    """Get products with filtering, pagination, and sorting"""
    try:
        # Build the query
        query = supabase.table("products").select("""
            id, name, price, currency, country, condition, photos, featured,
            quantity, allowPurchaseOnPlatform, created_at, sellerId,
            categoryId, subCategoryId
        """)

        # Apply filters
        if category_id:
            query = query.eq("categoryId", category_id)

        if subcategory_id:
            query = query.eq("subCategoryId", subcategory_id)

        if seller_id:
            query = query.eq("sellerId", seller_id)

        if condition:
            query = query.eq("condition", condition.value)

        if currency:
            query = query.eq("currency", currency.value)

        if country:
            query = query.ilike("country", f"%{country}%")

        if min_price is not None:
            query = query.gte("price", min_price)

        if max_price is not None:
            query = query.lte("price", max_price)

        if featured_only:
            query = query.eq("featured", True)

        if available_only:
            query = query.gt("quantity", 0)

        if search_query:
            query = query.or_(
                f"name.ilike.%{search_query}%,description.ilike.%{search_query}%"
            )

        # Apply sorting
        if sort_by == ProductSortBy.PRICE_LOW_TO_HIGH:
            query = query.order("price", desc=False)
        elif sort_by == ProductSortBy.PRICE_HIGH_TO_LOW:
            query = query.order("price", desc=True)
        elif sort_by == ProductSortBy.NAME:
            query = query.order("name", desc=False)
        elif sort_by == ProductSortBy.FEATURED:
            query = query.order("featured", desc=True).order("created_at", desc=True)
        else:  # CREATED_AT
            query = query.order("created_at", desc=True)

        # Get total count for pagination
        count_response = supabase.table("products").select("id", count="exact")

        # Apply same filters for count
        if category_id:
            count_response = count_response.eq("categoryId", category_id)
        if subcategory_id:
            count_response = count_response.eq("subCategoryId", subcategory_id)
        if seller_id:
            count_response = count_response.eq("sellerId", seller_id)
        if condition:
            count_response = count_response.eq("condition", condition.value)
        if currency:
            count_response = count_response.eq("currency", currency.value)
        if country:
            count_response = count_response.ilike("country", f"%{country}%")
        if min_price is not None:
            count_response = count_response.gte("price", min_price)
        if max_price is not None:
            count_response = count_response.lte("price", max_price)
        if featured_only:
            count_response = count_response.eq("featured", True)
        if available_only:
            count_response = count_response.gt("quantity", 0)
        if search_query:
            count_response = count_response.or_(
                f"name.ilike.%{search_query}%,description.ilike.%{search_query}%"
            )

        count_result = count_response.execute()
        total_count = count_result.count or 0

        # Apply pagination
        offset = (page - 1) * page_size
        query = query.range(offset, offset + page_size - 1)

        response = query.execute()

        if not response.data:
            return ProductsListResponse(
                products=[],
                total_count=total_count,
                page=page,
                page_size=page_size,
                total_pages=math.ceil(total_count / page_size)
                if total_count > 0
                else 0,
                has_next=False,
                has_previous=page > 1,
            )

        # Get seller, category, and subcategory info for each product
        products_list = []

        # Get all unique seller IDs, category IDs, and subcategory IDs
        seller_ids = list(set([p["sellerId"] for p in response.data]))
        category_ids = list(set([p["categoryId"] for p in response.data]))
        subcategory_ids = list(set([p["subCategoryId"] for p in response.data]))

        # Fetch sellers info
        sellers_info = {}
        if seller_ids:
            sellers_response = (
                supabase.table("users")
                .select("user_id, name, business_name")
                .in_("user_id", seller_ids)
                .execute()
            )
            for seller in sellers_response.data:
                sellers_info[seller["user_id"]] = (
                    seller["business_name"] or seller["name"]
                )

        # Fetch categories info
        categories_info = {}
        if category_ids:
            categories_response = (
                supabase.table("categories")
                .select("id, name")
                .in_("id", category_ids)
                .execute()
            )
            for category in categories_response.data:
                categories_info[category["id"]] = category["name"]

        # Fetch subcategories info
        subcategories_info = {}
        if subcategory_ids:
            subcategories_response = (
                supabase.table("subcategories")
                .select("id, name")
                .in_("id", subcategory_ids)
                .execute()
            )
            for subcategory in subcategories_response.data:
                subcategories_info[subcategory["id"]] = subcategory["name"]

        # Build product list
        for product in response.data:
            products_list.append(
                ProductListItem(
                    id=product["id"],
                    name=product["name"],
                    price=product["price"],
                    currency=product["currency"],
                    country=product["country"],
                    condition=product.get("condition"),
                    photos=product.get("photos", []),
                    featured=product.get("featured", False),
                    quantity=product.get("quantity", 0),
                    allowPurchaseOnPlatform=product.get(
                        "allowPurchaseOnPlatform", False
                    ),
                    created_at=product.get("created_at"),
                    seller_name=sellers_info.get(product["sellerId"]),
                    category_name=categories_info.get(product["categoryId"]),
                    subcategory_name=subcategories_info.get(product["subCategoryId"]),
                )
            )

        total_pages = math.ceil(total_count / page_size) if total_count > 0 else 0

        return ProductsListResponse(
            products=products_list,
            total_count=total_count,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_previous=page > 1,
        )

    except Exception as e:
        logger.error(f"Error fetching products: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch products",
        )


@router.get("/products/{product_id}", response_model=ProductResponse)
async def get_product_by_id(
    product_id: str,
    include_seller_info: bool = Query(True, description="Include seller information"),
    include_category_info: bool = Query(
        True, description="Include category information"
    ),
    current_user=Depends(get_current_user),
):
    """Get a specific product by ID with detailed information"""
    try:
        # Get the product
        product_response = (
            supabase.table("products").select("*").eq("id", product_id).execute()
        )

        if not product_response.data or len(product_response.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Product not found"
            )

        product = product_response.data[0]

        # Get seller info
        seller_info = None
        if include_seller_info:
            seller_response = (
                supabase.table("users")
                .select("user_id, name, email, phone_number, business_name")
                .eq("user_id", product["sellerId"])
                .execute()
            )
            if seller_response.data and len(seller_response.data) > 0:
                seller_data = seller_response.data[0]
                seller_info = SellerInfo(
                    user_id=seller_data["user_id"],
                    name=seller_data["name"],
                    email=seller_data["email"],
                    phone_number=seller_data.get("phone_number"),
                    business_name=seller_data.get("business_name"),
                )

        # Get category info
        category_info = None
        subcategory_info = None
        if include_category_info:
            category_response = (
                supabase.table("categories")
                .select("id, name, description")
                .eq("id", product["categoryId"])
                .execute()
            )
            if category_response.data and len(category_response.data) > 0:
                category_data = category_response.data[0]
                category_info = CategoryInfo(
                    id=category_data["id"],
                    name=category_data["name"],
                    description=category_data.get("description"),
                )

            subcategory_response = (
                supabase.table("subcategories")
                .select("id, name, description")
                .eq("id", product["subCategoryId"])
                .execute()
            )
            if subcategory_response.data and len(subcategory_response.data) > 0:
                subcategory_data = subcategory_response.data[0]
                subcategory_info = SubcategoryInfo(
                    id=subcategory_data["id"],
                    name=subcategory_data["name"],
                    description=subcategory_data.get("description"),
                )

        return ProductResponse(
            id=product["id"],
            name=product["name"],
            price=product["price"],
            country=product["country"],
            categoryId=product["categoryId"],
            subCategoryId=product["subCategoryId"],
            sellerId=product["sellerId"],
            description=product.get("description"),
            condition=product.get("condition"),
            photos=product.get("photos", []),
            fields=product.get("fields")
            if product.get("fields") and product.get("fields") != "[]"
            else None,
            currency=product["currency"],
            quantity=product.get("quantity", 0),
            allowPurchaseOnPlatform=product.get("allowPurchaseOnPlatform", False),
            featured=product.get("featured", False),
            created_at=product.get("created_at"),
            updated_at=product.get("updated_at"),
            seller=seller_info,
            category=category_info,
            subCategory=subcategory_info,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching product {product_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch product details",
        )


@router.post(
    "/products", response_model=ProductResponse, status_code=status.HTTP_201_CREATED
)
async def create_product(
    product: ProductCreate, current_user=Depends(get_required_user)
):
    """Create a new product (requires authentication)"""
    try:
        # Check user subscription before allowing product creation
        subscription_check = await check_user_subscription(current_user["user_id"])

        if not subscription_check["can_create_product"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=subscription_check["message"],
            )

        # Verify category and subcategory exist
        category_response = (
            supabase.table("categories")
            .select("id")
            .eq("id", product.categoryId)
            .execute()
        )
        if not category_response.data or len(category_response.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid category ID"
            )

        subcategory_response = (
            supabase.table("subcategories")
            .select("id, category_id")
            .eq("id", product.subCategoryId)
            .execute()
        )
        if not subcategory_response.data or len(subcategory_response.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid subcategory ID"
            )

        # Verify subcategory belongs to the specified category
        if subcategory_response.data[0]["category_id"] != product.categoryId:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Subcategory does not belong to the specified category",
            )

        # Create the product
        product_data = product.dict()
        product_data["id"] = str(uuid.uuid4())
        product_data["sellerId"] = current_user["user_id"]
        product_data["created_at"] = datetime.utcnow().isoformat()
        product_data["updated_at"] = datetime.utcnow().isoformat()

        # Convert Decimal to string for JSON serialization
        if "price" in product_data and product_data["price"] is not None:
            product_data["price"] = str(product_data["price"])

        response = supabase.table("products").insert(product_data).execute()

        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create product",
            )

        created_product = response.data[0]

        return ProductResponse(
            id=created_product["id"],
            name=created_product["name"],
            price=created_product["price"],
            country=created_product["country"],
            categoryId=created_product["categoryId"],
            subCategoryId=created_product["subCategoryId"],
            sellerId=created_product["sellerId"],
            description=created_product.get("description"),
            condition=created_product.get("description"),
            photos=created_product.get("photos", []),
            fields=created_product.get("fields")
            if created_product.get("fields") and created_product.get("fields") != "[]"
            else None,
            currency=created_product["currency"],
            quantity=created_product.get("quantity", 0),
            allowPurchaseOnPlatform=created_product.get(
                "allowPurchaseOnPlatform", False
            ),
            featured=created_product.get("featured", False),
            created_at=created_product.get("created_at"),
            updated_at=created_product.get("updated_at"),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating product: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create product",
        )


@router.post(
    "/products/create-with-images",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_product_with_images(
    name: str = Form(...),
    price: float = Form(..., gt=0),
    country: str = Form(...),
    categoryId: str = Form(...),
    subCategoryId: str = Form(...),
    description: Optional[str] = Form(None),
    condition: Optional[str] = Form(None),
    currency: str = Form("GHS"),
    quantity: int = Form(0, ge=0),
    allowPurchaseOnPlatform: bool = Form(False),
    featured: bool = Form(False),
    fields: Optional[str] = Form(None),
    images: List[UploadFile] = File([]),
    current_user=Depends(get_required_user),
):
    """
    Create a new product with image uploads in a single request.
    This endpoint accepts multipart/form-data with product details and image files.

    - **images**: Upload 1-10 product images (JPEG, PNG, WebP, max 5MB each)
    - **fields**: JSON string of custom attributes, e.g., '{"Storage": "64GB", "Color": "Black"}'
    """
    try:
        # Check user subscription before allowing product creation
        subscription_check = await check_user_subscription(current_user["user_id"])

        if not subscription_check["can_create_product"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=subscription_check["message"],
            )

        # Verify category and subcategory exist
        category_response = (
            supabase.table("categories").select("id").eq("id", categoryId).execute()
        )
        if not category_response.data or len(category_response.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid category ID"
            )

        subcategory_response = (
            supabase.table("subcategories")
            .select("id, category_id")
            .eq("id", subCategoryId)
            .execute()
        )
        if not subcategory_response.data or len(subcategory_response.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid subcategory ID"
            )

        # Verify subcategory belongs to the specified category
        if subcategory_response.data[0]["category_id"] != categoryId:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Subcategory does not belong to the specified category",
            )

        # Validate and upload images
        uploaded_urls = []
        if images:
            # Limit to 10 images
            if len(images) > 10:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Maximum 10 images allowed per product",
                )

            allowed_types = ["image/jpeg", "image/jpg", "image/png", "image/webp"]
            max_size = 5 * 1024 * 1024  # 5MB

            for file in images:
                # Check file type
                if file.content_type not in allowed_types:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Invalid file type: {file.content_type}. Allowed: JPEG, PNG, WebP",
                    )

                # Check file size
                file_content = await file.read()
                if len(file_content) > max_size:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"File too large: {file.filename}. Max size: 5MB",
                    )

                # Generate unique filename
                file_extension = mimetypes.guess_extension(file.content_type) or ".jpg"
                unique_filename = (
                    f"{current_user['user_id']}/{uuid.uuid4()}{file_extension}"
                )

                try:
                    # Upload to Supabase Storage
                    supabase.storage.from_("product-images").upload(
                        path=unique_filename,
                        file=file_content,
                        file_options={"content-type": file.content_type},
                    )

                    # Get public URL
                    public_url = supabase.storage.from_(
                        "product-images"
                    ).get_public_url(unique_filename)
                    uploaded_urls.append(public_url)

                except Exception as storage_error:
                    logger.error(f"Storage upload error: {str(storage_error)}")
                    # Clean up already uploaded images
                    for uploaded_url in uploaded_urls:
                        try:
                            path = (
                                uploaded_url.split("/")[-2]
                                + "/"
                                + uploaded_url.split("/")[-1]
                            )
                            supabase.storage.from_("product-images").remove([path])
                        except:
                            pass
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Failed to upload image: {file.filename}",
                    )

        # Parse fields JSON if provided
        parsed_fields = None
        if fields:
            try:
                parsed_fields = json.loads(fields)
            except json.JSONDecodeError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid JSON format for fields parameter",
                )

        # Validate condition
        product_condition = None
        if condition:
            if condition not in ["NEW", "USED", "REFURBISHED"]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid condition. Must be: NEW, USED, or REFURBISHED",
                )
            product_condition = condition

        # Validate currency
        if currency not in ["GHS", "USD"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid currency. Must be: GHS or USD",
            )

        # Create the product
        product_data = {
            "id": str(uuid.uuid4()),
            "name": name,
            "price": str(price),
            "country": country,
            "categoryId": categoryId,
            "subCategoryId": subCategoryId,
            "sellerId": current_user["user_id"],
            "description": description,
            "condition": product_condition,
            "photos": uploaded_urls,
            "fields": parsed_fields,
            "currency": currency,
            "quantity": quantity,
            "allowPurchaseOnPlatform": allowPurchaseOnPlatform,
            "featured": featured,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }

        response = supabase.table("products").insert(product_data).execute()

        if not response.data:
            # Clean up uploaded images if product creation fails
            for uploaded_url in uploaded_urls:
                try:
                    path = (
                        uploaded_url.split("/")[-2] + "/" + uploaded_url.split("/")[-1]
                    )
                    supabase.storage.from_("product-images").remove([path])
                except:
                    pass
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create product",
            )

        created_product = response.data[0]

        return ProductResponse(
            id=created_product["id"],
            name=created_product["name"],
            price=created_product["price"],
            country=created_product["country"],
            categoryId=created_product["categoryId"],
            subCategoryId=created_product["subCategoryId"],
            sellerId=created_product["sellerId"],
            description=created_product.get("description"),
            condition=created_product.get("condition"),
            photos=created_product.get("photos", []),
            fields=created_product.get("fields"),
            currency=created_product["currency"],
            quantity=created_product.get("quantity", 0),
            allowPurchaseOnPlatform=created_product.get(
                "allowPurchaseOnPlatform", False
            ),
            featured=created_product.get("featured", False),
            created_at=created_product.get("created_at"),
            updated_at=created_product.get("updated_at"),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating product with images: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create product: {str(e)}",
        )


@router.put("/products/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: str, product: ProductUpdate, current_user=Depends(get_required_user)
):
    """Update a product (only by the seller)"""
    try:
        # Check if product exists and belongs to the current user
        existing_product_response = (
            supabase.table("products").select("*").eq("id", product_id).execute()
        )

        if (
            not existing_product_response.data
            or len(existing_product_response.data) == 0
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Product not found"
            )

        existing_product = existing_product_response.data[0]

        if existing_product["sellerId"] != current_user["user_id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only update your own products",
            )

        # Validate category and subcategory if provided
        if product.categoryId or product.subCategoryId:
            category_id = product.categoryId or existing_product["categoryId"]
            subcategory_id = product.subCategoryId or existing_product["subCategoryId"]

            category_response = (
                supabase.table("categories")
                .select("id")
                .eq("id", category_id)
                .execute()
            )
            if not category_response.data or len(category_response.data) == 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid category ID",
                )

            subcategory_response = (
                supabase.table("subcategories")
                .select("id, category_id")
                .eq("id", subcategory_id)
                .execute()
            )
            if not subcategory_response.data or len(subcategory_response.data) == 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid subcategory ID",
                )

            if subcategory_response.data[0]["category_id"] != category_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Subcategory does not belong to the specified category",
                )

        # Update the product
        update_data = {}
        for k, v in product.dict().items():
            if v is not None:
                # Convert Decimal to float for JSON serialization
                if isinstance(v, Decimal):
                    update_data[k] = float(v)
                else:
                    update_data[k] = v
        update_data["updated_at"] = datetime.utcnow().isoformat()

        response = (
            supabase.table("products")
            .update(update_data)
            .eq("id", product_id)
            .execute()
        )

        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update product",
            )

        updated_product = response.data[0]

        return ProductResponse(
            id=updated_product["id"],
            name=updated_product["name"],
            price=updated_product["price"],
            country=updated_product["country"],
            categoryId=updated_product["categoryId"],
            subCategoryId=updated_product["subCategoryId"],
            sellerId=updated_product["sellerId"],
            description=updated_product.get("description"),
            condition=updated_product.get("condition"),
            photos=updated_product.get("photos", []),
            fields=updated_product.get("fields")
            if updated_product.get("fields") and updated_product.get("fields") != "[]"
            else None,
            currency=updated_product["currency"],
            quantity=updated_product.get("quantity", 0),
            allowPurchaseOnPlatform=updated_product.get(
                "allowPurchaseOnPlatform", False
            ),
            featured=updated_product.get("featured", False),
            created_at=updated_product.get("created_at"),
            updated_at=updated_product.get("updated_at"),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating product {product_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update product",
        )


@router.delete("/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(product_id: str, current_user=Depends(get_required_user)):
    """Delete a product (only by the seller)"""
    try:
        # Check if product exists and belongs to the current user
        existing_product_response = (
            supabase.table("products").select("sellerId").eq("id", product_id).execute()
        )

        if (
            not existing_product_response.data
            or len(existing_product_response.data) == 0
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Product not found"
            )

        existing_product = existing_product_response.data[0]

        if existing_product["sellerId"] != current_user["user_id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only delete your own products",
            )

        # Delete the product
        response = supabase.table("products").delete().eq("id", product_id).execute()

        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete product",
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting product {product_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete product",
        )


@router.patch("/products/{product_id}/featured", response_model=ProductResponse)
async def toggle_product_featured(
    product_id: str,
    featured: bool = Query(..., description="Set featured status"),
    current_user=Depends(get_required_user),
):
    """Toggle product featured status (only by the seller)"""
    try:
        # Check if product exists and belongs to the current user
        existing_product_response = (
            supabase.table("products")
            .select("sellerId, featured")
            .eq("id", product_id)
            .execute()
        )

        if (
            not existing_product_response.data
            or len(existing_product_response.data) == 0
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Product not found"
            )

        existing_product = existing_product_response.data[0]

        if existing_product["sellerId"] != current_user["user_id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only update your own products",
            )

        # Update featured status
        update_data = {
            "featured": featured,
            "updated_at": datetime.utcnow().isoformat(),
        }
        response = (
            supabase.table("products")
            .update(update_data)
            .eq("id", product_id)
            .execute()
        )

        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update product",
            )

        updated_product = response.data[0]

        return ProductResponse(
            id=updated_product["id"],
            name=updated_product["name"],
            price=updated_product["price"],
            country=updated_product["country"],
            categoryId=updated_product["categoryId"],
            subCategoryId=updated_product["subCategoryId"],
            sellerId=updated_product["sellerId"],
            description=updated_product.get("description"),
            condition=updated_product.get("condition"),
            photos=updated_product.get("photos", []),
            fields=updated_product.get("fields")
            if updated_product.get("fields") and updated_product.get("fields") != "[]"
            else None,
            currency=updated_product["currency"],
            quantity=updated_product.get("quantity", 0),
            allowPurchaseOnPlatform=updated_product.get(
                "allowPurchaseOnPlatform", False
            ),
            featured=updated_product.get("featured", False),
            created_at=updated_product.get("created_at"),
            updated_at=updated_product.get("updated_at"),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error toggling featured status for product {product_id}: {str(e)}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update product featured status",
        )


@router.patch("/products/{product_id}/online-payment", response_model=ProductResponse)
async def toggle_online_payment(
    product_id: str,
    allow_payment: bool = Query(..., description="Allow online payment"),
    current_user=Depends(get_required_user),
):
    """Toggle product online payment option (only by the seller)"""
    try:
        # Check if product exists and belongs to the current user
        existing_product_response = (
            supabase.table("products")
            .select("sellerId, allowPurchaseOnPlatform")
            .eq("id", product_id)
            .execute()
        )

        if (
            not existing_product_response.data
            or len(existing_product_response.data) == 0
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Product not found"
            )

        existing_product = existing_product_response.data[0]

        if existing_product["sellerId"] != current_user["user_id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only update your own products",
            )

        # Update online payment status
        update_data = {
            "allowPurchaseOnPlatform": allow_payment,
            "updated_at": datetime.utcnow().isoformat(),
        }
        response = (
            supabase.table("products")
            .update(update_data)
            .eq("id", product_id)
            .execute()
        )

        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update product",
            )

        updated_product = response.data[0]

        return ProductResponse(
            id=updated_product["id"],
            name=updated_product["name"],
            price=updated_product["price"],
            country=updated_product["country"],
            categoryId=updated_product["categoryId"],
            subCategoryId=updated_product["subCategoryId"],
            sellerId=updated_product["sellerId"],
            description=updated_product.get("description"),
            condition=updated_product.get("condition"),
            photos=updated_product.get("photos", []),
            fields=updated_product.get("fields")
            if updated_product.get("fields") and updated_product.get("fields") != "[]"
            else None,
            currency=updated_product["currency"],
            quantity=updated_product.get("quantity", 0),
            allowPurchaseOnPlatform=updated_product.get(
                "allowPurchaseOnPlatform", False
            ),
            featured=updated_product.get("featured", False),
            created_at=updated_product.get("created_at"),
            updated_at=updated_product.get("updated_at"),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error toggling online payment for product {product_id}: {str(e)}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update product online payment status",
        )
