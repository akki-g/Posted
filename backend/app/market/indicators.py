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


def compute_technical_indicators(*, symbol: str, bars: list[PriceBar]) -> TechnicalIndicators:
    ordered = sorted(bars, key=lambda bar: bar.timestamp)
    closes = [bar.close for bar in ordered]
    latest_close = closes[-1] if closes else None
    notes: list[str] = []

    sma_20, sma_50, sma_200 = sma(closes, 20), sma(closes, 50), sma(closes, 200)
    sma_windows = (("SMA(20)", 20, sma_20), ("SMA(50)", 50, sma_50), ("SMA(200)", 200, sma_200))
    for label, window, value in sma_windows:
        if value is None:
            notes.append(
                f"Not enough history for {label}: need {window} daily bars, have {len(closes)}."
            )
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
        macd_line=macd_line,
        signal_line=signal_line,
        histogram=histogram,
        read=_macd_read(histogram),
    )

    rsi_value = rsi(closes)
    if rsi_value is None:
        notes.append(f"Not enough history for RSI(14): need 15 daily bars, have {len(closes)}.")
    rsi_indicator = RsiIndicator(value=rsi_value, read=_rsi_read(rsi_value))

    percent_k, percent_d = stochastic(ordered)
    if percent_k is None:
        notes.append(
            "Not enough history for the stochastic oscillator: "
            f"need 16 daily bars, have {len(closes)}."
        )
    stochastic_indicator = StochasticIndicator(
        percent_k=percent_k, percent_d=percent_d, read=_stochastic_read(percent_k)
    )

    upper, middle, lower = bollinger_bands(closes)
    if upper is None:
        notes.append(
            f"Not enough history for Bollinger Bands(20): need 20 daily bars, have {len(closes)}."
        )
    bollinger_indicator = BollingerBandsIndicator(
        upper=upper,
        middle=middle,
        lower=lower,
        read=_bollinger_read(latest_close, upper, lower),
    )

    atr_value = atr(ordered)
    if atr_value is None:
        notes.append(f"Not enough history for ATR(14): need 15 daily bars, have {len(closes)}.")
    atr_indicator = AtrIndicator(value=atr_value, read=_atr_read(atr_value, latest_close))

    volume_result = volume_trend(ordered)
    if volume_result is None:
        notes.append(
            f"Not enough history for the volume trend: need 20 daily bars, have {len(closes)}."
        )
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


def _moving_average_read(
    latest_close: float | None, sma_50: float | None, sma_200: float | None
) -> str:
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
    return (
        f"Average true range is {value:.2f} ({percent_of_price:.1f}% of price) "
        "over the last 14 sessions."
    )


def _volume_trend_read(ratio: float | None) -> str:
    if ratio is None:
        return "Not enough history to compute the volume trend."
    if ratio >= 1.5:
        return f"Volume is {ratio:.1f}x its 20-day average -- notably elevated."
    if ratio <= 0.5:
        return f"Volume is {ratio:.1f}x its 20-day average -- notably light."
    return f"Volume is {ratio:.1f}x its 20-day average."
