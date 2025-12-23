from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.models.courier import CourierSignUpRequest
from app.database import supabase
from app.utils.auth_utils import AuthUtils
from datetime import datetime
from pydantic import BaseModel
from typing import Optional
import random
import string
import logging

router = APIRouter()
security = HTTPBearer()
logger = logging.getLogger(__name__)


def generate_courier_code() -> str:
    """Generate a unique courier code (e.g., COU-ABC123)"""
    random_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"COU-{random_part}"


@router.post("/signup")
async def courier_signup(user_data: CourierSignUpRequest):
    """
    Register a new courier account.
    Creates both a user account and a courier profile.

    Note: After signup, use the regular /api/auth/login endpoint to login.
    All authentication operations (login, password reset, token refresh, etc.)
    use the standard auth endpoints.
    """
    try:
        # Validate password strength
        is_strong, message = AuthUtils.is_strong_password(user_data.password)
        if not is_strong:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=message
            )

        # First check if email already exists in database before creating auth user
        try:
            existing_user = supabase.table("users").select("email").eq("email", user_data.email).execute()

            if existing_user.data and len(existing_user.data) > 0:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Email address is already registered. Please try logging in or use a different email."
                )
        except HTTPException:
            raise
        except Exception as db_error:
            print(f"Database check error: {db_error}")

        # Create user with metadata in Supabase Auth
        auth_response = supabase.auth.sign_up({
            "email": user_data.email,
            "password": user_data.password,
            "options": {
                "data": {
                    "name": user_data.name,
                    "phone_number": user_data.phone_number,
                    "country": user_data.country,
                    "city": user_data.city,
                    "address": user_data.address,
                    "user_type": "COURIER",
                    "verified": False
                }
            }
        })

        if auth_response.user is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to create courier account"
            )

        user = auth_response.user

        # Insert user data into users table
        try:
            user_db_data = {
                "user_id": user.id,
                "name": user_data.name,
                "email": user_data.email,
                "phone_number": user_data.phone_number,
                "country": user_data.country,
                "city": user_data.city,
                "address": user_data.address,
                "role": "COURIER",
                "user_type": "COURIER",
                "verified": False
            }

            # Remove None values
            user_db_data = {k: v for k, v in user_db_data.items() if v is not None}

            # Insert into users table
            db_response = supabase.table("users").insert(user_db_data).execute()

            if db_response.data:
                print(f"New courier user created in database: {user.id}")
            else:
                print(f"Database insertion warning: {db_response}")

        except Exception as db_error:
            print(f"User database insertion error: {db_error}")
            # Continue even if database fails

        # Create courier profile
        try:
            courier_code = generate_courier_code()

            # Check if courier code is unique
            while True:
                existing_code = supabase.table("Courier").select("courier_code").eq("courier_code", courier_code).execute()
                if not existing_code.data or len(existing_code.data) == 0:
                    break
                courier_code = generate_courier_code()

            current_time = datetime.utcnow().isoformat()

            courier_profile_data = {
                "user_id": user.id,
                "courier_code": courier_code,
                "vehicle_type": user_data.vehicle_type.value if user_data.vehicle_type else None,
                "vehicle_number": user_data.vehicle_number,
                "license_number": user_data.license_number,
                "is_available": True,
                "is_verified": False,
                "rating": 0.0,
                "total_deliveries": 0,
                "completed_deliveries": 0,
                "total_earnings": 0.0,
                "available_balance": 0.0,
                "created_at": current_time,
                "updated_at": current_time
            }

            # Remove None values
            courier_profile_data = {k: v for k, v in courier_profile_data.items() if v is not None}

            courier_response = supabase.table("Courier").insert(courier_profile_data).execute()

            if courier_response.data:
                print(f"Courier profile created for user: {user.id}")
                courier_data = courier_response.data[0]
            else:
                print(f"Courier profile creation warning: {courier_response}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to create courier profile"
                )

        except HTTPException:
            raise
        except Exception as courier_error:
            print(f"Courier profile creation error: {courier_error}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create courier profile"
            )

        return {
            "message": "Courier account created successfully! Please verify your email and then login using /api/auth/login",
            "user": {
                "user_id": user.id,
                "name": user_data.name,
                "email": user_data.email,
                "phone_number": user_data.phone_number,
                "user_type": "COURIER",
                "verified": False
            },
            "courier_profile": {
                "courier_id": courier_data["id"],
                "courier_code": courier_code,
                "vehicle_type": user_data.vehicle_type.value if user_data.vehicle_type else None,
                "vehicle_number": user_data.vehicle_number,
                "license_number": user_data.license_number,
                "is_verified": False,
                "is_available": True
            },
            "next_steps": [
                "1. Check your email and verify your account",
                "2. Use POST /api/auth/login to login with your credentials",
                "3. All other auth operations (password reset, token refresh, etc.) use /api/auth/* endpoints"
            ]
        }

    except HTTPException:
        raise
    except Exception as e:
        if "already been registered" in str(e):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User with this email already exists"
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


# ========== LOCATION UPDATE MODELS ==========

class CourierLocationUpdate(BaseModel):
    latitude: float
    longitude: float


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get current authenticated user"""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required"
        )

    try:
        user_data = AuthUtils.verify_supabase_token(credentials.credentials)
        if not user_data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            )
        return user_data
    except Exception as e:
        logger.error(f"Authentication failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication failed"
        )


# ========== UPDATE COURIER LOCATION ==========

@router.post("/update-location")
async def update_courier_location(
    location: CourierLocationUpdate,
    current_user=Depends(get_current_user)
):
    """
    Update courier's live location.
    This endpoint should be called every 30 seconds by the courier's app
    to broadcast their current location.
    """
    try:
        user_id = current_user["user_id"]
        user_type = current_user.get("user_type")

        # Verify user is a courier
        if user_type != "COURIER":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only couriers can update location",
            )

        logger.info(f"Updating location for courier {user_id}: lat={location.latitude}, lon={location.longitude}")

        # Update user's latitude and longitude in users table
        update_data = {
            "latitude": location.latitude,
            "longitude": location.longitude
        }

        user_update = supabase.table("users").update(update_data).eq("user_id", user_id).execute()

        if not user_update.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update location"
            )

        logger.info(f"✅ Location updated for courier {user_id}")

        return {
            "success": True,
            "message": "Location updated successfully",
            "latitude": location.latitude,
            "longitude": location.longitude
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating courier location: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update location"
        )
