"""Workflow Schemas for Credit Overrides and Approval Chains.

Implements the multi-level override ladder per CFG-WF-001.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class OverrideStatus(str, Enum):
    PENDING_BRANCH_MGR = "PENDING_BRANCH_MGR"
    PENDING_HEAD_CREDIT = "PENDING_HEAD_CREDIT"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class OverrideRequestCreate(BaseModel):
    account_id: str
    exposure_amount: float = Field(..., gt=0)
    current_cibil_score: int
    requested_limit: float = Field(..., gt=0)
    justification: str = Field(..., min_length=10)


class OverrideAction(BaseModel):
    action: str = Field(..., pattern="^(APPROVE|REJECT)$")
    comments: str = Field(..., min_length=5)


class OverrideRecord(BaseModel):
    override_id: str
    account_id: str
    initiator_id: str
    initiator_role: str
    exposure_amount: float
    current_cibil_score: int
    requested_limit: float
    justification: str
    status: OverrideStatus
    level_required: int
    created_at_utc: str
    approved_by: Optional[str] = None
    approval_comments: Optional[str] = None
