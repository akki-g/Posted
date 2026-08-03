# Stock Research Tools Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give Posted's financial assistant three new tools — `get_technical_indicators`, `get_sec_filings`, and `run_stock_research` — so it can do independent, multi-source stock research (indicators, insider sentiment, filings, news) on demand, in both the in-app chat and SMS, which already share one code path.

**Architecture:** Extend the existing hand-rolled Anthropic tool-use loop in `backend/app/services/assistant.py` (`TOOLS` list + `_execute_tool` dispatch) — no MCP protocol, no new process. New pure-Python indicator math in `app/market/indicators.py`, a cached SEC ticker→CIK resolver added to the existing `SecEdgarAdapter`, a new `app/services/sec_filings.py` for the filings tool, and a new `app/services/stock_research.py` that fans out concurrently to existing services (`get_stock_detail`, the new indicators, `summarize_insider_activity`/`interpret_insider_activity`, `MultiSourceNewsAdapter`, SEC filings) for the deep-research bundle. `run_assistant_turn` gains a one-line model escalation: once `run_stock_research` is called, the rest of that turn runs on `claude-sonnet-5` instead of `claude-haiku-4-5`.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy asyncio, Pydantic v2, httpx, pytest + pytest-asyncio (`asyncio_mode = "auto"`), Anthropic SDK (`anthropic`).

## Global Constraints

- Source spec: `docs/superpowers/specs/2026-08-03-stock-research-tools-design.md`. Follow it for anything this plan doesn't spell out.
- No new dependencies — indicator math is pure Python (no numpy/pandas/ta-lib), matching the codebase's existing use of `statistics.fmean` for similar math in `app/services/insider_analysis.py`.
- Do not migrate the assistant to the Model Context Protocol. Extend the existing `TOOLS`/`_execute_tool` pattern only.
- Any new tool that reads brokerage/position data must be added to `_BROKERAGE_BACKED_TOOLS` in `app/services/assistant.py` so it stays behind the existing `sync_stale_brokerage_connections` lazy-sync gate — this is what keeps Schwab/Plaid holdings fresh, and it must not regress.
- No SMS-specific code changes — SMS and chat already share `send_message`/`run_assistant_turn`.
- All backend commands run from `backend/`: `uv run pytest <path> -v` for a single test, `uv run pytest` for the full suite, `uv run ruff check .` for lint. `make check` (from the repo root) runs both backend checks and the frontend typecheck/test/export.
- Every new/changed Python file must pass `uv run ruff check .` before its task is committed.

---

### Task 1: Technical indicator math (`app/market/indicators.py`)

**Files:**
- Create: `backend/app/market/indicators.py`
- Test: `backend/app/tests/test_indicators.py`

**Interfaces:**
- Consumes: `app.market.schemas.PriceBar` (existing: `timestamp, open, high, low, close, volume`).
- Produces (used by Task 2 and Task 3):
  - `sma(values: list[float], window: int) -> float | None`
  - `ema_series(values: list[float], window: int) -> list[float]`
  - `ema_latest(values: list[float], window: int) -> float | None`
  - `macd(values: list[float], fast: int = 12, slow: int = 26, signal: int = 9) -> tuple[float | None, float | None, float | None]` (macd_line, signal_line, histogram)
  - `rsi(values: list[float], window: int = 14) -> float | None`
  - `stochastic(bars: list[PriceBar], window: int = 14, smooth: int = 3) -> tuple[float | None, float | None]` (percent_k, percent_d)
  - `bollinger_bands(values: list[float], window: int = 20, num_std: float = 2.0) -> tuple[float | None, float | None, float | None]` (upper, middle, lower)
  - `atr(bars: list[PriceBar], window: int = 14) -> float | None`
  - `volume_trend(bars: list[PriceBar], window: int = 20) -> tuple[int, float, float] | None` (latest_volume, average_volume, ratio)

- [ ] **Step 1: Write the failing tests**

```python
# backend/app/tests/test_indicators.py
from datetime import UTC, datetime

from app.market.indicators import (
    atr,
    bollinger_bands,
    ema_latest,
    ema_series,
    macd,
    rsi,
    sma,
    stochastic,
    volume_trend,
)
from app.market.schemas import PriceBar


def _bar(*, high: float, low: float, close: float, volume: int = 1000) -> PriceBar:
    return PriceBar(
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        open=close,
        high=high,
        low=low,
        close=close,
        volume=volume,
    )


def test_sma_averages_the_trailing_window() -> None:
    values = [float(v) for v in range(10, 21)]  # 10..20

    assert sma(values, 5) == 18.0


def test_sma_returns_none_when_history_is_shorter_than_the_window() -> None:
    values = [float(v) for v in range(10, 21)]

    assert sma(values, 20) is None


def test_ema_series_matches_the_standard_seeded_recursive_formula() -> None:
    values = [float(v) for v in range(1, 8)]  # 1..7

    assert ema_series(values, 3) == [2.0, 3.0, 4.0, 5.0, 6.0]
    assert ema_latest(values, 3) == 6.0


def test_ema_latest_returns_none_when_history_is_shorter_than_the_window() -> None:
    assert ema_latest([1.0, 2.0], 3) is None


def test_macd_matches_the_difference_of_its_own_fast_and_slow_ema_series() -> None:
    values = [float(100 + i) for i in range(40)]
    fast_series = ema_series(values, 12)
    slow_series = ema_series(values, 26)
    aligned_fast = fast_series[-len(slow_series):]
    macd_line_series = [f - s for f, s in zip(aligned_fast, slow_series, strict=True)]
    signal_series = ema_series(macd_line_series, 9)

    macd_line, signal_line, histogram = macd(values)

    assert macd_line == macd_line_series[-1]
    assert signal_line == signal_series[-1]
    assert histogram == macd_line_series[-1] - signal_series[-1]


def test_macd_returns_none_when_history_is_shorter_than_the_slow_ema_window() -> None:
    values = [float(100 + i) for i in range(20)]

    assert macd(values) == (None, None, None)


def test_rsi_of_a_mixed_series_matches_wilder_smoothing_by_hand() -> None:
    # deltas [2, -1, 3] -> avg_gain 5/3, avg_loss 1/3 -> RSI 100 - 100/6
    values = [10.0, 12.0, 11.0, 14.0]

    assert rsi(values, window=3) == 83.33


def test_rsi_is_100_when_every_session_gained() -> None:
    values = [10.0, 11.0, 12.0, 13.0, 14.0]

    assert rsi(values, window=4) == 100.0


def test_rsi_returns_none_when_history_is_shorter_than_the_window_plus_one() -> None:
    assert rsi([10.0, 11.0, 12.0], window=3) is None


def test_stochastic_matches_hand_computed_high_low_close_ranges() -> None:
    bars = [
        _bar(high=10, low=8, close=9),
        _bar(high=11, low=9, close=10),
        _bar(high=12, low=10, close=11),
        _bar(high=13, low=11, close=12),
    ]

    percent_k, percent_d = stochastic(bars, window=3, smooth=2)

    assert percent_k == 75.0
    assert percent_d == 75.0


def test_stochastic_returns_none_when_history_is_too_short() -> None:
    bars = [_bar(high=10, low=8, close=9), _bar(high=11, low=9, close=10)]

    assert stochastic(bars, window=3, smooth=2) == (None, None)


def test_bollinger_bands_matches_hand_computed_population_std_dev() -> None:
    values = [10.0, 12.0, 14.0, 16.0, 18.0]

    upper, middle, lower = bollinger_bands(values, window=5, num_std=2.0)

    assert upper == 19.66
    assert middle == 14.0
    assert lower == 8.34


def test_bollinger_bands_returns_none_when_history_is_shorter_than_the_window() -> None:
    assert bollinger_bands([1.0, 2.0], window=5) == (None, None, None)


def test_atr_matches_hand_computed_true_range_average() -> None:
    bars = [
        _bar(high=10, low=8, close=9),
        _bar(high=11, low=9, close=10),
        _bar(high=12, low=10, close=11),
    ]

    assert atr(bars, window=2) == 2.0


def test_atr_returns_none_when_history_is_shorter_than_the_window_plus_one() -> None:
    bars = [_bar(high=10, low=8, close=9), _bar(high=11, low=9, close=10)]

    assert atr(bars, window=2) is None


def test_volume_trend_matches_hand_computed_ratio_to_its_own_average() -> None:
    bars = [
        _bar(high=1, low=1, close=1, volume=100),
        _bar(high=1, low=1, close=1, volume=200),
        _bar(high=1, low=1, close=1, volume=300),
    ]

    latest_volume, average_volume, ratio = volume_trend(bars, window=3)

    assert latest_volume == 300
    assert average_volume == 200.0
    assert ratio == 1.5


def test_volume_trend_returns_none_when_history_is_shorter_than_the_window() -> None:
    bars = [_bar(high=1, low=1, close=1, volume=100)]

    assert volume_trend(bars, window=3) is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && uv run pytest app/tests/test_indicators.py -v`
Expected: FAIL/ERROR — `app.market.indicators` does not exist yet.

- [ ] **Step 3: Implement the indicator math**

```python
# backend/app/market/indicators.py
from app.market.schemas import PriceBar


def sma(values: list[float], window: int) -> float | None:
    if len(values) < window:
        return None
    return sum(values[-window:]) / window


def ema_series(values: list[float], window: int) -> list[float]:
    if len(values) < window:
        return []
    multiplier = 2 / (window + 1)
    series = [sum(values[:window]) / window]
    for value in values[window:]:
        series.append((value - series[-1]) * multiplier + series[-1])
    return series


def ema_latest(values: list[float], window: int) -> float | None:
    series = ema_series(values, window)
    return series[-1] if series else None


def macd(
    values: list[float], fast: int = 12, slow: int = 26, signal: int = 9
) -> tuple[float | None, float | None, float | None]:
    fast_series = ema_series(values, fast)
    slow_series = ema_series(values, slow)
    if not fast_series or not slow_series:
        return None, None, None
    aligned_fast = fast_series[-len(slow_series):]
    macd_line_series = [f - s for f, s in zip(aligned_fast, slow_series, strict=True)]
    macd_line = macd_line_series[-1]
    signal_series = ema_series(macd_line_series, signal)
    if not signal_series:
        return macd_line, None, None
    signal_line = signal_series[-1]
    return macd_line, signal_line, macd_line - signal_line


def rsi(values: list[float], window: int = 14) -> float | None:
    if len(values) < window + 1:
        return None
    deltas = [values[i] - values[i - 1] for i in range(1, len(values))]
    gains = [max(delta, 0.0) for delta in deltas]
    losses = [max(-delta, 0.0) for delta in deltas]
    avg_gain = sum(gains[:window]) / window
    avg_loss = sum(losses[:window]) / window
    for gain, loss in zip(gains[window:], losses[window:], strict=True):
        avg_gain = (avg_gain * (window - 1) + gain) / window
        avg_loss = (avg_loss * (window - 1) + loss) / window
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)


def stochastic(
    bars: list[PriceBar], window: int = 14, smooth: int = 3
) -> tuple[float | None, float | None]:
    if len(bars) < window + smooth - 1:
        return None, None
    percent_k_values: list[float] = []
    for i in range(window - 1, len(bars)):
        window_bars = bars[i - window + 1 : i + 1]
        highest = max(bar.high for bar in window_bars)
        lowest = min(bar.low for bar in window_bars)
        close = bars[i].close
        percent_k = 50.0 if highest == lowest else (close - lowest) / (highest - lowest) * 100
        percent_k_values.append(percent_k)
    latest_k = percent_k_values[-1]
    latest_d = sum(percent_k_values[-smooth:]) / smooth
    return round(latest_k, 2), round(latest_d, 2)


def bollinger_bands(
    values: list[float], window: int = 20, num_std: float = 2.0
) -> tuple[float | None, float | None, float | None]:
    if len(values) < window:
        return None, None, None
    recent = values[-window:]
    middle = sum(recent) / window
    variance = sum((value - middle) ** 2 for value in recent) / window
    std_dev = variance**0.5
    return round(middle + num_std * std_dev, 2), round(middle, 2), round(middle - num_std * std_dev, 2)


def atr(bars: list[PriceBar], window: int = 14) -> float | None:
    if len(bars) < window + 1:
        return None
    true_ranges = [
        max(
            bars[i].high - bars[i].low,
            abs(bars[i].high - bars[i - 1].close),
            abs(bars[i].low - bars[i - 1].close),
        )
        for i in range(1, len(bars))
    ]
    average = sum(true_ranges[:window]) / window
    for true_range in true_ranges[window:]:
        average = (average * (window - 1) + true_range) / window
    return round(average, 2)


def volume_trend(bars: list[PriceBar], window: int = 20) -> tuple[int, float, float] | None:
    if len(bars) < window:
        return None
    recent = bars[-window:]
    average_volume = sum(bar.volume for bar in recent) / window
    latest_volume = bars[-1].volume
    ratio = latest_volume / average_volume if average_volume else 0.0
    return latest_volume, round(average_volume, 2), round(ratio, 2)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && uv run pytest app/tests/test_indicators.py -v`
Expected: PASS (18 tests)

- [ ] **Step 5: Lint and commit**

```bash
cd backend && uv run ruff check app/market/indicators.py app/tests/test_indicators.py
git add backend/app/market/indicators.py backend/app/tests/test_indicators.py
git commit -m "feat: add pure-Python technical indicator math"
```

---

### Task 2: Indicator schemas + orchestration (`compute_technical_indicators`)

**Files:**
- Modify: `backend/app/market/schemas.py`
- Modify: `backend/app/market/indicators.py`
- Test: `backend/app/tests/test_indicators.py`

**Interfaces:**
- Consumes: Task 1's `sma`, `ema_latest`, `macd`, `rsi`, `stochastic`, `bollinger_bands`, `atr`, `volume_trend`; `app.market.schemas.PriceBar`.
- Produces (used by Task 3): `compute_technical_indicators(*, symbol: str, bars: list[PriceBar]) -> TechnicalIndicators`, and the `TechnicalIndicators` schema (with nested `MovingAverages`, `MacdIndicator`, `RsiIndicator`, `StochasticIndicator`, `BollingerBandsIndicator`, `AtrIndicator`, `VolumeTrendIndicator`), all in `app.market.schemas`.

- [ ] **Step 1: Add the schemas**

Append to `backend/app/market/schemas.py`:

```python
class MovingAverages(MarketModel):
    sma_20: float | None = None
    sma_50: float | None = None
    sma_200: float | None = None
    ema_12: float | None = None
    ema_26: float | None = None
    read: str


class MacdIndicator(MarketModel):
    macd_line: float | None = None
    signal_line: float | None = None
    histogram: float | None = None
    read: str


class RsiIndicator(MarketModel):
    value: float | None = None
    read: str


class StochasticIndicator(MarketModel):
    percent_k: float | None = None
    percent_d: float | None = None
    read: str


class BollingerBandsIndicator(MarketModel):
    upper: float | None = None
    middle: float | None = None
    lower: float | None = None
    read: str


class AtrIndicator(MarketModel):
    value: float | None = None
    read: str


class VolumeTrendIndicator(MarketModel):
    latest_volume: int | None = None
    average_volume: float | None = None
    ratio: float | None = None
    read: str


class TechnicalIndicators(MarketModel):
    symbol: str
    as_of: datetime
    data_points: int
    moving_averages: MovingAverages
    macd: MacdIndicator
    rsi: RsiIndicator
    stochastic: StochasticIndicator
    bollinger_bands: BollingerBandsIndicator
    atr: AtrIndicator
    volume_trend: VolumeTrendIndicator
    insufficient_history_notes: list[str]
```

`datetime` is already imported at the top of `schemas.py`; no new import needed there.

- [ ] **Step 2: Write the failing orchestration test**

Append to `backend/app/tests/test_indicators.py`:

```python
from app.market.indicators import compute_technical_indicators


def _daily_bars(count: int) -> list[PriceBar]:
    bars = []
    for i in range(count):
        close = 100.0 + i
        bars.append(
            PriceBar(
                timestamp=datetime(2026, 1, 1 + i, tzinfo=UTC),
                open=close,
                high=close + 1,
                low=close - 1,
                close=close,
                volume=1000,
            )
        )
    return bars


def test_compute_technical_indicators_degrades_gracefully_on_short_history() -> None:
    result = compute_technical_indicators(symbol="test", bars=_daily_bars(25))

    assert result.symbol == "TEST"
    assert result.data_points == 25
    assert result.moving_averages.sma_20 is not None
    assert result.moving_averages.sma_50 is None
    assert result.moving_averages.sma_200 is None
    assert result.macd.macd_line is None
    assert result.rsi.value is not None
    assert result.bollinger_bands.upper is not None
    assert result.atr.value is not None
    assert result.volume_trend.ratio is not None
    notes = result.insufficient_history_notes
    assert any("SMA(50)" in note for note in notes)
    assert any("SMA(200)" in note for note in notes)
    assert any("MACD" in note for note in notes)


def test_compute_technical_indicators_reads_reflect_thresholds() -> None:
    rising = compute_technical_indicators(symbol="UP", bars=_daily_bars(60))

    assert "Uptrend" in rising.moving_averages.read
    assert "Overbought" in rising.rsi.read
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `cd backend && uv run pytest app/tests/test_indicators.py -v`
Expected: FAIL — `compute_technical_indicators` not defined.

- [ ] **Step 4: Implement the orchestration function**

At the top of `backend/app/market/indicators.py`, replace the single existing import line
(`from app.market.schemas import PriceBar`) with:

```python
from datetime import UTC, datetime

from app.market.schemas import (
    AtrIndicator,
    BollingerBandsIndicator,
    MacdIndicator,
    MovingAverages,
    PriceBar,
    RsiIndicator,
    StochasticIndicator,
    TechnicalIndicators,
    VolumeTrendIndicator,
)
```

Then append the orchestration function and its helpers to the end of the file:

```python
def compute_technical_indicators(*, symbol: str, bars: list[PriceBar]) -> TechnicalIndicators:
    ordered = sorted(bars, key=lambda bar: bar.timestamp)
    closes = [bar.close for bar in ordered]
    latest_close = closes[-1] if closes else None
    notes: list[str] = []

    sma_20, sma_50, sma_200 = sma(closes, 20), sma(closes, 50), sma(closes, 200)
    for label, window, value in (("SMA(20)", 20, sma_20), ("SMA(50)", 50, sma_50), ("SMA(200)", 200, sma_200)):
        if value is None:
            notes.append(f"Not enough history for {label}: need {window} daily bars, have {len(closes)}.")
    moving_averages = MovingAverages(
        sma_20=sma_20,
        sma_50=sma_50,
        sma_200=sma_200,
        ema_12=ema_latest(closes, 12),
        ema_26=ema_latest(closes, 26),
        read=_moving_average_read(latest_close, sma_50, sma_200),
    )

    macd_line, signal_line, histogram = macd(closes)
    if macd_line is None:
        notes.append(f"Not enough history for MACD: need 26 daily bars, have {len(closes)}.")
    macd_indicator = MacdIndicator(
        macd_line=macd_line, signal_line=signal_line, histogram=histogram, read=_macd_read(histogram)
    )

    rsi_value = rsi(closes)
    if rsi_value is None:
        notes.append(f"Not enough history for RSI(14): need 15 daily bars, have {len(closes)}.")
    rsi_indicator = RsiIndicator(value=rsi_value, read=_rsi_read(rsi_value))

    percent_k, percent_d = stochastic(ordered)
    if percent_k is None:
        notes.append(f"Not enough history for the stochastic oscillator: need 16 daily bars, have {len(closes)}.")
    stochastic_indicator = StochasticIndicator(
        percent_k=percent_k, percent_d=percent_d, read=_stochastic_read(percent_k)
    )

    upper, middle, lower = bollinger_bands(closes)
    if upper is None:
        notes.append(f"Not enough history for Bollinger Bands(20): need 20 daily bars, have {len(closes)}.")
    bollinger_indicator = BollingerBandsIndicator(
        upper=upper, middle=middle, lower=lower, read=_bollinger_read(latest_close, upper, lower)
    )

    atr_value = atr(ordered)
    if atr_value is None:
        notes.append(f"Not enough history for ATR(14): need 15 daily bars, have {len(closes)}.")
    atr_indicator = AtrIndicator(value=atr_value, read=_atr_read(atr_value, latest_close))

    volume_result = volume_trend(ordered)
    if volume_result is None:
        notes.append(f"Not enough history for the volume trend: need 20 daily bars, have {len(closes)}.")
        volume_indicator = VolumeTrendIndicator(read=_volume_trend_read(None))
    else:
        latest_volume, average_volume, ratio = volume_result
        volume_indicator = VolumeTrendIndicator(
            latest_volume=latest_volume,
            average_volume=average_volume,
            ratio=ratio,
            read=_volume_trend_read(ratio),
        )

    return TechnicalIndicators(
        symbol=symbol.upper(),
        as_of=datetime.now(UTC),
        data_points=len(closes),
        moving_averages=moving_averages,
        macd=macd_indicator,
        rsi=rsi_indicator,
        stochastic=stochastic_indicator,
        bollinger_bands=bollinger_indicator,
        atr=atr_indicator,
        volume_trend=volume_indicator,
        insufficient_history_notes=notes,
    )


def _moving_average_read(latest_close: float | None, sma_50: float | None, sma_200: float | None) -> str:
    if latest_close is None or sma_50 is None or sma_200 is None:
        return "Not enough history to characterize the trend."
    if latest_close > sma_50 > sma_200:
        return "Uptrend: price is above both the 50- and 200-day averages."
    if latest_close < sma_50 < sma_200:
        return "Downtrend: price is below both the 50- and 200-day averages."
    return "Mixed trend: price and moving averages disagree on direction."


def _macd_read(histogram: float | None) -> str:
    if histogram is None:
        return "Not enough history to compute MACD."
    if histogram > 0:
        return "Bullish: MACD line is above its signal line."
    if histogram < 0:
        return "Bearish: MACD line is below its signal line."
    return "Flat: MACD line is at its signal line."


def _rsi_read(value: float | None) -> str:
    if value is None:
        return "Not enough history to compute RSI."
    if value >= 70:
        return f"Overbought (RSI {value:.1f})."
    if value <= 30:
        return f"Oversold (RSI {value:.1f})."
    return f"Neutral (RSI {value:.1f})."


def _stochastic_read(percent_k: float | None) -> str:
    if percent_k is None:
        return "Not enough history to compute the stochastic oscillator."
    if percent_k >= 80:
        return f"Overbought (%K {percent_k:.1f})."
    if percent_k <= 20:
        return f"Oversold (%K {percent_k:.1f})."
    return f"Neutral (%K {percent_k:.1f})."


def _bollinger_read(latest_close: float | None, upper: float | None, lower: float | None) -> str:
    if latest_close is None or upper is None or lower is None:
        return "Not enough history to compute Bollinger Bands."
    if latest_close >= upper:
        return "Price is at or above the upper Bollinger Band."
    if latest_close <= lower:
        return "Price is at or below the lower Bollinger Band."
    return "Price is within its Bollinger Bands."


def _atr_read(value: float | None, latest_close: float | None) -> str:
    if value is None or not latest_close:
        return "Not enough history to compute ATR."
    percent_of_price = value / latest_close * 100
    return f"Average true range is {value:.2f} ({percent_of_price:.1f}% of price) over the last 14 sessions."


def _volume_trend_read(ratio: float | None) -> str:
    if ratio is None:
        return "Not enough history to compute the volume trend."
    if ratio >= 1.5:
        return f"Volume is {ratio:.1f}x its 20-day average -- notably elevated."
    if ratio <= 0.5:
        return f"Volume is {ratio:.1f}x its 20-day average -- notably light."
    return f"Volume is {ratio:.1f}x its 20-day average."
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd backend && uv run pytest app/tests/test_indicators.py -v`
Expected: PASS (all tests, including the two new orchestration tests)

- [ ] **Step 6: Lint and commit**

```bash
cd backend && uv run ruff check app/market/schemas.py app/market/indicators.py app/tests/test_indicators.py
git add backend/app/market/schemas.py backend/app/market/indicators.py backend/app/tests/test_indicators.py
git commit -m "feat: compute technical indicators with graceful history degradation"
```

---

### Task 3: `get_technical_indicators` tool

**Files:**
- Modify: `backend/app/services/market_data.py`
- Modify: `backend/app/services/assistant.py`
- Test: `backend/app/tests/test_assistant.py`

**Interfaces:**
- Consumes: Task 2's `compute_technical_indicators`; existing `get_stock_history`, `normalize_symbol` in `market_data.py`.
- Produces (used by Task 6): `get_stock_indicators(*, symbol: str, settings: Settings) -> TechnicalIndicators` in `app.services.market_data`.

- [ ] **Step 1: Add the service wrapper**

In `backend/app/services/market_data.py`, add the import and function:

```python
from app.market.indicators import compute_technical_indicators
```

```python
async def get_stock_indicators(*, symbol: str, settings: Settings) -> TechnicalIndicators:
    symbol = normalize_symbol(symbol)
    history = await get_stock_history(symbol=symbol, period="1Y", settings=settings)
    return compute_technical_indicators(symbol=symbol, bars=history.points)
```

Add `TechnicalIndicators` to the existing `from app.market.schemas import (...)` block at the top of the file.

- [ ] **Step 2: Write the failing tool test**

Add to `backend/app/tests/test_assistant.py` (extend the existing import from `app.services.assistant` to include nothing new — `_execute_tool` is already imported):

```python
async def test_execute_tool_does_not_sync_for_technical_indicators() -> None:
    engine, session_factory, settings, user_id = await _user_session()

    fake_indicators = SimpleNamespace(model_dump=lambda mode=None: {"symbol": "AAPL"})

    async with session_factory() as session:
        with (
            patch(
                "app.services.assistant.sync_stale_brokerage_connections", new=AsyncMock()
            ) as brokerage_sync,
            patch(
                "app.services.assistant.sync_stale_money_connections", new=AsyncMock()
            ) as money_sync,
            patch(
                "app.services.assistant.get_stock_indicators",
                new=AsyncMock(return_value=fake_indicators),
            ) as lookup,
        ):
            result = await _execute_tool(
                "get_technical_indicators",
                {"symbol": "aapl"},
                session=session,
                user_id=user_id,
                settings=settings,
            )
        brokerage_sync.assert_not_awaited()
        money_sync.assert_not_awaited()
        lookup.assert_awaited_once_with(symbol="AAPL", settings=settings)
        assert result == {"symbol": "AAPL"}

    await engine.dispose()


def test_technical_indicators_tool_is_registered() -> None:
    tool = next(item for item in TOOLS if item.get("name") == "get_technical_indicators")

    assert tool["input_schema"]["required"] == ["symbol"]
    assert "RSI" in tool["description"]
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `cd backend && uv run pytest app/tests/test_assistant.py -v -k technical_indicators`
Expected: FAIL — tool `get_technical_indicators` not found / `get_stock_indicators` not imported in `assistant.py`.

- [ ] **Step 4: Wire the tool into `assistant.py`**

Add to the import from `app.services.market_data` (or add a new import line if one doesn't already exist — today `assistant.py` doesn't import from `market_data`, so add):

```python
from app.services.market_data import get_stock_indicators
```

Add to the `TOOLS` list, immediately after the `get_insider_activity` entry and before `WEB_SEARCH_TOOL`:

```python
    {
        "name": "get_technical_indicators",
        "description": (
            "Calculate current technical indicators for a ticker from its own daily price "
            "history: moving averages (SMA 20/50/200, EMA 12/26) with a trend read, MACD, "
            "RSI(14), stochastic oscillator, Bollinger Bands, ATR(14), and volume vs. its "
            "20-day average. Use this for questions about a stock's technical picture -- "
            "momentum, overbought/oversold, volatility, or unusual volume."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Ticker symbol, e.g. AAPL."},
            },
            "required": ["symbol"],
            "additionalProperties": False,
        },
    },
```

Add to `_execute_tool`, after the `get_insider_activity` branch and before the final `return {"error": ...}`:

```python
    if name == "get_technical_indicators":
        symbol = str(tool_input.get("symbol", "")).strip().upper()
        if not symbol:
            return {"error": "no symbol provided"}
        indicators = await get_stock_indicators(symbol=symbol, settings=settings)
        return indicators.model_dump(mode="json")
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd backend && uv run pytest app/tests/test_assistant.py -v -k technical_indicators`
Expected: PASS (2 tests)

- [ ] **Step 6: Run the full assistant test file to check for regressions**

Run: `cd backend && uv run pytest app/tests/test_assistant.py -v`
Expected: PASS (all tests, old and new)

- [ ] **Step 7: Lint and commit**

```bash
cd backend && uv run ruff check app/services/market_data.py app/services/assistant.py app/tests/test_assistant.py
git add backend/app/services/market_data.py backend/app/services/assistant.py backend/app/tests/test_assistant.py
git commit -m "feat: add get_technical_indicators assistant tool"
```

---

### Task 4: SEC ticker→CIK resolver

**Files:**
- Modify: `backend/app/providers/sec/client.py`
- Test: `backend/app/tests/test_sec_adapter.py`

**Interfaces:**
- Consumes: nothing new (uses `httpx`, the existing `SecEdgarAdapter.__init__(*, user_agent: str, http: httpx.AsyncClient | None = None)`).
- Produces (used by Task 5): `SecEdgarAdapter.resolve_cik(self, symbol: str) -> str | None`.

- [ ] **Step 1: Write the failing test**

Add to `backend/app/tests/test_sec_adapter.py`:

```python
import app.providers.sec.client as sec_client_module


async def test_resolve_cik_looks_up_ticker_in_sec_company_tickers_json() -> None:
    sec_client_module._TICKER_CIK_CACHE.clear()
    sec_client_module._TICKER_CIK_CACHE_LOADED_AT = None
    payload = {
        "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
        "1": {"cik_str": 789019, "ticker": "MSFT", "title": "Microsoft Corp"},
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["User-Agent"] == "Posted test@example.com"
        assert request.url.path.endswith("company_tickers.json")
        return httpx.Response(200, json=payload)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        headers={"User-Agent": "Posted test@example.com"},
    ) as http:
        adapter = sec_client_module.SecEdgarAdapter(user_agent="Posted test@example.com", http=http)
        cik = await adapter.resolve_cik("aapl")
        missing = await adapter.resolve_cik("ZZZZ")

    assert cik == "320193"
    assert missing is None


async def test_resolve_cik_reuses_the_cache_within_the_ttl() -> None:
    sec_client_module._TICKER_CIK_CACHE.clear()
    sec_client_module._TICKER_CIK_CACHE_LOADED_AT = None
    payload = {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}}
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(200, json=payload)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        headers={"User-Agent": "Posted test@example.com"},
    ) as http:
        adapter = sec_client_module.SecEdgarAdapter(user_agent="Posted test@example.com", http=http)
        await adapter.resolve_cik("AAPL")
        await adapter.resolve_cik("AAPL")

    assert call_count == 1
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && uv run pytest app/tests/test_sec_adapter.py -v -k resolve_cik`
Expected: FAIL — `resolve_cik` / `_TICKER_CIK_CACHE` do not exist yet.

- [ ] **Step 3: Implement the resolver**

In `backend/app/providers/sec/client.py`, add `import time` to the existing top-of-file
stdlib import group (alongside `import asyncio`):

```python
import asyncio
import time
from datetime import UTC, date, datetime, timedelta
```

Then add these constants directly after the existing `DEFAULT_FORMS` constant:

```python
TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"
_TICKER_CIK_CACHE_TTL_SECONDS = 24 * 60 * 60
_TICKER_CIK_CACHE: dict[str, str] = {}
_TICKER_CIK_CACHE_LOADED_AT: float | None = None
```

Add a method to `SecEdgarAdapter` (below `fetch_recent_filings`):

```python
    async def resolve_cik(self, symbol: str) -> str | None:
        await self._ensure_ticker_cache()
        return _TICKER_CIK_CACHE.get(symbol.upper())

    async def _ensure_ticker_cache(self) -> None:
        global _TICKER_CIK_CACHE_LOADED_AT
        now = time.monotonic()
        if (
            _TICKER_CIK_CACHE_LOADED_AT is not None
            and now - _TICKER_CIK_CACHE_LOADED_AT < _TICKER_CIK_CACHE_TTL_SECONDS
        ):
            return
        owns_client = self._http is None
        client = self._http or httpx.AsyncClient(
            timeout=20, headers={"User-Agent": self._user_agent, "Accept": "application/json"}
        )
        try:
            response = await client.get(
                TICKER_MAP_URL,
                headers={"User-Agent": self._user_agent, "Accept": "application/json"},
            )
            response.raise_for_status()
            payload = response.json()
        finally:
            if owns_client:
                await client.aclose()
        _TICKER_CIK_CACHE.clear()
        for entry in payload.values():
            ticker = str(entry.get("ticker") or "").upper()
            cik = entry.get("cik_str")
            if ticker and cik is not None:
                _TICKER_CIK_CACHE[ticker] = str(cik)
        _TICKER_CIK_CACHE_LOADED_AT = now
```

`SecEdgarAdapter.__init__` already stores `self._user_agent` and `self._http` — no constructor change needed.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && uv run pytest app/tests/test_sec_adapter.py -v`
Expected: PASS (all tests, old and new)

- [ ] **Step 5: Lint and commit**

```bash
cd backend && uv run ruff check app/providers/sec/client.py app/tests/test_sec_adapter.py
git add backend/app/providers/sec/client.py backend/app/tests/test_sec_adapter.py
git commit -m "feat: add cached SEC ticker-to-CIK resolver"
```

---

### Task 5: `get_sec_filings` tool

**Files:**
- Create: `backend/app/services/sec_filings.py`
- Modify: `backend/app/services/assistant.py`
- Test: `backend/app/tests/test_sec_filings.py`
- Test: `backend/app/tests/test_assistant.py`

**Interfaces:**
- Consumes: Task 4's `SecEdgarAdapter.resolve_cik`, existing `SecEdgarAdapter.fetch_recent_filings`.
- Produces (used by Task 6): `get_recent_filings(*, symbol: str, settings: Settings, days: int = 90, limit: int = 10) -> dict[str, object]` in `app.services.sec_filings`.

- [ ] **Step 1: Write the failing service test**

```python
# backend/app/tests/test_sec_filings.py
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from app.config import Settings
from app.domain.enums import EventProvider
from app.domain.models import ProviderEventEnvelope
from app.services.sec_filings import get_recent_filings


def _envelope(**overrides: object) -> ProviderEventEnvelope:
    from datetime import UTC, datetime

    defaults = dict(
        provider=EventProvider.SEC,
        provider_event_id=str(uuid4()),
        source_name="SEC EDGAR",
        source_url="https://www.sec.gov/example",
        headline="AAPL filed 8-K: Current report",
        summary=None,
        published_at=datetime(2026, 7, 21, tzinfo=UTC),
        received_at=datetime(2026, 7, 21, tzinfo=UTC),
        symbols=("AAPL",),
        form_type="8-K",
    )
    defaults.update(overrides)
    return ProviderEventEnvelope(**defaults)


async def test_get_recent_filings_returns_empty_with_a_note_when_cik_is_unresolvable() -> None:
    with patch(
        "app.services.sec_filings.SecEdgarAdapter.resolve_cik", new=AsyncMock(return_value=None)
    ):
        result = await get_recent_filings(symbol="ZZZZ", settings=Settings())

    assert result["symbol"] == "ZZZZ"
    assert result["filings"] == []
    assert "No SEC CIK found" in result["note"]


async def test_get_recent_filings_maps_envelopes_to_compact_dicts() -> None:
    with (
        patch(
            "app.services.sec_filings.SecEdgarAdapter.resolve_cik",
            new=AsyncMock(return_value="320193"),
        ),
        patch(
            "app.services.sec_filings.SecEdgarAdapter.fetch_recent_filings",
            new=AsyncMock(return_value=(_envelope(),)),
        ) as fetch,
    ):
        result = await get_recent_filings(symbol="aapl", settings=Settings())

    fetch.assert_awaited_once()
    assert fetch.await_args.kwargs["companies"] == {"AAPL": "320193"}
    assert result["symbol"] == "AAPL"
    assert result["filings"] == [
        {
            "form_type": "8-K",
            "headline": "AAPL filed 8-K: Current report",
            "source_url": "https://www.sec.gov/example",
            "filed_at": "2026-07-21T00:00:00+00:00",
        }
    ]
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd backend && uv run pytest app/tests/test_sec_filings.py -v`
Expected: FAIL — `app.services.sec_filings` does not exist yet.

- [ ] **Step 3: Implement the service**

```python
# backend/app/services/sec_filings.py
from datetime import date, timedelta
from typing import Any

from app.config import Settings
from app.providers.sec.client import SecEdgarAdapter


async def get_recent_filings(
    *, symbol: str, settings: Settings, days: int = 90, limit: int = 10
) -> dict[str, Any]:
    symbol = symbol.strip().upper()
    adapter = SecEdgarAdapter(user_agent=settings.sec_user_agent)
    cik = await adapter.resolve_cik(symbol)
    if cik is None:
        return {"symbol": symbol, "filings": [], "note": f"No SEC CIK found for {symbol}."}

    events = await adapter.fetch_recent_filings(
        companies={symbol: cik}, since=date.today() - timedelta(days=days)
    )
    return {
        "symbol": symbol,
        "filings": [
            {
                "form_type": event.form_type,
                "headline": event.headline,
                "source_url": event.source_url,
                "filed_at": event.published_at.isoformat(),
            }
            for event in events[:limit]
        ],
    }
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd backend && uv run pytest app/tests/test_sec_filings.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Write the failing tool test**

Add to `backend/app/tests/test_assistant.py`:

```python
async def test_execute_tool_does_not_sync_for_sec_filings() -> None:
    engine, session_factory, settings, user_id = await _user_session()

    fake_result = {"symbol": "AAPL", "filings": []}

    async with session_factory() as session:
        with (
            patch(
                "app.services.assistant.sync_stale_brokerage_connections", new=AsyncMock()
            ) as brokerage_sync,
            patch(
                "app.services.assistant.sync_stale_money_connections", new=AsyncMock()
            ) as money_sync,
            patch(
                "app.services.assistant.get_recent_filings",
                new=AsyncMock(return_value=fake_result),
            ) as lookup,
        ):
            result = await _execute_tool(
                "get_sec_filings",
                {"symbol": "aapl"},
                session=session,
                user_id=user_id,
                settings=settings,
            )
        brokerage_sync.assert_not_awaited()
        money_sync.assert_not_awaited()
        lookup.assert_awaited_once_with(symbol="AAPL", settings=settings)
        assert result == fake_result

    await engine.dispose()


def test_sec_filings_tool_is_registered() -> None:
    tool = next(item for item in TOOLS if item.get("name") == "get_sec_filings")

    assert tool["input_schema"]["required"] == ["symbol"]
    assert "EDGAR" in tool["description"] or "SEC" in tool["description"]
```

- [ ] **Step 6: Run the tests to verify they fail**

Run: `cd backend && uv run pytest app/tests/test_assistant.py -v -k sec_filings`
Expected: FAIL — tool not registered / `get_recent_filings` not imported in `assistant.py`.

- [ ] **Step 7: Wire the tool into `assistant.py`**

Add import:

```python
from app.services.sec_filings import get_recent_filings
```

Add to `TOOLS`, after the `get_technical_indicators` entry:

```python
    {
        "name": "get_sec_filings",
        "description": (
            "Get a ticker's recent material SEC filings (8-K, 10-K, 10-Q, 6-K, 20-F) with "
            "filing date, a short description, and a link to the filing on EDGAR. Use for "
            "questions about recent company disclosures or filings, separate from news "
            "commentary."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Ticker symbol, e.g. AAPL."},
            },
            "required": ["symbol"],
            "additionalProperties": False,
        },
    },
```

Add to `_execute_tool`, after the `get_technical_indicators` branch:

```python
    if name == "get_sec_filings":
        symbol = str(tool_input.get("symbol", "")).strip().upper()
        if not symbol:
            return {"error": "no symbol provided"}
        try:
            return await get_recent_filings(symbol=symbol, settings=settings)
        except Exception as exc:  # noqa: BLE001 - a broken filings lookup must not crash the turn
            return {"error": f"SEC filings lookup failed: {exc}"}
```

- [ ] **Step 8: Run the tests to verify they pass**

Run: `cd backend && uv run pytest app/tests/test_assistant.py -v -k sec_filings`
Expected: PASS (2 tests)

- [ ] **Step 9: Lint and commit**

```bash
cd backend && uv run ruff check app/services/sec_filings.py app/services/assistant.py app/tests/test_sec_filings.py app/tests/test_assistant.py
git add backend/app/services/sec_filings.py backend/app/services/assistant.py backend/app/tests/test_sec_filings.py backend/app/tests/test_assistant.py
git commit -m "feat: add get_sec_filings assistant tool"
```

---

### Task 6: `run_stock_research` deep-research bundle

**Files:**
- Create: `backend/app/services/stock_research.py`
- Modify: `backend/app/services/assistant.py`
- Test: `backend/app/tests/test_stock_research.py`
- Test: `backend/app/tests/test_assistant.py`

**Interfaces:**
- Consumes: existing `get_stock_detail` (`market_data.py`), Task 3's `get_stock_indicators`, existing `summarize_insider_activity`/`interpret_insider_activity` (`insider_analysis.py`), existing `MultiSourceNewsAdapter` (`app.providers.news.multi`), Task 5's `get_recent_filings`.
- Produces (used by Task 7's system-prompt wiring, and the tool dispatch below): `run_stock_research(session: AsyncSession, *, user_id: UUID, symbol: str, settings: Settings) -> dict[str, Any]` in `app.services.stock_research`.

- [ ] **Step 1: Write the failing service test**

```python
# backend/app/tests/test_stock_research.py
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from app.config import Settings
from app.market.schemas import (
    CompanyProfile,
    InsiderSentimentPoint,
    InsiderTransaction,
    MarketQuote,
)
from app.services.stock_research import run_stock_research


def _detail(*, position=None):
    from datetime import UTC, date, datetime

    return SimpleNamespace(
        symbol="AAPL",
        name="Apple Inc.",
        quote=MarketQuote(
            price=200.0,
            change=1.0,
            change_percent=0.5,
            timestamp=datetime(2026, 8, 1, tzinfo=UTC),
            source="Alpaca IEX",
            freshness="real_time_iex",
        ),
        company=CompanyProfile(sector="Technology"),
        earnings=[],
        insider_transactions=[
            InsiderTransaction(
                id="tx-1",
                name="Example Insider",
                filing_date=date(2026, 7, 1),
                transaction_date=date(2026, 6, 30),
                transaction_code="S",
                shares_changed=-500,
                transaction_price=190.0,
            )
        ],
        insider_sentiment=[InsiderSentimentPoint(year=2026, month=6, change=-500, mspr=-20)],
        position=position,
    )


async def test_run_stock_research_bundles_all_sources_concurrently() -> None:
    fake_indicators = SimpleNamespace(model_dump=lambda mode=None: {"rsi": {"value": 55.0}})
    fake_news = SimpleNamespace(
        providers=("alpaca",),
        warnings=(),
        envelopes=(),
    )
    fake_filings = {"symbol": "AAPL", "filings": []}

    with (
        patch(
            "app.services.stock_research.get_stock_detail", new=AsyncMock(return_value=_detail())
        ),
        patch(
            "app.services.stock_research.get_stock_indicators",
            new=AsyncMock(return_value=fake_indicators),
        ),
        patch(
            "app.services.stock_research.MultiSourceNewsAdapter"
        ) as adapter_cls,
        patch(
            "app.services.stock_research.get_recent_filings",
            new=AsyncMock(return_value=fake_filings),
        ),
    ):
        adapter_cls.return_value.fetch_company_news = AsyncMock(return_value=fake_news)
        result = await run_stock_research(
            None, user_id=uuid4(), symbol="aapl", settings=Settings()
        )

    assert result["symbol"] == "AAPL"
    assert result["technical_indicators"] == {"rsi": {"value": 55.0}}
    assert result["sec_filings"] == fake_filings
    assert result["news"]["providers"] == ["alpaca"]
    assert result["insider_summary"]["signal"] == "Moderate insider distribution"
    assert "not investment advice" in result["disclaimer"]


async def test_run_stock_research_keeps_the_bundle_when_news_lookup_fails() -> None:
    fake_indicators = SimpleNamespace(model_dump=lambda mode=None: {})
    fake_filings = {"symbol": "AAPL", "filings": []}

    with (
        patch(
            "app.services.stock_research.get_stock_detail", new=AsyncMock(return_value=_detail())
        ),
        patch(
            "app.services.stock_research.get_stock_indicators",
            new=AsyncMock(return_value=fake_indicators),
        ),
        patch("app.services.stock_research.MultiSourceNewsAdapter") as adapter_cls,
        patch(
            "app.services.stock_research.get_recent_filings",
            new=AsyncMock(return_value=fake_filings),
        ),
    ):
        adapter_cls.return_value.fetch_company_news = AsyncMock(side_effect=RuntimeError("boom"))
        result = await run_stock_research(
            None, user_id=uuid4(), symbol="AAPL", settings=Settings()
        )

    assert "error" in result["news"]
    assert result["symbol"] == "AAPL"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && uv run pytest app/tests/test_stock_research.py -v`
Expected: FAIL — `app.services.stock_research` does not exist yet.

- [ ] **Step 3: Implement the bundle**

```python
# backend/app/services/stock_research.py
import asyncio
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.providers.news.multi import MultiSourceNewsAdapter
from app.services.insider_analysis import interpret_insider_activity, summarize_insider_activity
from app.services.market_data import get_stock_detail, get_stock_indicators, normalize_symbol
from app.services.sec_filings import get_recent_filings


async def run_stock_research(
    session: AsyncSession, *, user_id: UUID, symbol: str, settings: Settings
) -> dict[str, Any]:
    symbol = normalize_symbol(symbol)

    async def _safe_news() -> dict[str, Any]:
        try:
            result = await MultiSourceNewsAdapter(settings=settings).fetch_company_news(
                symbols=[symbol], limit=10
            )
        except Exception as exc:  # noqa: BLE001 - one failing source must not break the bundle
            return {"error": f"news lookup failed: {exc}"}
        return {
            "providers": list(result.providers),
            "articles": [
                {
                    "headline": envelope.headline,
                    "summary": envelope.summary,
                    "source": envelope.source_name,
                    "url": envelope.source_url,
                    "published_at": envelope.published_at.isoformat(),
                }
                for envelope in result.envelopes
            ],
        }

    async def _safe_filings() -> dict[str, Any]:
        try:
            return await get_recent_filings(symbol=symbol, settings=settings)
        except Exception as exc:  # noqa: BLE001 - one failing source must not break the bundle
            return {"error": f"SEC filings lookup failed: {exc}"}

    async def _safe_indicators() -> dict[str, Any]:
        try:
            indicators = await get_stock_indicators(symbol=symbol, settings=settings)
        except Exception as exc:  # noqa: BLE001 - one failing source must not break the bundle
            return {"error": f"indicator calculation failed: {exc}"}
        return indicators.model_dump(mode="json")

    detail, indicators, news, filings = await asyncio.gather(
        get_stock_detail(session, user_id=user_id, symbol=symbol, settings=settings),
        _safe_indicators(),
        _safe_news(),
        _safe_filings(),
    )

    insider_summary = summarize_insider_activity(
        transactions=detail.insider_transactions, sentiment=detail.insider_sentiment
    )
    insider_interpretation = interpret_insider_activity(
        symbol=symbol, summary=insider_summary, has_position=detail.position is not None
    )

    return {
        "symbol": symbol,
        "company_name": detail.name,
        "quote": detail.quote.model_dump(mode="json"),
        "company_profile": detail.company.model_dump(mode="json"),
        "earnings": [item.model_dump(mode="json") for item in detail.earnings],
        "position": detail.position.model_dump(mode="json") if detail.position else None,
        "technical_indicators": indicators,
        "insider_summary": insider_summary.model_dump(mode="json"),
        "insider_interpretation": insider_interpretation.model_dump(mode="json"),
        "news": news,
        "sec_filings": filings,
        "disclaimer": (
            "This bundle is informational context assembled from multiple third-party "
            "sources; it is not investment advice and no part of it is a recommendation "
            "to buy, sell, or hold."
        ),
    }
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && uv run pytest app/tests/test_stock_research.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Write the failing tool + brokerage-gate tests**

Add to `backend/app/tests/test_assistant.py`. First, **modify** the existing generic brokerage-sync test to also exclude `run_stock_research` (it needs a `symbol` input like `get_insider_activity`, so the empty-input loop can't cover it):

```python
async def test_execute_tool_syncs_only_brokerage_connections_for_portfolio_reads() -> None:
    # get_insider_activity and run_stock_research are also brokerage-backed but need a
    # symbol input and realistic mocks -- each has its own dedicated test instead of this
    # generic empty-input loop.
    engine, session_factory, settings, user_id = await _user_session()

    async with session_factory() as session:
        for tool_name in _BROKERAGE_BACKED_TOOLS - {"get_insider_activity", "run_stock_research"}:
            with (
                patch(
                    "app.services.assistant.sync_stale_brokerage_connections", new=AsyncMock()
                ) as brokerage_sync,
                patch(
                    "app.services.assistant.sync_stale_money_connections", new=AsyncMock()
                ) as money_sync,
            ):
                await _execute_tool(
                    tool_name, {}, session=session, user_id=user_id, settings=settings
                )
            brokerage_sync.assert_awaited_once_with(session, user_id=user_id, settings=settings)
            money_sync.assert_not_awaited()

    await engine.dispose()
```

Then add the new dedicated tests:

```python
async def test_execute_tool_syncs_brokerage_connections_before_stock_research() -> None:
    engine, session_factory, settings, user_id = await _user_session()

    fake_result = {"symbol": "AAPL"}

    async with session_factory() as session:
        with (
            patch(
                "app.services.assistant.sync_stale_brokerage_connections", new=AsyncMock()
            ) as brokerage_sync,
            patch(
                "app.services.assistant.sync_stale_money_connections", new=AsyncMock()
            ) as money_sync,
            patch(
                "app.services.assistant.run_stock_research",
                new=AsyncMock(return_value=fake_result),
            ) as lookup,
        ):
            result = await _execute_tool(
                "run_stock_research",
                {"symbol": "aapl"},
                session=session,
                user_id=user_id,
                settings=settings,
            )
        brokerage_sync.assert_awaited_once_with(session, user_id=user_id, settings=settings)
        money_sync.assert_not_awaited()
        lookup.assert_awaited_once_with(session, user_id=user_id, symbol="AAPL", settings=settings)
        assert result == fake_result

    await engine.dispose()


def test_run_stock_research_tool_is_registered_and_brokerage_backed() -> None:
    tool = next(item for item in TOOLS if item.get("name") == "run_stock_research")

    assert tool["input_schema"]["required"] == ["symbol"]
    assert "deep dive" in tool["description"]
    assert "run_stock_research" in _BROKERAGE_BACKED_TOOLS
```

- [ ] **Step 6: Run the tests to verify they fail**

Run: `cd backend && uv run pytest app/tests/test_assistant.py -v -k stock_research`
Expected: FAIL — tool not registered, `run_stock_research` not imported/not in `_BROKERAGE_BACKED_TOOLS`.

- [ ] **Step 7: Wire the tool into `assistant.py`**

Add import:

```python
from app.services.stock_research import run_stock_research
```

Add `"run_stock_research"` to `_BROKERAGE_BACKED_TOOLS`:

```python
_BROKERAGE_BACKED_TOOLS = {
    "get_portfolio_overview",
    "get_portfolio_holdings",
    "get_insider_activity",
    "run_stock_research",
}
```

Add to `TOOLS`, after the `get_sec_filings` entry:

```python
    {
        "name": "run_stock_research",
        "description": (
            "Run a full independent research workup on a ticker: quote, fundamentals, "
            "earnings, technical indicators (moving averages, MACD, RSI, stochastic, "
            "Bollinger Bands, ATR, volume trend), insider transactions/sentiment with "
            "interpretation, fresh multi-source news, and recent SEC filings -- all in one "
            "call. Use this when the user clearly wants a full workup or deep dive on a "
            "stock (e.g. 'give me a full research report on X', 'do a deep dive on Y'), not "
            "for quick single-fact questions -- those should use the lighter, targeted "
            "tools instead."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Ticker symbol, e.g. AAPL."},
            },
            "required": ["symbol"],
            "additionalProperties": False,
        },
    },
```

Add to `_execute_tool`, after the `get_sec_filings` branch:

```python
    if name == "run_stock_research":
        symbol = str(tool_input.get("symbol", "")).strip().upper()
        if not symbol:
            return {"error": "no symbol provided"}
        return await run_stock_research(session, user_id=user_id, symbol=symbol, settings=settings)
```

- [ ] **Step 8: Run the tests to verify they pass**

Run: `cd backend && uv run pytest app/tests/test_assistant.py -v`
Expected: PASS (all tests, old and new)

- [ ] **Step 9: Lint and commit**

```bash
cd backend && uv run ruff check app/services/stock_research.py app/services/assistant.py app/tests/test_stock_research.py app/tests/test_assistant.py
git add backend/app/services/stock_research.py backend/app/services/assistant.py backend/app/tests/test_stock_research.py backend/app/tests/test_assistant.py
git commit -m "feat: add run_stock_research deep-research assistant tool"
```

---

### Task 7: Model escalation to Sonnet for research turns

**Files:**
- Modify: `backend/app/services/assistant.py`
- Test: `backend/app/tests/test_assistant.py`

**Interfaces:**
- Consumes: `run_assistant_turn`'s existing per-iteration loop.
- Produces: a new module constant `RESEARCH_MODEL = "claude-sonnet-5"` in `app.services.assistant`, and escalation behavior inside `run_assistant_turn`.

- [ ] **Step 1: Write the failing test**

Add to `backend/app/tests/test_assistant.py`. Update the existing import line to also pull in `MODEL` and `RESEARCH_MODEL`:

```python
from app.services.assistant import (
    _BROKERAGE_BACKED_TOOLS,
    _MONEY_BACKED_TOOLS,
    MODEL,
    RELIABLE_DOMAINS,
    RESEARCH_MODEL,
    SYSTEM_PROMPT,
    TOOLS,
    WEB_SEARCH_TOOL,
    AssistantTurnResult,
    _execute_tool,
    _extract_sources,
    run_assistant_turn,
    send_message,
)
```

Then add:

```python
async def test_run_assistant_turn_escalates_to_sonnet_after_stock_research_tool_call() -> None:
    tool_use_response = SimpleNamespace(
        stop_reason="tool_use",
        content=[
            SimpleNamespace(
                type="tool_use", id="tool-1", name="run_stock_research", input={"symbol": "NVDA"}
            )
        ],
    )
    final_response = SimpleNamespace(
        stop_reason="end_turn",
        content=[SimpleNamespace(type="text", text="Here's the research.", citations=None)],
    )
    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(side_effect=[tool_use_response, final_response])

    with (
        patch("app.services.assistant.AsyncAnthropic", return_value=mock_client),
        patch(
            "app.services.assistant._execute_tool",
            new=AsyncMock(return_value={"symbol": "NVDA"}),
        ),
    ):
        result = await run_assistant_turn(
            None,
            user_id=uuid4(),
            settings=Settings(anthropic_api_key="test-key"),
            history=[],
            user_message="Give me a full research report on NVDA",
            section="investing",
        )

    first_model = mock_client.messages.create.await_args_list[0].kwargs["model"]
    second_model = mock_client.messages.create.await_args_list[1].kwargs["model"]
    assert first_model == MODEL
    assert second_model == RESEARCH_MODEL
    assert result.reply == "Here's the research."


async def test_run_assistant_turn_stays_on_the_default_model_without_stock_research() -> None:
    final_response = SimpleNamespace(
        stop_reason="end_turn",
        content=[SimpleNamespace(type="text", text="Your cash balance is $500.", citations=None)],
    )
    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(return_value=final_response)

    with patch("app.services.assistant.AsyncAnthropic", return_value=mock_client):
        await run_assistant_turn(
            None,
            user_id=uuid4(),
            settings=Settings(anthropic_api_key="test-key"),
            history=[],
            user_message="What's my cash balance?",
            section="money",
        )

    assert mock_client.messages.create.await_args_list[0].kwargs["model"] == MODEL
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && uv run pytest app/tests/test_assistant.py -v -k escalat`
Expected: FAIL — `RESEARCH_MODEL` not defined, and/or the model passed to `messages.create` never changes.

- [ ] **Step 3: Implement the escalation**

Add the constant next to the existing `MODEL`:

```python
MODEL = "claude-haiku-4-5"
RESEARCH_MODEL = "claude-sonnet-5"
MAX_TOOL_ITERATIONS = 6
```

In `run_assistant_turn`, initialize the active model before the loop and use it in the `messages.create` call:

```python
    tool_calls_made = 0
    active_model = MODEL
    for _ in range(MAX_TOOL_ITERATIONS):
        try:
            response = await client.messages.create(
                model=active_model,
                max_tokens=1500,
                system=system,
                tools=TOOLS,
                messages=messages,
            )
```

After the existing `tool_use_blocks = [...]` line (inside the `stop_reason == "tool_use"` branch), add:

```python
        if any(block.name == "run_stock_research" for block in tool_use_blocks):
            active_model = RESEARCH_MODEL
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && uv run pytest app/tests/test_assistant.py -v`
Expected: PASS (all tests, old and new)

- [ ] **Step 5: Lint and commit**

```bash
cd backend && uv run ruff check app/services/assistant.py app/tests/test_assistant.py
git add backend/app/services/assistant.py backend/app/tests/test_assistant.py
git commit -m "feat: escalate to claude-sonnet-5 for deep stock research turns"
```

---

### Task 8: System prompt guidance for the new tools

**Files:**
- Modify: `backend/app/services/assistant.py`
- Test: `backend/app/tests/test_assistant.py`

**Interfaces:**
- Consumes: existing `SYSTEM_PROMPT` string.
- Produces: nothing new consumed by later tasks — this is a leaf task.

- [ ] **Step 1: Write the failing test**

Add to `backend/app/tests/test_assistant.py`:

```python
def test_system_prompt_directs_deep_dives_to_stock_research_tool() -> None:
    assert "run_stock_research" in SYSTEM_PROMPT
    assert "deep dive" in SYSTEM_PROMPT


def test_system_prompt_treats_indicators_and_filings_as_context_not_signals() -> None:
    assert "not trading signals" in SYSTEM_PROMPT
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && uv run pytest app/tests/test_assistant.py -v -k system_prompt_directs`
Expected: FAIL — phrases not present in `SYSTEM_PROMPT`.

- [ ] **Step 3: Update the system prompt**

In `SYSTEM_PROMPT`, immediately after the existing bullet that starts `"- When the user asks why a specific stock moved, ..."` and before the `"- For investment analysis, ..."` bullet, insert two new bullets:

```python
    "- When the user clearly wants a full workup or deep dive on a stock (e.g. 'give me a "
    "full research report on X', 'do a deep dive on Y'), use run_stock_research rather than "
    "assembling the same picture from individual tools one at a time. For quick single-fact "
    "questions -- a price, a single indicator, a specific filing -- use the lighter targeted "
    "tool instead and do not over-fetch.\n"
    "- Technical indicators and SEC filings are informational context, not trading signals: "
    "never frame an indicator reading or a filing as a reason to buy, sell, or hold, and "
    "always note when there isn't enough price history to compute an indicator rather than "
    "guessing.\n"
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && uv run pytest app/tests/test_assistant.py -v`
Expected: PASS (all tests, old and new)

- [ ] **Step 5: Lint and commit**

```bash
cd backend && uv run ruff check app/services/assistant.py app/tests/test_assistant.py
git add backend/app/services/assistant.py app/tests/test_assistant.py
git commit -m "docs: guide the assistant on when to use the new research tools"
```

---

### Task 9: Full verification

**Files:** none (verification only).

- [ ] **Step 1: Run the full backend test suite**

Run: `cd backend && uv run pytest`
Expected: PASS, zero failures, including every test added in Tasks 1-8 and every pre-existing test in `test_assistant.py`, `test_sec_adapter.py`, and elsewhere.

- [ ] **Step 2: Run backend lint**

Run: `cd backend && uv run ruff check .`
Expected: no errors.

- [ ] **Step 3: Confirm the Schwab/brokerage sync gate still covers every brokerage-backed tool**

Run: `cd backend && uv run pytest app/tests/test_assistant.py -v -k "brokerage or sync"`
Expected: PASS — specifically confirm `test_execute_tool_syncs_only_brokerage_connections_for_portfolio_reads`, `test_execute_tool_syncs_brokerage_connections_before_insider_activity`, and `test_execute_tool_syncs_brokerage_connections_before_stock_research` are all green, proving `get_portfolio_overview`, `get_portfolio_holdings`, `get_insider_activity`, and `run_stock_research` all still trigger `sync_stale_brokerage_connections` before reading brokerage data.

- [ ] **Step 4: Manual smoke check against a running API (requires `ANTHROPIC_API_KEY` and at least `FINNHUB_API_KEY` in `backend/.env`; demo mode is fine for everything except the new tools, which need live provider keys)**

```bash
make api
```

In a second terminal, exercise the assistant endpoint directly (replace `DEV_USER_ID` auth as the existing dev setup requires):

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/assistant/messages \
  -H 'Content-Type: application/json' \
  -d '{"message": "What is AAPL'\''s RSI and MACD right now?", "section": "investing"}' | jq .
```

Expected: a reply that references real RSI/MACD values (or a clear statement that indicator data wasn't available), not an error. Then:

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/assistant/messages \
  -H 'Content-Type: application/json' \
  -d '{"message": "Give me a full research report on NVDA", "section": "investing"}' | jq .
```

Expected: a longer, synthesized reply covering quote/fundamentals, indicators, insider sentiment, news, and filings, still plain text (no markdown), still declining to recommend buying/selling.

- [ ] **Step 5: Confirm no unrelated files changed**

```bash
git status --short
```

Expected: only the files touched by Tasks 1-8 show as committed on this branch; no other in-progress work (e.g. the SignalWire→Telnyx migration already in the working tree before this plan started) was touched.
