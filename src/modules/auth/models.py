"""Enterprise RBAC Models and Permission Scopes.

Defines roles, data access boundaries, and credential validation schemas
compliant with Sections A6 and B8 of the platform specification.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class UserRole(str, Enum):
    """Platform roles aligned with Vridhi Financial Services hierarchy."""
    CRO = "CRO"
    HEAD_CREDIT_RISK = "HEAD_CREDIT_RISK"
    CREDIT_ANALYST = "CREDIT_ANALYST"
    BRANCH_CREDIT_MGR = "BRANCH_CREDIT_MGR"
    LOAN_OFFICER = "LOAN_OFFICER"
    HEAD_COMPLIANCE = "HEAD_COMPLIANCE"
    SYSTEM_ADMIN = "SYSTEM_ADMIN"
    EXTERNAL_AUDITOR = "EXTERNAL_AUDITOR"
    BOARD_MEMBER = "BOARD_MEMBER"


class DataScope(str, Enum):
    """Data visibility scope per role."""
    ALL = "ALL"
    REGIONAL = "REGIONAL"
    OWN_BRANCH = "OWN_BRANCH"
    ASSIGNED_PORTFOLIO = "ASSIGNED_PORTFOLIO"
    OWN_APPLICATIONS = "OWN_APPLICATIONS"


class UserProfile(BaseModel):
    """Authenticated user profile with assigned RBAC scope."""
    user_id: str
    username: str
    email: str
    full_name: str
    role: UserRole
    data_scope: DataScope
    branch_id: Optional[str] = None
    is_active: bool = True
    mfa_verified: bool = False


class TokenPayload(BaseModel):
    """Decoded JWT claims payload."""
    sub: str  # user_id
    username: str
    role: UserRole
    data_scope: DataScope
    branch_id: Optional[str] = None
    mfa_verified: bool = False
    exp: int


class LoginRequest(BaseModel):
    """SAML/SSO mock login authentication payload."""
    username: str
    password: str
    mfa_code: Optional[str] = None


class TokenResponse(BaseModel):
    """JWT bearer token response."""
    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int
    user: UserProfile
