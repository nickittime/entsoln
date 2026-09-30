"""Credit Limit Override Workflow Engine.

Orchestrates multi-level approvals and enforces SoD constraints (CFG-WF-001).
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional
import uuid
from src.common.exceptions.base import ZERMPBaseException
from src.common.logging.logger import get_logger
from src.modules.auth.models import TokenPayload, UserRole
from src.modules.workflow.models import (
    OverrideAction,
    OverrideRecord,
    OverrideRequestCreate,
    OverrideStatus,
)

logger = get_logger("modules.workflow")

# In-memory storage for active override requests
OVERRIDE_STORE: Dict[str, OverrideRecord] = {}


class WorkflowService:
    """Manages credit override submissions, tier evaluations, and decision recording."""

    def submit_override_request(
        self, req: OverrideRequestCreate, user: TokenPayload
    ) -> OverrideRecord:
        override_id = f"OVR-{uuid.uuid4().hex[:8].upper()}"

        # Level determination: <= 5 Crore requires Branch Manager; > 5 Crore requires Head of Credit
        is_large_exposure = req.exposure_amount > 50_000_000.0
        initial_status = (
            OverrideStatus.PENDING_HEAD_CREDIT
            if is_large_exposure
            else OverrideStatus.PENDING_BRANCH_MGR
        )
        level_required = 3 if is_large_exposure else 2

        record = OverrideRecord(
            override_id=override_id,
            account_id=req.account_id,
            initiator_id=user.sub,
            initiator_role=user.role.value,
            exposure_amount=req.exposure_amount,
            current_cibil_score=req.current_cibil_score,
            requested_limit=req.requested_limit,
            justification=req.justification,
            status=initial_status,
            level_required=level_required,
            created_at_utc=datetime.now(timezone.utc).isoformat(),
        )

        OVERRIDE_STORE[override_id] = record
        logger.info(
            "Submitted credit limit override request",
            override_id=override_id,
            account_id=req.account_id,
            status=initial_status.value,
            level=level_required,
        )
        return record

    def decide_override(
        self, override_id: str, action_req: OverrideAction, user: TokenPayload
    ) -> OverrideRecord:
        record = OVERRIDE_STORE.get(override_id)
        if not record:
            raise ZERMPBaseException("Override request not found", error_code="NOT_FOUND")

        # 1. 4-Eyes Check: Initiator cannot self-approve
        if record.initiator_id == user.sub:
            raise ZERMPBaseException(
                "Segregation of Duties violation: Initiator cannot self-approve override",
                error_code="SOD_VIOLATION",
            )

        # 2. Authorization Ladder Check
        if record.status == OverrideStatus.PENDING_BRANCH_MGR:
            allowed = {UserRole.BRANCH_CREDIT_MGR, UserRole.HEAD_CREDIT_RISK, UserRole.CRO}
            if user.role not in allowed:
                raise ZERMPBaseException(
                    "Only Branch Credit Managers, Head of Credit Risk, or CRO can decide this request",
                    error_code="FORBIDDEN_APPROVAL",
                )
        elif record.status == OverrideStatus.PENDING_HEAD_CREDIT:
            allowed = {UserRole.HEAD_CREDIT_RISK, UserRole.CRO}
            if user.role not in allowed:
                raise ZERMPBaseException(
                    "Exposures exceeding INR 5 Crore require approval from Head of Credit Risk or CRO",
                    error_code="ESCALATION_REQUIRED",
                )
        else:
            raise ZERMPBaseException(
                f"Cannot decide override in status {record.status.value}",
                error_code="INVALID_STATE",
            )

        # 3. Update Decision
        if action_req.action == "APPROVE":
            record.status = OverrideStatus.APPROVED
        else:
            record.status = OverrideStatus.REJECTED

        record.approved_by = f"{user.username} ({user.role.value})"
        record.approval_comments = action_req.comments
        OVERRIDE_STORE[override_id] = record

        logger.info(
            "Processed credit override decision",
            override_id=override_id,
            decision=record.status.value,
            approver=user.username,
        )
        return record

    def list_pending_overrides(self) -> List[OverrideRecord]:
        return [r for r in OVERRIDE_STORE.values() if "PENDING" in r.status.value]


workflow_service = WorkflowService()
