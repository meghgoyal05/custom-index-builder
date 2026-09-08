"""
validation.py

Centralises input validation and missing-data handling so both the API
layer and the calculation layer can rely on clean, well-understood inputs.
Every check returns human-readable warnings/errors rather than failing
silently, per the project spec's requirement to surface validation issues.
"""

from __future__ import annotations

import pandas as pd


class ValidationError(Exception):
    """Raised for validation failures that should stop calculation."""


class Validator:
    """Validates user selections and the resulting price data before calculation."""

    def __init__(self):
        self.warnings: list[str] = []

    def validate_selection(self, tickers: list[str], universe_tickers: list[str]) -> None:
        if not tickers:
            raise ValidationError("Select at least one stock from the universe.")
        unknown = [t for t in tickers if t not in universe_tickers]
        if unknown:
            raise ValidationError(f"Unknown ticker(s) not in universe: {unknown}")
        if len(set(tickers)) != len(tickers):
            raise ValidationError("Duplicate tickers selected.")

    def validate_date_range(self, start: pd.Timestamp, end: pd.Timestamp,
                             available_start: pd.Timestamp, available_end: pd.Timestamp) -> None:
        if start > end:
            raise ValidationError("Start date must be on or before end date.")
        if start < available_start or end > available_end:
            raise ValidationError(
                f"Date range must be within available data "
                f"({available_start.date()} to {available_end.date()})."
            )
        if start == end:
            raise ValidationError("Select a date range spanning at least two trading days.")

    def clean_price_matrix(self, prices: pd.DataFrame) -> pd.DataFrame:
        """
        Handle missing observations (gaps in the price feed).

        Policy: forward-fill gaps within the series (a stock's last known
        price carries forward, which is a standard, simple assumption for
        illiquid/missing prints), then drop any ticker that has no data at
        all in the selected window. Every action taken is logged as a
        warning so the user can see what happened.
        """
        cleaned = prices.copy()

        fully_missing = cleaned.columns[cleaned.isna().all()].tolist()
        if fully_missing:
            self.warnings.append(
                f"No price data at all for {fully_missing} in the selected range; excluded from the index."
            )
            cleaned = cleaned.drop(columns=fully_missing)

        gap_counts = cleaned.isna().sum()
        gappy = gap_counts[gap_counts > 0]
        if not gappy.empty:
            details = ", ".join(f"{t} ({n} day(s))" for t, n in gappy.items())
            self.warnings.append(f"Missing prices forward-filled for: {details}.")
            cleaned = cleaned.ffill()

        # If the very first row still has NaNs (gap at the start), back-fill
        # those specific leading gaps and warn -- ffill can't fix a leading NaN.
        leading_na = cleaned.iloc[0].isna()
        if leading_na.any():
            leading_tickers = cleaned.columns[leading_na].tolist()
            self.warnings.append(
                f"Leading missing prices back-filled for: {leading_tickers}."
            )
            cleaned = cleaned.bfill()

        if cleaned.shape[1] == 0:
            raise ValidationError("No usable price data remains for the selected stocks/date range.")

        return cleaned

    def validate_weights(self, weights: pd.Series) -> None:
        total = weights.sum()
        if abs(total - 1.0) > 1e-6:
            raise ValidationError(f"Weights must sum to 1.0 (got {total:.6f}).")
        if (weights < 0).any():
            raise ValidationError("Weights cannot be negative.")
