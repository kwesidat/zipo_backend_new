from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal
from enum import Enum


class DeliveryStatus(str, Enum):
    PENDING = "PENDING"
    ASSIGNED = "ASSIGNED"
    ACCEPTED = "ACCEPTED"
    PICKED_UP = "PICKED_UP"
    IN_TRANSIT = "IN_TRANSIT"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


class DeliveryPriority(str, Enum):
    STANDARD = "STANDARD"
    EXPRESS = "EXPRESS"
    URGENT = "URGENT"


class UserType(str, Enum):
    CUSTOMER = "CUSTOMER"
    SELLER = "SELLER"
    AGENT = "AGENT"
    ADMIN = "ADMIN"
    COURIER = "COURIER"


class DeliveryAddress(BaseModel):
    """Address details for pickup or delivery"""
    address: str = Field(..., min_length=1, description="Full address")
    city: str = Field(..., min_length=1, description="City")
    country: str = Field(..., min_length=1, description="Country")
    latitude: Optional[float] = Field(None, description="GPS latitude")
    longitude: Optional[float] = Field(None, description="GPS longitude")
    additional_info: Optional[str] = Field(None, description="Landmark or additional info")


class ScheduleDeliveryRequest(BaseModel):
    """
    Case 2: Customer schedules a standalone delivery (ZipoExpress)
    Customer provides pickup and delivery addresses
    """
    pickup_address: DeliveryAddress
    delivery_address: DeliveryAddress
    pickup_contact_name: str = Field(..., min_length=1)
    pickup_contact_phone: str = Field(..., min_length=1)
    delivery_contact_name: str = Field(..., min_length=1)
    delivery_contact_phone: str = Field(..., min_length=1)
    scheduled_date: Optional[datetime] = Field(None, description="When to schedule the delivery")
    priority: DeliveryPriority = DeliveryPriority.STANDARD
    notes: Optional[str] = Field(None, description="Special instructions")
    item_description: Optional[str] = Field(None, description="What is being delivered")


class OrderDeliveryRequest(BaseModel):
    """
    Case 1: Customer wants courier delivery for their order
    Used during checkout to enable courier delivery option
    """
    enable_courier_delivery: bool = Field(True, description="Enable courier pickup and delivery")
    delivery_priority: DeliveryPriority = DeliveryPriority.STANDARD
    scheduled_date: Optional[datetime] = Field(None, description="Preferred delivery date")
    delivery_notes: Optional[str] = Field(None, description="Special delivery instructions")


class DeliveryResponse(BaseModel):
    """Response model for delivery details"""
    id: str
    order_id: str
    courier_id: Optional[str]
    pickup_address: Dict[str, Any]
    delivery_address: Dict[str, Any]
    pickup_contact_name: Optional[str]
    pickup_contact_phone: Optional[str]
    delivery_contact_name: Optional[str]
    delivery_contact_phone: Optional[str]
    scheduled_by_user: str
    scheduled_by_type: UserType
    delivery_fee: Decimal
    courier_fee: Optional[Decimal]
    platform_fee: Optional[Decimal]
    distance_km: Optional[float]
    status: DeliveryStatus
    priority: DeliveryPriority
    scheduled_date: Optional[datetime]
    estimated_pickup_time: Optional[datetime]
    estimated_delivery_time: Optional[datetime]
    actual_pickup_time: Optional[datetime]
    actual_delivery_time: Optional[datetime]
    notes: Optional[str]
    courier_notes: Optional[str]
    cancellation_reason: Optional[str]
    proof_of_delivery: List[str] = []
    customer_signature: Optional[str]
    rating: Optional[float]
    review: Optional[str]
    created_at: datetime
    updated_at: datetime


class AvailableDeliveryResponse(BaseModel):
    """Simplified delivery info for couriers browsing available deliveries"""
    id: str
    order_id: str
    pickup_address: Dict[str, Any]
    delivery_address: Dict[str, Any]
    pickup_contact_name: Optional[str]
    pickup_contact_phone: Optional[str]
    delivery_contact_name: Optional[str]
    delivery_contact_phone: Optional[str]
    delivery_fee: Decimal
    courier_fee: Optional[Decimal]
    distance_km: Optional[float]
    priority: DeliveryPriority
    scheduled_date: Optional[datetime]
    estimated_pickup_time: Optional[datetime]
    estimated_delivery_time: Optional[datetime]
    notes: Optional[str]
    created_at: datetime


class AcceptDeliveryRequest(BaseModel):
    """Request to accept a delivery as a courier"""
    delivery_id: str = Field(..., description="Delivery ID to accept")
    estimated_pickup_time: Optional[datetime] = Field(None, description="When courier expects to pick up")
    estimated_delivery_time: Optional[datetime] = Field(None, description="When courier expects to deliver")


class UpdateDeliveryStatusRequest(BaseModel):
    """Update delivery status by courier"""
    status: DeliveryStatus
    notes: Optional[str] = Field(None, description="Status update notes")
    location: Optional[Dict[str, Any]] = Field(None, description="Current location")
    proof_of_delivery_urls: Optional[List[str]] = Field(None, description="Proof of delivery images")
    customer_signature: Optional[str] = Field(None, description="Customer signature URL")


class DeliveryListResponse(BaseModel):
    """Paginated list of deliveries"""
    deliveries: List[DeliveryResponse]
    total_count: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_previous: bool


class AvailableDeliveryListResponse(BaseModel):
    """Paginated list of available deliveries for couriers"""
    deliveries: List[AvailableDeliveryResponse]
    total_count: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_previous: bool


class AddressRequest(BaseModel):
    """Address request model for payment initialization"""
    address: str
    city: str
    country: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    additional_info: Optional[str] = ""


class CalculateDeliveryFeeRequest(BaseModel):
    """Request model for fee calculation"""
    priority: DeliveryPriority = DeliveryPriority.STANDARD
    distance_km: Optional[float] = None
