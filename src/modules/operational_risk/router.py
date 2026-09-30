"""Operational Risk API Endpoints."""

from typing import Dict
from fastapi import APIRouter, Depends
from src.common.security.dependencies import RequireRole, TokenPayload
from src.modules.auth.models import UserRole
from src.modules.operational_risk.engine import (
    IncidentSeverity,
    OperationalIncident,
    operational_risk_engine,
)

router = APIRouter(prefix="/ops", tags=["Operational Risk & KRIs"])


@router.get("/kri/{kri_id}")
async def evaluate_kri_status(
    kri_id: str,
    value: float,
    user: TokenPayload = Depends(
        RequireRole([UserRole.CRO, UserRole.HEAD_COMPLIANCE, UserRole.SYSTEM_ADMIN, UserRole.EXTERNAL_AUDITOR])
    ),
) -> Dict[str, str]:
    """Calculate 3-tier KRI breach status (CFG-OR-001)."""
    return operational_risk_engine.evaluate_kri(kri_id, value)


@router.post("/incident", response_model=Dict[str, str])
async def log_loss_incident(
    incident: OperationalIncident,
    user: TokenPayload = Depends(
        RequireRole([UserRole.CRO, UserRole.HEAD_COMPLIANCE, UserRole.BRANCH_CREDIT_MGR])
    ),
):
    """Classify and record operational loss incidents into severity categories."""
    severity = operational_risk_engine.classify_loss_incident(incident)
    return {
        "incident_id": incident.incident_id,
        "loss_amount_inr": str(incident.loss_amount_inr),
        "severity": severity.value,
        "logged_by": user.username,
    }
