"""Self-service SMS phone-number verification, managed from Settings."""

import hmac
import re
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_app_settings, get_current_user_id, get_db
from app.api.schemas import SmsLinkRequest, SmsLinkStatus, SmsVerifyRequest
from app.config import Settings
from app.db.models import SmsLink
from app.providers.signalwire.client import send_sms
from app.services.sms import normalize_phone
from app.services.sms_link import (
    CODE_TTL,
    MAX_REQUESTS_PER_WINDOW,
    MAX_VERIFY_ATTEMPTS,
    REQUEST_WINDOW,
    RESEND_COOLDOWN,
    generate_code,
    hash_code,
)

router = APIRouter(prefix="/settings/sms", tags=["sms-link"])

PHONE_PATTERN = re.compile(r"^\+[1-9]\d{7,14}$")


def _as_aware(value: datetime | None) -> datetime | None:
    """Normalize a datetime to timezone-aware; SQLite round-trips naive datetimes."""
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


@router.post("/request", status_code=status.HTTP_204_NO_CONTENT)
async def request_code(
    body: SmsLinkRequest,
    session: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
    settings: Settings = Depends(get_app_settings),
) -> None:
    phone_number = normalize_phone(body.phone_number)
    if not PHONE_PATTERN.match(phone_number):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Enter a phone number in E.164 format, e.g. +15551234567.",
        )

    now = datetime.now(UTC)
    link = await session.scalar(select(SmsLink).where(SmsLink.user_id == user_id))
    if link is None:
        link = SmsLink(user_id=user_id, phone_number=phone_number)
        session.add(link)

    last_sent_at = _as_aware(link.last_sent_at)

    if last_sent_at is not None and now - last_sent_at < RESEND_COOLDOWN:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Wait a bit before requesting another code.",
        )

    request_window_started_at = _as_aware(link.request_window_started_at)

    if (
        request_window_started_at is None
        or now - request_window_started_at > REQUEST_WINDOW
    ):
        link.request_window_started_at = now
        link.request_count = 0
    if link.request_count >= MAX_REQUESTS_PER_WINDOW:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many code requests. Try again in an hour.",
        )

    code = generate_code()
    link.phone_number = phone_number
    link.code_hash = hash_code(code, settings.app_secret.get_secret_value())
    link.code_expires_at = now + CODE_TTL
    link.attempt_count = 0
    link.last_sent_at = now
    link.request_count += 1
    link.verified_at = None

    try:
        await send_sms(
            settings=settings, to=phone_number, text=f"Your Posted verification code is {code}."
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Couldn't send the verification text. Try again shortly.",
        ) from exc

    await session.commit()


@router.post("/verify", response_model=SmsLinkStatus)
async def verify_code(
    body: SmsVerifyRequest,
    session: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
    settings: Settings = Depends(get_app_settings),
) -> SmsLinkStatus:
    link = await session.scalar(select(SmsLink).where(SmsLink.user_id == user_id))
    if link is None or link.code_hash is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No pending verification. Request a code first.",
        )

    now = datetime.now(UTC)
    code_expires_at = _as_aware(link.code_expires_at)

    if code_expires_at is None or now > code_expires_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="That code expired. Request a new one."
        )

    if link.attempt_count >= MAX_VERIFY_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many incorrect attempts. Request a new code.",
        )

    expected = hash_code(body.code, settings.app_secret.get_secret_value())
    if not hmac.compare_digest(expected, link.code_hash):
        link.attempt_count += 1
        await session.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Incorrect code.")

    previous_owner = await session.scalar(
        select(SmsLink).where(
            SmsLink.phone_number == link.phone_number,
            SmsLink.verified_at.is_not(None),
            SmsLink.user_id != user_id,
        )
    )
    if previous_owner is not None:
        await session.delete(previous_owner)

    link.verified_at = now
    link.code_hash = None
    link.code_expires_at = None
    link.attempt_count = 0
    await session.commit()

    return SmsLinkStatus(
        status="verified", phone_number_masked=_mask(link.phone_number), opted_out=link.opted_out
    )


@router.delete("/link", status_code=status.HTTP_204_NO_CONTENT)
async def unlink(
    session: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
) -> None:
    link = await session.scalar(select(SmsLink).where(SmsLink.user_id == user_id))
    if link is not None:
        await session.delete(link)
        await session.commit()


@router.get("/link", response_model=SmsLinkStatus)
async def get_link_status(
    session: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
) -> SmsLinkStatus:
    link = await session.scalar(select(SmsLink).where(SmsLink.user_id == user_id))
    if link is None:
        return SmsLinkStatus(status="none")
    if link.verified_at is not None:
        return SmsLinkStatus(
            status="verified",
            phone_number_masked=_mask(link.phone_number),
            opted_out=link.opted_out,
        )
    return SmsLinkStatus(
        status="pending",
        phone_number_masked=_mask(link.phone_number),
        opted_out=link.opted_out,
    )


def _mask(phone_number: str) -> str:
    return f"•••• {phone_number[-4:]}"
