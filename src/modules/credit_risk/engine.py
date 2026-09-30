"""Credit Risk & RBI IRAC Provisioning Engine.

Calculates scorecards, ECL, asset classifications, and provisioning schedules
in compliance with RBI Master Directions for NBFC-ND-SI.
"""

from typing import Dict, Tuple
from src.common.config.settings import get_settings
from src.common.logging.logger import get_logger
from src.modules.credit_risk.models import (
    AssetClassification,
    CreditAssessmentResult,
    LoanAccount,
    ProductType,
)

logger = get_logger("modules.credit_risk")
settings = get_settings()


class CreditRiskEngine:
    """Calculates quantitative risk indicators, scorecards, and regulatory provisions."""

    def __init__(self) -> None:
        self.cibil_floor = 650
        self.cibil_referral_floor = 600

    def evaluate_cibil_gate(self, score: int) -> Tuple[str, bool]:
        """Enforces bureau score threshold controls (CFG-CR-003)."""
        if score == -1:
            return "NO_HIT_REFERRED", True
        if score >= self.cibil_floor:
            return "AUTO_APPROVED", False
        if score >= self.cibil_referral_floor:
            return "REFER_CREDIT_COMMITTEE", True
        return "REJECTED_BELOW_FLOOR", False

    def calculate_scorecard(self, loan: LoanAccount) -> Tuple[int, float]:
        """Calculates credit scorecard points and PD using WoE binning (CFG-CR-001)."""
        points = 500  # Baseline intercept

        # 1. Bureau Score Points
        if loan.cibil_score >= 750:
            points += 150
        elif loan.cibil_score >= 700:
            points += 100
        elif loan.cibil_score >= 650:
            points += 50
        elif loan.cibil_score >= 600:
            points += 10
        else:
            points -= 80

        # 2. Debt-to-Income / Capacity Score
        annual_emi = loan.monthly_emi * 12
        if loan.annual_income > 0:
            dti = annual_emi / loan.annual_income
            if dti <= 0.30:
                points += 100
            elif dti <= 0.50:
                points += 50
            elif dti <= 0.70:
                points -= 30
            else:
                points -= 100
        else:
            points -= 20

        # 3. Product Collateral Weight
        product_collateral_weights: Dict[ProductType, int] = {
            ProductType.GOLD_LOAN: 120,
            ProductType.HOUSING_FINANCE: 80,
            ProductType.VEHICLE_FINANCE: 40,
            ProductType.SME_LENDING: 10,
            ProductType.MICROFINANCE: -30,
        }
        points += product_collateral_weights.get(loan.product_type, 0)

        # PD mapping calibrated for retail NBFC portfolios
        # PD ranges from 0.8% (high tier) to 25.0% (distressed tier)
        if points >= 750:
            pd = 0.008
        elif points >= 680:
            pd = 0.015
        elif points >= 600:
            pd = 0.032
        elif points >= 520:
            pd = 0.065
        elif points >= 450:
            pd = 0.120
        else:
            pd = 0.250

        return points, pd

    def get_lgd_benchmark(self, product_type: ProductType, secured_ratio: float) -> float:
        """Determines Loss Given Default (LGD) based on collateral recovery rates."""
        base_unsecured_lgd = 0.65
        base_secured_lgd = 0.35

        if product_type == ProductType.GOLD_LOAN:
            return 0.15
        if product_type == ProductType.HOUSING_FINANCE:
            return 0.25
        if product_type == ProductType.VEHICLE_FINANCE:
            return 0.40

        weighted_lgd = (secured_ratio * base_secured_lgd) + ((1.0 - secured_ratio) * base_unsecured_lgd)
        return round(weighted_lgd, 4)

    def classify_asset_and_provision(
        self, dpd: int, outstanding: float, secured_ratio: float
    ) -> Tuple[AssetClassification, bool, float, float]:
        """Classifies asset and computes mandatory provisioning per RBI IRAC norms."""
        secured_amount = outstanding * secured_ratio
        unsecured_amount = outstanding * (1.0 - secured_ratio)

        # Standard & Special Mention Categories (0 - 90 DPD)
        if dpd == 0:
            category = AssetClassification.STANDARD
            rate = 0.0040  # 0.40% standard asset provisioning
            provision = outstanding * rate
            is_npa = False
        elif dpd <= 30:
            category = AssetClassification.SMA_0
            rate = 0.0040
            provision = outstanding * rate
            is_npa = False
        elif dpd <= 60:
            category = AssetClassification.SMA_1
            rate = 0.0040
            provision = outstanding * rate
            is_npa = False
        elif dpd <= 90:
            category = AssetClassification.SMA_2
            rate = 0.0040
            provision = outstanding * rate
            is_npa = False

        # Non-Performing Asset (NPA) Categories (> 90 DPD)
        elif dpd <= 365:
            # Sub-Standard Asset (10% uniform rate for NBFC-ND-SI)
            category = AssetClassification.SUB_STANDARD
            rate = settings.SUBSTANDARD_PROVISION_SECURED
            provision = outstanding * rate
            is_npa = True
        elif dpd <= 730:
            # Doubtful 1 (D1): 25% secured + 100% unsecured
            category = AssetClassification.DOUBTFUL_1
            provision = (secured_amount * settings.D1_PROVISION_SECURED) + (unsecured_amount * 1.00)
            rate = provision / outstanding if outstanding > 0 else settings.D1_PROVISION_SECURED
            is_npa = True
        elif dpd <= 1095:
            # Doubtful 2 (D2): 40% secured + 100% unsecured
            category = AssetClassification.DOUBTFUL_2
            provision = (secured_amount * settings.D2_PROVISION_SECURED) + (unsecured_amount * 1.00)
            rate = provision / outstanding if outstanding > 0 else settings.D2_PROVISION_SECURED
            is_npa = True
        else:
            # Doubtful 3 (D3): 100% full provisioning
            category = AssetClassification.DOUBTFUL_3
            rate = settings.D3_PROVISION_TOTAL
            provision = outstanding * rate
            is_npa = True

        return category, is_npa, round(rate, 4), round(provision, 2)

    def evaluate_account(self, loan: LoanAccount) -> CreditAssessmentResult:
        """Executes full quantitative and regulatory evaluation for a loan account."""
        cibil_decision, requires_override = self.evaluate_cibil_gate(loan.cibil_score)
        scorecard_points, pd = self.calculate_scorecard(loan)
        lgd = self.get_lgd_benchmark(loan.product_type, loan.secured_percentage)
        ead = loan.outstanding_principal

        # ECL = PD * LGD * EAD
        ecl = round(pd * lgd * ead, 2)

        classification, is_npa, prov_pct, prov_amt = self.classify_asset_and_provision(
            loan.current_dpd, loan.outstanding_principal, loan.secured_percentage
        )

        # CRILC reporting mandatory for aggregate exposures >= INR 5 Crore
        crilc_reportable = loan.outstanding_principal >= 50_000_000.0

        return CreditAssessmentResult(
            account_id=loan.account_id,
            product_type=loan.product_type,
            cibil_score=loan.cibil_score,
            cibil_decision=cibil_decision,
            requires_override=requires_override,
            scorecard_points=scorecard_points,
            probability_of_default=pd,
            loss_given_default=lgd,
            exposure_at_default=ead,
            expected_credit_loss=ecl,
            asset_classification=classification,
            is_npa=is_npa,
            provision_percentage=prov_pct,
            required_provision_amount=prov_amt,
            crilc_reportable=crilc_reportable,
        )


credit_risk_engine = CreditRiskEngine()
