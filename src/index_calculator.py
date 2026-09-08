"""
index_calculator.py

Implements the core price-return index math:

    r_i(t)     = close_i(t) / close_i(t-1) - 1        (per-stock daily return)
    r_index(t) = sum(w_i * r_i(t))                     (weighted index return)
    level(t)   = level(t-1) * (1 + r_index(t))          (index level, base=100)
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from .validation import Validator
from .weighting import WeightingStrategy

BASE_LEVEL = 100.0


@dataclass
class IndexResult:
    """Container for everything the frontend needs to render/report on a run."""

    levels: pd.Series               # date -> index level
    daily_returns: pd.Series        # date -> r_index(t)
    weights: pd.Series              # ticker -> weight used
    cumulative_return: float
    annualized_return: float
    annualized_volatility: float
    warnings: list[str] = field(default_factory=list)


class IndexCalculator:
    """
    Computes a custom Price Return Index for a chosen set of stocks,
    weighting strategy, and date range.
    """

    def __init__(self, validator: Validator | None = None):
        self.validator = validator or Validator()

    def compute(self, price_matrix: pd.DataFrame, strategy: WeightingStrategy,
                market_caps: dict[str, float] | None = None,
                custom_weights: dict[str, float] | None = None) -> IndexResult:
        """
        price_matrix: wide DataFrame, index=date, columns=ticker, values=close_price
                      (already restricted to the selected tickers/date range).
        """
        cleaned_prices = self.validator.clean_price_matrix(price_matrix)
        tickers = cleaned_prices.columns.tolist()

        weights = strategy.compute_weights(
            tickers, market_caps=market_caps, custom_weights=custom_weights
        )
        # Re-align in case a ticker was dropped for having no data at all.
        weights = weights.reindex(tickers).fillna(0.0)
        if weights.sum() == 0:
            raise ValueError("Computed weights sum to zero after removing stocks with no data.")
        weights = weights / weights.sum()
        self.validator.validate_weights(weights)

        # r_i(t) = close_i(t) / close_i(t-1) - 1
        stock_returns = cleaned_prices.pct_change().dropna(how="all")

        # r_index(t) = sum(w_i * r_i(t)), treating any single missing stock
        # return on a given day as a zero contribution rather than dropping
        # the whole day.
        weighted = stock_returns.mul(weights, axis=1)
        index_daily_returns = weighted.sum(axis=1, skipna=True)

        # level(t) = level(t-1) * (1 + r_index(t)), level(0) = BASE_LEVEL
        levels = (1 + index_daily_returns).cumprod() * BASE_LEVEL
        first_date = cleaned_prices.index[0]
        levels.loc[first_date] = BASE_LEVEL
        levels = levels.sort_index()

        cumulative_return = levels.iloc[-1] / levels.iloc[0] - 1
        n_days = len(index_daily_returns)
        annualized_return, annualized_vol = self._annualize(index_daily_returns, n_days)

        return IndexResult(
            levels=levels,
            daily_returns=index_daily_returns,
            weights=weights,
            cumulative_return=float(cumulative_return),
            annualized_return=annualized_return,
            annualized_volatility=annualized_vol,
            warnings=list(self.validator.warnings),
        )

    @staticmethod
    def _annualize(daily_returns: pd.Series, n_days: int, trading_days_per_year: int = 252) -> tuple[float, float]:
        if n_days == 0:
            return 0.0, 0.0
        mean_daily = daily_returns.mean()
        std_daily = daily_returns.std()
        annualized_return = (1 + mean_daily) ** trading_days_per_year - 1
        annualized_vol = std_daily * (trading_days_per_year ** 0.5)
        return float(annualized_return), float(0.0 if pd.isna(annualized_vol) else annualized_vol)
