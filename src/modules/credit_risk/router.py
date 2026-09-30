"""Credit Risk & Limit Override API Endpoints."""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from src.common.exceptions.base import ZERMPBaseException
from src.common.security.dependencies import RequireRole, TokenPayload, get_current_user
from src.common.telemetry.metrics import CREDIT_ASSESSMENTS_TOTAL, NPA_PROVISIONS_INR_TOTAL
from src.modules.auth.models import UserRole
from src.modules.credit_risk.engine import credit_risk_engine
from src.modules.credit_risk.models import CreditAssessmentResult, LoanAccount
from src.modules.workflow.models import (
    OverrideAction,
    OverrideRecord,
    OverrideRequestCreate,
)
from src.modules.workflow.service import workflow_service

router = APIRouter(prefix="/credit", tags=["Credit Risk & Origination"])


@router.post("/assess", response_model=CreditAssessmentResult)
async def assess_loan_account(
    loan: LoanAccount,
    user: TokenPayload = Depends(
        RequireRole([
            UserRole.CRO,
            UserRole.HEAD_CREDIT_RISK,
            UserRole.CREDIT_ANALYST,
            UserRole.BRANCH_CREDIT_MGR,
            UserRole.LOAN_OFFICER,
        ])
    ),
):
    """Evaluate credit scorecard, ECL, and RBI IRAC provisioning for a loan account."""
    result = credit_risk_engine.evaluate_account(loan)

    # Instrument Prometheus domain metrics
    CREDIT_ASSESSMENTS_TOTAL.labels(
        product_type=result.product_type.value,
        asset_classification=result.asset_classification.value,
        is_npa=str(result.is_npa).lower(),
    ).inc()

    NPA_PROVISIONS_INR_TOTAL.labels(
        asset_classification=result.asset_classification.value
    ).inc(result.required_provision_amount)

    return result


@router.post("/override/request", response_model=OverrideRecord)
async def request_credit_override(
    req: OverrideRequestCreate,
    user: TokenPayload = Depends(
        RequireRole([UserRole.CREDIT_ANALYST, UserRole.LOAN_OFFICER, UserRole.BRANCH_CREDIT_MGR])
    ),
):
    """Initiate a credit limit override workflow (CFG-WF-001)."""
    return workflow_service.submit_override_request(req, user)


@router.post("/override/{override_id}/decide", response_model=OverrideRecord)
async def decide_credit_override(
    override_id: str,
    action: OverrideAction,
    user: TokenPayload = Depends(
        RequireRole([UserRole.BRANCH_CREDIT_MGR, UserRole.HEAD_CREDIT_RISK, UserRole.CRO])
    ),
):
    """Approve or reject a credit limit override enforcing Segregation of Duties."""
    try:
        return workflow_service.decide_override(override_id, action, user)
    except ZERMPBaseException as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN if "SOD" in exc.error_code else status.HTTP_400_BAD_REQUEST,
            detail=exc.message,
        ) from exc


@router.get("/overrides/pending", response_model=List[OverrideRecord])
async def list_pending_overrides(
    user: TokenPayload = Depends(
        RequireRole([UserRole.CRO, UserRole.HEAD_CREDIT_RISK, UserRole.BRANCH_CREDIT_MGR])
    ),
):
    """List all pending credit limit overrides awaiting review."""
    return workflow_service.list_pending_overrides()
