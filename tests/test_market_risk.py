"""Unit Tests for Market Risk Historical VaR & ALM Liquidity Gaps."""

import random
import pytest
from src.modules.market_risk.engine import market_risk_engine


def test_historical_var_simulation():
    """Verify 99% 10-day Historical Simulation Value at Risk (CFG-MR-001)."""
    random.seed(42)
    daily_returns = [random.gauss(0.0003, 0.012) for _ in range(60)]
    var_result = market_risk_engine.calculate_historical_var(
        portfolio_value=1_000_000_000.0,  # 100 Crore
        daily_returns=daily_returns,
        confidence_level=0.99,
        holding_period_days=10,
    )
    assert var_result["var_amount_inr"] > 0
    assert var_result["confidence_level"] == 0.99
    assert var_result["holding_period_days"] == 10


def test_alm_liquidity_gap_computation():
    """Verify structural liquidity net and cumulative gap calculation."""
    raw_buckets = [
        ("1-14 Days", 150_000_000.0, 100_000_000.0),
        ("15-28 Days", 80_000_000.0, 120_000_000.0),
    ]
    gaps = market_risk_engine.generate_alm_liquidity_gaps(raw_buckets)
    assert len(gaps) == 2
    assert gaps[0].net_gap_inr == 50_000_000.0
    assert gaps[1].net_gap_inr == -40_000_000.0
    assert gaps[1].cumulative_gap_inr == 10_000_000.0
