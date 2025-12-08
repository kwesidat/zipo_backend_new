from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal
from enum import Enum

class ProductCondition(str, Enum):
    NEW = "NEW"
    USED = "USED"
    REFURBISHED = "REFURBISHED"

class SupportedCurrencies(str, Enum):
    GHS = "GHS"
    USD = "USD"
    EUR = "EUR"

class ProductSortBy(str, Enum):
    CREATED_AT = "created_at"
    PRICE_LOW_TO_HIGH = "price_asc"
    PRICE_HIGH_TO_LOW = "price_desc"
    NAME = "name"
    FEATURED = "featured"

class ProductBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    price: Decimal = Field(..., gt=0, decimal_places=2)
    country: str = Field(..., min_length=1)
    categoryId: str = Field(..., description="Category UUID")
    subCategoryId: str = Field(..., description="Subcategory UUID")
    description: Optional[str] = None
    condition: Optional[ProductCondition] = None
    photos: List[str] = Field(default_factory=list, description="Array of image URLs")
    fields: Optional[Dict[str, Any]] = Field(
        None,
        description="Custom product attributes as key-value pairs. Example: {'Storage': '64GB', 'Color': 'Black', 'RAM': '8GB'}"
    )
    currency: SupportedCurrencies = SupportedCurrencies.GHS
    quantity: int = Field(default=0, ge=0, description="Available stock quantity")
    allowPurchaseOnPlatform: bool = Field(default=False, description="Enable online payment for this product")
    featured: bool = Field(default=False, description="Mark product as featured")
    free_delivery: bool = Field(default=True, description="Offer free delivery for this product")

class ProductCreate(ProductBase):
    pass

class ProductUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    price: Optional[Decimal] = Field(None, gt=0, decimal_places=2)
    country: Optional[str] = Field(None, min_length=1)
    categoryId: Optional[str] = None
    subCategoryId: Optional[str] = None
    description: Optional[str] = None
    condition: Optional[ProductCondition] = None
    photos: Optional[List[str]] = None
    fields: Optional[Dict[str, Any]] = None
    currency: Optional[SupportedCurrencies] = None
    quantity: Optional[int] = Field(None, ge=0)
    allowPurchaseOnPlatform: Optional[bool] = None
    featured: Optional[bool] = None
    free_delivery: Optional[bool] = None

class SellerInfo(BaseModel):
    user_id: str
    name: str
    email: str
    phone_number: Optional[str] = None
    business_name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

class CategoryInfo(BaseModel):
    id: str
    name: str
    description: Optional[str] = None

class SubcategoryInfo(BaseModel):
    id: str
    name: str
    description: Optional[str] = None

class ProductResponse(ProductBase):
    id: str
    sellerId: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    seller: Optional[SellerInfo] = None
    category: Optional[CategoryInfo] = None
    subCategory: Optional[SubcategoryInfo] = None

class ProductListItem(BaseModel):
    id: str
    name: str
    price: Decimal
    currency: SupportedCurrencies
    country: str
    condition: Optional[ProductCondition] = None
    photos: List[str] = []
    featured: bool = False
    quantity: int = 0
    allowPurchaseOnPlatform: bool = False
    free_delivery: bool = True
    created_at: Optional[datetime] = None
    seller_name: Optional[str] = None
    category_name: Optional[str] = None
    subcategory_name: Optional[str] = None

class ProductsListResponse(BaseModel):
    products: List[ProductListItem]
    total_count: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_previous: bool

class ProductSearchFilters(BaseModel):
    category_id: Optional[str] = None
    subcategory_id: Optional[str] = None
    seller_id: Optional[str] = None
    condition: Optional[ProductCondition] = None
    currency: Optional[SupportedCurrencies] = None
    country: Optional[str] = None
    min_price: Optional[Decimal] = Field(None, ge=0)
    max_price: Optional[Decimal] = Field(None, ge=0)
    featured_only: Optional[bool] = False
    available_only: Optional[bool] = True
    search_query: Optional[str] = None

    @validator('max_price')
    def validate_price_range(cls, v, values):
        if v is not None and 'min_price' in values and values['min_price'] is not None:
            if v < values['min_price']:
                raise ValueError('max_price must be greater than or equal to min_price')
        return v

class FeaturedProductsResponse(BaseModel):
    featured_products: List[ProductListItem]
    total_count: int

class ProductStats(BaseModel):
    total_products: int
    products_by_category: Dict[str, int]
    products_by_condition: Dict[str, int]
    products_by_currency: Dict[str, int]
    featured_products_count: int
    available_products_count: int