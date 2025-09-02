"""Error handling middleware and exception handlers."""

import logging
from typing import Union
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import ValidationError

logger = logging.getLogger(__name__)


class APIError(Exception):
    """Custom API error class."""
    
    def __init__(
        self,
        message: str,
        status_code: int = 500,
        error_code: str = "INTERNAL_ERROR",
        details: Union[str, dict] = None
    ):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.details = details
        super().__init__(self.message)


def create_error_response(
    status_code: int,
    message: str,
    error_code: str = None,
    details: Union[str, dict] = None,
    request_id: str = None
) -> JSONResponse:
    """Create standardized error response."""
    
    error_data = {
        "error": {
            "message": message,
            "code": error_code or f"HTTP_{status_code}",
            "timestamp": None,  # Will be set by the frontend or client
        }
    }
    
    if details:
        error_data["error"]["details"] = details
    
    if request_id:
        error_data["error"]["request_id"] = request_id
    
    return JSONResponse(
        status_code=status_code,
        content=error_data
    )


async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
    """Handle custom API errors."""
    
    request_id = getattr(request.state, "request_id", None)
    
    logger.error(
        f"API Error - Request ID: {request_id} | "
        f"Code: {exc.error_code} | "
        f"Message: {exc.message} | "
        f"Details: {exc.details}"
    )
    
    return create_error_response(
        status_code=exc.status_code,
        message=exc.message,
        error_code=exc.error_code,
        details=exc.details,
        request_id=request_id
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle FastAPI HTTP exceptions."""
    
    request_id = getattr(request.state, "request_id", None)
    
    logger.warning(
        f"HTTP Exception - Request ID: {request_id} | "
        f"Status: {exc.status_code} | "
        f"Detail: {exc.detail}"
    )
    
    return create_error_response(
        status_code=exc.status_code,
        message=exc.detail,
        error_code=f"HTTP_{exc.status_code}",
        request_id=request_id
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handle request validation errors."""
    
    request_id = getattr(request.state, "request_id", None)
    
    # Format validation errors
    errors = []
    for error in exc.errors():
        field_path = " -> ".join(str(loc) for loc in error["loc"])
        errors.append({
            "field": field_path,
            "message": error["msg"],
            "type": error["type"]
        })
    
    logger.warning(
        f"Validation Error - Request ID: {request_id} | "
        f"Errors: {errors}"
    )
    
    return create_error_response(
        status_code=422,
        message="请求参数验证失败",
        error_code="VALIDATION_ERROR",
        details={"validation_errors": errors},
        request_id=request_id
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions."""
    
    request_id = getattr(request.state, "request_id", None)
    
    logger.error(
        f"Unexpected Error - Request ID: {request_id} | "
        f"Type: {type(exc).__name__} | "
        f"Message: {str(exc)}",
        exc_info=True
    )
    
    return create_error_response(
        status_code=500,
        message="服务器内部错误",
        error_code="INTERNAL_SERVER_ERROR",
        details="请稍后重试或联系系统管理员",
        request_id=request_id
    )