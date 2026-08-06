from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class MarketModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class MarketSearchResult(MarketModel):
    symbol: str
    name: str
    exchange: str | None = None
    asset_type: str
    source: str
    in_portfolio: bool = False


class MarketQuote(MarketModel):
    price: float
    change: float
    change_percent: float
    open: float | None = None
    high: float | None = None
    low: float | None = None
    previous_close: float | None = None
    bid: float | None = None
    ask: float | None = None
    volume: int | None = None
    timestamp: datetime
    source: str
    freshness: str


class CompanyProfile(MarketModel):
    description: str | None = None
    sector: str | None = None
    industry: str | None = None
    exchange: str | None = None
    website: str | None = None
    logo_url: str | None = None
    market_cap: float | None = None
    pe_ratio: float | None = None
    dividend_yield: float | None = None
    beta: float | None = None
    fifty_two_week_high: float | None = None
    fifty_two_week_low: float | None = None


class EarningsResult(MarketModel):
    date: date
    fiscal_quarter: str | None = None
    timing: str | None = None
    eps_estimate: float | None = None
    eps_actual: float | None = None
    revenue_estimate: float | None = None
    revenue_actual: float | None = None


class InsiderTransaction(MarketModel):
    id: str
    name: str
    filing_date: date
    transaction_date: date
    transaction_code: str
    shares_owned: float | None = None
    shares_changed: float | None = None
    transaction_price: float | None = None
    currency: str = "USD"
    is_derivative: bool = False


class InsiderSentimentPoint(MarketModel):
    year: int
    month: int
    change: float
    mspr: float


class InsiderActivitySummary(MarketModel):
    latest_mspr: float | None = None
    three_month_average_mspr: float | None = None
    prior_three_month_average_mspr: float | None = None
    mspr_trend: str
    three_month_net_shares: float | None = None
    open_market_purchases: int
    open_market_sales: int
    purchase_shares: float
    sale_shares: float
    purchase_value: float
    sale_value: float
    non_directional_transactions: int
    signal: str
    confidence: str


class InsiderInterpretation(MarketModel):
    headline: str
    summary: str
    factors: list[str]
    caveats: list[str]


class RelatedMarketNews(MarketModel):
    id: str
    headline: str
    summary: str | None = None
    source_name: str
    source_url: str | None = None
    occurred_at: datetime
    event_type: str


class PortfolioPosition(MarketModel):
    quantity: float
    average_price: float | None = None
    market_value: float
    total_gain: float
    total_gain_percent: float
    portfolio_weight: float
    account_count: int


class InsiderAnalysisResponse(MarketModel):
    symbol: str
    name: str
    quote: MarketQuote
    position: PortfolioPosition | None = None
    transactions: list[InsiderTransaction]
    sentiment: list[InsiderSentimentPoint]
    summary: InsiderActivitySummary
    interpretation: InsiderInterpretation
    one_month_price_change_percent: float | None = None
    recent_news: list[RelatedMarketNews]
    ai_insight: str | None = None
    ai_available: bool
    source: str
    updated_at: datetime
    is_demo: bool = False
    disclaimer: str


class PortfolioInsiderWatchItem(MarketModel):
    symbol: str
    name: str
    market_value: float
    portfolio_weight: float
    latest_mspr: float | None = None
    three_month_average_mspr: float | None = None
    three_month_net_shares: float | None = None
    mspr_trend: str
    signal: str
    confidence: str


class PortfolioInsiderWatchResponse(MarketModel):
    items: list[PortfolioInsiderWatchItem]
    source: str
    updated_at: datetime
    is_demo: bool = False


class MarketProviderStatus(MarketModel):
    name: str
    role: str
    status: str
    detail: str


class StockDetailResponse(MarketModel):
    symbol: str
    name: str
    asset_type: str
    exchange: str | None = None
    currency: str = "USD"
    quote: MarketQuote
    company: CompanyProfile
    earnings: list[EarningsResult]
    insider_transactions: list[InsiderTransaction]
    insider_sentiment: list[InsiderSentimentPoint]
    related_news: list[RelatedMarketNews]
    position: PortfolioPosition | None = None
    providers: list[MarketProviderStatus]
    is_demo: bool = False
    disclaimer: str


class PriceBar(MarketModel):
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int


class StockHistoryResponse(MarketModel):
    symbol: str
    period: str
    interval: str
    points: list[PriceBar]
    source: str
    freshness: str
    last_updated: datetime
    coverage_note: str
    is_demo: bool = False


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
