"""Market Risk & Asset Liability Management (ALM) Engine.

Calculates Value at Risk (VaR) and structural liquidity maturity gap mismatches.
"""

from typing import Dict, List, Tuple
import numpy as np
from pydantic import BaseModel, Field
from src.common.logging.logger import get_logger

logger = get_logger("modules.market_risk")


class LiquidityBucket(BaseModel):
    bucket_name: str
    inflows_inr: float = Field(..., ge=0.0)
    outflows_inr: float = Field(..., ge=0.0)
    net_gap_inr: float = 0.0
    cumulative_gap_inr: float = 0.0
    cumulative_gap_percentage: float = 0.0


class MarketRiskEngine:
    """Computes historical VaR and structural liquidity maturity gap returns."""

    def calculate_historical_var(
        self,
        portfolio_value: float,
        daily_returns: List[float],
        confidence_level: float = 0.99,
        holding_period_days: int = 10,
    ) -> Dict[str, float]:
        """Calculates VaR via Historical Simulation (CFG-MR-001)."""
        if len(daily_returns) < 30:
            raise ValueError("Historical simulation requires at least 30 historical return data points")

        returns_array = np.array(daily_returns)
        percentile = (1.0 - confidence_level) * 100
        daily_var_pct = float(np.percentile(returns_array, percentile))
        
        # Scale 1-day VaR to 10-day holding period using the square root of time rule
        scaled_var_pct = abs(daily_var_pct) * np.sqrt(holding_period_days)
        var_amount = portfolio_value * scaled_var_pct

        return {
            "portfolio_value": portfolio_value,
            "confidence_level": confidence_level,
            "holding_period_days": holding_period_days,
            "var_percentage": round(float(scaled_var_pct) * 100, 4),
            "var_amount_inr": round(float(var_amount), 2),
        }

    def generate_alm_liquidity_gaps(
        self, raw_buckets: List[Tuple[str, float, float]]
    ) -> List[LiquidityBucket]:
        """Calculates net and cumulative liquidity gaps per RBI ALM Guidelines."""
        results: List[LiquidityBucket] = []
        cumulative_gap = 0.0
        cumulative_outflow = 0.0

        for name, inflows, outflows in raw_buckets:
            net_gap = inflows - outflows
            cumulative_gap += net_gap
            cumulative_outflow += outflows

            gap_ratio = (
                (cumulative_gap / cumulative_outflow * 100.0)
                if cumulative_outflow > 0
                else 0.0
            )

            results.append(
                LiquidityBucket(
                    bucket_name=name,
                    inflows_inr=inflows,
                    outflows_inr=outflows,
                    net_gap_inr=round(net_gap, 2),
                    cumulative_gap_inr=round(cumulative_gap, 2),
                    cumulative_gap_percentage=round(gap_ratio, 2),
                )
            )

        return results


market_risk_engine = MarketRiskEngine()
