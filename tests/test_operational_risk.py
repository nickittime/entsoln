"""Unit Tests for Operational Risk Key Risk Indicators & Incident Severity."""

import pytest
from src.modules.operational_risk.engine import (
    IncidentSeverity,
    OperationalIncident,
    operational_risk_engine,
)


def test_kri_threshold_evaluation():
    """Verify 3-tier KRI breach triggers (Green <60%, Amber 60-80%, Red >80%)."""
    green = operational_risk_engine.evaluate_kri("KRI-OPS-01", 45.0)
    assert green["status"] == "GREEN"

    amber = operational_risk_engine.evaluate_kri("KRI-OPS-01", 72.0)
    assert amber["status"] == "AMBER"

    red = operational_risk_engine.evaluate_kri("KRI-OPS-01", 88.0)
    assert red["status"] == "RED"
    assert red["action"] == "IMMEDIATE_ESCALATION_TO_CRO"


def test_incident_loss_bands():
    """Validate operational loss severity classification (CFG-OR-002)."""
    inc_minor = OperationalIncident(
        incident_id="INC-T-01",
        description="Cash drawer shortage",
        department="Branch Operations",
        loss_amount_inr=50_000.0,
        root_cause="Teller balancing error",
    )
    assert operational_risk_engine.classify_loss_incident(inc_minor) == IncidentSeverity.NEGLIGIBLE

    inc_major = OperationalIncident(
        incident_id="INC-T-02",
        description="Vendor data breach settlement",
        department="IT Security",
        loss_amount_inr=20_000_000.0,
        root_cause="Third-party API vulnerability",
    )
    assert operational_risk_engine.classify_loss_incident(inc_major) == IncidentSeverity.MAJOR
