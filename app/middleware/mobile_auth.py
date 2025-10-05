from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from app.utils.auth_utils import AuthUtils
import time
import logging

logger = logging.getLogger(__name__)

class MobileAuthMiddleware(BaseHTTPMiddleware):
    """Middleware for mobile authentication and request validation"""

    def __init__(self, app, excluded_paths: list = None):
        super().__init__(app)
        self.excluded_paths = excluded_paths or [
            "/docs",
            "/redoc",
            "/openapi.json",
            "/api/auth/signup",
            "/api/auth/login",
            "/api/auth/refresh",
            "/health",
            "/"
        ]

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        # Skip middleware for excluded paths
        if any(request.url.path.startswith(path) for path in self.excluded_paths):
            response = await call_next(request)
            process_time = time.time() - start_time
            response.headers["X-Process-Time"] = str(process_time)
            return response

        try:
            # Validate mobile request headers
            headers = dict(request.headers)

            # Check for mobile user agent
            user_agent = headers.get('user-agent', '')
            if not self._is_mobile_request(user_agent):
                logger.warning(f"Non-mobile request from: {user_agent}")

            # Validate authorization if required
            if request.url.path.startswith("/api/") and request.url.path not in self.excluded_paths:
                auth_header = headers.get('authorization')
                if not auth_header:
                    return JSONResponse(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        content={"detail": "Authorization header required"}
                    )

                if not auth_header.startswith('Bearer '):
                    return JSONResponse(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        content={"detail": "Invalid authorization header format"}
                    )

                # Verify token
                token = auth_header.split(' ')[1]
                try:
                    user_data = AuthUtils.verify_supabase_token(token)
                    if not user_data:
                        return JSONResponse(
                            status_code=status.HTTP_401_UNAUTHORIZED,
                            content={
                                "detail": "Invalid or expired token",
                                "error_code": "TOKEN_EXPIRED",
                                "suggestion": "Please refresh your token using /api/auth/refresh or /api/auth/mobile/refresh"
                            }
                        )

                    # Add user data to request state
                    request.state.user = user_data

                except Exception as e:
                    logger.error(f"Token verification failed: {str(e)}")

                    # Check if it's a token expiration error
                    error_msg = str(e).lower()
                    if "expired" in error_msg or "invalid" in error_msg:
                        return JSONResponse(
                            status_code=status.HTTP_401_UNAUTHORIZED,
                            content={
                                "detail": "Token has expired",
                                "error_code": "TOKEN_EXPIRED",
                                "suggestion": "Please refresh your token using /api/auth/refresh or /api/auth/mobile/refresh"
                            }
                        )
                    else:
                        return JSONResponse(
                            status_code=status.HTTP_401_UNAUTHORIZED,
                            content={
                                "detail": "Token verification failed",
                                "error_code": "TOKEN_INVALID"
                            }
                        )

            response = await call_next(request)

            # Add custom headers
            process_time = time.time() - start_time
            response.headers["X-Process-Time"] = str(process_time)
            response.headers["X-API-Version"] = "1.0"

            return response

        except Exception as e:
            logger.error(f"Middleware error: {str(e)}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "Internal server error"}
            )

    def _is_mobile_request(self, user_agent: str) -> bool:
        """Check if request is from mobile device"""
        mobile_indicators = [
            'mobile', 'android', 'iphone', 'ipad',
            'react-native', 'expo', 'flutter'
        ]
        return any(indicator.lower() in user_agent.lower() for indicator in mobile_indicators)

class CORSMiddleware(BaseHTTPMiddleware):
    """Enhanced CORS middleware for mobile apps"""

    async def dispatch(self, request: Request, call_next):
        if request.method == "OPTIONS":
            # Handle preflight requests
            response = JSONResponse(content={})
            response.headers["Access-Control-Allow-Origin"] = "*"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type, X-Requested-With"
            response.headers["Access-Control-Max-Age"] = "86400"
            return response

        response = await call_next(request)

        # Add CORS headers
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type, X-Requested-With"

        return response

class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple rate limiting middleware"""

    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.request_counts = {}

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host
        current_time = time.time()

        # Clean old entries
        self.request_counts = {
            ip: (count, timestamp) for ip, (count, timestamp) in self.request_counts.items()
            if current_time - timestamp < 60
        }

        # Check rate limit
        if client_ip in self.request_counts:
            count, timestamp = self.request_counts[client_ip]
            if current_time - timestamp < 60:
                if count >= self.requests_per_minute:
                    return JSONResponse(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        content={"detail": "Rate limit exceeded"}
                    )
                self.request_counts[client_ip] = (count + 1, timestamp)
            else:
                self.request_counts[client_ip] = (1, current_time)
        else:
            self.request_counts[client_ip] = (1, current_time)

        return await call_next(request)

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Request logging middleware"""

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        # Log request
        logger.info(f"Request: {request.method} {request.url.path}")

        response = await call_next(request)

        # Log response
        process_time = time.time() - start_time
        logger.info(f"Response: {response.status_code} - {process_time:.4f}s")

        return response