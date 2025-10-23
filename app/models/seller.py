from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal
from enum import Enum


class EventType(str, Enum):
    PRODUCT_LOW_STOCK = "PRODUCT_LOW_STOCK"
    PAYMENT_RECEIVED = "PAYMENT_RECEIVED"
    NEW_CUSTOMER = "NEW_CUSTOMER"
    SUBSCRIPTION_EXPIRING = "SUBSCRIPTION_EXPIRING"
    PRODUCT_REVIEW = "PRODUCT_REVIEW"
    DISCOUNT_EXPIRING = "DISCOUNT_EXPIRING"
    INVENTORY_UPDATE = "INVENTORY_UPDATE"
    CUSTOMER_INQUIRY = "CUSTOMER_INQUIRY"


class EventPriority(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    URGENT = "URGENT"


class EventStatus(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    DISMISSED = "DISMISSED"


class InvoiceStatus(str, Enum):
    DRAFT = "DRAFT"
    SENT = "SENT"
    PAID = "PAID"
    CANCELLED = "CANCELLED"


class SupportedCurrencies(str, Enum):
    USD = "USD"
    GHS = "GHS"


# ========== Seller Analytics Models ==========


class SellerAnalyticsResponse(BaseModel):
    id: str
    sellerId: str
    totalSales: Decimal
    totalOrders: int
    totalCustomers: int
    averageOrderValue: Decimal
    topSellingProductId: Optional[str] = None
    lastSaleDate: Optional[datetime] = None
    monthlyRevenue: Optional[Dict[str, Any]] = None
    customerRetentionRate: float
    updatedAt: datetime

    class Config:
        json_encoders = {Decimal: lambda v: float(v)}


class TopSellingProduct(BaseModel):
    productId: str
    productName: str
    totalSold: int
    totalRevenue: Decimal
    photos: Optional[List[str]] = None

    class Config:
        json_encoders = {Decimal: lambda v: float(v)}


# ========== Seller Event Models ==========


class SellerEventResponse(BaseModel):
    id: str
    sellerId: str
    type: EventType
    title: str
    description: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    priority: EventPriority
    status: EventStatus
    dueDate: Optional[datetime] = None
    createdAt: datetime
    updatedAt: datetime


class EventUpdateRequest(BaseModel):
    status: Optional[EventStatus] = None
    priority: Optional[EventPriority] = None
    description: Optional[str] = None
    dueDate: Optional[datetime] = None


class SellerEventsListResponse(BaseModel):
    events: List[SellerEventResponse]
    total_count: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_previous: bool


# ========== Invoice Models ==========


class InvoiceResponse(BaseModel):
    id: str
    invoiceNumber: str
    purchaseId: str
    sellerId: str
    customerEmail: str
    customerName: Optional[str] = None
    subtotal: Decimal
    tax: Decimal
    discount: Decimal
    total: Decimal
    currency: SupportedCurrencies
    status: InvoiceStatus
    sentAt: Optional[datetime] = None
    paidAt: Optional[datetime] = None
    createdAt: datetime
    updatedAt: datetime

    class Config:
        json_encoders = {Decimal: lambda v: float(v)}


class InvoiceWithPurchaseDetails(BaseModel):
    id: str
    invoiceNumber: str
    purchaseId: str
    sellerId: str
    customerEmail: str
    customerName: Optional[str] = None
    subtotal: Decimal
    tax: Decimal
    discount: Decimal
    total: Decimal
    currency: SupportedCurrencies
    status: InvoiceStatus
    sentAt: Optional[datetime] = None
    paidAt: Optional[datetime] = None
    createdAt: datetime
    updatedAt: datetime
    # Purchase details
    productName: Optional[str] = None
    quantity: Optional[int] = None
    unitPrice: Optional[Decimal] = None
    shippingAddress: Optional[Dict[str, Any]] = None

    class Config:
        json_encoders = {Decimal: lambda v: float(v)}


class InvoicesListResponse(BaseModel):
    invoices: List[InvoiceWithPurchaseDetails]
    total_count: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_previous: bool


# ========== Seller Dashboard Models ==========


class RevenueData(BaseModel):
    period: str  # e.g., "2025-01", "Week 1"
    revenue: Decimal
    orders: int

    class Config:
        json_encoders = {Decimal: lambda v: float(v)}


class ProductPerformance(BaseModel):
    productId: str
    productName: str
    totalSold: int
    totalRevenue: Decimal
    averagePrice: Decimal
    stockRemaining: int
    photos: Optional[List[str]] = None

    class Config:
        json_encoders = {Decimal: lambda v: float(v)}


class RecentOrder(BaseModel):
    orderId: str
    orderDate: datetime
    customerName: Optional[str] = None
    totalAmount: Decimal
    itemCount: int
    status: str
    paymentStatus: str

    class Config:
        json_encoders = {Decimal: lambda v: float(v)}


class InventoryAlert(BaseModel):
    productId: str
    productName: str
    currentStock: int
    status: str  # "OUT_OF_STOCK", "LOW_STOCK"
    photos: Optional[List[str]] = None


# ========== Seller Customers Models ==========


class CustomerOrder(BaseModel):
    orderId: str
    orderDate: datetime
    totalAmount: Decimal
    itemCount: int
    status: str
    paymentStatus: str

    class Config:
        json_encoders = {Decimal: lambda v: float(v)}


class SellerOrderItem(BaseModel):
    id: str
    productId: str
    title: str
    image: Optional[str] = None
    quantity: int
    price: Decimal
    subtotal: Decimal
    condition: Optional[str] = None
    location: Optional[str] = None

    class Config:
        json_encoders = {Decimal: lambda v: float(v)}


class SellerOrder(BaseModel):
    id: str
    userId: str
    customerName: Optional[str] = None
    customerEmail: Optional[str] = None
    customerPhone: Optional[str] = None
    subtotal: Decimal
    discountAmount: Decimal
    tax: Decimal
    total: Decimal
    sellerRevenue: Decimal  # Only the seller's portion of the total
    status: str
    paymentStatus: str
    currency: str
    shippingAddress: Optional[Dict[str, Any]] = None
    trackingNumber: Optional[str] = None
    paymentMethod: Optional[str] = None
    paymentGateway: Optional[str] = None
    createdAt: datetime
    updatedAt: datetime
    items: List[SellerOrderItem]
    itemCount: int

    class Config:
        json_encoders = {Decimal: lambda v: float(v)}


class SellerOrdersListResponse(BaseModel):
    orders: List[SellerOrder]
    total: int
    page: int
    limit: int
    totalPages: int


class SellerCustomer(BaseModel):
    userId: Optional[str] = None
    customerName: str
    customerEmail: str
    customerPhone: Optional[str] = None
    totalOrders: int
    totalSpent: Decimal
    firstOrderDate: datetime
    lastOrderDate: datetime
    averageOrderValue: Decimal
    shippingAddress: Optional[Dict[str, Any]] = None
    # Recent orders from this customer
    recentOrders: Optional[List[CustomerOrder]] = None

    class Config:
        json_encoders = {
            Decimal: lambda v: float(v),
            datetime: lambda v: v.isoformat(),
        }


class SellerCustomersListResponse(BaseModel):
    customers: List[SellerCustomer]
    total_count: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_previous: bool


class CustomerDetailResponse(BaseModel):
    userId: Optional[str] = None
    customerName: str
    customerEmail: str
    customerPhone: Optional[str] = None
    totalOrders: int
    totalSpent: Decimal
    firstOrderDate: datetime
    lastOrderDate: datetime
    averageOrderValue: Decimal
    shippingAddress: Optional[Dict[str, Any]] = None
    # All orders from this customer
    orders: List[CustomerOrder]
    # Customer stats
    productsOrdered: int
    favoriteProducts: Optional[List[str]] = None

    class Config:
        json_encoders = {
            Decimal: lambda v: float(v),
            datetime: lambda v: v.isoformat(),
        }


class SellerDashboardResponse(BaseModel):
    # Summary Statistics
    totalSales: Decimal
    totalOrders: int
    totalCustomers: int
    averageOrderValue: Decimal
    totalProducts: int
    activeProducts: int
    lowStockProducts: int
    outOfStockProducts: int

    # Revenue & Orders
    todayRevenue: Decimal
    weekRevenue: Decimal
    monthRevenue: Decimal
    revenueGrowth: float  # Percentage growth compared to previous period
    ordersGrowth: float

    # Charts Data
    revenueByMonth: List[RevenueData]  # Last 12 months
    revenueByWeek: List[RevenueData]  # Last 8 weeks

    # Top Selling Products
    topSellingProducts: List[ProductPerformance]

    # Recent Activity
    recentOrders: List[RecentOrder]
    pendingEvents: List[SellerEventResponse]

    # Inventory Alerts
    inventoryAlerts: List[InventoryAlert]

    # Analytics
    lastSaleDate: Optional[datetime] = None
    customerRetentionRate: float
    totalInvoices: int
    paidInvoices: int
    pendingInvoices: int

    class Config:
        json_encoders = {
            Decimal: lambda v: float(v),
            datetime: lambda v: v.isoformat(),
        }
