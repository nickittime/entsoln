"""Auth API Endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from src.common.exceptions.base import ZERMPBaseException
from src.common.security.dependencies import get_current_user
from src.modules.auth.models import LoginRequest, TokenPayload, TokenResponse, UserProfile
from src.modules.auth.service import auth_service

router = APIRouter(prefix="/auth", tags=["Identity & Access Control"])


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest):
    """Authenticate user against Vridhi SSO identity provider."""
    try:
        user = auth_service.authenticate_user(req.username, req.password, req.mfa_code)
        token = auth_service.create_access_token(user)
        return TokenResponse(
            access_token=token,
            expires_in_minutes=60,
            user=user,
        )
    except ZERMPBaseException as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=exc.message,
        ) from exc


@router.get("/me", response_model=TokenPayload)
async def get_my_profile(current_user: TokenPayload = Depends(get_current_user)):
    """Retrieve verified claims of the current authenticated user session."""
    return current_user
