from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from decimal import Decimal
from app.models.products import SupportedCurrencies

class CartItemBase(BaseModel):
    productId: str = Field(..., description="Product UUID")
    quantity: int = Field(default=1, ge=1, description="Quantity to add")

class CartItemAdd(CartItemBase):
    pass

class CartItemUpdate(BaseModel):
    quantity: int = Field(..., ge=1, description="New quantity")

class CartItemResponse(BaseModel):
    id: str
    cartId: str
    productId: str
    quantity: int
    price: Decimal
    condition: Optional[str] = None
    image: Optional[str] = None
    location: Optional[str] = None
    maxQuantity: Optional[int] = None
    sellerId: Optional[str] = None
    sellerName: Optional[str] = None
    title: Optional[str] = None
    createdAt: datetime
    updatedAt: datetime

class CartResponse(BaseModel):
    id: str
    userId: str
    currency: SupportedCurrencies
    discountAmount: Decimal
    itemCount: int
    subtotal: Decimal
    tax: Decimal
    total: Decimal
    items: List[CartItemResponse]
    createdAt: datetime
    updatedAt: datetime

class CartSummary(BaseModel):
    itemCount: int
    subtotal: Decimal
    tax: Decimal
    discountAmount: Decimal
    total: Decimal
    currency: SupportedCurrencies