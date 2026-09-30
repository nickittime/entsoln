"""FastAPI Security Dependencies, RBAC Gating, and Segregation of Duties."""

from typing import List, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from src.common.exceptions.base import ZERMPBaseException
from src.modules.auth.models import TokenPayload, UserRole
from src.modules.auth.service import auth_service

security_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
) -> TokenPayload:
    """Dependency extracting and validating Bearer JWT claims."""
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        return auth_service.decode_token(credentials.credentials)
    except ZERMPBaseException as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=exc.message,
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


class RequireRole:
    """RBAC Route Guard checking authorized role membership."""

    def __init__(self, allowed_roles: List[UserRole]) -> None:
        self.allowed_roles = allowed_roles

    def __call__(self, user: TokenPayload = Depends(get_current_user)) -> TokenPayload:
        if user.role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Requires one of roles: {[r.value for r in self.allowed_roles]}",
            )
        return user


def enforce_segregation_of_duties(
    initiator_id: str,
    approver_user: TokenPayload,
    action: str = "OVERRIDE_APPROVAL",
) -> None:
    """Enforces 4-Eyes Principle: Initiator cannot approve their own financial request."""
    if approver_user.sub == initiator_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Segregation of Duties violation: Initiator cannot self-approve {action}",
        )
    if approver_user.role == UserRole.SYSTEM_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="System Administrator is prohibited from approving financial risk decisions",
        )
