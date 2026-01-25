"""
Custom Exceptions and Error Handlers
"""

from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from app.models.schemas import ErrorCodes, ERROR_MESSAGES, ErrorResponse
from app.utils.logger import logger


class TradingException(Exception):
    """Base exception for trading backend"""
    
    def __init__(
        self,
        code: str,
        message: str = None,
        details: dict = None,
        status_code: int = 400
    ):
        self.code = code
        self.message = message or ERROR_MESSAGES.get(code, "Unknown error")
        self.details = details
        self.status_code = status_code
        super().__init__(self.message)


class AuthenticationError(TradingException):
    """Authentication related errors"""
    
    def __init__(self, message: str = None, details: dict = None):
        super().__init__(
            code=ErrorCodes.AUTH_FAILED,
            message=message,
            details=details,
            status_code=401
        )


class TokenExpiredError(TradingException):
    """Token expired error"""
    
    def __init__(self, message: str = None):
        super().__init__(
            code=ErrorCodes.TOKEN_EXPIRED,
            message=message or "Session token has expired",
            status_code=401
        )


class RateLimitError(TradingException):
    """Rate limit exceeded error"""
    
    def __init__(self, message: str = None):
        super().__init__(
            code=ErrorCodes.RATE_LIMITED,
            message=message,
            status_code=429
        )


class BrokerError(TradingException):
    """Broker API error"""
    
    def __init__(self, message: str = None, details: dict = None):
        super().__init__(
            code=ErrorCodes.BROKER_ERROR,
            message=message,
            details=details,
            status_code=502
        )


class SymbolNotFoundError(TradingException):
    """Symbol not found error"""
    
    def __init__(self, symbol: str):
        super().__init__(
            code=ErrorCodes.SYMBOL_NOT_FOUND,
            message=f"Symbol '{symbol}' not found",
            status_code=404
        )


class ValidationError(TradingException):
    """Validation error"""
    
    def __init__(self, message: str, details: dict = None):
        super().__init__(
            code=ErrorCodes.VALIDATION_ERROR,
            message=message,
            details=details,
            status_code=422
        )


# ==================== Exception Handlers ====================

async def trading_exception_handler(request: Request, exc: TradingException):
    """Handle TradingException"""
    logger.error(f"TradingException: {exc.code} - {exc.message}")
    
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            code=exc.code,
            message=exc.message,
            details=exc.details
        ).model_dump()
    )


async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTPException"""
    # Suppress 401 errors during logout (expected behavior)
    # Only log if it's not a simple auth failure
    if exc.status_code == 401:
        # Don't log 401 errors - they're expected when session expires or user logs out
        pass
    else:
        logger.error(f"HTTPException: {exc.status_code} - {exc.detail}")
    
    # If detail is already formatted, use it
    if isinstance(exc.detail, dict) and "code" in exc.detail:
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.detail
        )
    
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            code=ErrorCodes.INTERNAL_ERROR,
            message=str(exc.detail)
        ).model_dump()
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors"""
    errors = exc.errors()
    logger.warning(f"Validation error: {errors}")
    
    return JSONResponse(
        status_code=422,
        content=ErrorResponse(
            code=ErrorCodes.VALIDATION_ERROR,
            message="Request validation failed",
            details={"errors": errors}
        ).model_dump()
    )


async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions"""
    logger.exception(f"Unexpected error: {exc}")
    
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            code=ErrorCodes.INTERNAL_ERROR,
            message="An unexpected error occurred"
        ).model_dump()
    )


def register_exception_handlers(app):
    """Register all exception handlers with the app"""
    app.add_exception_handler(TradingException, trading_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)
