"""Regulatory Reporting API Endpoints."""

from typing import Any, Dict
from fastapi import APIRouter, Depends
from src.common.security.dependencies import RequireRole, TokenPayload
from src.modules.auth.models import UserRole
from src.modules.credit_risk.models import CreditAssessmentResult
from src.modules.regulatory_reporting.engine import regulatory_engine

router = APIRouter(prefix="/regulatory", tags=["Regulatory Reporting & RBI Compliance"])


@router.post("/generate-nbs7")
async def generate_nbs7_return(
    quarter: str = "Q4-2026",
    user: TokenPayload = Depends(RequireRole([UserRole.CRO, UserRole.HEAD_COMPLIANCE])),
) -> Dict[str, Any]:
    """Compile and archive RBI NBS-7 return in immutable S3 WORM storage."""
    # Build sample portfolio representing Vridhi's risk distribution
    from src.modules.credit_risk.models import AssetClassification, ProductType
    dummy_assessments = [
        CreditAssessmentResult(
            account_id="ACC_REG_01",
            product_type=ProductType.SME_LENDING,
            cibil_score=720,
            cibil_decision="APPROVED",
            requires_override=False,
            scorecard_points=680,
            probability_of_default=0.015,
            loss_given_default=0.35,
            exposure_at_default=120_000_000.0,
            expected_credit_loss=630_000.0,
            asset_classification=AssetClassification.STANDARD,
            is_npa=False,
            provision_percentage=0.004,
            required_provision_amount=480_000.0,
            crilc_reportable=True,
        ),
        CreditAssessmentResult(
            account_id="ACC_REG_02",
            product_type=ProductType.VEHICLE_FINANCE,
            cibil_score=580,
            cibil_decision="REFERRED",
            requires_override=True,
            scorecard_points=490,
            probability_of_default=0.12,
            loss_given_default=0.40,
            exposure_at_default=25_000_000.0,
            expected_credit_loss=1_200_000.0,
            asset_classification=AssetClassification.SUB_STANDARD,
            is_npa=True,
            provision_percentage=0.10,
            required_provision_amount=2_500_000.0,
            crilc_reportable=False,
        ),
    ]

    report = regulatory_engine.compile_nbs7_return(dummy_assessments, quarter)
    archive = regulatory_engine.archive_report_to_s3(report, "NBS-7")
    return {
        "report_summary": report["summary_metrics"],
        "archive_details": archive,
    }
