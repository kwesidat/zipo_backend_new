from pydantic import BaseModel, EmailStr
from typing import Optional
from enum import Enum

class UserType(str, Enum):
    CUSTOMER = "CUSTOMER"
    SELLER = "SELLER"
    AGENT = "AGENT"
    ADMIN = "ADMIN"
    COURIER = "COURIER"

class SignUpRequest(BaseModel):
    email: EmailStr
    password: str
    name: str
    phone_number: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    address: Optional[str] = None
    business_name: Optional[str] = None
    business_description: Optional[str] = None
    role: UserType = UserType.CUSTOMER

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class CourierProfileData(BaseModel):
    courier_id: str
    courier_code: str
    vehicle_type: Optional[str] = None
    vehicle_number: Optional[str] = None
    license_number: Optional[str] = None
    rating: float = 0.0
    total_deliveries: int = 0
    completed_deliveries: int = 0
    is_available: bool = True
    is_verified: bool = False

class UserResponse(BaseModel):
    user_id: str
    name: str
    email: str
    phone_number: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    address: Optional[str] = None
    business_name: Optional[str] = None
    business_description: Optional[str] = None
    verified: bool = False
    role: str
    user_type: Optional[str] = None
    courier_profile: Optional[CourierProfileData] = None

class AuthResponse(BaseModel):
    user: UserResponse
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class PasswordResetRequest(BaseModel):
    email: EmailStr

class PasswordResetVerify(BaseModel):
    token: str
    new_password: str

class PasswordResetOTPVerify(BaseModel):
    email: EmailStr
    token: str

class PasswordResetComplete(BaseModel):
    email: EmailStr
    token: str
    new_password: str

class RefreshTokenRequest(BaseModel):
    refresh_token: str

class AuthStatusResponse(BaseModel):
    is_authenticated: bool
    user: Optional[UserResponse] = None
    session_valid: bool
    token_expires_at: Optional[str] = None
    needs_refresh: bool = False

class LogoutResponse(BaseModel):
    message: str
    logged_out: bool