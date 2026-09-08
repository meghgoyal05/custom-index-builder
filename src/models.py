"""
models.py

Data-model layer: loading and representing the stock universe and the
daily price history. Kept separate from calculation logic so each class
has a single responsibility (data loading / representation only).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd


@dataclass(frozen=True)
class Stock:
    """A single security in the investable universe."""

    ticker: str
    company_name: str
    sector: str
    market_cap_musd: float


class StockUniverse:
    """Loads and exposes the full 30-stock universe from universe.csv."""

    def __init__(self, universe_csv_path: str | Path):
        self._path = Path(universe_csv_path)
        self._df = pd.read_csv(self._path)
        self._validate_schema()

    def _validate_schema(self) -> None:
        required = {"ticker", "company_name", "sector", "market_cap_musd"}
        missing = required - set(self._df.columns)
        if missing:
            raise ValueError(f"universe.csv is missing required columns: {missing}")
        if self._df["ticker"].duplicated().any():
            dupes = self._df.loc[self._df["ticker"].duplicated(), "ticker"].tolist()
            raise ValueError(f"Duplicate tickers found in universe.csv: {dupes}")

    @property
    def as_dataframe(self) -> pd.DataFrame:
        return self._df.copy()

    @property
    def tickers(self) -> list[str]:
        return self._df["ticker"].tolist()

    def get_stock(self, ticker: str) -> Stock:
        row = self._df.loc[self._df["ticker"] == ticker]
        if row.empty:
            raise KeyError(f"Ticker '{ticker}' not found in universe")
        r = row.iloc[0]
        return Stock(r["ticker"], r["company_name"], r["sector"], float(r["market_cap_musd"]))

    def market_caps(self, tickers: list[str]) -> dict[str, float]:
        """Return {ticker: market_cap_musd} for the requested tickers."""
        subset = self._df[self._df["ticker"].isin(tickers)]
        return dict(zip(subset["ticker"], subset["market_cap_musd"]))


class PriceHistory:
    """Loads daily close prices and reshapes them into a wide date x ticker matrix."""

    def __init__(self, prices_csv_path: str | Path):
        self._path = Path(prices_csv_path)
        long_df = pd.read_csv(self._path, parse_dates=["date"])
        self._validate_schema(long_df)
        self._long = long_df.sort_values(["ticker", "date"])
        # Wide matrix: index=date, columns=ticker, values=close_price.
        self._wide = self._long.pivot(index="date", columns="ticker", values="close_price").sort_index()

    @staticmethod
    def _validate_schema(df: pd.DataFrame) -> None:
        required = {"date", "ticker", "close_price"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"prices.csv is missing required columns: {missing}")

    @property
    def available_date_range(self) -> tuple[pd.Timestamp, pd.Timestamp]:
        return self._wide.index.min(), self._wide.index.max()

    def wide_prices(self, tickers: list[str], start: str, end: str) -> pd.DataFrame:
        """Return the close-price matrix for the given tickers and date range."""
        sub = self._wide.loc[start:end, tickers]
        return sub
