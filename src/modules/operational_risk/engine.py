"""Operational Risk Engine.

Monitors Key Risk Indicators (KRIs), tracks severity bands, and classifies loss events.
"""

from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from src.common.logging.logger import get_logger

logger = get_logger("modules.operational_risk")


class KRIStatus(str, Enum):
    GREEN = "GREEN"    # Normal: < 60%
    AMBER = "AMBER"    # Elevated Monitoring: 60% - 80%
    RED = "RED"        # Breach / Critical Action Required: > 80%


class IncidentSeverity(str, Enum):
    NEGLIGIBLE = "NEGLIGIBLE"  # < 1 Lakh
    MINOR = "MINOR"            # 1 - 10 Lakhs
    MODERATE = "MODERATE"      # 10 Lakhs - 1 Crore
    MAJOR = "MAJOR"            # 1 Crore - 10 Crores
    CRITICAL = "CRITICAL"      # > 10 Crores


class KRIThresholdConfig(BaseModel):
    kri_id: str
    kri_name: str
    department: str
    unit: str
    amber_threshold: float = Field(default=60.0)
    red_threshold: float = Field(default=80.0)


class OperationalIncident(BaseModel):
    incident_id: str
    description: str
    department: str
    loss_amount_inr: float = Field(..., ge=0.0)
    root_cause: str


class OperationalRiskEngine:
    """Evaluates KRI metrics and classifies operational risk loss incidents."""

    def __init__(self) -> None:
        self.kri_registry: Dict[str, KRIThresholdConfig] = {
            "KRI-OPS-01": KRIThresholdConfig(
                kri_id="KRI-OPS-01",
                kri_name="Branch Cash Reconciliation Discrepancy Rate",
                department="Branch Operations",
                unit="percentage",
                amber_threshold=60.0,
                red_threshold=80.0,
            ),
            "KRI-IT-02": KRIThresholdConfig(
                kri_id="KRI-IT-02",
                kri_name="Core Banking Infrastructure CPU & Memory Saturation",
                department="IT Infrastructure",
                unit="percentage",
                amber_threshold=70.0,
                red_threshold=85.0,
            ),
            "KRI-HR-03": KRIThresholdConfig(
                kri_id="KRI-HR-03",
                kri_name="Branch Loan Officer Quarterly Attrition Rate",
                department="Human Resources",
                unit="percentage",
                amber_threshold=15.0,
                red_threshold=25.0,
            ),
        }

    def evaluate_kri(self, kri_id: str, current_value: float) -> Dict[str, str]:
        """Calculates 3-tier KRI breach status (CFG-OR-001)."""
        config = self.kri_registry.get(kri_id)
        if not config:
            return {"kri_id": kri_id, "status": "UNKNOWN", "action": "NO_CONFIG_FOUND"}

        if current_value >= config.red_threshold:
            status = KRIStatus.RED
            action = "IMMEDIATE_ESCALATION_TO_CRO"
        elif current_value >= config.amber_threshold:
            status = KRIStatus.AMBER
            action = "ENHANCED_SUPERVISION_LOGGED"
        else:
            status = KRIStatus.GREEN
            action = "OPERATING_WITHIN_APPETITE"

        return {
            "kri_id": kri_id,
            "kri_name": config.kri_name,
            "current_value": str(current_value),
            "status": status.value,
            "action": action,
        }

    def classify_loss_incident(self, incident: OperationalIncident) -> IncidentSeverity:
        """Classifies operational loss severity into calibrated bands (CFG-OR-002)."""
        amount = incident.loss_amount_inr
        if amount < 100_000:
            severity = IncidentSeverity.NEGLIGIBLE
        elif amount <= 1_000_000:
            severity = IncidentSeverity.MINOR
        elif amount <= 10_000_000:
            severity = IncidentSeverity.MODERATE
        elif amount <= 100_000_000:
            severity = IncidentSeverity.MAJOR
        else:
            severity = IncidentSeverity.CRITICAL

        logger.info(
            "Classified operational loss incident",
            incident_id=incident.incident_id,
            amount=amount,
            severity=severity.value,
        )
        return severity


operational_risk_engine = OperationalRiskEngine()
