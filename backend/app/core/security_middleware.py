"""
Security middleware for FastAPI application.

This module provides comprehensive security headers and middleware
for protecting the ConvoSphere application.
"""

import time

from fastapi import Request, Response
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware for adding security headers to all responses."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Add security headers to response."""
        start_time = time.time()

        # Process request
        response = await call_next(request)

        # Calculate response time
        process_time = time.time() - start_time

        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains; preload"
        )
        response.headers["Content-Security-Policy"] = self._get_csp_header()
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=(), payment=(), usb=()"
        )
        response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
        response.headers["X-Download-Options"] = "noopen"
        response.headers["X-DNS-Prefetch-Control"] = "off"

        # Add performance headers
        response.headers["X-Response-Time"] = f"{process_time:.4f}"
        response.headers["Server"] = "ConvoSphere/1.0"

        # Log security events
        await self._log_security_event(request, response, process_time)

        return response

    def _get_csp_header(self) -> str:
        """Get Content Security Policy header."""
        return (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: https:; "
            "connect-src 'self' https://api.openai.com https://api.anthropic.com; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'; "
            "upgrade-insecure-requests;"
        )

    async def _log_security_event(
        self, request: Request, response: Response, process_time: float
    ):
        """Log security-relevant events."""
        # Log suspicious requests
        if response.status_code >= 400:
            logger.warning(
                f"Security event: {request.method} {request.url.path} "
                f"returned {response.status_code} from {request.client.host}"
            )

        # Log slow requests
        if process_time > 5.0:
            logger.warning(
                f"Slow request: {request.method} {request.url.path} "
                f"took {process_time:.2f}s from {request.client.host}"
            )


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware for rate limiting requests."""

    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.request_counts = {}

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Apply rate limiting to requests."""
        client_ip = self._get_client_ip(request)
        current_time = int(time.time() / 60)  # Minute-based window

        # Clean old entries
        self._cleanup_old_entries(current_time)

        # Check rate limit
        if not self._check_rate_limit(client_ip, current_time):
            logger.warning(f"Rate limit exceeded for IP: {client_ip}")
            return Response(
                content="Rate limit exceeded",
                status_code=429,
                headers={"Retry-After": "60"},
            )

        # Process request
        response = await call_next(request)

        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(
            self._get_remaining_requests(client_ip, current_time)
        )

        return response

    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address."""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host

    def _check_rate_limit(self, client_ip: str, current_time: int) -> bool:
        """Check if request is within rate limit."""
        key = f"{client_ip}:{current_time}"
        count = self.request_counts.get(key, 0)

        if count >= self.requests_per_minute:
            return False

        self.request_counts[key] = count + 1
        return True

    def _get_remaining_requests(self, client_ip: str, current_time: int) -> int:
        """Get remaining requests for client."""
        key = f"{client_ip}:{current_time}"
        count = self.request_counts.get(key, 0)
        return max(0, self.requests_per_minute - count)

    def _cleanup_old_entries(self, current_time: int):
        """Clean up old rate limit entries."""
        keys_to_remove = [
            key
            for key in self.request_counts
            if int(key.split(":")[1]) < current_time - 1
        ]
        for key in keys_to_remove:
            del self.request_counts[key]


class SecurityValidationMiddleware(BaseHTTPMiddleware):
    """Middleware for security validation."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Validate request for security issues."""

        # Check for suspicious headers
        if self._has_suspicious_headers(request):
            logger.warning(f"Suspicious headers from {request.client.host}")
            return Response(content="Invalid request", status_code=400)

        # Check for suspicious user agents
        if self._has_suspicious_user_agent(request):
            logger.warning(f"Suspicious user agent from {request.client.host}")
            return Response(content="Invalid request", status_code=400)

        # Check for path traversal attempts
        if self._has_path_traversal(request):
            logger.warning(f"Path traversal attempt from {request.client.host}")
            return Response(content="Invalid request", status_code=400)

        # Process request
        return await call_next(request)

    def _has_suspicious_headers(self, request: Request) -> bool:
        """Check for suspicious headers."""
        suspicious_headers = ["X-Forwarded-Host", "X-Original-URL", "X-Rewrite-URL"]

        return any(header in request.headers for header in suspicious_headers)

    def _has_suspicious_user_agent(self, request: Request) -> bool:
        """Check for suspicious user agents."""
        user_agent = request.headers.get("user-agent", "").lower()

        suspicious_patterns = [
            "sqlmap",
            "nikto",
            "nmap",
            "scanner",
            "bot",
            "crawler",
            "spider",
        ]

        return any(pattern in user_agent for pattern in suspicious_patterns)

    def _has_path_traversal(self, request: Request) -> bool:
        """Check for path traversal attempts."""
        path = request.url.path.lower()

        suspicious_patterns = [
            "..",
            "~",
            "/etc/",
            "/proc/",
            "/sys/",
            "/dev/",
            "cmd",
            "exec",
            "system",
        ]

        return any(pattern in path for pattern in suspicious_patterns)


def setup_security_middleware(app):
    """Setup all security middleware for the application."""

    # Add security headers middleware
    app.add_middleware(SecurityHeadersMiddleware)

    # Add rate limiting middleware
    app.add_middleware(RateLimitMiddleware, requests_per_minute=60)

    # Add security validation middleware
    app.add_middleware(SecurityValidationMiddleware)

    logger.info("Security middleware configured successfully")
