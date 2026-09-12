# Custom Index Builder (Price Return)

A small web app that builds a custom dummy equity index from a 30-stock
universe and computes a Price Return Index over a chosen date range.

Built for the Index Engineering Apprentice project exercise.

## Overview

- Pick any number of stocks from a 30-stock dummy universe.
- Choose a weighting method: **equal**, **market-cap**, or **custom**.
- Pick a date range within the available price history.
- Click **Generate** to see the index level chart, summary metrics
  (cumulative return, annualized return, annualized volatility), and any
  data-quality warnings.

## Architecture

| Layer      | Technology                          | Responsibility |
|------------|--------------------------------------|----------------|
| Frontend   | HTML / CSS / vanilla JS + Chart.js  | Stock picker, weighting/date controls, chart & summary rendering |
| Backend    | Flask (Python)                       | Thin HTTP layer: `/api/universe`, `/api/generate` |
| Analytics  | Python (`src/`), pandas              | Data loading, weighting strategies, index math, validation |
| Data       | CSV (dummy, generated)               | `data/universe.csv`, `data/prices.csv` |

**Why this split:** the exercise asks for a web-served UI with Python
analytics underneath, and for the code to be explainable rather than a
single script. Putting all math/validation in `src/` and keeping `app.py`
as a thin request/response layer means the calculation logic can be
unit-tested and reasoned about independently of Flask, and the frontend is
just a client of a small JSON API (so it could be swapped for React, a
CLI, or a notebook without touching `src/`).

A plain HTML/JS frontend (rather than a heavier framework) was chosen
because the UI surface is small — a filterable list, some radio buttons,
a date range, and one chart — and it keeps the whole project runnable
with just Flask + pandas, no build step or Node toolchain required.

### Code layout

```
app.py                         Flask app: routes + request/response glue only
src/
  models.py                    Stock, StockUniverse, PriceHistory (data loading)
  weighting.py                 WeightingStrategy ABC + Equal/MarketCap/Custom
  validation.py                Validator: input checks + missing-data handling
  index_calculator.py          IndexCalculator: the price-return math
static/
  index.html, style.css, app.js  Frontend
data/
  universe.csv, prices.csv     Generated dummy data
scripts/
  generate_dummy_data.py       Regenerates the dummy data (deterministic seed)
tests/
  test_index_calculator.py     Unit tests for weighting/validation/calculation
```

### OOP design

- `WeightingStrategy` is an abstract base class with three concrete
  subclasses (`EqualWeighting`, `MarketCapWeighting`, `CustomWeighting`).
  `IndexCalculator` depends only on the `WeightingStrategy` interface
  (`compute_weights(...)`), so a new weighting method can be added by
  writing one new subclass — no changes needed to the calculator or the
  API route. This is the project's main polymorphism example.
- `StockUniverse` and `PriceHistory` encapsulate CSV loading/reshaping
  and expose a small, purpose-built interface (`tickers`, `market_caps`,
  `wide_prices`, `available_date_range`) rather than leaking raw
  DataFrames and file paths around the codebase.
- `Validator` is a separate class (not static functions scattered
  around) so it can accumulate `warnings` across a single run and be
  unit-tested in isolation from Flask or the calculator.

## Weighting method implemented

- **Equal weight**: `w_i = 1 / N` for the N selected stocks.
- **Market-cap weight**: `w_i = market_cap_i / sum(market_cap)` using the
  `market_cap_musd` field from `universe.csv`.
- **Custom weight**: user supplies a weight per selected stock; the app
  normalizes them to sum to 1.0 (so entering `3, 1` is treated the same
  as `0.75, 0.25`) and rejects negative weights.

All three implement the same `WeightingStrategy` interface.

## Price return formula

For each stock *i* and day *t*:

```
r_i(t)     = close_i(t) / close_i(t-1) - 1
r_index(t) = sum(w_i * r_i(t))                # weighted across selected stocks
level(t)   = level(t-1) * (1 + r_index(t))    # level(t0) = 100
```

Summary metrics shown alongside the chart:

- **Cumulative return** = `level(end) / level(start) - 1`
- **Annualized return** = `(1 + mean(daily r_index)) ** 252 - 1`
- **Annualized volatility** = `std(daily r_index) * sqrt(252)`

## Missing-data handling

The dummy price feed intentionally contains occasional gaps (simulating a
missing print). `Validator.clean_price_matrix`:

1. Drops any selected ticker with **no** price data at all in the chosen
   window, and warns which ticker(s) were excluded.
2. **Forward-fills** interior gaps (carries the last known price forward)
   and warns which ticker(s)/how many days were affected. This is a
   simple, standard assumption for a short data gap; it does not attempt
   to interpolate or model the missing price.
3. **Back-fills** a gap at the very first date in the window (forward-fill
   can't fix a leading `NaN`) and warns about it separately.

All warnings are returned by the API and shown in the UI rather than
failing silently.

## How to run

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# (data/universe.csv and data/prices.csv are already generated and
#  committed; re-run this only if you want to regenerate them)
python scripts/generate_dummy_data.py

python app.py
# then open http://127.0.0.1:5000
```

### Running the tests

```bash
pip install pytest
pytest tests/
```

## Limitations / future improvements

- **In-memory data only**: the app loads the two CSVs into memory at
  startup; there's no database, so it won't scale past a small dummy
  universe without a data-access layer swap.
- **Price-return only**: no dividends/total-return, no corporate actions
  (splits, spin-offs) — the exercise scope was explicitly price return.
- **Missing-data policy is a single default** (forward-fill/back-fill).
  A production version would let the user choose the policy (e.g. drop
  the stock entirely, exclude the day from the index, or flag for
  manual review) and would distinguish "genuinely missing" from
  "market holiday" rather than treating every non-trading day as a gap.
- **No auth / persistence**: there's no way to save a built index or
  share a permalink to a specific run; every "Generate" is a fresh,
  stateless calculation.
- **Rebalancing is implicit**: weights are computed once, at the start
  of the period, and held fixed — there's no periodic rebalancing
  (e.g. monthly reweighting back to target), which a real index would
  typically do.
- **Single-process dev server**: `app.run(debug=True)` is fine for this
  exercise but isn't production-ready (see Flask's own warning in the
  console); a real deployment would use gunicorn/uwsgi behind a proper
  WSGI setup.

## Git workflow

This repo was built with incremental commits and a feature branch:

1. `master`: dummy data generator + core data/index-calculation modules
   (`src/models.py`, `src/weighting.py`, `src/validation.py`,
   `src/index_calculator.py`).
2. `feature/web-app` branch: Flask API layer (`app.py`) and the
   HTML/CSS/JS frontend (`static/`), plus tests.
3. `feature/web-app` merged back into `master`.

Run `git log --oneline --graph --all` to see the full history.


![Image Alt] (https://github.com/meghgoyal05/custom-index-builder/blob/7c3f3e4e296bfcde22ed4ded9af81c68ebdf6474/App-screenshot.PNG)
