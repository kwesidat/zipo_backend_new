from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime, timezone
from enum import Enum

class DiscountStatus(str, Enum):
    ENABLED = "ENABLED"
    DISABLED = "DISABLED"
    EXPIRED = "EXPIRED"

class DiscountCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=50, description="Unique discount code")
    percentage: float = Field(..., gt=0, le=100, description="Discount percentage (1-100)")
    description: Optional[str] = Field(None, max_length=500)
    limit: Optional[int] = Field(None, gt=0, description="Usage limit")
    showOnPlatform: bool = Field(True, description="Show discount publicly on platform")
    expiresAt: Optional[datetime] = Field(None, description="Expiration date")
    productIds: List[str] = Field(..., min_items=1, description="List of product IDs to apply discount to")

    @validator('code')
    def code_must_be_uppercase_alphanumeric(cls, v):
        v = v.strip().upper()
        if not v.replace('_', '').replace('-', '').isalnum():
            raise ValueError('Code must contain only letters, numbers, hyphens, and underscores')
        return v

    @validator('expiresAt')
    def expiry_must_be_future(cls, v):
        if v:
            now = datetime.now(timezone.utc)
            # Make v timezone-aware if it's naive
            compare_time = v if v.tzinfo else v.replace(tzinfo=timezone.utc)
            if compare_time <= now:
                raise ValueError('Expiration date must be in the future')
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "code": "SUMMER2025",
                "percentage": 15.5,
                "description": "Summer Sale Discount",
                "limit": 100,
                "showOnPlatform": True,
                "expiresAt": "2025-12-31T23:59:59Z",
                "productIds": ["uuid1", "uuid2", "uuid3"]
            }
        }

class DiscountUpdate(BaseModel):
    description: Optional[str] = Field(None, max_length=500)
    percentage: Optional[float] = Field(None, gt=0, le=100)
    limit: Optional[int] = Field(None, gt=0)
    showOnPlatform: Optional[bool] = None
    expiresAt: Optional[datetime] = None

    @validator('expiresAt')
    def expiry_must_be_future(cls, v):
        if v:
            now = datetime.now(timezone.utc)
            # Make v timezone-aware if it's naive
            compare_time = v if v.tzinfo else v.replace(tzinfo=timezone.utc)
            if compare_time <= now:
                raise ValueError('Expiration date must be in the future')
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "description": "Updated description",
                "percentage": 20.0,
                "limit": 150,
                "showOnPlatform": False
            }
        }

class DiscountStatusUpdate(BaseModel):
    status: DiscountStatus

class DiscountProductsRequest(BaseModel):
    productIds: List[str] = Field(..., min_items=1)

class DiscountProductItem(BaseModel):
    id: str
    name: str
    price: float
    currency: str
    photos: List[str]
    appliedAt: datetime

class DiscountListItem(BaseModel):
    id: str
    code: str
    percentage: float
    description: Optional[str]
    status: DiscountStatus
    limit: Optional[int]
    usedCount: int = 0
    showOnPlatform: bool
    expiresAt: Optional[datetime]
    createdAt: datetime
    appliedProductsCount: int

class DiscountResponse(BaseModel):
    id: str
    code: str
    percentage: float
    description: Optional[str]
    status: DiscountStatus
    limit: Optional[int]
    usedCount: int = 0
    showOnPlatform: bool
    expiresAt: Optional[datetime]
    createdAt: datetime
    updatedAt: datetime
    products: List[DiscountProductItem] = []

class DiscountsListResponse(BaseModel):
    discounts: List[DiscountListItem]
    total_count: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_previous: bool

class DiscountCreateResponse(BaseModel):
    id: str
    code: str
    percentage: float
    description: Optional[str]
    expiresAt: Optional[datetime]
    limit: Optional[int]
    showOnPlatform: bool
    status: DiscountStatus
    userId: str
    createdAt: datetime
    updatedAt: datetime
    appliedProducts: int

class DiscountProductsResponse(BaseModel):
    message: str
    addedCount: int
    totalProducts: int
