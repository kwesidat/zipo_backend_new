from fastapi import APIRouter, HTTPException, Depends, status, Request
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.models.auth import (
    SignUpRequest, LoginRequest, AuthResponse, UserResponse, TokenResponse,
    PasswordResetRequest, PasswordResetVerify, RefreshTokenRequest,
    AuthStatusResponse, LogoutResponse, PasswordResetOTPVerify, PasswordResetComplete
)
from app.database import supabase
from app.utils.auth_utils import AuthUtils
from typing import Optional
import uuid
from datetime import datetime

router = APIRouter()
auth = supabase.auth
security = HTTPBearer()



@router.get("/")
async def get_all_user():
    response = supabase.table("users").select("*").execute()
    users = response.data
    return {"users": users, "count": len(users)}

@router.post("/signup", response_model=AuthResponse)
async def signup(user_data: SignUpRequest):
    try:
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
            # Continue if database check fails

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
                    "business_name": user_data.business_name,
                    "business_description": user_data.business_description,
                    "role": user_data.role.value,
                    "verified": False
                }
            }
        })

        if auth_response.user is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to create user account"
            )

        user = auth_response.user

        # Insert user data into users table using Supabase
        try:
            # Create new user record
            user_db_data = {}
            fields = {
                "user_id": user.id,
                "name": user_data.name,
                "email": user_data.email,
                "phone_number": user_data.phone_number,
                "country": user_data.country,
                "city": user_data.city,
                "address": user_data.address,
                "business_name": user_data.business_name,
                "business_description": user_data.business_description,
                "role": user_data.role.value,
                "verified": False
            }

            # Only include non-None values
            for key, value in fields.items():
                if value is not None:
                    user_db_data[key] = value

            # Insert into users table
            db_response = supabase.table("users").insert(user_db_data).execute()

            if db_response.data:
                print(f"New user created in database: {user.id}")
            else:
                print(f"Database insertion warning: {db_response}")

        except Exception as db_error:
            print(f"Database insertion error: {db_error}")
            # Continue with auth response even if database fails

        user_response = UserResponse(
            user_id=user.id,
            name=user_data.name,
            email=user_data.email,
            phone_number=user_data.phone_number,
            country=user_data.country,
            city=user_data.city,
            address=user_data.address,
            business_name=user_data.business_name,
            business_description=user_data.business_description,
            verified=False,
            role=user_data.role.value
        )

        return AuthResponse(
            user=user_response,
            access_token=auth_response.session.access_token if auth_response.session else "",
            refresh_token=auth_response.session.refresh_token if auth_response.session else ""
        )

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

@router.post("/login", response_model=AuthResponse)
async def login(credentials: LoginRequest):
    try:
        auth_response = supabase.auth.sign_in_with_password({
            "email": credentials.email,
            "password": credentials.password
        })

        if auth_response.user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )

        user = auth_response.user

        # Fetch user data from users table
        try:
            db_response = supabase.table("users").select("*").eq("user_id", user.id).execute()

            if db_response.data and len(db_response.data) > 0:
                user_db = db_response.data[0]
                user_response = UserResponse(
                    user_id=user_db["user_id"],
                    name=user_db["name"],
                    email=user_db["email"],
                    phone_number=user_db.get("phone_number"),
                    country=user_db.get("country"),
                    city=user_db.get("city"),
                    address=user_db.get("address"),
                    business_name=user_db.get("business_name"),
                    business_description=user_db.get("business_description"),
                    verified=user_db.get("verified", False),
                    role=user_db.get("role", "CUSTOMER")
                )
            else:
                # Fallback to metadata if no database record
                user_metadata = user.user_metadata or {}
                user_response = UserResponse(
                    user_id=user.id,
                    name=user_metadata.get("name", ""),
                    email=user.email or "",
                    phone_number=user_metadata.get("phone_number"),
                    country=user_metadata.get("country"),
                    city=user_metadata.get("city"),
                    address=user_metadata.get("address"),
                    business_name=user_metadata.get("business_name"),
                    business_description=user_metadata.get("business_description"),
                    verified=user_metadata.get("verified", False),
                    role=user_metadata.get("role", "CUSTOMER")
                )

        except Exception as db_error:
            print(f"Database fetch error: {db_error}")
            # Fallback to metadata
            user_metadata = user.user_metadata or {}
            user_response = UserResponse(
                user_id=user.id,
                name=user_metadata.get("name", ""),
                email=user.email or "",
                phone_number=user_metadata.get("phone_number"),
                country=user_metadata.get("country"),
                city=user_metadata.get("city"),
                address=user_metadata.get("address"),
                business_name=user_metadata.get("business_name"),
                business_description=user_metadata.get("business_description"),
                verified=user_metadata.get("verified", False),
                role=user_metadata.get("role", "CUSTOMER")
            )

        return AuthResponse(
            user=user_response,
            access_token=auth_response.session.access_token if auth_response.session else "",
            refresh_token=auth_response.session.refresh_token if auth_response.session else ""
        )

    except HTTPException:
        raise
    except Exception as e:
        if "Invalid login credentials" in str(e):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )

# Mobile-specific endpoints

@router.post("/mobile/login", response_model=dict)
async def mobile_login(credentials: LoginRequest, request: Request):
    """Enhanced login endpoint for mobile apps with device tracking"""
    try:
        # Get device info from headers
        user_agent = request.headers.get('user-agent', '')
        device_info = {
            "user_agent": user_agent,
            "platform": "mobile",
            "timestamp": datetime.utcnow().isoformat()
        }

        # Standard Supabase login
        auth_response = supabase.auth.sign_in_with_password({
            "email": credentials.email,
            "password": credentials.password
        })

        if auth_response.user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )

        user = auth_response.user

        # Fetch user data from users table
        try:
            db_response = supabase.table("users").select("*").eq("user_id", user.id).execute()

            if db_response.data and len(db_response.data) > 0:
                user_db = db_response.data[0]
                user_response = UserResponse(
                    user_id=user_db["user_id"],
                    name=user_db["name"],
                    email=user_db["email"],
                    phone_number=user_db.get("phone_number"),
                    country=user_db.get("country"),
                    city=user_db.get("city"),
                    address=user_db.get("address"),
                    business_name=user_db.get("business_name"),
                    business_description=user_db.get("business_description"),
                    verified=user_db.get("verified", False),
                    role=user_db.get("role", "CUSTOMER")
                )
            else:
                # Fallback to metadata if no database record
                user_metadata = user.user_metadata or {}
                user_response = UserResponse(
                    user_id=user.id,
                    name=user_metadata.get("name", ""),
                    email=user.email or "",
                    phone_number=user_metadata.get("phone_number"),
                    country=user_metadata.get("country"),
                    city=user_metadata.get("city"),
                    address=user_metadata.get("address"),
                    business_name=user_metadata.get("business_name"),
                    business_description=user_metadata.get("business_description"),
                    verified=user_metadata.get("verified", False),
                    role=user_metadata.get("role", "CUSTOMER")
                )

        except Exception as db_error:
            print(f"Mobile database fetch error: {db_error}")
            # Fallback to metadata
            user_metadata = user.user_metadata or {}
            user_response = UserResponse(
                user_id=user.id,
                name=user_metadata.get("name", ""),
                email=user.email or "",
                phone_number=user_metadata.get("phone_number"),
                country=user_metadata.get("country"),
                city=user_metadata.get("city"),
                address=user_metadata.get("address"),
                business_name=user_metadata.get("business_name"),
                business_description=user_metadata.get("business_description"),
                verified=user_metadata.get("verified", False),
                role=user_metadata.get("role", "CUSTOMER")
            )

        # Create mobile session
        mobile_session = AuthUtils.create_mobile_session(
            user_id=user.id,
            device_info=user_agent
        )

        return {
            "user": user_response.dict(),
            "session": mobile_session,
            "supabase_tokens": {
                "access_token": auth_response.session.access_token if auth_response.session else "",
                "refresh_token": auth_response.session.refresh_token if auth_response.session else ""
            },
            "device_info": device_info
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )

@router.post("/mobile/signup", response_model=dict)
async def mobile_signup(user_data: SignUpRequest, request: Request):
    """Enhanced signup endpoint for mobile apps"""
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
            print(f"Mobile database check error: {db_error}")
            # Continue if database check fails

        # Create user with Supabase
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
                    "business_name": user_data.business_name,
                    "business_description": user_data.business_description,
                    "role": user_data.role.value,
                    "verified": False
                }
            }
        })

        if auth_response.user is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to create user account"
            )

        user = auth_response.user

        # Insert user data into users table using Supabase
        try:
            # Create new user record
            user_db_data = {}
            fields = {
                "user_id": user.id,
                "name": user_data.name,
                "email": user_data.email,
                "phone_number": user_data.phone_number,
                "country": user_data.country,
                "city": user_data.city,
                "address": user_data.address,
                "business_name": user_data.business_name,
                "business_description": user_data.business_description,
                "role": user_data.role.value,
                "verified": False
            }

            # Only include non-None values
            for key, value in fields.items():
                if value is not None:
                    user_db_data[key] = value

            # Insert into users table
            db_response = supabase.table("users").insert(user_db_data).execute()

            if db_response.data:
                print(f"New mobile user created in database: {user.id}")
            else:
                print(f"Mobile database insertion warning: {db_response}")

        except Exception as db_error:
            print(f"Mobile database insertion error: {db_error}")
            # Continue with auth response even if database fails

        # Create mobile session
        mobile_session = AuthUtils.create_mobile_session(
            user_id=user.id,
            device_info=request.headers.get('user-agent', '')
        )

        user_response = UserResponse(
            user_id=user.id,
            name=user_data.name,
            email=user_data.email,
            phone_number=user_data.phone_number,
            country=user_data.country,
            city=user_data.city,
            address=user_data.address,
            business_name=user_data.business_name,
            business_description=user_data.business_description,
            verified=False,
            role=user_data.role.value
        )

        return {
            "user": user_response.dict(),
            "session": mobile_session,
            "supabase_tokens": {
                "access_token": auth_response.session.access_token if auth_response.session else "",
                "refresh_token": auth_response.session.refresh_token if auth_response.session else ""
            },
            "message": "Account created successfully. Please check your email for verification."
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

# Password Reset Endpoints

@router.post("/password-reset/request")
async def request_password_reset(request_data: PasswordResetRequest):
    """
    Request password reset OTP code for user.
    Sends a 6-digit OTP code to the user's email.
    """
    try:
        # Validate email format
        if not AuthUtils.is_valid_email(request_data.email):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid email format"
            )

        # Use Supabase password reset with OTP
        try:
            # This triggers the password reset email with OTP token
            supabase.auth.reset_password_email(
                request_data.email,
                redirect_to=None  # No redirect needed for OTP flow
            )

            print(f"Password reset OTP sent to: {request_data.email}")
        except Exception as auth_error:
            print(f"Supabase password reset OTP error: {auth_error}")

        return {
            "message": "If the email exists, a password reset code has been sent to your email",
            "success": True
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"Password reset request error: {e}")
        return {
            "message": "If the email exists, a password reset code has been sent to your email",
            "success": True
        }


@router.post("/password-reset/verify-otp")
async def verify_password_reset_otp(verify_data: PasswordResetOTPVerify):
    """
    Verify the OTP token sent to user's email.
    This is step 1 before allowing password reset.

    Request body:
    - email: User's email address
    - token: 6-digit OTP code from email
    """
    try:
        # Validate email format
        if not AuthUtils.is_valid_email(verify_data.email):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid email format"
            )

        # Verify OTP with Supabase
        try:
            auth_response = supabase.auth.verify_otp({
                'email': verify_data.email,
                'token': verify_data.token,
                'type': 'recovery'
            })

            if not auth_response.user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid or expired verification code"
                )

            return {
                "message": "Token verified successfully. You can now reset your password.",
                "verified": True,
                "email": verify_data.email
            }

        except Exception as verify_error:
            print(f"OTP verification error: {verify_error}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired verification code"
            )

    except HTTPException:
        raise
    except Exception as e:
        print(f"Verify OTP endpoint error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during verification"
        )


@router.post("/password-reset/complete")
async def complete_password_reset(reset_data: PasswordResetComplete):
    """
    Complete password reset after OTP verification.
    This updates the user's password.

    Request body:
    - email: User's email address
    - token: The verified OTP code
    - new_password: New password to set
    """
    try:
        # Validate email format
        if not AuthUtils.is_valid_email(reset_data.email):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid email format"
            )

        # Validate password strength
        is_strong, message = AuthUtils.is_strong_password(reset_data.new_password)
        if not is_strong:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=message
            )

        try:
            # First verify the OTP again to get a valid session
            auth_response = supabase.auth.verify_otp({
                'email': reset_data.email,
                'token': reset_data.token,
                'type': 'recovery'
            })

            if not auth_response.user or not auth_response.session:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid or expired verification code"
                )

            # Now update the password using the session
            update_response = supabase.auth.update_user({
                "password": reset_data.new_password
            })

            if update_response.user:
                print(f"Password reset completed for user: {reset_data.email}")

                return {
                    "message": "Password updated successfully. Please log in with your new password.",
                    "success": True
                }
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to update password"
                )

        except HTTPException:
            raise
        except Exception as reset_error:
            print(f"Password reset completion error: {reset_error}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired verification code"
            )

    except HTTPException:
        raise
    except Exception as e:
        print(f"Complete password reset endpoint error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while resetting password"
        )


@router.post("/password-reset/verify")
async def verify_password_reset(reset_data: PasswordResetVerify):
    """
    DEPRECATED: Legacy endpoint for password reset.
    Use /password-reset/verify-otp and /password-reset/complete instead.
    """
    try:
        # Validate password strength
        is_strong, message = AuthUtils.is_strong_password(reset_data.new_password)
        if not is_strong:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=message
            )

        # Use Supabase to verify token and update password
        try:
            auth_response = supabase.auth.update_user({
                "password": reset_data.new_password
            }, access_token=reset_data.token)

            if auth_response.user:
                return {"message": "Password updated successfully. Please log in with your new password."}
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid or expired reset token"
                )

        except Exception as auth_error:
            print(f"Password reset verification error: {auth_error}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired reset token"
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

# Token Refresh Endpoints

@router.post("/refresh", response_model=TokenResponse)
async def refresh_access_token(refresh_data: RefreshTokenRequest):
    """Refresh expired access token using refresh token"""
    try:
        auth_response = supabase.auth.refresh_session(refresh_data.refresh_token)

        if auth_response.session is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token"
            )

        return TokenResponse(
            access_token=auth_response.session.access_token,
            refresh_token=auth_response.session.refresh_token
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not refresh token"
        )

@router.post("/mobile/refresh")
async def mobile_refresh_token(refresh_data: RefreshTokenRequest, request: Request):
    """Enhanced refresh token endpoint for mobile apps"""
    try:
        user_agent = request.headers.get("user-agent", "")

        auth_response = supabase.auth.refresh_session(refresh_data.refresh_token)

        if auth_response.session is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token"
            )

        user = auth_response.user
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )

        mobile_session = AuthUtils.create_mobile_session(
            user_id=user.id,
            device_info=user_agent
        )

        return {
            "session": mobile_session,
            "supabase_tokens": {
                "access_token": auth_response.session.access_token,
                "refresh_token": auth_response.session.refresh_token
            },
            "device_info": {
                "user_agent": user_agent,
                "platform": "mobile",
                "timestamp": datetime.utcnow().isoformat()
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not refresh token"
        )



# Auth Status and Logout Endpoints

@router.get("/status", response_model=AuthStatusResponse)
async def check_auth_status(credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False))):
    """Check user authentication status"""
    try:
        if not credentials:
            return AuthStatusResponse(
                is_authenticated=False,
                session_valid=False,
                needs_refresh=False
            )

        token = credentials.credentials

        # Verify token with Supabase using proper method
        try:
            # Use the AuthUtils verify_supabase_token method which properly handles the token
            user_data = AuthUtils.verify_supabase_token(token)

            if not user_data:
                return AuthStatusResponse(
                    is_authenticated=False,
                    session_valid=False,
                    needs_refresh=True
                )

            user_id = user_data.get("user_id")
            user_email = user_data.get("email")
            user_metadata_from_token = user_data.get("user_metadata", {})

            # Fetch user data from database
            try:
                db_response = supabase.table("users").select("*").eq("user_id", user_id).execute()

                if db_response.data and len(db_response.data) > 0:
                    user_db = db_response.data[0]
                    user_response_data = UserResponse(
                        user_id=user_db["user_id"],
                        name=user_db["name"],
                        email=user_db["email"],
                        phone_number=user_db.get("phone_number"),
                        country=user_db.get("country"),
                        city=user_db.get("city"),
                        address=user_db.get("address"),
                        business_name=user_db.get("business_name"),
                        business_description=user_db.get("business_description"),
                        verified=user_db.get("verified", False),
                        role=user_db.get("role", "CUSTOMER")
                    )
                else:
                    # Fallback to metadata from token
                    user_response_data = UserResponse(
                        user_id=user_id,
                        name=user_metadata_from_token.get("name", ""),
                        email=user_email or "",
                        phone_number=user_metadata_from_token.get("phone_number"),
                        country=user_metadata_from_token.get("country"),
                        city=user_metadata_from_token.get("city"),
                        address=user_metadata_from_token.get("address"),
                        business_name=user_metadata_from_token.get("business_name"),
                        business_description=user_metadata_from_token.get("business_description"),
                        verified=user_metadata_from_token.get("verified", False),
                        role=user_metadata_from_token.get("role", "CUSTOMER")
                    )

                return AuthStatusResponse(
                    is_authenticated=True,
                    user=user_response_data,
                    session_valid=True,
                    needs_refresh=False
                )

            except Exception as db_error:
                print(f"Database fetch error in auth status: {db_error}")
                # Still return authenticated if Supabase user exists - use token metadata
                user_response_data = UserResponse(
                    user_id=user_id,
                    name=user_metadata_from_token.get("name", ""),
                    email=user_email or "",
                    phone_number=user_metadata_from_token.get("phone_number"),
                    country=user_metadata_from_token.get("country"),
                    city=user_metadata_from_token.get("city"),
                    address=user_metadata_from_token.get("address"),
                    business_name=user_metadata_from_token.get("business_name"),
                    business_description=user_metadata_from_token.get("business_description"),
                    verified=user_metadata_from_token.get("verified", False),
                    role=user_metadata_from_token.get("role", "CUSTOMER")
                )

                return AuthStatusResponse(
                    is_authenticated=True,
                    user=user_response_data,
                    session_valid=True,
                    needs_refresh=False
                )

        except Exception as auth_error:
            print(f"Auth status check error: {auth_error}")
            return AuthStatusResponse(
                is_authenticated=False,
                session_valid=False,
                needs_refresh=True
            )

    except Exception as e:
        print(f"Auth status endpoint error: {e}")
        return AuthStatusResponse(
            is_authenticated=False,
            session_valid=False,
            needs_refresh=False
        )

@router.post("/logout", response_model=LogoutResponse)
async def logout_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False))):
    """Logout user and invalidate session"""
    try:
        if credentials:
            token = credentials.credentials
            
            try:
                # Sign out from Supabase
                supabase.auth.sign_out()
                print(f"User logged out successfully")
            except Exception as logout_error:
                print(f"Logout error: {logout_error}")
                # Continue even if logout fails

        return LogoutResponse(
            message="Successfully logged out",
            logged_out=True
        )

    except Exception as e:
        print(f"Logout endpoint error: {e}")
        # Always return success for better UX
        return LogoutResponse(
            message="Successfully logged out",
            logged_out=True
        )

@router.get("/mobile/status")
async def check_mobile_auth_status(request: Request, credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False))):
    """Check mobile user authentication status with device info"""
    try:
        user_agent = request.headers.get("user-agent", "")
        
        if not credentials:
            return {
                "is_authenticated": False,
                "session_valid": False,
                "needs_refresh": False,
                "device_info": {
                    "user_agent": user_agent,
                    "platform": "mobile",
                    "timestamp": datetime.utcnow().isoformat()
                }
            }

        token = credentials.credentials

        try:
            # Use the AuthUtils verify_supabase_token method which properly handles the token
            user_data = AuthUtils.verify_supabase_token(token)

            if not user_data:
                return {
                    "is_authenticated": False,
                    "session_valid": False,
                    "needs_refresh": True,
                    "device_info": {
                        "user_agent": user_agent,
                        "platform": "mobile",
                        "timestamp": datetime.utcnow().isoformat()
                    }
                }

            user_id = user_data.get("user_id")
            user_email = user_data.get("email")
            user_metadata_from_token = user_data.get("user_metadata", {})

            # Fetch user data from database
            try:
                db_response = supabase.table("users").select("*").eq("user_id", user_id).execute()

                if db_response.data and len(db_response.data) > 0:
                    user_db = db_response.data[0]
                    user_data = UserResponse(
                        user_id=user_db["user_id"],
                        name=user_db["name"],
                        email=user_db["email"],
                        phone_number=user_db.get("phone_number"),
                        country=user_db.get("country"),
                        city=user_db.get("city"),
                        address=user_db.get("address"),
                        business_name=user_db.get("business_name"),
                        business_description=user_db.get("business_description"),
                        verified=user_db.get("verified", False),
                        role=user_db.get("role", "CUSTOMER")
                    )
                else:
                    # Fallback to metadata from token
                    user_data = UserResponse(
                        user_id=user_id,
                        name=user_metadata_from_token.get("name", ""),
                        email=user_email or "",
                        phone_number=user_metadata_from_token.get("phone_number"),
                        country=user_metadata_from_token.get("country"),
                        city=user_metadata_from_token.get("city"),
                        address=user_metadata_from_token.get("address"),
                        business_name=user_metadata_from_token.get("business_name"),
                        business_description=user_metadata_from_token.get("business_description"),
                        verified=user_metadata_from_token.get("verified", False),
                        role=user_metadata_from_token.get("role", "CUSTOMER")
                    )

                return {
                    "is_authenticated": True,
                    "user": user_data.dict(),
                    "session_valid": True,
                    "needs_refresh": False,
                    "device_info": {
                        "user_agent": user_agent,
                        "platform": "mobile",
                        "timestamp": datetime.utcnow().isoformat()
                    }
                }

            except Exception as db_error:
                print(f"Mobile auth status database error: {db_error}")
                user_data = UserResponse(
                    user_id=user_id,
                    name=user_metadata_from_token.get("name", ""),
                    email=user_email or "",
                    phone_number=user_metadata_from_token.get("phone_number"),
                    country=user_metadata_from_token.get("country"),
                    city=user_metadata_from_token.get("city"),
                    address=user_metadata_from_token.get("address"),
                    business_name=user_metadata_from_token.get("business_name"),
                    business_description=user_metadata_from_token.get("business_description"),
                    verified=user_metadata_from_token.get("verified", False),
                    role=user_metadata_from_token.get("role", "CUSTOMER")
                )

                return {
                    "is_authenticated": True,
                    "user": user_data.dict(),
                    "session_valid": True,
                    "needs_refresh": False,
                    "device_info": {
                        "user_agent": user_agent,
                        "platform": "mobile",
                        "timestamp": datetime.utcnow().isoformat()
                    }
                }

        except Exception as auth_error:
            print(f"Mobile auth status check error: {auth_error}")
            return {
                "is_authenticated": False,
                "session_valid": False,
                "needs_refresh": True,
                "device_info": {
                    "user_agent": user_agent,
                    "platform": "mobile",
                    "timestamp": datetime.utcnow().isoformat()
                }
            }

    except Exception as e:
        print(f"Mobile auth status endpoint error: {e}")
        return {
            "is_authenticated": False,
            "session_valid": False,
            "needs_refresh": False,
            "device_info": {
                "user_agent": request.headers.get("user-agent", ""),
                "platform": "mobile",
                "timestamp": datetime.utcnow().isoformat()
            }
        }

@router.post("/mobile/logout")
async def mobile_logout(request: Request, credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False))):
    """Mobile logout with device tracking"""
    try:
        user_agent = request.headers.get("user-agent", "")

        if credentials:
            token = credentials.credentials

            try:
                # Get user info before logout for logging
                user_response = supabase.auth.get_user(token)
                user_id = user_response.user.id if user_response.user else "unknown"

                # Sign out from Supabase
                supabase.auth.sign_out()
                print(f"Mobile user {user_id} logged out successfully")
            except Exception as logout_error:
                print(f"Mobile logout error: {logout_error}")

        return {
            "message": "Successfully logged out",
            "logged_out": True,
            "device_info": {
                "user_agent": user_agent,
                "platform": "mobile",
                "timestamp": datetime.utcnow().isoformat()
            }
        }

    except Exception as e:
        print(f"Mobile logout endpoint error: {e}")
        return {
            "message": "Successfully logged out",
            "logged_out": True,
            "device_info": {
                "user_agent": request.headers.get("user-agent", ""),
                "platform": "mobile",
                "timestamp": datetime.utcnow().isoformat()
            }
        }


# Email Verification Endpoints

@router.get("/confirm")
async def verify_email(token_hash: str, type: str, email: Optional[str] = None):
    """
    Verify user email using the token from email confirmation link.
    This endpoint handles both web and mobile deep link confirmations.

    Query parameters:
    - token_hash: The token hash from the email confirmation link
    - type: The type of confirmation (signup, email_change, etc.)
    - email: (optional) The user's email address
    """
    try:
        # Verify the token with Supabase
        try:
            # Use the verify_otp method to confirm the email
            auth_response = supabase.auth.verify_otp({
                'token_hash': token_hash,
                'type': type
            })

            if not auth_response.user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid or expired verification token"
                )

            user = auth_response.user

            # Update user verification status in database
            try:
                update_response = supabase.table("users").update({
                    "verified": True
                }).eq("user_id", user.id).execute()

                if update_response.data:
                    print(f"User {user.id} verified successfully in database")
                else:
                    print(f"Database update warning for user {user.id}")

            except Exception as db_error:
                print(f"Database update error during verification: {db_error}")
                # Continue even if database update fails since Supabase auth is verified

            # Return success response with tokens for automatic login
            return {
                "message": "Email verified successfully! You can now log in.",
                "verified": True,
                "user": {
                    "user_id": user.id,
                    "email": user.email,
                    "email_confirmed_at": user.email_confirmed_at
                },
                "session": {
                    "access_token": auth_response.session.access_token if auth_response.session else None,
                    "refresh_token": auth_response.session.refresh_token if auth_response.session else None
                }
            }

        except Exception as verify_error:
            print(f"Email verification error: {verify_error}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired verification token. Please request a new verification email."
            )

    except HTTPException:
        raise
    except Exception as e:
        print(f"Email verification endpoint error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during email verification"
        )


@router.post("/resend-verification")
async def resend_verification_email(email: str):
    """
    Resend verification email to user.

    Request body:
    - email: The user's email address
    """
    try:
        # Validate email format
        if not AuthUtils.is_valid_email(email):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid email format"
            )

        # Resend verification email using Supabase
        try:
            supabase.auth.resend({
                'type': 'signup',
                'email': email
            })

            return {
                "message": "Verification email has been resent. Please check your inbox.",
                "success": True
            }

        except Exception as resend_error:
            print(f"Resend verification error: {resend_error}")
            # Return success message anyway for security (don't reveal if email exists)
            return {
                "message": "If the email exists, a verification link has been sent.",
                "success": True
            }

    except HTTPException:
        raise
    except Exception as e:
        print(f"Resend verification endpoint error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while resending verification email"
        )

