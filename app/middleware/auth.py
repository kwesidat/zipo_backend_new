from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.database import supabase
from app.models.auth import UserResponse
from typing import Optional

security = HTTPBearer()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> UserResponse:
    try:
        token = credentials.credentials

        user_response = supabase.auth.get_user(token)

        if user_response.user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        user = user_response.user
        user_metadata = user.user_metadata or {}

        return UserResponse(
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

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Authentication error: {str(e)}"
        )

async def get_current_active_user(current_user: UserResponse = Depends(get_current_user)) -> UserResponse:
    if not current_user.verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    return current_user

def require_role(required_role: str):
    def role_checker(current_user: UserResponse = Depends(get_current_user)) -> UserResponse:
        if current_user.role != required_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation requires {required_role} role"
            )
        return current_user
    return role_checker

def require_roles(required_roles: list):
    def role_checker(current_user: UserResponse = Depends(get_current_user)) -> UserResponse:
        if current_user.role not in required_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation requires one of the following roles: {', '.join(required_roles)}"
            )
        return current_user
    return role_checker

async def get_optional_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False))) -> Optional[UserResponse]:
    if credentials is None:
        return None

    try:
        token = credentials.credentials
        user_response = supabase.auth.get_user(token)

        if user_response.user is None:
            return None

        user = user_response.user
        user_metadata = user.user_metadata or {}

        return UserResponse(
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

    except Exception:
        return None