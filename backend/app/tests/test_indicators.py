from datetime import UTC, datetime, timedelta

from app.market.indicators import (
    atr,
    bollinger_bands,
    compute_technical_indicators,
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


def _daily_bars(count: int) -> list[PriceBar]:
    bars = []
    for i in range(count):
        close = 100.0 + i
        bars.append(
            PriceBar(
                timestamp=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(days=i),
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
    rising = compute_technical_indicators(symbol="UP", bars=_daily_bars(200))

    assert "Uptrend" in rising.moving_averages.read
    assert "Overbought" in rising.rsi.read
