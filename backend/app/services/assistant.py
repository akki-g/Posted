"""Posted's financial assistant: a real Claude tool-use agent over the user's live data.

Resilience is the point of this module, not an afterthought: a hard iteration cap so a
confused tool loop can't run forever, typed API-error handling so a network blip or rate
limit surfaces as a plain sentence instead of a stack trace, and every tool call wrapped so
one bad lookup can't crash the whole turn.
"""

import json
from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID

import structlog
from anthropic import (
    APIConnectionError,
    APIStatusError,
    AsyncAnthropic,
    RateLimitError,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db.models import AssistantMessage
from app.domain.errors import ProviderNotConfiguredError
from app.providers.openbb.news import OpenBBNewsAdapter
from app.services.dashboard import get_dashboard, get_feed, get_holdings
from app.services.money import get_money_overview, get_money_transactions, get_recurring_streams

logger = structlog.get_logger()

MODEL = "claude-opus-4-8"
MAX_TOOL_ITERATIONS = 6

SECTION_FRAMING = {
    "money": (
        "The user just came from the Money & Budgeting section of the app. Default to "
        "answering questions about spending, cash flow, subscriptions, and budgeting unless "
        "they clearly ask about investments instead."
    ),
    "investing": (
        "The user just came from the Investing section of the app. Default to answering "
        "questions about their portfolio, holdings, and market news unless they clearly ask "
        "about budgeting or spending instead."
    ),
    "general": "The user has not signaled which part of the app they care about right now.",
}

SYSTEM_PROMPT = (
    "You are Posted's financial assistant, embedded in a personal finance and portfolio app. "
    "You have tools to look up the user's real account data and real market news - use them "
    "instead of guessing or relying on prior turns. Ground every answer in numbers you actually "
    "retrieved this turn.\n\n"
    "Hard rules:\n"
    "- Never recommend buying, selling, or holding a specific security, and never predict price "
    "direction. You can explain risk, concentration, and tradeoffs, but the decision is the "
    "user's.\n"
    "- Never invent numbers. If a tool call fails or returns nothing useful, say so plainly.\n"
    "- Be concise. Default to a few sentences; use short lists only when enumerating multiple "
    "items (e.g. several transactions).\n"
    "- This is a read-only assistant: you cannot place trades, move money, or change settings.\n"
    "- This chat renders plain text only, not markdown. Never use **bold**, # headers, or "
    "bullet dashes; write plain sentences and paragraphs. For a list of items, put each on its "
    "own line with a number like '1.' rather than a dash or asterisk."
)

TOOLS: list[dict[str, Any]] = [
    {
        "name": "get_money_overview",
        "description": (
            "Get the user's current cash position, weekly spending/income, recurring charges "
            "total, and spending broken down by category."
        ),
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "get_recent_transactions",
        "description": "Get the user's bank/card transactions, optionally filtered by search text.",
        "input_schema": {
            "type": "object",
            "properties": {
                "search": {
                    "type": "string",
                    "description": "Optional merchant/description text to filter by.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max transactions to return (default 20, max 100).",
                },
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "get_recurring_subscriptions",
        "description": "Get detected recurring charges/subscriptions with amounts and cadence.",
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "get_portfolio_overview",
        "description": (
            "Get the user's total portfolio value, day change, total gain, and brokerage "
            "account list."
        ),
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "get_portfolio_holdings",
        "description": "Get the user's individual security holdings with weight and gain/loss.",
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "get_impact_feed",
        "description": (
            "Get recent portfolio-relevant news events, ranked by impact score, already scored "
            "against the user's holdings."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Max events to return (default 10)."},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "search_company_news",
        "description": (
            "Search recent news for a specific company/ticker, including ones the user does "
            "not currently hold. Use this for 'what's going on with X' questions about a stock "
            "not in the impact feed."
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
]


def _decimal_default(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    return str(value)


async def _execute_tool(
    name: str,
    tool_input: dict[str, Any],
    *,
    session: AsyncSession,
    user_id: UUID,
    settings: Settings,
) -> dict[str, Any]:
    if name == "get_money_overview":
        overview = await get_money_overview(session, user_id=user_id, demo_mode=settings.demo_mode)
        return {
            "cash_balance": overview.cash_balance,
            "card_balance": overview.card_balance,
            "net_cash_position": overview.net_cash_position,
            "weekly_spending": overview.weekly_spending,
            "weekly_income": overview.weekly_income,
            "monthly_recurring": overview.monthly_recurring,
            "spending_by_category": [
                {"category": item.label, "amount": item.amount, "percent": item.percent}
                for item in overview.spending_by_category
            ],
        }

    if name == "get_recent_transactions":
        limit = min(int(tool_input.get("limit") or 20), 100)
        search = tool_input.get("search") or None
        result = await get_money_transactions(session, user_id=user_id, search=search, limit=limit)
        return {
            "total_matching": result.total,
            "transactions": [
                {
                    "merchant": item.merchant_name,
                    "amount": item.amount,
                    "direction": item.direction,
                    "category": item.category,
                    "status": item.status,
                    "occurred_at": item.occurred_at.isoformat(),
                }
                for item in result.items
            ],
        }

    if name == "get_recurring_subscriptions":
        streams = await get_recurring_streams(session, user_id=user_id)
        return {
            "subscriptions": [
                {
                    "merchant": stream.merchant_name,
                    "average_amount": stream.average_amount,
                    "frequency": stream.frequency,
                    "next_expected_date": stream.next_expected_date,
                    "confidence": stream.confidence,
                    "status": stream.status,
                }
                for stream in streams
            ]
        }

    if name == "get_portfolio_overview":
        dashboard = await get_dashboard(session, user_id=user_id, demo_mode=settings.demo_mode)
        return {
            "total_value": dashboard.portfolio.total_value,
            "day_change_amount": dashboard.portfolio.day_change.amount,
            "day_change_percent": dashboard.portfolio.day_change.percent,
            "total_gain_amount": dashboard.portfolio.total_gain.amount,
            "total_gain_percent": dashboard.portfolio.total_gain.percent,
            "accounts": [
                {"name": account.name, "type": account.account_type, "balance": account.balance}
                for account in dashboard.accounts
            ],
        }

    if name == "get_portfolio_holdings":
        holdings = await get_holdings(session, user_id=user_id)
        return {
            "holdings": [
                {
                    "symbol": holding.symbol,
                    "name": holding.name,
                    "market_value": holding.market_value,
                    "portfolio_weight": holding.portfolio_weight,
                    "day_change_percent": holding.day_change_percent,
                    "total_gain_percent": holding.total_gain_percent,
                }
                for holding in holdings
            ]
        }

    if name == "get_impact_feed":
        limit = min(int(tool_input.get("limit") or 10), 50)
        feed = await get_feed(
            session, user_id=user_id, limit=limit, include_demo=settings.demo_mode
        )
        return {
            "events": [
                {
                    "headline": event.headline,
                    "level": event.level,
                    "score": event.score,
                    "symbols": [security.symbol for security in event.securities],
                    "occurred_at": event.occurred_at.isoformat(),
                }
                for event in feed.items
            ]
        }

    if name == "search_company_news":
        symbol = str(tool_input.get("symbol", "")).strip().upper()
        if not symbol:
            return {"error": "no symbol provided"}
        adapter = OpenBBNewsAdapter(provider=settings.openbb_news_provider)
        try:
            envelopes = await adapter.fetch_company_news(symbols=[symbol], limit=10)
        except ProviderNotConfiguredError as exc:
            return {"error": str(exc)}
        except Exception as exc:  # noqa: BLE001 - surface as a tool error, not a crash
            return {"error": f"news lookup failed: {exc}"}
        return {
            "articles": [
                {
                    "headline": envelope.headline,
                    "summary": envelope.summary,
                    "source": envelope.source_name,
                    "published_at": envelope.published_at.isoformat(),
                }
                for envelope in envelopes
            ]
        }

    return {"error": f"unknown tool {name}"}


@dataclass(frozen=True, slots=True)
class AssistantTurnResult:
    reply: str
    tool_calls_made: int


async def run_assistant_turn(
    session: AsyncSession,
    *,
    user_id: UUID,
    settings: Settings,
    history: list[dict[str, Any]],
    user_message: str,
    section: str,
) -> AssistantTurnResult:
    if not settings.ai_insights_configured:
        return AssistantTurnResult(
            reply=(
                "The AI assistant needs an Anthropic API key configured on the backend "
                "(ANTHROPIC_API_KEY) before it can respond."
            ),
            tool_calls_made=0,
        )

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    system = f"{SYSTEM_PROMPT}\n\n{SECTION_FRAMING.get(section, SECTION_FRAMING['general'])}"
    messages: list[dict[str, Any]] = [*history, {"role": "user", "content": user_message}]

    tool_calls_made = 0
    for _ in range(MAX_TOOL_ITERATIONS):
        try:
            response = await client.messages.create(
                model=MODEL,
                max_tokens=1500,
                system=system,
                tools=TOOLS,
                thinking={"type": "adaptive"},
                messages=messages,
            )
        except RateLimitError:
            return AssistantTurnResult(
                reply="I'm getting rate-limited right now - please try again in a moment.",
                tool_calls_made=tool_calls_made,
            )
        except APIConnectionError:
            return AssistantTurnResult(
                reply="I couldn't reach the AI service - check your connection and try again.",
                tool_calls_made=tool_calls_made,
            )
        except APIStatusError as exc:
            logger.warning("assistant_api_error", error=str(exc))
            return AssistantTurnResult(
                reply="Something went wrong talking to the AI service. Please try again.",
                tool_calls_made=tool_calls_made,
            )

        if response.stop_reason == "refusal":
            return AssistantTurnResult(
                reply="I can't help with that request.", tool_calls_made=tool_calls_made
            )

        if response.stop_reason != "tool_use":
            text = "".join(
                block.text for block in response.content if getattr(block, "type", None) == "text"
            ).strip()
            return AssistantTurnResult(
                reply=text or "I don't have a response for that.",
                tool_calls_made=tool_calls_made,
            )

        messages.append({"role": "assistant", "content": response.content})
        tool_use_blocks = [
            block for block in response.content if getattr(block, "type", None) == "tool_use"
        ]
        tool_results = []
        for block in tool_use_blocks:
            tool_calls_made += 1
            try:
                result = await _execute_tool(
                    block.name,
                    block.input,
                    session=session,
                    user_id=user_id,
                    settings=settings,
                )
            except Exception as exc:  # noqa: BLE001 - a broken tool must not crash the turn
                logger.warning("assistant_tool_failed", tool=block.name, error=str(exc))
                result = {"error": f"{block.name} failed: {exc}"}
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result, default=_decimal_default),
                }
            )
        messages.append({"role": "user", "content": tool_results})

    return AssistantTurnResult(
        reply=(
            "I needed more tool calls than I'm allowed to fully answer that - try asking a "
            "narrower question."
        ),
        tool_calls_made=tool_calls_made,
    )


async def get_conversation(session: AsyncSession, *, user_id: UUID) -> list[AssistantMessage]:
    result = await session.scalars(
        select(AssistantMessage)
        .where(AssistantMessage.user_id == user_id)
        .order_by(AssistantMessage.created_at)
    )
    return list(result.all())


async def send_message(
    session: AsyncSession,
    *,
    user_id: UUID,
    settings: Settings,
    message: str,
    section: str,
) -> AssistantMessage:
    history_rows = await get_conversation(session, user_id=user_id)
    history = [{"role": row.role, "content": row.content} for row in history_rows]

    user_row = AssistantMessage(user_id=user_id, role="user", content=message, section=section)
    session.add(user_row)
    await session.flush()

    result = await run_assistant_turn(
        session,
        user_id=user_id,
        settings=settings,
        history=history,
        user_message=message,
        section=section,
    )

    assistant_row = AssistantMessage(
        user_id=user_id, role="assistant", content=result.reply, section=section
    )
    session.add(assistant_row)
    await session.commit()
    await session.refresh(assistant_row)
    return assistant_row


async def clear_conversation(session: AsyncSession, *, user_id: UUID) -> None:
    rows = await get_conversation(session, user_id=user_id)
    for row in rows:
        await session.delete(row)
    await session.commit()
