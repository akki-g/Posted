import asyncio
import logging
from datetime import UTC, datetime
from statistics import fmean
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import HoldingSummary
from app.config import Settings
from app.market.schemas import (
    InsiderActivitySummary,
    InsiderAnalysisResponse,
    InsiderInterpretation,
    InsiderSentimentPoint,
    InsiderTransaction,
    PortfolioInsiderWatchItem,
    PortfolioInsiderWatchResponse,
    PriceBar,
)
from app.providers.market.demo import demo_insider_sentiment
from app.providers.market.finnhub import FinnhubMarketClient
from app.services.ai_insights import generate_insider_insight
from app.services.dashboard import get_holdings
from app.services.market_data import get_stock_detail, get_stock_history, normalize_symbol

logger = logging.getLogger(__name__)


async def get_insider_analysis(
    session: AsyncSession,
    *,
    user_id: UUID,
    symbol: str,
    settings: Settings,
    generate_ai: bool = True,
) -> InsiderAnalysisResponse:
    symbol = normalize_symbol(symbol)
    detail, history = await asyncio.gather(
        get_stock_detail(
            session,
            user_id=user_id,
            symbol=symbol,
            settings=settings,
        ),
        get_stock_history(symbol=symbol, period="1M", settings=settings),
    )
    summary = summarize_insider_activity(
        transactions=detail.insider_transactions,
        sentiment=detail.insider_sentiment,
    )
    interpretation = interpret_insider_activity(
        symbol=symbol,
        summary=summary,
        has_position=detail.position is not None,
    )
    one_month_change = _price_change(history.points)
    ai_insight = None
    if generate_ai:
        ai_insight = await generate_insider_insight(
            symbol=symbol,
            company_name=detail.name,
            summary=summary.model_dump(),
            transactions=[
                transaction.model_dump(mode="json")
                for transaction in detail.insider_transactions
            ],
            sentiment=[point.model_dump(mode="json") for point in detail.insider_sentiment],
            day_change_percent=detail.quote.change_percent,
            one_month_price_change_percent=one_month_change,
            position=detail.position.model_dump() if detail.position else None,
            recent_news=[item.headline for item in detail.related_news],
            settings=settings,
        )

    return InsiderAnalysisResponse(
        symbol=symbol,
        name=detail.name,
        quote=detail.quote,
        position=detail.position,
        transactions=detail.insider_transactions,
        sentiment=detail.insider_sentiment,
        summary=summary,
        interpretation=interpretation,
        one_month_price_change_percent=one_month_change,
        recent_news=detail.related_news,
        ai_insight=ai_insight,
        ai_available=settings.ai_insights_configured,
        source="Posted demo" if settings.demo_mode else "Finnhub + Alpaca + Posted",
        updated_at=datetime.now(UTC),
        is_demo=settings.demo_mode,
        disclaimer=(
            "Insider filings can lag the underlying transaction and do not reveal motive. "
            "MSPR and AI interpretation are informational context, not investment advice or "
            "a forecast of future returns."
        ),
    )


async def get_portfolio_insider_watch(
    session: AsyncSession,
    *,
    user_id: UUID,
    settings: Settings,
    limit: int = 25,
) -> PortfolioInsiderWatchResponse:
    holdings = [
        holding
        for holding in await get_holdings(session, user_id=user_id)
        if holding.asset_type.lower() not in {"cash", "etf", "fund", "mutual fund"}
    ][:limit]
    if not holdings:
        return PortfolioInsiderWatchResponse(
            items=[],
            source="Posted demo" if settings.demo_mode else "Finnhub",
            updated_at=datetime.now(UTC),
            is_demo=settings.demo_mode,
        )

    semaphore = asyncio.Semaphore(4)
    finnhub = (
        FinnhubMarketClient(api_key=settings.finnhub_api_key or "")
        if settings.finnhub_configured and not settings.demo_mode
        else None
    )

    async def watch_item(holding: HoldingSummary) -> PortfolioInsiderWatchItem:
        if settings.demo_mode:
            sentiment = demo_insider_sentiment(holding.symbol)
        elif finnhub is not None:
            async with semaphore:
                try:
                    sentiment = await finnhub.insider_sentiment(holding.symbol)
                except Exception as exc:  # noqa: BLE001 - one ticker cannot break the watchlist
                    logger.warning(
                        "Finnhub insider sentiment unavailable for %s: %s",
                        holding.symbol,
                        exc,
                    )
                    sentiment = []
        else:
            sentiment = []
        summary = summarize_insider_activity(transactions=[], sentiment=sentiment)
        return PortfolioInsiderWatchItem(
            symbol=holding.symbol,
            name=holding.name,
            market_value=float(holding.market_value),
            portfolio_weight=float(holding.portfolio_weight),
            latest_mspr=summary.latest_mspr,
            three_month_average_mspr=summary.three_month_average_mspr,
            three_month_net_shares=summary.three_month_net_shares,
            mspr_trend=summary.mspr_trend,
            signal=summary.signal,
            confidence=summary.confidence,
        )

    items = await asyncio.gather(*(watch_item(holding) for holding in holdings))
    return PortfolioInsiderWatchResponse(
        items=list(items),
        source="Posted demo" if settings.demo_mode else "Finnhub",
        updated_at=datetime.now(UTC),
        is_demo=settings.demo_mode,
    )


def summarize_insider_activity(
    *,
    transactions: list[InsiderTransaction],
    sentiment: list[InsiderSentimentPoint],
) -> InsiderActivitySummary:
    ordered_sentiment = sorted(sentiment, key=lambda point: (point.year, point.month))
    latest = ordered_sentiment[-1] if ordered_sentiment else None
    recent = ordered_sentiment[-3:]
    prior = ordered_sentiment[-6:-3]
    recent_average = _average([point.mspr for point in recent])
    prior_average = _average([point.mspr for point in prior])
    trend = _mspr_trend(recent_average, prior_average)

    purchases = [
        item for item in transactions if item.transaction_code.upper() == "P"
    ]
    sales = [item for item in transactions if item.transaction_code.upper() == "S"]
    purchase_shares = sum(abs(item.shares_changed or 0) for item in purchases)
    sale_shares = sum(abs(item.shares_changed or 0) for item in sales)
    purchase_value = sum(
        abs(item.shares_changed or 0) * (item.transaction_price or 0)
        for item in purchases
    )
    sale_value = sum(
        abs(item.shares_changed or 0) * (item.transaction_price or 0) for item in sales
    )
    directional_count = len(purchases) + len(sales)
    non_directional_count = max(0, len(transactions) - directional_count)
    net_shares = sum(point.change for point in recent) if recent else None
    signal = _signal(recent_average)
    confidence = _confidence(
        sentiment_count=len(ordered_sentiment),
        directional_count=directional_count,
        mspr_average=recent_average,
        directional_net=purchase_shares - sale_shares,
    )
    return InsiderActivitySummary(
        latest_mspr=latest.mspr if latest else None,
        three_month_average_mspr=recent_average,
        prior_three_month_average_mspr=prior_average,
        mspr_trend=trend,
        three_month_net_shares=net_shares,
        open_market_purchases=len(purchases),
        open_market_sales=len(sales),
        purchase_shares=purchase_shares,
        sale_shares=sale_shares,
        purchase_value=purchase_value,
        sale_value=sale_value,
        non_directional_transactions=non_directional_count,
        signal=signal,
        confidence=confidence,
    )


def interpret_insider_activity(
    *,
    symbol: str,
    summary: InsiderActivitySummary,
    has_position: bool,
) -> InsiderInterpretation:
    if summary.three_month_average_mspr is None:
        return InsiderInterpretation(
            headline="Insufficient insider-sentiment history",
            summary=(
                f"Finnhub did not return enough monthly MSPR data to characterize {symbol}. "
                "The transaction ledger remains useful, but it should be read filing by filing."
            ),
            factors=[
                (
                    f"{summary.open_market_purchases} open-market purchases and "
                    f"{summary.open_market_sales} open-market sales are present in the "
                    "returned transaction window."
                ),
                (
                    f"{summary.non_directional_transactions} awards, exercises, gifts, or "
                    "other non-directional rows were kept separate."
                ),
            ],
            caveats=_standard_caveats(),
        )

    position_sentence = (
        "Because this is a current holding, the signal is most useful as a monitoring input "
        "alongside position size, earnings, and company-specific news."
        if has_position
        else "Because this is not a current holding, no portfolio exposure is directly affected."
    )
    return InsiderInterpretation(
        headline=summary.signal,
        summary=(
            f"{symbol}'s latest MSPR is {summary.latest_mspr:+.1f}, with a three-month "
            f"average of {summary.three_month_average_mspr:+.1f} and a "
            f"{summary.mspr_trend} trend. {position_sentence}"
        ),
        factors=[
            (
                f"Finnhub reports a three-month net insider share change of "
                f"{_shares(summary.three_month_net_shares)}."
            ),
            (
                f"The returned filings contain {summary.open_market_purchases} discretionary "
                f"purchase rows ({_share_count(summary.purchase_shares)}) and "
                f"{summary.open_market_sales} sale rows ({_share_count(summary.sale_shares)})."
            ),
            (
                f"{summary.non_directional_transactions} compensation, derivative, gift, or "
                "administrative rows are excluded from the directional read."
            ),
        ],
        caveats=_standard_caveats(),
    )


def _standard_caveats() -> list[str]:
    return [
        "Form 4 filing dates can lag transaction dates, so this is not a real-time trading tape.",
        (
            "Finnhub does not identify personal motives or whether a sale followed a "
            "pre-arranged 10b5-1 plan."
        ),
        (
            "Insider activity can add context, but it does not establish why the stock moved "
            "and should not be read as a standalone forecast."
        ),
    ]


def _signal(mspr_average: float | None) -> str:
    if mspr_average is None:
        return "Insufficient data"
    if mspr_average >= 25:
        return "Strong insider accumulation"
    if mspr_average >= 8:
        return "Moderate insider accumulation"
    if mspr_average <= -25:
        return "Strong insider distribution"
    if mspr_average <= -8:
        return "Moderate insider distribution"
    return "Mixed / neutral insider activity"


def _mspr_trend(recent: float | None, prior: float | None) -> str:
    if recent is None or prior is None:
        return "unavailable"
    change = recent - prior
    if change >= 8:
        return "improving"
    if change <= -8:
        return "weakening"
    return "stable"


def _confidence(
    *,
    sentiment_count: int,
    directional_count: int,
    mspr_average: float | None,
    directional_net: float,
) -> str:
    if sentiment_count < 3:
        return "low"
    if directional_count == 0:
        return "medium"
    agrees = (
        mspr_average is not None
        and (mspr_average == 0 or directional_net == 0 or mspr_average * directional_net > 0)
    )
    if sentiment_count >= 6 and directional_count >= 3 and agrees:
        return "high"
    return "medium"


def _average(values: list[float]) -> float | None:
    return round(fmean(values), 2) if values else None


def _price_change(points: list[PriceBar]) -> float | None:
    if len(points) < 2 or points[0].close == 0:
        return None
    return round((points[-1].close / points[0].close - 1) * 100, 2)


def _shares(value: float | None) -> str:
    if value is None:
        return "unavailable"
    return f"{value:+,.0f} shares"


def _share_count(value: float) -> str:
    return f"{value:,.0f} shares"
