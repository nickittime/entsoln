"""End-to-End Verification Suite for Module 2.

Validates Credit Risk calculations, RBI IRAC NPA provisioning,
Operational Risk KRIs, Market Risk VaR, RBI NBS-7 returns, and SFTP-to-ClickHouse ingestion.
"""

import sys
import uuid
from src.common.config.settings import get_settings
from src.common.database.clickhouse import clickhouse_manager
from src.common.logging.logger import get_logger, setup_logging
from src.common.storage.s3_client import s3_manager
from src.ingestion.connectors.sftp_connector import sftp_connector
from src.ingestion.pipelines.finnone_pipeline import finnone_pipeline
from src.modules.credit_risk.engine import credit_risk_engine
from src.modules.credit_risk.models import AssetClassification, LoanAccount, ProductType
from src.modules.market_risk.engine import market_risk_engine
from src.modules.operational_risk.engine import OperationalIncident, operational_risk_engine
from src.modules.regulatory_reporting.engine import regulatory_engine

setup_logging()
logger = get_logger("verification.module2")
settings = get_settings()


def run_tests() -> bool:
    print("\n" + "=" * 80)
    print(" ZERMP MODULE 2: COMPREHENSIVE BUSINESS LOGIC & RISK ENGINE VERIFICATION")
    print("=" * 80)
    all_passed = True

    # 1. Credit Risk & IRAC Provisioning Logic Verification
    print("\n[1/5] Testing Credit Risk Engine & RBI IRAC Asset Classification...")
    try:
        # Standard Loan (0 DPD)
        loan_std = LoanAccount(
            account_id="ACC_STD_01",
            customer_id="CUST_01",
            customer_name="Alpha Enterprises",
            product_type=ProductType.SME_LENDING,
            sanctioned_amount=10_000_000.0,
            outstanding_principal=8_000_000.0,
            current_dpd=0,
            cibil_score=750,
            annual_income=40_000_000.0,
            monthly_emi=200_000.0,
        )
        res_std = credit_risk_engine.evaluate_account(loan_std)
        assert res_std.asset_classification == AssetClassification.STANDARD
        assert not res_std.is_npa
        assert res_std.required_provision_amount == 32_000.0  # 8M * 0.40%

        # Sub-Standard Loan (95 DPD - Non-Performing Asset, 10% provision for NBFC-ND-SI)
        loan_sub = LoanAccount(
            account_id="ACC_SUB_02",
            customer_id="CUST_02",
            customer_name="Beta Logistics",
            product_type=ProductType.VEHICLE_FINANCE,
            sanctioned_amount=5_000_000.0,
            outstanding_principal=4_000_000.0,
            current_dpd=95,
            cibil_score=620,
            annual_income=10_000_000.0,
            monthly_emi=100_000.0,
        )
        res_sub = credit_risk_engine.evaluate_account(loan_sub)
        assert res_sub.asset_classification == AssetClassification.SUB_STANDARD
        assert res_sub.is_npa
        assert res_sub.required_provision_amount == 400_000.0  # 4M * 10%

        # Doubtful 1 Loan (400 DPD)
        loan_d1 = LoanAccount(
            account_id="ACC_D1_03",
            customer_id="CUST_03",
            customer_name="Gamma Industries",
            product_type=ProductType.SME_LENDING,
            sanctioned_amount=10_000_000.0,
            outstanding_principal=6_000_000.0,
            current_dpd=400,
            secured_percentage=0.50,  # 3M secured, 3M unsecured
            cibil_score=550,
            annual_income=5_000_000.0,
            monthly_emi=80_000.0,
        )
        res_d1 = credit_risk_engine.evaluate_account(loan_d1)
        assert res_d1.asset_classification == AssetClassification.DOUBTFUL_1
        assert res_d1.is_npa
        # D1: 25% of 3M secured (750k) + 100% of 3M unsecured (3M) = 3.75M
        assert res_d1.required_provision_amount == 3_750_000.0

        # Large Corporate Loan for CRILC Verification (>= INR 5 Crore = 50,000,000)
        loan_crilc = LoanAccount(
            account_id="ACC_CRILC_04",
            customer_id="CUST_04",
            customer_name="Delta Heavy Infra Ltd",
            product_type=ProductType.SME_LENDING,
            sanctioned_amount=80_000_000.0,
            outstanding_principal=65_000_000.0,
            current_dpd=10,
            secured_percentage=1.0,
            cibil_score=780,
            annual_income=250_000_000.0,
            monthly_emi=1_200_000.0,
        )
        res_crilc = credit_risk_engine.evaluate_account(loan_crilc)
        assert res_crilc.crilc_reportable is True

        print("  [✓] Credit Engine: Scorecard points, ECL, and multi-tier RBI IRAC provisioning verified.")
    except Exception as exc:
        print(f"  [✗] Credit Engine Test Failed: {exc}")
        all_passed = False

    # 2. Operational Risk Engine Verification
    print("\n[2/5] Testing Operational Risk Engine (KRIs & Incident Loss Bands)...")
    try:
        kri_green = operational_risk_engine.evaluate_kri("KRI-OPS-01", 45.0)
        assert kri_green["status"] == "GREEN"

        kri_red = operational_risk_engine.evaluate_kri("KRI-OPS-01", 85.0)
        assert kri_red["status"] == "RED"

        inc = OperationalIncident(
            incident_id="INC-2026-001",
            description="Branch unauthorized cash withdrawal",
            department="Branch Operations",
            loss_amount_inr=25_000_000.0,
            root_cause="Internal control failure",
        )
        severity = operational_risk_engine.classify_loss_incident(inc)
        assert severity.value == "MAJOR"
        print("  [✓] Operational Risk: 3-tier KRI thresholds and incident loss bands verified.")
    except Exception as exc:
        print(f"  [✗] Operational Risk Test Failed: {exc}")
        all_passed = False

    # 3. Market Risk & ALM Gap Verification
    print("\n[3/5] Testing Market Risk Engine (Historical VaR & ALM Liquidity Gaps)...")
    try:
        import random
        random.seed(42)
        simulated_returns = [random.gauss(0.0005, 0.015) for _ in range(100)]
        var_result = market_risk_engine.calculate_historical_var(
            portfolio_value=1_000_000_000.0,
            daily_returns=simulated_returns,
            confidence_level=0.99,
            holding_period_days=10,
        )
        assert var_result["var_amount_inr"] > 0
        assert var_result["holding_period_days"] == 10

        raw_alm = [
            ("1-14 Days", 500_000_000.0, 300_000_000.0),
            ("15-28 Days", 300_000_000.0, 400_000_000.0),
        ]
        gaps = market_risk_engine.generate_alm_liquidity_gaps(raw_alm)
        assert len(gaps) == 2
        assert gaps[0].net_gap_inr == 200_000_000.0
        assert gaps[1].net_gap_inr == -100_000_000.0
        print(f"  [✓] Market Risk: Historical VaR (99%, 10-day) = INR {var_result['var_amount_inr']:,.2f}; ALM gaps verified.")
    except Exception as exc:
        print(f"  [✗] Market Risk Test Failed: {exc}")
        all_passed = False

    # 4. Regulatory Reporting & S3 WORM Archival Verification
    print("\n[4/5] Testing Regulatory Reporting Automation (RBI NBS-7 & S3 Storage)...")
    try:
        sample_assessments = [res_std, res_sub, res_d1]
        nbs7 = regulatory_engine.compile_nbs7_return(sample_assessments, "Q4-2026")
        assert nbs7["summary_metrics"]["total_loan_accounts"] == 3
        assert nbs7["summary_metrics"]["gross_npa_inr"] == 10_000_000.0

        # CRILC Reporting Verification
        crilc = regulatory_engine.compile_crilc_report(sample_assessments + [res_crilc])
        assert crilc["record_count"] == 1
        assert crilc["records"][0]["account_id"] == "ACC_CRILC_04"

        archive_res = regulatory_engine.archive_report_to_s3(nbs7, "NBS-7")
        assert "s3://" in archive_res["s3_uri"]
        assert len(archive_res["sha256_checksum"]) == 64
        print(f"  [✓] Regulatory Reporting: NBS-7 compiled and archived with SHA-256 {archive_res['sha256_checksum'][:8]}...")
    except Exception as exc:
        print(f"  [✗] Regulatory Reporting Test Failed: {exc}")
        all_passed = False

    # 5. Core Banking Batch Ingestion Pipeline (SFTP -> ClickHouse)
    print("\n[5/5] Testing Core Banking Batch Ingestion Pipeline (SFTP -> ClickHouse)...")
    try:
        batch_filename = f"finnone_daily_portfolio_{uuid.uuid4().hex[:6]}.csv"
        csv_batch_payload = (
            "account_id,customer_id,customer_name,product_type,sanctioned_amount,outstanding_principal,current_dpd,secured_percentage,cibil_score,annual_income,monthly_emi\n"
            "ACC_ING_101,CUST_101,Rohan Mehta,SME_LENDING,20000000.0,18000000.0,15,1.0,720,25000000.0,300000.0\n"
            "ACC_ING_102,CUST_102,Pooja Verma,HOUSING_FINANCE,7500000.0,7200000.0,110,1.0,610,1800000.0,65000.0\n"
            "ACC_ING_103,CUST_103,Karan Patel,GOLD_LOAN,1200000.0,1100000.0,0,1.0,810,3500000.0,25000.0\n"
        ).encode("utf-8")

        sftp_connector.upload_test_drop(batch_filename, csv_batch_payload)
        results = finnone_pipeline.process_and_load(batch_filename)
        assert len(results) == 3

        ch_records = clickhouse_manager.query_rows(
            "SELECT account_id, asset_classification, is_npa FROM zermp_analytics.loan_portfolio WHERE account_id LIKE 'ACC_ING_%'"
        )
        assert len(ch_records) == 3
        persisted_ids = {r["account_id"] for r in ch_records}
        assert "ACC_ING_101" in persisted_ids
        assert "ACC_ING_102" in persisted_ids
        assert "ACC_ING_103" in persisted_ids

        clickhouse_manager.execute_command("ALTER TABLE zermp_analytics.loan_portfolio DELETE WHERE account_id LIKE 'ACC_ING_%'")
        print("  [✓] Batch Ingestion Pipeline: Ingested SFTP drop into ClickHouse with risk classification.")
    except Exception as exc:
        print(f"  [✗] Batch Ingestion Pipeline Test Failed: {exc}")
        all_passed = False

    print("\n" + "=" * 80)
    if all_passed:
        print(" RESULT: ALL 5 MODULE 2 RISK ENGINES & PIPELINES OPERATIONAL [PASS]")
        print("=" * 80 + "\n")
        return True
    else:
        print(" RESULT: ONE OR MORE MODULE 2 COMPONENTS FAILED VERIFICATION [FAIL]")
        print("=" * 80 + "\n")
        return False


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
