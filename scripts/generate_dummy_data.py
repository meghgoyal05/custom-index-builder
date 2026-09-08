"""
generate_dummy_data.py

Generates reproducible dummy market data for the Custom Index Builder:
  - data/universe.csv : the 30-stock investable universe
  - data/prices.csv   : daily close prices for every ticker

Re-run this script any time to regenerate the data (it is deterministic
because a fixed random seed is used).
"""

import csv
import random
from datetime import date, timedelta
from pathlib import Path

RANDOM_SEED = 42
NUM_STOCKS = 30
START_DATE = date(2023, 1, 2)
END_DATE = date(2024, 12, 31)
ANNUAL_TRADING_DAYS = 252

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

SECTORS = [
    "Technology", "Healthcare", "Financials", "Energy", "Consumer Discretionary",
    "Consumer Staples", "Industrials", "Utilities", "Materials", "Real Estate",
]

# Deterministic, made-up company/ticker names -- NOT real securities.
COMPANY_NAME_PARTS = [
    "Nova", "Atlas", "Vertex", "Summit", "Pioneer", "Horizon", "Beacon", "Orbit",
    "Cascade", "Granite", "Meridian", "Pinnacle", "Anchor", "Lumen", "Falcon",
    "Cobalt", "Sterling", "Harbor", "Vanguard", "Redwood", "Zenith", "Quartz",
    "Ember", "Crestline", "Solace", "Ironwood", "Silverline", "Northgate",
    "Bluepeak", "Amberfield",
]
COMPANY_SUFFIXES = ["Corp", "Inc", "Holdings", "Group", "Industries", "Partners"]


def build_universe(rng: random.Random) -> list[dict]:
    """Create the 30-stock universe with ticker, name, sector, and market cap."""
    universe = []
    used_tickers = set()
    for i, name_part in enumerate(COMPANY_NAME_PARTS[:NUM_STOCKS]):
        ticker = (name_part[:3] + "X").upper()
        # Guarantee ticker uniqueness even if two name parts collide.
        suffix_idx = 0
        base_ticker = ticker
        while ticker in used_tickers:
            suffix_idx += 1
            ticker = f"{base_ticker[:3]}{suffix_idx}"
        used_tickers.add(ticker)

        sector = SECTORS[i % len(SECTORS)]
        company_name = f"{name_part} {rng.choice(COMPANY_SUFFIXES)}"
        # Market cap in $millions, log-uniform-ish spread so a few "mega caps"
        # exist alongside many small/mid caps -- makes cap-weighting meaningful.
        market_cap = round(rng.choice([1, 1, 1, 2, 2, 4, 8]) * rng.uniform(800, 60000), 1)

        universe.append({
            "ticker": ticker,
            "company_name": company_name,
            "sector": sector,
            "market_cap_musd": market_cap,
        })
    return universe


def build_price_series(rng: random.Random, tickers: list[str]) -> list[dict]:
    """Simulate daily close prices for each ticker via a simple GBM-style random walk."""
    rows = []
    trading_days = []
    d = START_DATE
    while d <= END_DATE:
        if d.weekday() < 5:  # Mon-Fri only
            trading_days.append(d)
        d += timedelta(days=1)

    for ticker in tickers:
        price = rng.uniform(20, 250)  # starting price
        # Per-ticker drift/volatility so index behaviour differs by stock.
        daily_drift = rng.uniform(-0.0002, 0.0006)
        daily_vol = rng.uniform(0.008, 0.03)

        for i, trading_day in enumerate(trading_days):
            if i > 0:
                shock = rng.gauss(daily_drift, daily_vol)
                price = max(0.5, price * (1 + shock))
            # Occasionally simulate a missing observation (e.g. data feed gap).
            if rng.random() < 0.003 and i not in (0, len(trading_days) - 1):
                continue
            rows.append({
                "date": trading_day.isoformat(),
                "ticker": ticker,
                "close_price": round(price, 2),
            })
    return rows


def main():
    rng = random.Random(RANDOM_SEED)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    universe = build_universe(rng)
    tickers = [row["ticker"] for row in universe]

    universe_path = DATA_DIR / "universe.csv"
    with universe_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["ticker", "company_name", "sector", "market_cap_musd"])
        writer.writeheader()
        writer.writerows(universe)

    prices = build_price_series(rng, tickers)
    prices_path = DATA_DIR / "prices.csv"
    with prices_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["date", "ticker", "close_price"])
        writer.writeheader()
        writer.writerows(prices)

    print(f"Wrote {len(universe)} stocks to {universe_path}")
    print(f"Wrote {len(prices)} price rows to {prices_path}")


if __name__ == "__main__":
    main()
