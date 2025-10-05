from pydantic import BaseModel
from typing import Optional, List
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

class SubcategoryBase(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    category_id: str
    created_at: datetime
    updated_at: datetime

class SubcategoryResponse(SubcategoryBase):
    product_count: Optional[int] = 0

class CategoryBase(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime

class CategoryResponse(CategoryBase):
    subcategories: List[SubcategoryResponse] = []
    product_count: Optional[int] = 0

class CategoryWithSubcategories(CategoryBase):
    subcategories: List[SubcategoryBase] = []

class ProductSummary(BaseModel):
    id: str
    name: str
    price: Decimal
    currency: SupportedCurrencies
    condition: Optional[ProductCondition] = None
    photos: List[str] = []
    featured: bool = False

class CategoryDetailResponse(CategoryBase):
    subcategories: List[SubcategoryResponse] = []
    recent_products: List[ProductSummary] = []
    total_products: int = 0

class CategoriesListResponse(BaseModel):
    categories: List[CategoryResponse]
    total_count: int