from fastapi import APIRouter, HTTPException, status, Query
from app.models.categories import (
    CategoryResponse, CategoryDetailResponse, CategoriesListResponse,
    SubcategoryResponse, CategoryWithSubcategories, ProductSummary
)
from app.database import supabase
from typing import Optional, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/categories", response_model=CategoriesListResponse)
async def get_all_categories(
    include_subcategories: bool = Query(True, description="Include subcategories in response"),
    include_product_count: bool = Query(True, description="Include product count for each category")
):
    """Get all categories with optional subcategories and product counts"""
    try:
        # Get all categories
        categories_response = supabase.table("categories").select("*").is_("deleted_at", "null").order("name").execute()

        if not categories_response.data:
            return CategoriesListResponse(categories=[], total_count=0)

        categories_list = []

        # Get all subcategories and product counts in batched queries if needed
        all_subcategories = {}
        product_counts_by_subcategory = {}

        if include_subcategories:
            # Get all subcategories for all categories in one query
            all_subcategories_response = supabase.table("subcategories").select("*").is_("deleted_at", "null").order("name").execute()

            # Group subcategories by category_id
            for subcategory in all_subcategories_response.data:
                category_id = subcategory["category_id"]
                if category_id not in all_subcategories:
                    all_subcategories[category_id] = []
                all_subcategories[category_id].append(subcategory)

            if include_product_count:
                # Try to use RPC function first, fallback to manual counting if it doesn't exist
                try:
                    products_count_response = supabase.rpc("get_product_counts_by_subcategory").execute()
                    # Use RPC result if available
                    for row in products_count_response.data:
                        product_counts_by_subcategory[row["subcategory_id"]] = row["product_count"]
                except Exception:
                    # Fallback: get all products with their subcategory IDs
                    all_products_response = supabase.table("products").select("subCategoryId").execute()

                    # Count products per subcategory
                    for product in all_products_response.data:
                        sub_cat_id = product["subCategoryId"]
                        if sub_cat_id:
                            product_counts_by_subcategory[sub_cat_id] = product_counts_by_subcategory.get(sub_cat_id, 0) + 1

        for category in categories_response.data:
            subcategories_list = []
            category_product_count = 0

            if include_subcategories:
                # Get subcategories for this category from our pre-fetched data
                category_subcategories = all_subcategories.get(category["id"], [])

                for subcategory in category_subcategories:
                    subcategory_product_count = 0

                    if include_product_count:
                        # Get product count from our pre-calculated counts
                        subcategory_product_count = product_counts_by_subcategory.get(subcategory["id"], 0)

                    subcategories_list.append(SubcategoryResponse(
                        id=subcategory["id"],
                        name=subcategory["name"],
                        description=subcategory["description"],
                        category_id=subcategory["category_id"],
                        created_at=subcategory["created_at"],
                        updated_at=subcategory["updated_at"],
                        product_count=subcategory_product_count
                    ))

                    category_product_count += subcategory_product_count

            if include_product_count and not include_subcategories:
                # Count products in this category directly
                products_count_response = supabase.table("products").select("id", count="exact").eq("categoryId", category["id"]).execute()
                category_product_count = products_count_response.count or 0

            categories_list.append(CategoryResponse(
                id=category["id"],
                name=category["name"],
                description=category["description"],
                created_at=category["created_at"],
                updated_at=category["updated_at"],
                subcategories=subcategories_list,
                product_count=category_product_count
            ))

        return CategoriesListResponse(
            categories=categories_list,
            total_count=len(categories_list)
        )

    except Exception as e:
        logger.error(f"Error fetching categories: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch categories"
        )

@router.get("/categories/{category_id}", response_model=CategoryDetailResponse)
async def get_category_by_id(
    category_id: str,
    include_recent_products: bool = Query(True, description="Include recent products"),
    recent_products_limit: int = Query(10, description="Number of recent products to include")
):
    """Get a specific category with its subcategories and optional recent products"""
    try:
        # Get the category
        category_response = supabase.table("categories").select("*").eq("id", category_id).is_("deleted_at", "null").execute()

        if not category_response.data or len(category_response.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Category not found"
            )

        category = category_response.data[0]

        # Get subcategories
        subcategories_response = supabase.table("subcategories").select("*").eq("category_id", category_id).is_("deleted_at", "null").order("name").execute()

        subcategories_list = []
        total_products = 0

        for subcategory in subcategories_response.data:
            # Count products in subcategory
            products_count_response = supabase.table("products").select("id", count="exact").eq("subCategoryId", subcategory["id"]).execute()
            subcategory_product_count = products_count_response.count or 0
            total_products += subcategory_product_count

            subcategories_list.append(SubcategoryResponse(
                id=subcategory["id"],
                name=subcategory["name"],
                description=subcategory["description"],
                category_id=subcategory["category_id"],
                created_at=subcategory["created_at"],
                updated_at=subcategory["updated_at"],
                product_count=subcategory_product_count
            ))

        recent_products = []
        if include_recent_products:
            # Get recent products in this category
            products_response = supabase.table("products").select("id, name, price, currency, condition, photos, featured, created_at").eq("categoryId", category_id).order("created_at", desc=True).limit(recent_products_limit).execute()

            for product in products_response.data:
                recent_products.append(ProductSummary(
                    id=product["id"],
                    name=product["name"],
                    price=product["price"],
                    currency=product["currency"],
                    condition=product.get("condition"),
                    photos=product.get("photos", []),
                    featured=product.get("featured", False)
                ))

        return CategoryDetailResponse(
            id=category["id"],
            name=category["name"],
            description=category["description"],
            created_at=category["created_at"],
            updated_at=category["updated_at"],
            subcategories=subcategories_list,
            recent_products=recent_products,
            total_products=total_products
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching category {category_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch category details"
        )

@router.get("/subcategories", response_model=List[SubcategoryResponse])
async def get_all_subcategories(
    category_id: Optional[str] = Query(None, description="Filter by category ID"),
    include_product_count: bool = Query(True, description="Include product count for each subcategory")
):
    """Get all subcategories, optionally filtered by category"""
    try:
        query = supabase.table("subcategories").select("*").is_("deleted_at", "null")

        if category_id:
            query = query.eq("category_id", category_id)

        subcategories_response = query.order("name").execute()

        if not subcategories_response.data:
            return []

        subcategories_list = []

        for subcategory in subcategories_response.data:
            subcategory_product_count = 0

            if include_product_count:
                # Count products in this subcategory
                products_count_response = supabase.table("products").select("id", count="exact").eq("subCategoryId", subcategory["id"]).execute()
                subcategory_product_count = products_count_response.count or 0

            subcategories_list.append(SubcategoryResponse(
                id=subcategory["id"],
                name=subcategory["name"],
                description=subcategory["description"],
                category_id=subcategory["category_id"],
                created_at=subcategory["created_at"],
                updated_at=subcategory["updated_at"],
                product_count=subcategory_product_count
            ))

        return subcategories_list

    except Exception as e:
        logger.error(f"Error fetching subcategories: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch subcategories"
        )

@router.get("/subcategories/{subcategory_id}", response_model=SubcategoryResponse)
async def get_subcategory_by_id(subcategory_id: str):
    """Get a specific subcategory by ID"""
    try:
        # Get the subcategory
        subcategory_response = supabase.table("subcategories").select("*").eq("id", subcategory_id).is_("deleted_at", "null").execute()

        if not subcategory_response.data or len(subcategory_response.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Subcategory not found"
            )

        subcategory = subcategory_response.data[0]

        # Count products in this subcategory
        products_count_response = supabase.table("products").select("id", count="exact").eq("subCategoryId", subcategory_id).execute()
        product_count = products_count_response.count or 0

        return SubcategoryResponse(
            id=subcategory["id"],
            name=subcategory["name"],
            description=subcategory["description"],
            category_id=subcategory["category_id"],
            created_at=subcategory["created_at"],
            updated_at=subcategory["updated_at"],
            product_count=product_count
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching subcategory {subcategory_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch subcategory details"
        )

@router.get("/categories-tree", response_model=List[CategoryWithSubcategories])
async def get_categories_tree():
    """Get categories with their subcategories in a tree structure (simplified without product counts)"""
    try:
        # Get all categories
        categories_response = supabase.table("categories").select("*").is_("deleted_at", "null").order("name").execute()

        if not categories_response.data:
            return []

        categories_tree = []

        for category in categories_response.data:
            # Get subcategories for this category
            subcategories_response = supabase.table("subcategories").select("*").eq("category_id", category["id"]).is_("deleted_at", "null").order("name").execute()

            subcategories_list = []
            for subcategory in subcategories_response.data:
                subcategories_list.append({
                    "id": subcategory["id"],
                    "name": subcategory["name"],
                    "description": subcategory["description"],
                    "category_id": subcategory["category_id"],
                    "created_at": subcategory["created_at"],
                    "updated_at": subcategory["updated_at"]
                })

            categories_tree.append(CategoryWithSubcategories(
                id=category["id"],
                name=category["name"],
                description=category["description"],
                created_at=category["created_at"],
                updated_at=category["updated_at"],
                subcategories=subcategories_list
            ))

        return categories_tree

    except Exception as e:
        logger.error(f"Error fetching categories tree: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch categories tree"
        )