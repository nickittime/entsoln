"""Regulatory Reporting Engine for RBI Submissions.

Compiles automated NBS-7 returns and CRILC large borrower extracts,
generating cryptographic SHA-256 digests for archival in S3 WORM storage.
"""

from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Dict, List
from src.common.config.settings import get_settings
from src.common.logging.logger import get_logger
from src.common.storage.s3_client import s3_manager
from src.modules.credit_risk.models import CreditAssessmentResult

logger = get_logger("modules.regulatory_reporting")
settings = get_settings()


class RegulatoryReportingEngine:
    """Generates auditable regulatory packages compliant with RBI Master Directions."""

    def compile_nbs7_return(
        self,
        assessments: List[CreditAssessmentResult],
        reporting_quarter: str = "Q4-2026",
    ) -> Dict[str, Any]:
        """Compiles the RBI NBS-7 quarterly return on asset quality and provisioning."""
        total_accounts = len(assessments)
        total_exposure = sum(a.exposure_at_default for a in assessments)

        standard_advances = sum(
            a.exposure_at_default
            for a in assessments
            if a.asset_classification.value in ("STANDARD", "SMA_0", "SMA_1", "SMA_2")
        )
        substandard_advances = sum(
            a.exposure_at_default for a in assessments if a.asset_classification.value == "SUB_STANDARD"
        )
        doubtful_advances = sum(
            a.exposure_at_default
            for a in assessments
            if a.asset_classification.value in ("DOUBTFUL_1", "DOUBTFUL_2", "DOUBTFUL_3")
        )
        loss_advances = sum(
            a.exposure_at_default for a in assessments if a.asset_classification.value == "LOSS"
        )

        gross_npa = substandard_advances + doubtful_advances + loss_advances
        gross_npa_ratio = (gross_npa / total_exposure * 100.0) if total_exposure > 0 else 0.0

        total_provisions_held = sum(a.required_provision_amount for a in assessments)
        net_npa = max(0.0, gross_npa - total_provisions_held)
        net_npa_ratio = (net_npa / (total_exposure - total_provisions_held) * 100.0) if total_exposure > total_provisions_held else 0.0
        pcr = (total_provisions_held / gross_npa * 100.0) if gross_npa > 0 else 100.0

        report_payload = {
            "return_type": "RBI_NBS_7",
            "institution_name": "Vridhi Financial Services Limited",
            "rbi_registration": "N-13.02215",
            "category": "NBFC-ICC (Systemically Important Non-Deposit Taking)",
            "reporting_quarter": reporting_quarter,
            "generated_timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "summary_metrics": {
                "total_loan_accounts": total_accounts,
                "total_gross_exposure_inr": round(total_exposure, 2),
                "standard_advances_inr": round(standard_advances, 2),
                "substandard_advances_inr": round(substandard_advances, 2),
                "doubtful_advances_inr": round(doubtful_advances, 2),
                "loss_advances_inr": round(loss_advances, 2),
                "gross_npa_inr": round(gross_npa, 2),
                "gross_npa_ratio_percentage": round(gross_npa_ratio, 2),
                "net_npa_inr": round(net_npa, 2),
                "net_npa_ratio_percentage": round(net_npa_ratio, 2),
                "total_provisions_required_inr": round(total_provisions_held, 2),
                "provision_coverage_ratio_percentage": round(pcr, 2),
            },
        }

        return report_payload

    def compile_crilc_report(
        self, assessments: List[CreditAssessmentResult]
    ) -> Dict[str, Any]:
        """Extracts exposures >= INR 5 Crore for Central Repository of Large Credits."""
        large_exposures = [a for a in assessments if a.crilc_reportable]
        return {
            "return_type": "RBI_CRILC_MAIN",
            "institution": "Vridhi Financial Services Limited",
            "threshold_inr": 50_000_000.0,
            "record_count": len(large_exposures),
            "generated_timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "records": [
                {
                    "account_id": item.account_id,
                    "product": item.product_type.value,
                    "exposure_inr": item.exposure_at_default,
                    "asset_class": item.asset_classification.value,
                    "is_npa": item.is_npa,
                }
                for item in large_exposures
            ],
        }

    def archive_report_to_s3(
        self, report_data: Dict[str, Any], return_code: str
    ) -> Dict[str, str]:
        """Serializes report, computes cryptographic SHA-256 hash, and archives to WORM S3."""
        json_payload = json.dumps(report_data, indent=2, sort_keys=True).encode("utf-8")
        sha256_hash = hashlib.sha256(json_payload).hexdigest()

        timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        key = f"rbi_returns/{return_code}/{return_code}_{timestamp_str}_{sha256_hash[:8]}.json"

        s3_uri = s3_manager.upload_bytes(
            bucket=settings.S3_BUCKET_REPORTS,
            key=key,
            data=json_payload,
            content_type="application/json",
            metadata={
                "sha256_checksum": sha256_hash,
                "return_code": return_code,
                "immutable_retention_years": "7",
            },
        )

        logger.info(
            "Regulatory return archived in WORM storage",
            return_code=return_code,
            s3_uri=s3_uri,
            checksum=sha256_hash,
        )

        return {
            "s3_uri": s3_uri,
            "sha256_checksum": sha256_hash,
            "byte_size": str(len(json_payload)),
        }


regulatory_engine = RegulatoryReportingEngine()
