"""Unit and Regression Tests for Credit Risk Engine & RBI IRAC Provisioning."""

import pytest
from src.modules.credit_risk.engine import credit_risk_engine
from src.modules.credit_risk.models import AssetClassification, LoanAccount, ProductType


def test_cibil_gate_enforcement():
    """Verify bureau score thresholds (CFG-CR-003)."""
    # Floor: 650+
    decision_pass, ref_pass = credit_risk_engine.evaluate_cibil_gate(710)
    assert decision_pass == "AUTO_APPROVED"
    assert ref_pass is False

    # Referral: 600 - 649
    decision_ref, ref_needed = credit_risk_engine.evaluate_cibil_gate(625)
    assert decision_ref == "REFER_CREDIT_COMMITTEE"
    assert ref_needed is True

    # Reject: < 600
    decision_rej, ref_rej = credit_risk_engine.evaluate_cibil_gate(580)
    assert decision_rej == "REJECTED_BELOW_FLOOR"
    assert ref_rej is False

    # No hit
    decision_nh, ref_nh = credit_risk_engine.evaluate_cibil_gate(-1)
    assert decision_nh == "NO_HIT_REFERRED"
    assert ref_nh is True


def test_standard_asset_provisioning():
    """Standard loans (0 DPD) require 0.40% provisioning."""
    loan = LoanAccount(
        account_id="ACC_STD_TEST",
        customer_id="CUST_001",
        customer_name="Alpha Tech",
        product_type=ProductType.SME_LENDING,
        sanctioned_amount=10_000_000.0,
        outstanding_principal=8_000_000.0,
        current_dpd=0,
        cibil_score=750,
    )
    res = credit_risk_engine.evaluate_account(loan)
    assert res.asset_classification == AssetClassification.STANDARD
    assert res.is_npa is False
    assert res.required_provision_amount == 32_000.0  # 8M * 0.004


def test_substandard_asset_provisioning_nbfc_nd_si():
    """Sub-Standard loans (>90 DPD) require uniform 10% provisioning under RBI IRAC."""
    loan = LoanAccount(
        account_id="ACC_SUB_TEST",
        customer_id="CUST_002",
        customer_name="Beta Logistics",
        product_type=ProductType.VEHICLE_FINANCE,
        sanctioned_amount=5_000_000.0,
        outstanding_principal=4_000_000.0,
        current_dpd=95,
        cibil_score=620,
    )
    res = credit_risk_engine.evaluate_account(loan)
    assert res.asset_classification == AssetClassification.SUB_STANDARD
    assert res.is_npa is True
    assert res.required_provision_amount == 400_000.0  # 4M * 0.10


def test_doubtful_provisioning_split():
    """Doubtful 1 requires 25% on secured portion and 100% on unsecured portion."""
    loan = LoanAccount(
        account_id="ACC_D1_TEST",
        customer_id="CUST_003",
        customer_name="Gamma Industries",
        product_type=ProductType.SME_LENDING,
        sanctioned_amount=10_000_000.0,
        outstanding_principal=6_000_000.0,
        current_dpd=400,
        secured_percentage=0.50,  # 3M secured, 3M unsecured
        cibil_score=550,
    )
    res = credit_risk_engine.evaluate_account(loan)
    assert res.asset_classification == AssetClassification.DOUBTFUL_1
    assert res.is_npa is True
    # Secured: 3M * 25% = 750k; Unsecured: 3M * 100% = 3M; Total = 3.75M
    assert res.required_provision_amount == 3_750_000.0
