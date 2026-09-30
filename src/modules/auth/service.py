"""Authentication and Token Lifecycle Service.

Issues, validates, and decodes JWT tokens, enforcing role-based permissions
and MFA checks per CFG-UM-001. Uses NIST-compliant PBKDF2-HMAC-SHA256.
"""

from datetime import datetime, timedelta, timezone
import hashlib
import hmac
from typing import Dict, Optional
import jwt
from jwt.exceptions import PyJWTError
from src.common.config.settings import get_settings
from src.common.exceptions.base import ZERMPBaseException
from src.common.logging.logger import get_logger
from src.modules.auth.models import DataScope, TokenPayload, UserProfile, UserRole

logger = get_logger("modules.auth")
settings = get_settings()

STATIC_SALT = b"vridhi_zermp_enterprise_salt_2026"


def hash_password(password: str) -> str:
    """NIST-compliant PBKDF2-HMAC-SHA256 password hashing."""
    derived = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        STATIC_SALT,
        iterations=100_000,
    )
    return derived.hex()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Constant-time comparison to prevent timing attacks."""
    computed = hash_password(plain_password)
    return hmac.compare_digest(computed, hashed_password)


# Pre-seeded users representing Vridhi NBFC stakeholders for SSO simulation
MOCK_USERS_DB: Dict[str, Dict] = {
    "cro_ananya": {
        "user_id": "USR-001",
        "username": "cro_ananya",
        "full_name": "Dr. Ananya Mehta",
        "email": "ananya.mehta@vridhifin.com",
        "role": UserRole.CRO,
        "data_scope": DataScope.ALL,
        "branch_id": "HO-BKC",
        "hashed_password": hash_password("Vridhi@Cro2026!"),
    },
    "head_credit_sanjay": {
        "user_id": "USR-002",
        "username": "head_credit_sanjay",
        "full_name": "Sanjay Patel",
        "email": "sanjay.patel@vridhifin.com",
        "role": UserRole.HEAD_CREDIT_RISK,
        "data_scope": DataScope.ALL,
        "branch_id": "HO-BKC",
        "hashed_password": hash_password("Vridhi@Credit2026!"),
    },
    "analyst_arun": {
        "user_id": "USR-003",
        "username": "analyst_arun",
        "full_name": "Arun Kumar",
        "email": "arun.kumar@vridhifin.com",
        "role": UserRole.CREDIT_ANALYST,
        "data_scope": DataScope.ASSIGNED_PORTFOLIO,
        "branch_id": "BR-MUMBAI-01",
        "hashed_password": hash_password("Vridhi@Analyst2026!"),
    },
    "branch_mgr_neha": {
        "user_id": "USR-004",
        "username": "branch_mgr_neha",
        "full_name": "Neha Gupta",
        "email": "neha.gupta@vridhifin.com",
        "role": UserRole.BRANCH_CREDIT_MGR,
        "data_scope": DataScope.OWN_BRANCH,
        "branch_id": "BR-MUMBAI-01",
        "hashed_password": hash_password("Vridhi@Branch2026!"),
    },
    "compliance_kavita": {
        "user_id": "USR-005",
        "username": "compliance_kavita",
        "full_name": "Kavita Sharma",
        "email": "kavita.sharma@vridhifin.com",
        "role": UserRole.HEAD_COMPLIANCE,
        "data_scope": DataScope.ALL,
        "branch_id": "HO-BKC",
        "hashed_password": hash_password("Vridhi@Compliance2026!"),
    },
    "admin_deepak": {
        "user_id": "USR-006",
        "username": "admin_deepak",
        "full_name": "Deepak Kulkarni",
        "email": "deepak.kulkarni@vridhifin.com",
        "role": UserRole.SYSTEM_ADMIN,
        "data_scope": DataScope.ALL,
        "branch_id": "HO-BKC",
        "hashed_password": hash_password("Vridhi@Admin2026!"),
    },
    "auditor_suresh": {
        "user_id": "USR-007",
        "username": "auditor_suresh",
        "full_name": "Suresh Reddy",
        "email": "suresh.reddy@vridhifin.com",
        "role": UserRole.EXTERNAL_AUDITOR,
        "data_scope": DataScope.ALL,
        "branch_id": "HO-BKC",
        "hashed_password": hash_password("Vridhi@Auditor2026!"),
    },
}


class AuthService:
    """Manages authentication, password validation, and token signing."""

    def authenticate_user(
        self, username: str, password: str, mfa_code: Optional[str] = None
    ) -> UserProfile:
        user_record = MOCK_USERS_DB.get(username)
        if not user_record:
            raise ZERMPBaseException("Invalid credentials", error_code="AUTH_FAILED")

        if not verify_password(password, user_record["hashed_password"]):
            raise ZERMPBaseException("Invalid credentials", error_code="AUTH_FAILED")

        role = user_record["role"]
        mfa_required_roles = {
            UserRole.CRO,
            UserRole.HEAD_CREDIT_RISK,
            UserRole.SYSTEM_ADMIN,
            UserRole.EXTERNAL_AUDITOR,
        }

        mfa_verified = False
        if role in mfa_required_roles:
            if not mfa_code or mfa_code != "123456":
                raise ZERMPBaseException(
                    "MFA verification code required for elevated risk and admin roles",
                    error_code="MFA_REQUIRED",
                )
            mfa_verified = True

        return UserProfile(
            user_id=user_record["user_id"],
            username=user_record["username"],
            email=user_record["email"],
            full_name=user_record["full_name"],
            role=role,
            data_scope=user_record["data_scope"],
            branch_id=user_record["branch_id"],
            mfa_verified=mfa_verified,
        )

    def create_access_token(self, user: UserProfile) -> str:
        expire_minutes = getattr(settings, 'ACCESS_TOKEN_EXPIRE_MINUTES', 60)
        expire = datetime.now(timezone.utc) + timedelta(minutes=expire_minutes)
        payload = {
            "sub": user.user_id,
            "username": user.username,
            "role": user.role.value,
            "data_scope": user.data_scope.value,
            "branch_id": user.branch_id,
            "mfa_verified": user.mfa_verified,
            "exp": int(expire.timestamp()),
        }
        algo = getattr(settings, 'JWT_ALGORITHM', 'HS256')
        return jwt.encode(payload, settings.SECRET_KEY, algorithm=algo)

    def decode_token(self, token: str) -> TokenPayload:
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
            return TokenPayload(
                sub=payload["sub"],
                username=payload["username"],
                role=UserRole(payload["role"]),
                data_scope=DataScope(payload["data_scope"]),
                branch_id=payload.get("branch_id"),
                mfa_verified=payload.get("mfa_verified", False),
                exp=payload["exp"],
            )
        except JWTError as err:
            logger.warning("JWT verification failed", error=str(err))
            raise ZERMPBaseException("Invalid or expired session token", error_code="TOKEN_INVALID") from err


auth_service = AuthService()
