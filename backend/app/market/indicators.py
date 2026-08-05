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
    upper = round(middle + num_std * std_dev, 2)
    lower = round(middle - num_std * std_dev, 2)
    return upper, round(middle, 2), lower


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
