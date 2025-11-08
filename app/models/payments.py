from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal
from enum import Enum

class PaymentGateway(str, Enum):
    PAYSTACK = "PAYSTACK"
    STRIPE = "STRIPE"

class PaymentStatus(str, Enum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"
    CANCELLED = "CANCELLED"

class OrderStatus(str, Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    PROCESSING = "PROCESSING"
    SHIPPED = "SHIPPED"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"
    REFUNDED = "REFUNDED"

class SupportedCurrencies(str, Enum):
    GHS = "GHS"
    USD = "USD"

# ========== CART MODELS ==========

class AddToCartRequest(BaseModel):
    productId: str = Field(..., description="Product UUID")
    quantity: int = Field(default=1, ge=1, description="Quantity to add")

class UpdateCartItemRequest(BaseModel):
    quantity: int = Field(..., ge=1, description="New quantity")

class ApplyDiscountRequest(BaseModel):
    discountCode: str = Field(..., min_length=1, description="Discount code to apply")

class CartItemResponse(BaseModel):
    id: str
    productId: str
    quantity: int
    price: Decimal
    title: str
    image: Optional[str]
    condition: Optional[str]
    location: Optional[str]
    maxQuantity: Optional[int]
    sellerId: str
    sellerName: str
    subtotal: Decimal

class CartResponse(BaseModel):
    id: str
    userId: str
    currency: SupportedCurrencies
    itemCount: int
    subtotal: Decimal
    discountAmount: Decimal
    tax: Decimal
    total: Decimal
    items: List[CartItemResponse]
    appliedDiscount: Optional[Dict[str, Any]] = None
    createdAt: datetime
    updatedAt: datetime

# ========== ORDER/PAYMENT MODELS ==========

class ShippingAddress(BaseModel):
    name: str = Field(..., min_length=1)
    phone: str = Field(..., min_length=1)
    address: str = Field(..., min_length=1)
    city: str = Field(..., min_length=1)
    country: str = Field(..., min_length=1)
    additionalInfo: Optional[str] = None

class BuyNowRequest(BaseModel):
    productId: str = Field(..., description="Product UUID")
    quantity: int = Field(default=1, ge=1, description="Quantity to purchase")
    discountCode: Optional[str] = Field(None, description="Optional discount code")
    shippingAddress: ShippingAddress
    paymentGateway: PaymentGateway = PaymentGateway.PAYSTACK
    enableCourierDelivery: bool = Field(False, description="Enable courier pickup and delivery")
    deliveryPriority: Optional[str] = Field(None, description="STANDARD, EXPRESS, or URGENT")
    deliveryNotes: Optional[str] = Field(None, description="Special delivery instructions")

class CheckoutRequest(BaseModel):
    shippingAddress: ShippingAddress
    discountCode: Optional[str] = Field(None, description="Optional discount code")
    paymentGateway: PaymentGateway = PaymentGateway.PAYSTACK
    enableCourierDelivery: bool = Field(False, description="Enable courier pickup and delivery")
    deliveryPriority: Optional[str] = Field(None, description="STANDARD, EXPRESS, or URGENT")
    deliveryNotes: Optional[str] = Field(None, description="Special delivery instructions")

class PaymentInitResponse(BaseModel):
    authorization_url: str
    access_code: str
    reference: str
    order_id: Optional[str] = None

class OrderItemResponse(BaseModel):
    id: str
    productId: str
    title: str
    image: Optional[str]
    quantity: int
    price: Decimal
    subtotal: Decimal
    sellerId: str
    sellerName: str
    condition: Optional[str]
    location: Optional[str]

class OrderResponse(BaseModel):
    id: str
    userId: str
    subtotal: Decimal
    discountAmount: Decimal
    tax: Decimal
    total: Decimal
    status: OrderStatus
    paymentStatus: PaymentStatus
    currency: SupportedCurrencies
    shippingAddress: Dict[str, Any]
    trackingNumber: Optional[str]
    paymentMethod: Optional[str]
    paymentGateway: Optional[PaymentGateway]
    createdAt: datetime
    updatedAt: datetime
    items: List[OrderItemResponse]
    appliedDiscounts: List[Dict[str, Any]] = []

class PaymentVerificationResponse(BaseModel):
    status: str
    reference: str
    amount: float
    currency: str
    paid_at: Optional[str]
    order: Optional[OrderResponse]
    message: str
