import jwt
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from fastapi import HTTPException, status
from passlib.context import CryptContext
from app.database import supabase, SUPABASE_JWT_SECRET
import uuid

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

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
    def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
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
                    detail=f"Invalid token type. Expected {token_type}"
                )
            return payload
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired"
            )
        except jwt.JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials"
            )

    @staticmethod
    def verify_supabase_token(token: str) -> Optional[Dict[str, Any]]:
     """Verify Supabase JWT token"""
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
                "verify_aud": False
            }
        )
        
        # Supabase tokens have 'sub' claim
        if 'sub' in payload:
            return {
                "user_id": payload['sub'],
                "email": payload.get('email'),
                "user_metadata": payload.get('user_metadata', {})
            }
        
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
                detail="Invalid or expired token"
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
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
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
        sensitive_fields = ['password', 'password_hash', 'raw_user_meta_data']
        return {k: v for k, v in user_data.items() if k not in sensitive_fields}

    @staticmethod
    def create_mobile_session(user_id: str, device_info: Optional[str] = None) -> Dict[str, Any]:
        """Create a mobile session with tokens"""
        session_data = {
            "user_id": user_id,
            "session_id": AuthUtils.generate_session_id(),
            "device_info": device_info,
            "created_at": datetime.utcnow().isoformat()
        }

        access_token = AuthUtils.create_access_token(session_data)
        refresh_token = AuthUtils.create_refresh_token({"user_id": user_id, "session_id": session_data["session_id"]})

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "session_id": session_data["session_id"]
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
                    detail="Invalid refresh token"
                )

            # Create new access token
            new_access_token = AuthUtils.create_access_token({
                "user_id": user_id,
                "session_id": session_id
            })

            return {
                "access_token": new_access_token,
                "token_type": "bearer",
                "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60
            }

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not refresh token"
            )

    @staticmethod
    def validate_mobile_request(headers: Dict[str, str]) -> Dict[str, Any]:
        """Validate mobile app request headers"""
        required_headers = ['user-agent', 'authorization']
        missing_headers = [h for h in required_headers if h not in headers]

        if missing_headers:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing required headers: {', '.join(missing_headers)}"
            )

        auth_header = headers.get('authorization', '')
        if not auth_header.startswith('Bearer '):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authorization header format"
            )

        token = auth_header.split(' ')[1]
        return AuthUtils.extract_user_from_supabase_token(token)

    @staticmethod
    def create_password_reset_token(email: str) -> str:
        """Create a password reset token"""
        data = {
            "email": email,
            "purpose": "password_reset",
            "exp": datetime.utcnow() + timedelta(hours=1)  # 1 hour expiry
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
                    detail="Invalid token purpose"
                )
            return payload.get("email")
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password reset token has expired"
            )
        except jwt.JWTError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid password reset token"
            )