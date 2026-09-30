"""FinnOne Core Banking Batch Ingestion Pipeline (DS-01).

Retrieves SFTP drops, parses loan records, executes risk models,
and loads data into ClickHouse OLAP tables with PostgreSQL audit trails.
"""

from __future__ import annotations
import csv
import io
from typing import Any, Dict, List
from src.common.config.settings import get_settings
from src.common.database.clickhouse import clickhouse_manager
from src.common.exceptions.base import ValidationError
from src.common.logging.logger import get_logger
from src.ingestion.connectors.sftp_connector import sftp_connector
from src.modules.credit_risk.engine import credit_risk_engine
from src.modules.credit_risk.models import CreditAssessmentResult, LoanAccount, ProductType

logger = get_logger("ingestion.pipeline.finnone")
settings = get_settings()

CREATE_DB_DDL = "CREATE DATABASE IF NOT EXISTS zermp_analytics"

CREATE_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS zermp_analytics.loan_portfolio (
    account_id String,
    customer_id String,
    customer_name String,
    product_type LowCardinality(String),
    sanctioned_amount Float64,
    outstanding_principal Float64,
    current_dpd UInt32,
    cibil_score Int32,
    scorecard_points Int32,
    probability_of_default Float64,
    expected_credit_loss Float64,
    asset_classification LowCardinality(String),
    is_npa UInt8,
    required_provision_amount Float64,
    ingestion_timestamp DateTime DEFAULT now()
) ENGINE = MergeTree()
ORDER BY (product_type, asset_classification, account_id)
"""


class FinnOneBatchPipeline:
    """Manages end-to-end ingestion and analytical indexing of core banking records."""

    def ensure_clickhouse_schema(self) -> None:
        """Initializes destination ClickHouse database and tables individually."""
        clickhouse_manager.execute_command(CREATE_DB_DDL)
        clickhouse_manager.execute_command(CREATE_TABLE_DDL)
        logger.info("Verified ClickHouse zermp_analytics.loan_portfolio schema")

    def parse_csv_stream(self, file_content: bytes) -> List[LoanAccount]:
        """Parses CSV stream into validated LoanAccount entities."""
        text_stream = io.StringIO(file_content.decode("utf-8-sig"))
        reader = csv.DictReader(text_stream)
        loan_records: List[LoanAccount] = []

        for row_idx, row in enumerate(reader, start=1):
            try:
                prod_str = row.get("product_type", "SME_LENDING").strip().upper()
                product = getattr(ProductType, prod_str, ProductType.SME_LENDING)

                loan = LoanAccount(
                    account_id=str(row["account_id"]).strip(),
                    customer_id=str(row.get("customer_id", f"CUST_{row['account_id']}")).strip(),
                    customer_name=str(row.get("customer_name", "Unknown")).strip(),
                    product_type=product,
                    sanctioned_amount=float(row["sanctioned_amount"]),
                    outstanding_principal=float(row["outstanding_principal"]),
                    current_dpd=int(row.get("current_dpd", 0)),
                    secured_percentage=float(row.get("secured_percentage", 1.0)),
                    cibil_score=int(row.get("cibil_score", 700)),
                    annual_income=float(row.get("annual_income", 1_000_000.0)),
                    monthly_emi=float(row.get("monthly_emi", 25_000.0)),
                )
                loan_records.append(loan)
            except Exception as err:
                logger.error("Row validation failed in FinnOne batch", row_idx=row_idx, error=str(err))
                raise ValidationError(f"Invalid record at line {row_idx}: {err}") from err

        return loan_records

    def process_and_load(self, filename: str) -> List[CreditAssessmentResult]:
        """Executes full ingestion: read from SFTP, evaluate risk models, and load to ClickHouse."""
        self.ensure_clickhouse_schema()

        logger.info("Reading batch drop from SFTP", filename=filename)
        content = sftp_connector.read_file_bytes(filename)
        loans = self.parse_csv_stream(content)

        assessments: List[CreditAssessmentResult] = []
        ch_rows: List[List[Any]] = []

        for loan in loans:
            result = credit_risk_engine.evaluate_account(loan)
            assessments.append(result)

            ch_rows.append([
                loan.account_id,
                loan.customer_id,
                loan.customer_name,
                loan.product_type.value,
                loan.sanctioned_amount,
                loan.outstanding_principal,
                loan.current_dpd,
                loan.cibil_score,
                result.scorecard_points,
                result.probability_of_default,
                result.expected_credit_loss,
                result.asset_classification.value,
                1 if result.is_npa else 0,
                result.required_provision_amount,
            ])

        columns = [
            "account_id", "customer_id", "customer_name", "product_type",
            "sanctioned_amount", "outstanding_principal", "current_dpd",
            "cibil_score", "scorecard_points", "probability_of_default",
            "expected_credit_loss", "asset_classification", "is_npa",
            "required_provision_amount"
        ]
        clickhouse_manager.insert_batch("zermp_analytics.loan_portfolio", ch_rows, columns)
        logger.info("Successfully ingested loan batch into ClickHouse", row_count=len(ch_rows))

        sftp_connector.delete_remote_file(filename)
        return assessments


finnone_pipeline = FinnOneBatchPipeline()
