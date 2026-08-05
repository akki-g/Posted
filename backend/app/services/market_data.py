import asyncio
import logging
import re
from collections.abc import Awaitable
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db.models import (
    BrokerageAccount,
    BrokerageConnection,
    EventSecurityLink,
    MarketEvent,
    Position,
    Security,
)
from app.market.indicators import compute_technical_indicators
from app.market.schemas import (
    CompanyProfile,
    MarketProviderStatus,
    MarketQuote,
    MarketSearchResult,
    PortfolioPosition,
    RelatedMarketNews,
    StockDetailResponse,
    StockHistoryResponse,
    TechnicalIndicators,
)
from app.providers.market.alpaca import AlpacaMarketClient
from app.providers.market.demo import (
    demo_detail,
    demo_history,
    demo_insider_sentiment,
    demo_insider_transactions,
    search_demo,
)
from app.providers.market.finnhub import FinnhubMarketClient
from app.providers.market.yahoo import YahooMarketClient
from app.services.dashboard import get_holdings

logger = logging.getLogger(__name__)
SYMBOL_PATTERN = re.compile(r"^[A-Z][A-Z0-9.-]{0,14}$")
VALID_PERIODS = {"1D", "5D", "1M", "6M", "1Y", "5Y"}


class StockNotFoundError(ValueError):
    pass


async def search_market(
    session: AsyncSession,
    *,
    user_id: UUID,
    query: str,
    settings: Settings,
) -> list[MarketSearchResult]:
    query = query.strip()
    if not query:
        return []

    local = await _local_search(session, user_id=user_id, query=query)
    if settings.demo_mode:
        external = search_demo(query)
    elif settings.finnhub_configured:
        external = await _safe(
            FinnhubMarketClient(api_key=settings.finnhub_api_key or "").search(query),
            provider="Finnhub search",
            fallback=[],
        )
    elif settings.market_data_yahoo_fallback:
        external = await _safe(
            YahooMarketClient().search(query),
            provider="Yahoo search",
            fallback=[],
        )
    else:
        external = []

    portfolio_symbols = {item.symbol for item in local}
    merged: dict[str, MarketSearchResult] = {item.symbol: item for item in local}
    for item in external:
        item.in_portfolio = item.symbol in portfolio_symbols
        merged.setdefault(item.symbol, item)
    return list(merged.values())[:8]


async def get_stock_detail(
    session: AsyncSession,
    *,
    user_id: UUID,
    symbol: str,
    settings: Settings,
) -> StockDetailResponse:
    symbol = normalize_symbol(symbol)
    security = await session.scalar(select(Security).where(Security.symbol == symbol))
    position = await _position_for_symbol(session, user_id=user_id, symbol=symbol)
    related_news = await _related_news(session, symbol=symbol)

    if settings.demo_mode:
        name, asset_type, quote, company, earnings = demo_detail(symbol)
        return StockDetailResponse(
            symbol=symbol,
            name=security.name if security else name,
            asset_type=security.asset_type if security else asset_type,
            exchange=company.exchange,
            quote=quote,
            company=company,
            earnings=earnings,
            insider_transactions=demo_insider_transactions(symbol),
            insider_sentiment=demo_insider_sentiment(symbol),
            related_news=related_news,
            position=position,
            providers=[
                MarketProviderStatus(
                    name="Posted demo",
                    role="Price, chart, profile, and earnings",
                    status="demo",
                    detail="Deterministic data; add provider keys to enable live requests.",
                ),
                MarketProviderStatus(
                    name="Posted event store",
                    role="Related portfolio news",
                    status="active",
                    detail="Uses the existing normalized news and filing pipeline.",
                ),
            ],
            is_demo=True,
            disclaimer=(
                "Demonstration market data only. Quotes are not executable and this is not "
                "investment advice."
            ),
        )

    alpaca = (
        AlpacaMarketClient(
            api_key=settings.alpaca_api_key or "",
            api_secret=settings.alpaca_api_secret or "",
        )
        if settings.alpaca_configured
        else None
    )
    finnhub = (
        FinnhubMarketClient(api_key=settings.finnhub_api_key or "")
        if settings.finnhub_configured
        else None
    )
    yahoo = YahooMarketClient() if settings.market_data_yahoo_fallback else None

    alpaca_quote_task = _optional(alpaca.quote(symbol) if alpaca else None, "Alpaca quote")
    finnhub_quote_task = _optional(finnhub.quote(symbol) if finnhub else None, "Finnhub quote")
    finnhub_company_task = _optional(
        finnhub.company(symbol) if finnhub else None, "Finnhub company"
    )
    finnhub_earnings_task = _optional(
        finnhub.earnings(symbol) if finnhub else None, "Finnhub earnings"
    )
    finnhub_insiders_task = _optional(
        finnhub.insider_transactions(symbol) if finnhub else None,
        "Finnhub insider transactions",
    )
    finnhub_insider_sentiment_task = _optional(
        finnhub.insider_sentiment(symbol) if finnhub else None,
        "Finnhub insider sentiment",
    )
    yahoo_detail_task = _optional(
        yahoo.detail(symbol) if yahoo else None, "Yahoo detail"
    )
    (
        alpaca_quote,
        finnhub_quote,
        finnhub_company,
        finnhub_earnings,
        finnhub_insiders,
        finnhub_insider_sentiment,
        yahoo_detail,
    ) = await asyncio.gather(
        alpaca_quote_task,
        finnhub_quote_task,
        finnhub_company_task,
        finnhub_earnings_task,
        finnhub_insiders_task,
        finnhub_insider_sentiment_task,
        yahoo_detail_task,
    )

    yahoo_name, yahoo_quote, yahoo_company = yahoo_detail or (
        None,
        None,
        CompanyProfile(),
    )
    finnhub_name, finnhub_profile = finnhub_company or (None, CompanyProfile())
    quote = alpaca_quote or finnhub_quote or yahoo_quote
    if quote is None and position is not None:
        last_price = (
            position.market_value / position.quantity if position.quantity else 0
        )
        quote = MarketQuote(
            price=last_price,
            change=0,
            change_percent=0,
            previous_close=last_price,
            timestamp=datetime.now(UTC),
            source="Portfolio snapshot",
            freshness="snapshot",
        )
    if quote is None:
        raise StockNotFoundError(f"No market data is available for {symbol}")

    company = _merge_profiles(finnhub_profile, yahoo_company)
    if company.sector is None and security is not None:
        company.sector = security.sector
    name = (
        finnhub_name
        or yahoo_name
        or (security.name if security else None)
        or symbol
    )
    asset_type = security.asset_type if security else "equity"
    earnings = finnhub_earnings or []
    providers = _provider_statuses(
        settings=settings,
        quote=quote,
        finnhub_company=bool(finnhub_company),
        finnhub_earnings=bool(earnings),
        finnhub_insiders=bool(finnhub_insiders or finnhub_insider_sentiment),
        yahoo_detail=bool(yahoo_detail),
        related_news=len(related_news),
    )
    return StockDetailResponse(
        symbol=symbol,
        name=name,
        asset_type=asset_type,
        exchange=company.exchange,
        quote=quote,
        company=company,
        earnings=earnings,
        insider_transactions=finnhub_insiders or [],
        insider_sentiment=finnhub_insider_sentiment or [],
        related_news=related_news,
        position=position,
        providers=providers,
        disclaimer=(
            "Market data may be delayed, incomplete, or limited to a single exchange. "
            "Quotes are informational and not executable."
        ),
    )


async def get_stock_history(
    *,
    symbol: str,
    period: str,
    settings: Settings,
) -> StockHistoryResponse:
    symbol = normalize_symbol(symbol)
    period = period.upper()
    if period not in VALID_PERIODS:
        raise ValueError(f"Unsupported period: {period}")
    interval = "1Min" if period == "1D" else "1Day"
    now = datetime.now(UTC)

    if settings.demo_mode:
        points = demo_history(symbol, period)
        return StockHistoryResponse(
            symbol=symbol,
            period=period,
            interval=interval,
            points=points,
            source="Posted demo",
            freshness="demo",
            last_updated=points[-1].timestamp if points else now,
            coverage_note=(
                "One-minute sample bars for the latest session."
                if period == "1D"
                else "Daily sample bars; no intraday interpolation is used."
            ),
            is_demo=True,
        )

    if settings.alpaca_configured:
        alpaca = AlpacaMarketClient(
            api_key=settings.alpaca_api_key or "",
            api_secret=settings.alpaca_api_secret or "",
        )
        points = await _safe(
            alpaca.history(symbol, period),
            provider="Alpaca history",
            fallback=[],
        )
        if points:
            return StockHistoryResponse(
                symbol=symbol,
                period=period,
                interval=interval,
                points=points,
                source="Alpaca IEX",
                freshness="real_time_iex",
                last_updated=points[-1].timestamp,
                coverage_note=(
                    "Latest trading session in one-minute IEX bars."
                    if period == "1D"
                    else (
                        "Daily IEX bars. Free coverage represents one exchange, "
                        "not full SIP volume."
                    )
                ),
            )

    if settings.market_data_yahoo_fallback:
        points = await _safe(
            YahooMarketClient().history(symbol, period),
            provider="Yahoo history",
            fallback=[],
        )
        if points:
            return StockHistoryResponse(
                symbol=symbol,
                period=period,
                interval=interval,
                points=points,
                source="Yahoo Finance",
                freshness="delayed_or_cached",
                last_updated=points[-1].timestamp,
                coverage_note=(
                    "One-minute bars for the latest available trading session."
                    if period == "1D"
                    else "Daily adjusted bars from the personal-use fallback."
                ),
            )

    return StockHistoryResponse(
        symbol=symbol,
        period=period,
        interval=interval,
        points=[],
        source="Unavailable",
        freshness="unavailable",
        last_updated=now,
        coverage_note=(
            "Configure Alpaca credentials or enable the Yahoo fallback for price history."
        ),
    )


async def get_stock_indicators(*, symbol: str, settings: Settings) -> TechnicalIndicators:
    symbol = normalize_symbol(symbol)
    history = await get_stock_history(symbol=symbol, period="1Y", settings=settings)
    return compute_technical_indicators(symbol=symbol, bars=history.points)


def normalize_symbol(value: str) -> str:
    symbol = value.strip().upper()
    if not SYMBOL_PATTERN.fullmatch(symbol):
        raise ValueError("Enter a valid ticker symbol")
    return symbol


async def _local_search(
    session: AsyncSession, *, user_id: UUID, query: str
) -> list[MarketSearchResult]:
    like = f"%{query}%"
    result = await session.scalars(
        select(Security)
        .join(Position, Position.security_id == Security.id)
        .join(BrokerageAccount, Position.account_id == BrokerageAccount.id)
        .join(BrokerageConnection, BrokerageAccount.connection_id == BrokerageConnection.id)
        .where(
            BrokerageConnection.user_id == user_id,
            Security.asset_type != "cash",
            or_(Security.symbol.ilike(like), Security.name.ilike(like)),
        )
        .distinct()
        .order_by(Security.symbol)
        .limit(8)
    )
    return [
        MarketSearchResult(
            symbol=item.symbol,
            name=item.name,
            asset_type=item.asset_type,
            source="Portfolio",
            in_portfolio=True,
        )
        for item in result.all()
    ]


async def _position_for_symbol(
    session: AsyncSession, *, user_id: UUID, symbol: str
) -> PortfolioPosition | None:
    holdings = await get_holdings(session, user_id=user_id)
    holding = next((item for item in holdings if item.symbol == symbol), None)
    if holding is None:
        return None
    return PortfolioPosition(
        quantity=float(holding.quantity),
        average_price=float(holding.average_price) if holding.average_price is not None else None,
        market_value=float(holding.market_value),
        total_gain=float(holding.total_gain),
        total_gain_percent=float(holding.total_gain_percent),
        portfolio_weight=float(holding.portfolio_weight),
        account_count=holding.account_count,
    )


async def _related_news(
    session: AsyncSession, *, symbol: str
) -> list[RelatedMarketNews]:
    result = await session.scalars(
        select(MarketEvent)
        .join(EventSecurityLink, EventSecurityLink.event_id == MarketEvent.id)
        .join(Security, Security.id == EventSecurityLink.security_id)
        .where(Security.symbol == symbol)
        .order_by(MarketEvent.occurred_at.desc())
        .limit(6)
    )
    return [
        RelatedMarketNews(
            id=str(item.id),
            headline=item.headline,
            summary=item.summary,
            source_name=item.source_name,
            source_url=item.source_url,
            occurred_at=item.occurred_at,
            event_type=item.event_type,
        )
        for item in result.unique().all()
    ]


def _merge_profiles(primary: CompanyProfile, fallback: CompanyProfile) -> CompanyProfile:
    return CompanyProfile(
        **{
            field: getattr(primary, field) or getattr(fallback, field)
            for field in CompanyProfile.model_fields
        }
    )


def _provider_statuses(
    *,
    settings: Settings,
    quote: MarketQuote,
    finnhub_company: bool,
    finnhub_earnings: bool,
    finnhub_insiders: bool,
    yahoo_detail: bool,
    related_news: int,
) -> list[MarketProviderStatus]:
    alpaca_active = quote.source == "Alpaca IEX"
    finnhub_active = (
        quote.source == "Finnhub"
        or finnhub_company
        or finnhub_earnings
        or finnhub_insiders
    )
    return [
        MarketProviderStatus(
            name="Alpaca",
            role="One-minute/daily bars, IEX quote, and company news",
            status=(
                "active"
                if alpaca_active
                else ("configured" if settings.alpaca_configured else "off")
            ),
            detail=(
                "Real-time IEX is partial-market coverage."
                if settings.alpaca_configured
                else "Add ALPACA_API_KEY and ALPACA_API_SECRET."
            ),
        ),
        MarketProviderStatus(
            name="Finnhub",
            role=(
                "Symbol lookup, profile, quote, earnings, insider activity, "
                "and company news"
            ),
            status=(
                "active"
                if finnhub_active
                else ("configured" if settings.finnhub_configured else "off")
            ),
            detail=(
                "Free enrichment/news are enabled; premium historical candles are not used."
                if settings.finnhub_configured
                else "Add FINNHUB_API_KEY for enrichment."
            ),
        ),
        MarketProviderStatus(
            name="Yahoo Finance",
            role="Personal-use fallback and missing profile fields",
            status=(
                "active"
                if yahoo_detail
                else ("available" if settings.market_data_yahoo_fallback else "off")
            ),
            detail="Fallback only; not treated as a commercial market-data entitlement.",
        ),
        MarketProviderStatus(
            name="Posted event store",
            role="Related portfolio news and filings",
            status="active",
            detail=(
                f"{related_news} normalized event"
                f"{'s' if related_news != 1 else ''} linked to this ticker."
            ),
        ),
    ]


async def _optional[T](awaitable: Awaitable[T] | None, provider: str) -> T | None:
    if awaitable is None:
        return None
    return await _safe(awaitable, provider=provider, fallback=None)


async def _safe[T](awaitable: Awaitable[T], *, provider: str, fallback: T) -> T:
    try:
        return await awaitable
    except Exception as exc:
        logger.warning("%s unavailable: %s", provider, exc)
        return fallback
