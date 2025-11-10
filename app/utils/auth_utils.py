from jose import jwt
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from fastapi import HTTPException, status
from passlib.context import CryptContext
from app.database import supabase, SUPABASE_JWT_SECRET
import uuid

# Password hashing (use PBKDF2 to avoid native wheels on Lambda)
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

# JWT Configuration
SECRET_KEY = SUPABASE_JWT_SECRET or "your-fallback-secret-key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7


class AuthUtils:
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash"""
        return pwd_context.verify(plain_password, hashed_password)

    @staticmethod
    def get_password_hash(password: str) -> str:
        """Hash a password"""
        return pwd_context.hash(password)

    @staticmethod
    def create_access_token(
        data: Dict[str, Any], expires_delta: Optional[timedelta] = None
    ) -> str:
        """Create a JWT access token"""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

        to_encode.update({"exp": expire, "type": "access"})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt

    @staticmethod
    def create_refresh_token(data: Dict[str, Any]) -> str:
        """Create a JWT refresh token"""
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        to_encode.update({"exp": expire, "type": "refresh"})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt

    @staticmethod
    def verify_token(token: str, token_type: str = "access") -> Dict[str, Any]:
        """Verify and decode a JWT token"""
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            if payload.get("type") != token_type:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Invalid token type. Expected {token_type}",
                )
            return payload
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired"
            )
        except jwt.JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
            )

    @staticmethod
    def verify_supabase_token(token: str) -> Optional[Dict[str, Any]]:
        """Verify Supabase JWT token and enrich with database user info"""
        try:
            # Clean the token
            token = token.strip()

            # Import Supabase JWT secret
            from app.database import SUPABASE_JWT_SECRET

            # Decode with Supabase's JWT secret
            payload = jwt.decode(
                token,
                SUPABASE_JWT_SECRET,  # Use this, NOT SECRET_KEY
                algorithms=["HS256"],
                options={
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_aud": False,
                },
            )

            # Supabase tokens have 'sub' claim
            if "sub" in payload:
                user_id = payload["sub"]
                user_data = {
                    "user_id": user_id,
                    "email": payload.get("email"),
                    "user_metadata": payload.get("user_metadata", {}),
                }

                # Fetch additional user info from database (user_type, role)
                try:
                    from app.database import supabase
                    db_user_response = supabase.table("users").select("role, user_type").eq("user_id", user_id).execute()

                    if db_user_response.data and len(db_user_response.data) > 0:
                        db_user = db_user_response.data[0]
                        user_data["role"] = db_user.get("role")
                        user_data["user_type"] = db_user.get("user_type") or db_user.get("role")  # Fallback to role if user_type not set
                except Exception as db_error:
                    print(f"Could not fetch user role from database: {str(db_error)}")
                    # Continue without role/user_type - endpoint will handle if needed

                return user_data

            return None

        except jwt.ExpiredSignatureError:
            print(f"Token has expired")
            return None
        except jwt.InvalidTokenError as e:
            print(f"Invalid token: {str(e)}")
            return None
        except Exception as e:
            print(f"Token verification error: {str(e)}")
            return None

    @staticmethod
    def extract_user_from_supabase_token(token: str) -> Dict[str, Any]:
        """Extract user information from Supabase token"""
        user_data = AuthUtils.verify_supabase_token(token)
        if not user_data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            )
        return user_data

    @staticmethod
    def generate_session_id() -> str:
        """Generate a unique session ID"""
        return str(uuid.uuid4())

    @staticmethod
    def is_valid_email(email: str) -> bool:
        """Basic email validation"""
        import re

        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        return re.match(pattern, email) is not None

    @staticmethod
    def is_strong_password(password: str) -> tuple[bool, str]:
        """Check if password meets security requirements"""
        if len(password) < 8:
            return False, "Password must be at least 8 characters long"

        if not any(c.isupper() for c in password):
            return False, "Password must contain at least one uppercase letter"

        if not any(c.islower() for c in password):
            return False, "Password must contain at least one lowercase letter"

        if not any(c.isdigit() for c in password):
            return False, "Password must contain at least one digit"

        special_chars = "!@#$%^&*()_+-=[]{}|;:,.<>?"
        if not any(c in special_chars for c in password):
            return False, "Password must contain at least one special character"

        return True, "Password is strong"

    @staticmethod
    def sanitize_user_data(user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Remove sensitive data from user object"""
        sensitive_fields = ["password", "password_hash", "raw_user_meta_data"]
        return {k: v for k, v in user_data.items() if k not in sensitive_fields}

    @staticmethod
    def create_mobile_session(
        user_id: str, device_info: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a mobile session with tokens"""
        session_data = {
            "user_id": user_id,
            "session_id": AuthUtils.generate_session_id(),
            "device_info": device_info,
            "created_at": datetime.utcnow().isoformat(),
        }

        access_token = AuthUtils.create_access_token(session_data)
        refresh_token = AuthUtils.create_refresh_token(
            {"user_id": user_id, "session_id": session_data["session_id"]}
        )

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "session_id": session_data["session_id"],
        }

    @staticmethod
    def refresh_access_token(refresh_token: str) -> Dict[str, Any]:
        """Refresh access token using refresh token"""
        try:
            payload = AuthUtils.verify_token(refresh_token, "refresh")
            user_id = payload.get("user_id")
            session_id = payload.get("session_id")

            if not user_id or not session_id:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid refresh token",
                )

            # Create new access token
            new_access_token = AuthUtils.create_access_token(
                {"user_id": user_id, "session_id": session_id}
            )

            return {
                "access_token": new_access_token,
                "token_type": "bearer",
                "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            }

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not refresh token",
            )

    @staticmethod
    def validate_mobile_request(headers: Dict[str, str]) -> Dict[str, Any]:
        """Validate mobile app request headers"""
        required_headers = ["user-agent", "authorization"]
        missing_headers = [h for h in required_headers if h not in headers]

        if missing_headers:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing required headers: {', '.join(missing_headers)}",
            )

        auth_header = headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authorization header format",
            )

        token = auth_header.split(" ")[1]
        return AuthUtils.extract_user_from_supabase_token(token)

    @staticmethod
    def create_password_reset_token(email: str) -> str:
        """Create a password reset token"""
        data = {
            "email": email,
            "purpose": "password_reset",
            "exp": datetime.utcnow() + timedelta(hours=1),  # 1 hour expiry
        }
        return jwt.encode(data, SECRET_KEY, algorithm=ALGORITHM)

    @staticmethod
    def verify_password_reset_token(token: str) -> str:
        """Verify password reset token and return email"""
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            if payload.get("purpose") != "password_reset":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid token purpose",
                )
            return payload.get("email")
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password reset token has expired",
            )
        except jwt.JWTError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid password reset token",
            )

    @staticmethod
    async def ensure_user_exists_in_db(user_data: Dict[str, Any]) -> bool:
        """
        Ensure user exists in local database, create if not exists.
        This is used to sync users from Supabase auth to local database.

        Args:
            user_data: User data from JWT token containing user_id, email, user_metadata

        Returns:
            bool: True if user exists or was created successfully, False otherwise
        """
        try:
            from app.database import supabase
            from datetime import datetime
            import logging

            logger = logging.getLogger(__name__)

            user_id = user_data.get("user_id")
            if not user_id:
                logger.error("No user_id found in user_data")
                return False

            email = user_data.get("email", "")
            user_metadata = user_data.get("user_metadata", {})

            # Check if user exists in local database by user_id
            user_check_response = (
                supabase.table("users")
                .select("user_id")
                .eq("user_id", user_id)
                .execute()
            )

            # If user exists, return True
            if user_check_response.data and len(user_check_response.data) > 0:
                return True

            # User doesn't exist by user_id, need to create them
            logger.info(f"User {user_id} not found in local database, creating...")

            # Handle potential email conflict by creating unique email if needed
            create_email = email
            if email:
                # Check if email exists with different user_id
                email_check_response = (
                    supabase.table("users")
                    .select("user_id")
                    .eq("email", email)
                    .execute()
                )

                if email_check_response.data and len(email_check_response.data) > 0:
                    # Email exists with different user_id, create unique email
                    base_email = email.split("@")
                    if len(base_email) == 2:
                        create_email = f"{base_email[0]}+{user_id[:8]}@{base_email[1]}"
                        logger.info(
                            f"Email conflict detected, using modified email: {create_email}"
                        )
                    else:
                        create_email = f"user_{user_id[:8]}@example.com"

            # Create new user record
            new_user_data = {
                "user_id": user_id,
                "email": create_email,
                "name": user_metadata.get(
                    "name",
                    create_email.split("@")[0]
                    if create_email
                    else f"User_{user_id[:8]}",
                ),
                "verified": True,
                "role": "client",
                "created_at": datetime.utcnow().isoformat(),
            }

            # Add optional fields if available
            if user_metadata.get("phone_number"):
                new_user_data["phone_number"] = user_metadata["phone_number"]

            create_response = supabase.table("users").insert(new_user_data).execute()

            if create_response.data:
                logger.info(f"Successfully created user {user_id} in local database")
                return True
            else:
                logger.error(f"Failed to create user {user_id}: {create_response}")

                # Fallback: Try creating user without email to avoid any conflicts
                logger.info(
                    f"Attempting fallback user creation without email for {user_id}"
                )
                fallback_user_data = {
                    "user_id": user_id,
                    "name": f"User_{user_id[:8]}",
                    "verified": True,
                    "role": "client",
                    "created_at": datetime.utcnow().isoformat(),
                }

                fallback_response = (
                    supabase.table("users").insert(fallback_user_data).execute()
                )

                if fallback_response.data:
                    logger.info(
                        f"Successfully created user {user_id} with fallback method"
                    )
                    return True
                else:
                    logger.error(
                        f"Fallback user creation also failed for {user_id}: {fallback_response}"
                    )
                    return False

        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Error ensuring user exists in database: {str(e)}")
            return False
