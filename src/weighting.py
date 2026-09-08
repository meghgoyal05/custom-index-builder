"""
weighting.py

Weighting strategies for the custom index, implemented as an abstract base
class with concrete subclasses. This is the project's main OOP/polymorphism
example: IndexCalculator only ever calls `strategy.compute_weights(...)`
and does not need to know which concrete strategy it is talking to.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class WeightingStrategy(ABC):
    """Common interface every weighting method must implement."""

    name: str = "base"

    @abstractmethod
    def compute_weights(self, tickers: list[str], market_caps: dict[str, float] | None = None,
                         custom_weights: dict[str, float] | None = None) -> pd.Series:
        """Return a pandas Series of weights indexed by ticker, summing to 1.0."""
        raise NotImplementedError


class EqualWeighting(WeightingStrategy):
    """Every selected stock gets the same weight: 1 / N."""

    name = "equal"

    def compute_weights(self, tickers, market_caps=None, custom_weights=None) -> pd.Series:
        n = len(tickers)
        if n == 0:
            raise ValueError("At least one stock must be selected for equal weighting.")
        return pd.Series(1.0 / n, index=tickers)


class MarketCapWeighting(WeightingStrategy):
    """Weight proportional to each stock's float market capitalisation."""

    name = "market_cap"

    def compute_weights(self, tickers, market_caps=None, custom_weights=None) -> pd.Series:
        if not market_caps:
            raise ValueError("Market-cap weighting requires market_caps for every selected ticker.")
        missing = [t for t in tickers if t not in market_caps]
        if missing:
            raise ValueError(f"Missing market cap data for: {missing}")
        caps = pd.Series({t: market_caps[t] for t in tickers})
        if (caps <= 0).any():
            raise ValueError("Market caps must be positive for market-cap weighting.")
        return caps / caps.sum()


class CustomWeighting(WeightingStrategy):
    """User-supplied weights per ticker. Must be positive and sum to ~1.0."""

    name = "custom"

    def compute_weights(self, tickers, market_caps=None, custom_weights=None) -> pd.Series:
        if not custom_weights:
            raise ValueError("Custom weighting requires a weight for every selected ticker.")
        missing = [t for t in tickers if t not in custom_weights]
        if missing:
            raise ValueError(f"Missing custom weight for: {missing}")
        weights = pd.Series({t: float(custom_weights[t]) for t in tickers})
        if (weights < 0).any():
            raise ValueError("Custom weights cannot be negative.")
        total = weights.sum()
        if total <= 0:
            raise ValueError("Custom weights must sum to a positive number.")
        # Normalise so the caller doesn't have to hand-tune to exactly 1.0.
        return weights / total


WEIGHTING_STRATEGIES: dict[str, type[WeightingStrategy]] = {
    "equal": EqualWeighting,
    "market_cap": MarketCapWeighting,
    "custom": CustomWeighting,
}


def get_strategy(name: str) -> WeightingStrategy:
    try:
        return WEIGHTING_STRATEGIES[name]()
    except KeyError:
        raise ValueError(f"Unknown weighting method '{name}'. Choose from {list(WEIGHTING_STRATEGIES)}.")
