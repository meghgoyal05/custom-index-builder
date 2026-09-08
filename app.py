"""
app.py

Flask backend for the Custom Index Builder.

Responsibilities of this layer only:
  - expose the stock universe and available date range to the frontend
  - accept a "generate index" request (tickers, weighting method, dates)
  - run validation + calculation (src/) and return JSON for the UI to plot

All analytical logic (returns, weighting, index levels, validation) lives
in src/ so this file stays a thin HTTP layer, per the project's
separation-of-concerns requirement.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from flask import Flask, jsonify, request, send_from_directory

from src.models import PriceHistory, StockUniverse
from src.index_calculator import IndexCalculator
from src.validation import Validator, ValidationError
from src.weighting import get_strategy

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
STATIC_DIR = BASE_DIR / "static"

app = Flask(__name__, static_folder=str(STATIC_DIR), static_url_path="")

# Loaded once at startup; the dummy dataset is small enough to keep in memory.
universe = StockUniverse(DATA_DIR / "universe.csv")
price_history = PriceHistory(DATA_DIR / "prices.csv")


@app.get("/")
def index_page():
    return send_from_directory(STATIC_DIR, "index.html")


@app.get("/api/universe")
def get_universe():
    """Return the 30-stock universe and the available price date range."""
    available_start, available_end = price_history.available_date_range
    return jsonify({
        "stocks": universe.as_dataframe.to_dict(orient="records"),
        "date_range": {
            "start": available_start.date().isoformat(),
            "end": available_end.date().isoformat(),
        },
    })


@app.post("/api/generate")
def generate_index():
    """
    Body: {
      "tickers": ["NOVX", "ATLX", ...],
      "weighting_method": "equal" | "market_cap" | "custom",
      "custom_weights": {"NOVX": 0.5, ...}   # required only for "custom"
      "start_date": "2023-01-02",
      "end_date": "2024-12-31"
    }
    """
    body = request.get_json(force=True, silent=True) or {}
    tickers = body.get("tickers", [])
    weighting_method = body.get("weighting_method", "equal")
    custom_weights = body.get("custom_weights")
    start_date = body.get("start_date")
    end_date = body.get("end_date")

    validator = Validator()

    try:
        validator.validate_selection(tickers, universe.tickers)

        if not start_date or not end_date:
            raise ValidationError("Both start_date and end_date are required.")
        start = pd.Timestamp(start_date)
        end = pd.Timestamp(end_date)
        available_start, available_end = price_history.available_date_range
        validator.validate_date_range(start, end, available_start, available_end)

        price_matrix = price_history.wide_prices(tickers, start_date, end_date)

        strategy = get_strategy(weighting_method)
        market_caps = universe.market_caps(tickers) if weighting_method == "market_cap" else None

        calculator = IndexCalculator(validator=validator)
        result = calculator.compute(
            price_matrix, strategy, market_caps=market_caps, custom_weights=custom_weights
        )

    except ValidationError as e:
        return jsonify({"error": str(e)}), 400
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({
        "dates": [d.date().isoformat() for d in result.levels.index],
        "levels": [round(v, 4) for v in result.levels.tolist()],
        "daily_returns": [round(v, 6) for v in result.daily_returns.tolist()],
        "weights": {k: round(v, 6) for k, v in result.weights.to_dict().items()},
        "summary": {
            "cumulative_return": round(result.cumulative_return, 6),
            "annualized_return": round(result.annualized_return, 6),
            "annualized_volatility": round(result.annualized_volatility, 6),
        },
        "warnings": result.warnings,
    })


if __name__ == "__main__":
    app.run(debug=True, port=5000)
