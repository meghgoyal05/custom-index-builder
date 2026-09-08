"""
Basic tests for the calculation and validation logic.
Run with: pytest tests/
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.index_calculator import IndexCalculator
from src.validation import Validator, ValidationError
from src.weighting import EqualWeighting, MarketCapWeighting, CustomWeighting, get_strategy


def make_price_matrix():
    dates = pd.date_range("2024-01-01", periods=5, freq="D")
    return pd.DataFrame(
        {
            "AAA": [100, 102, 101, 103, 104],
            "BBB": [50, 49, 51, 52, 52],
        },
        index=dates,
    )


def test_equal_weighting_sums_to_one():
    w = EqualWeighting().compute_weights(["AAA", "BBB"])
    assert w.sum() == pytest.approx(1.0)
    assert w["AAA"] == pytest.approx(0.5)


def test_market_cap_weighting_proportions():
    w = MarketCapWeighting().compute_weights(["AAA", "BBB"], market_caps={"AAA": 300, "BBB": 100})
    assert w.sum() == pytest.approx(1.0)
    assert w["AAA"] == pytest.approx(0.75)


def test_custom_weighting_normalizes():
    w = CustomWeighting().compute_weights(["AAA", "BBB"], custom_weights={"AAA": 3, "BBB": 1})
    assert w.sum() == pytest.approx(1.0)
    assert w["AAA"] == pytest.approx(0.75)


def test_get_strategy_unknown_raises():
    with pytest.raises(ValueError):
        get_strategy("not_a_real_method")


def test_index_starts_at_base_100():
    pm = make_price_matrix()
    result = IndexCalculator().compute(pm, EqualWeighting())
    assert result.levels.iloc[0] == pytest.approx(100.0)


def test_index_level_matches_manual_calc():
    pm = make_price_matrix()
    result = IndexCalculator().compute(pm, EqualWeighting())
    # day 2: r_AAA=102/100-1=0.02, r_BBB=49/50-1=-0.02 -> r_index=0.5*0.02+0.5*(-0.02)=0
    assert result.levels.iloc[1] == pytest.approx(100.0, abs=1e-6)


def test_validator_rejects_empty_selection():
    v = Validator()
    with pytest.raises(ValidationError):
        v.validate_selection([], ["AAA", "BBB"])


def test_validator_rejects_unknown_ticker():
    v = Validator()
    with pytest.raises(ValidationError):
        v.validate_selection(["ZZZ"], ["AAA", "BBB"])


def test_validator_forward_fills_missing_prices():
    dates = pd.date_range("2024-01-01", periods=4, freq="D")
    pm = pd.DataFrame({"AAA": [100, None, 102, 103]}, index=dates)
    v = Validator()
    cleaned = v.clean_price_matrix(pm)
    assert cleaned.isna().sum().sum() == 0
    assert any("forward-filled" in w for w in v.warnings)


def test_weights_must_sum_to_one():
    v = Validator()
    bad_weights = pd.Series({"AAA": 0.3, "BBB": 0.3})
    with pytest.raises(ValidationError):
        v.validate_weights(bad_weights)
