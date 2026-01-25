"""
Authentication Endpoints
Login and logout endpoints for broker authentication
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.auth import AuthService
from app.models.schemas import (
    LoginRequest, LoginResponse, BaseResponse, ErrorResponse, SavedCredentialsResponse, VerifyRequest
)
from app.api.deps import get_api_key, get_api_key_flexible
from app.api.exceptions import AuthenticationError
from app.utils.logger import logger

router = APIRouter()


@router.post("/verify-session", response_model=BaseResponse)
async def verify_session(
    request: VerifyRequest,
    db: AsyncSession = Depends(get_db)
):
    """Verify session validity"""
    auth_service = AuthService(db)
    await auth_service.validate_session(request.apikey)
    return BaseResponse(status="success")


@router.post("/login", response_model=LoginResponse)
async def login(
    request: LoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Login to broker and get API key.
    
    - **broker**: Broker name (angelone)
    - **client_id**: Client/User ID
    - **password**: Password or PIN
    - **totp**: TOTP code from authenticator app
    - **api_key**: Broker API key (required)
    - **totp_secret**: TOTP secret for auto-generation (optional)
    - **save_credentials**: Save credentials to database (optional)
    
    Returns API key for subsequent requests.
    """
    auth_service = AuthService(db)
    
    try:
        result = await auth_service.login(
            broker_name=request.broker,
            client_id=request.client_id,
            password=request.password,
            totp=request.totp,
            broker_api_key=request.api_key,
            totp_secret=request.totp_secret,
            save_credentials=request.save_credentials
        )
        
        logger.info(f"Login successful for {request.client_id}")
        
        return LoginResponse(
            status="success",
            data=result
        )
        
    except AuthenticationError as e:
        logger.warning(f"Login failed for {request.client_id}: {e.message}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "status": "error",
                "code": e.code,
                "message": e.message,
                "details": e.details
            }
        )
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "code": "INTERNAL_ERROR",
                "message": "Login failed due to internal error"
            }
        )


@router.post("/logout", response_model=BaseResponse)
async def logout(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Logout and invalidate session.
    
    Accepts API key from:
    - X-API-Key header (preferred)
    - apikey in JSON body (for compatibility)
    """
    # Try to get from header first
    api_key = request.headers.get("X-API-Key")
    
    # If not in header, try body
    if not api_key:
        try:
            body = await request.json()
            api_key = body.get("apikey")
        except:
            pass
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "status": "error",
                "code": "AUTH_FAILED",
                "message": "API key required in header or body"
            }
        )
    
    auth_service = AuthService(db)
    success = await auth_service.logout(api_key)
    
    if success:
        return BaseResponse(status="success")
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "status": "error",
                "code": "LOGOUT_FAILED",
                "message": "Logout failed or session not found"
            }
        )


@router.post("/quick-login", response_model=LoginResponse)
async def quick_login(
    broker: str,
    client_id: str,
    totp: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Quick login using saved credentials.
    Only requires TOTP - uses saved password and API key.
    
    - **broker**: Broker name (angelone)
    - **client_id**: Client/User ID
    - **totp**: TOTP code from authenticator app
    
    Returns API key for subsequent requests.
    """
    auth_service = AuthService(db)
    
    try:
        result = await auth_service.quick_login(
            broker_name=broker,
            client_id=client_id,
            totp=totp
        )
        
        logger.info(f"Quick login successful for {client_id}")
        
        return LoginResponse(
            status="success",
            data=result
        )
        
    except AuthenticationError as e:
        logger.warning(f"Quick login failed for {client_id}: {e.message}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "status": "error",
                "code": e.code,
                "message": e.message,
                "details": e.details
            }
        )
    except Exception as e:
        logger.error(f"Quick login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "code": "INTERNAL_ERROR",
                "message": "Login failed due to internal error"
            }
        )


@router.get("/credentials", response_model=SavedCredentialsResponse)
async def list_credentials(
    db: AsyncSession = Depends(get_db)
):
    """
    List saved broker credentials (without sensitive data).
    Returns list of {broker, client_id} for saved accounts.
    """
    auth_service = AuthService(db)
    credentials = await auth_service.list_saved_credentials()
    
    return SavedCredentialsResponse(
        status="success",
        data=credentials
    )


@router.delete("/credentials/{broker}/{client_id}", response_model=BaseResponse)
async def delete_credentials(
    broker: str,
    client_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Delete saved broker credentials.
    """
    auth_service = AuthService(db)
    success = await auth_service.delete_credentials(broker, client_id)
    
    if success:
        return BaseResponse(status="success")
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "status": "error",
                "code": "NOT_FOUND",
                "message": "Credentials not found"
            }
        )
