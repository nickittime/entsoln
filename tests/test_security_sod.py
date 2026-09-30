"""Unit Tests for Authentication, MFA, RBAC & Segregation of Duties (SoD)."""

import pytest
from src.common.exceptions.base import ZERMPBaseException
from src.modules.auth.models import DataScope, TokenPayload, UserRole
from src.modules.auth.service import auth_service
from src.modules.workflow.models import OverrideAction, OverrideRequestCreate, OverrideStatus
from src.modules.workflow.service import workflow_service


def test_mfa_enforcement_for_elevated_roles():
    """Ensure elevated roles (CRO, Admin) strictly require MFA codes."""
    with pytest.raises(ZERMPBaseException) as exc_info:
        auth_service.authenticate_user("cro_ananya", "Vridhi@Cro2026!", mfa_code=None)
    assert exc_info.value.error_code == "MFA_REQUIRED"

    # Authenticate successfully with valid MFA
    user = auth_service.authenticate_user("cro_ananya", "Vridhi@Cro2026!", mfa_code="123456")
    assert user.mfa_verified is True
    assert user.role == UserRole.CRO


def test_sod_anti_self_approval():
    """Enforce 4-Eyes Principle: Initiator cannot self-approve override requests."""
    initiator = TokenPayload(
        sub="USR-BRANCH-01",
        username="branch_mgr_neha",
        role=UserRole.BRANCH_CREDIT_MGR,
        data_scope=DataScope.OWN_BRANCH,
        exp=9999999999,
    )
    req = OverrideRequestCreate(
        account_id="ACC_SOD_UNIT_01",
        exposure_amount=20_000_000.0,
        current_cibil_score=630,
        requested_limit=25_000_000.0,
        justification="Strong seasonal cashflows",
    )
    record = workflow_service.submit_override_request(req, initiator)

    # Attempt self-approval -> Must raise SOD_VIOLATION
    action = OverrideAction(action="APPROVE", comments="Self approving")
    with pytest.raises(ZERMPBaseException) as exc_info:
        workflow_service.decide_override(record.override_id, action, initiator)
    assert exc_info.value.error_code == "SOD_VIOLATION"


def test_escalation_ladder_threshold():
    """Exposures exceeding INR 5 Crore must route to Head of Credit or CRO."""
    analyst = TokenPayload(
        sub="USR-ANALYST-01",
        username="analyst_arun",
        role=UserRole.CREDIT_ANALYST,
        data_scope=DataScope.ASSIGNED_PORTFOLIO,
        exp=9999999999,
    )
    req_large = OverrideRequestCreate(
        account_id="ACC_LARGE_UNIT_02",
        exposure_amount=70_000_000.0,  # 7 Crore
        current_cibil_score=640,
        requested_limit=85_000_000.0,
        justification="Large infrastructure working capital",
    )
    record = workflow_service.submit_override_request(req_large, analyst)
    assert record.status == OverrideStatus.PENDING_HEAD_CREDIT
    assert record.level_required == 3
