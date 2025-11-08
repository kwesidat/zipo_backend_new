from pydantic import BaseModel, EmailStr
from typing import Optional
from enum import Enum

class VehicleType(str, Enum):
    BICYCLE = "BICYCLE"
    MOTORCYCLE = "MOTORCYCLE"
    CAR = "CAR"
    VAN = "VAN"
    TRUCK = "TRUCK"

class CourierSignUpRequest(BaseModel):
    email: EmailStr
    password: str
    name: str
    phone_number: str
    country: Optional[str] = None
    city: Optional[str] = None
    address: Optional[str] = None
    # Courier-specific fields
    vehicle_type: Optional[VehicleType] = None
    vehicle_number: Optional[str] = None
    license_number: Optional[str] = None

class CourierLoginRequest(BaseModel):
    email: EmailStr
    password: str

class CourierProfileResponse(BaseModel):
    courier_id: str
    user_id: str
    courier_code: str
    vehicle_type: Optional[str] = None
    vehicle_number: Optional[str] = None
    license_number: Optional[str] = None
    service_areas: list[str] = []
    rating: float = 0.0
    total_deliveries: int = 0
    completed_deliveries: int = 0
    total_earnings: float = 0.0
    available_balance: float = 0.0
    bank_name: Optional[str] = None
    account_number: Optional[str] = None
    account_name: Optional[str] = None
    is_available: bool = True
    is_verified: bool = False

class CourierResponse(BaseModel):
    user_id: str
    name: str
    email: str
    phone_number: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    address: Optional[str] = None
    verified: bool = False
    user_type: str = "COURIER"
    courier_profile: Optional[CourierProfileResponse] = None

class CourierAuthResponse(BaseModel):
    user: CourierResponse
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class CourierTokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class CourierPasswordResetRequest(BaseModel):
    email: EmailStr

class CourierPasswordResetOTPVerify(BaseModel):
    email: EmailStr
    token: str

class CourierPasswordResetComplete(BaseModel):
    email: EmailStr
    token: str
    new_password: str

class CourierRefreshTokenRequest(BaseModel):
    refresh_token: str

class CourierAuthStatusResponse(BaseModel):
    is_authenticated: bool
    user: Optional[CourierResponse] = None
    session_valid: bool
    needs_refresh: bool = False

class CourierLogoutResponse(BaseModel):
    message: str
    logged_out: bool
