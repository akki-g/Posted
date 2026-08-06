"""Channel-specific handling for Posted's SMS assistant.

Identity is resolved through SmsLink: a phone number only reaches the
assistant once its owner has verified it from Posted Settings.
"""

import re
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db.models import SmsLink
from app.providers.telnyx.client import send_sms
from app.services.assistant import send_message

logger = structlog.get_logger()

HELP_REPLY = (
    "Posted: Text a question about your portfolio, spending, market news, or investments "
    "and we'll reply with a quick summary. Reply STOP to opt out, START to resume. "
    "Msg&data rates may apply. Support: support@posted.app"
)
# Sent on START — doubles as the opt-in confirmation explaining how texting works.
START_REPLY = (
    "You're set up to text Posted. Ask anything about your portfolio, spending, market news, "
    "or investments in plain English and we'll reply with a short summary—open the Posted app "
    "for full detail. For your privacy we never text balances or account numbers. "
    "Reply HELP for help, STOP to opt out anytime. Msg&data rates may apply."
)
STOP_REPLY = (
    "Posted: You're opted out and won't receive any more texts. "
    "Reply START to resume anytime. Msg&data rates may apply."
)
UNLINKED_REPLY = "Posted: this number is not linked for SMS. Link it from Posted Settings first."
OPTED_OUT_REPLY = "Posted: you're opted out. Reply START to resume texting Posted."


def normalize_phone(number: str) -> str:
    """Normalize enough for E.164 comparison; Telnyx supplies E.164 numbers."""
    return re.sub(r"[^0-9+]", "", number)


def section_for_sms(message: str) -> str:
    """Use deterministic routing for the assistant's existing three contexts."""
    value = message.lower()
    if any(word in value for word in ("budget", "spend", "transaction", "cash", "subscription")):
        return "money"
    if any(
        word in value
        for word in ("portfolio", "stock", "holding", "invest", "ticker", "insider")
    ):
        return "investing"
    return "general"


async def _verified_link_for_phone(session: AsyncSession, phone_number: str) -> SmsLink | None:
    """The verified-link invariant (Task 4's ownership transfer) guarantees at most
    one row can have verified_at set for a given phone number at any time, so this
    is always a safe single-row lookup even though phone_number itself isn't unique
    across pending (unverified) rows."""
    result = await session.scalars(
        select(SmsLink).where(
            SmsLink.phone_number == normalize_phone(phone_number),
            SmsLink.verified_at.is_not(None),
        )
    )
    return result.one_or_none()


async def find_verified_user(session: AsyncSession, phone_number: str) -> UUID | None:
    """Resolve an inbound SMS sender to a Posted user, if their number is verified."""
    link = await _verified_link_for_phone(session, phone_number)
    return link.user_id if link is not None else None


async def _set_opted_out(session: AsyncSession, phone_number: str, *, opted_out: bool) -> None:
    link = await _verified_link_for_phone(session, phone_number)
    if link is not None:
        link.opted_out = opted_out
        await session.commit()


async def process_inbound_sms(
    session: AsyncSession,
    *,
    from_number: str,
    body: str,
    settings: Settings,
) -> None:
    """Process a single authenticated Telnyx inbound message.

    The route that invokes this runs it after acknowledging Telnyx. The
    webhook delivery window is short; AI/tool calls must not hold that response.
    """
    message = body.strip()
    if not message:
        return

    command = message.upper()
    if command == "HELP":
        reply = HELP_REPLY
    elif command == "STOP":
        await _set_opted_out(session, from_number, opted_out=True)
        reply = STOP_REPLY
    elif command == "START":
        await _set_opted_out(session, from_number, opted_out=False)
        reply = START_REPLY
    else:
        link = await _verified_link_for_phone(session, from_number)
        if link is None:
            reply = UNLINKED_REPLY
        elif link.opted_out:
            reply = OPTED_OUT_REPLY
        else:
            result = await send_message(
                session,
                user_id=link.user_id,
                settings=settings,
                message=message[:1200],
                section=section_for_sms(message),
                screen_context=(
                    "The user is asking through Posted SMS. Keep the answer concise and plain text."
                ),
            )
            reply = result.content

    try:
        await send_sms(settings=settings, to=from_number, text=reply)
    except Exception:  # delivery failure must not crash the webhook worker
        logger.exception("telnyx_sms_delivery_failed", recipient_suffix=from_number[-4:])
