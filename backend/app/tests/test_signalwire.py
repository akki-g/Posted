import base64
import hashlib
import hmac
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.api.routes.signalwire import verify_signalwire_signature
from app.config import Settings
from app.db.base import Base
from app.db.models import SmsLink, User
from app.db.session import create_engine, create_session_factory
from app.services.sms import find_verified_user, process_inbound_sms, section_for_sms

TOKEN = "test-signalwire-token"  # noqa: S105 - fixture value, not a real secret
URL = "https://example.trycloudflare.com/api/v1/webhooks/signalwire"


def _sign(url: str, params: dict[str, str], token: str = TOKEN) -> str:
    data = url + "".join(key + params[key] for key in sorted(params))
    digest = hmac.new(token.encode(), data.encode("utf-8"), hashlib.sha1).digest()
    return base64.b64encode(digest).decode()


def _settings() -> Settings:
    # Force signed-webhook enforcement so these tests exercise real signature
    # verification regardless of the ambient .env, which enables the dev bypass
    # (SIGNALWIRE_ALLOW_UNSIGNED_WEBHOOKS=true) for local manual testing.
    return Settings(signalwire_api_token=TOKEN, signalwire_allow_unsigned_webhooks=False)


def test_signature_verification_accepts_a_valid_signature() -> None:
    params = {"From": "+15550101234", "To": "+15550109999", "Body": "PORTFOLIO"}

    verify_signalwire_signature(
        url=URL, params=params, signature=_sign(URL, params), settings=_settings()
    )


def test_signature_verification_rejects_a_tampered_param() -> None:
    params = {"From": "+15550101234", "To": "+15550109999", "Body": "PORTFOLIO"}
    signature = _sign(URL, params)
    tampered = {**params, "Body": "SPENDING"}

    with pytest.raises(HTTPException, match="Invalid SignalWire signature"):
        verify_signalwire_signature(
            url=URL, params=tampered, signature=signature, settings=_settings()
        )


def test_signature_verification_rejects_a_missing_header() -> None:
    with pytest.raises(HTTPException, match="Missing SignalWire signature"):
        verify_signalwire_signature(
            url=URL, params={"Body": "hi"}, signature=None, settings=_settings()
        )


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("show my spending", "money"),
        ("why did AAPL stock move?", "investing"),
        ("what are the headlines?", "general"),
    ],
)
def test_sms_section_routing(message: str, expected: str) -> None:
    assert section_for_sms(message) == expected


async def _session_factory():
    settings = Settings(database_url="sqlite+aiosqlite:///:memory:")
    engine = create_engine(settings)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine, create_session_factory(engine)


async def test_find_verified_user_matches_only_a_verified_link() -> None:
    engine, session_factory = await _session_factory()
    user_id = uuid4()
    async with session_factory() as session:
        session.add(User(id=user_id, email="find-user-test@example.com", display_name="Test User"))
        session.add(
            SmsLink(user_id=user_id, phone_number="+15550101234", verified_at=datetime.now(UTC))
        )
        session.add(SmsLink(user_id=uuid4(), phone_number="+15550109999"))
        await session.commit()

    async with session_factory() as session:
        assert await find_verified_user(session, "+15550101234") == user_id
        assert await find_verified_user(session, "+15550109999") is None
        assert await find_verified_user(session, "+15550100000") is None

    await engine.dispose()


async def test_process_inbound_sms_replies_unlinked_for_an_unverified_number(monkeypatch) -> None:
    from app.services import sms as sms_service

    sent = {}

    async def fake_send_sms(*, settings, to, text) -> str:
        sent["text"] = text
        return "SMxxxx"

    monkeypatch.setattr(sms_service, "send_sms", fake_send_sms)

    engine, session_factory = await _session_factory()
    async with session_factory() as session:
        await process_inbound_sms(
            session,
            from_number="+15550101234",
            body="What's my portfolio doing?",
            settings=Settings(),
        )

    assert "not linked" in sent["text"]
    await engine.dispose()


async def test_process_inbound_sms_stop_persists_and_blocks_future_questions(monkeypatch) -> None:
    from app.services import sms as sms_service

    sent = []

    async def fake_send_sms(*, settings, to, text) -> str:
        sent.append(text)
        return "SMxxxx"

    monkeypatch.setattr(sms_service, "send_sms", fake_send_sms)

    engine, session_factory = await _session_factory()
    user_id = uuid4()
    async with session_factory() as session:
        session.add(User(id=user_id, email="stop-test@example.com", display_name="Test User"))
        session.add(
            SmsLink(user_id=user_id, phone_number="+15550101234", verified_at=datetime.now(UTC))
        )
        await session.commit()

    async with session_factory() as session:
        await process_inbound_sms(
            session, from_number="+15550101234", body="STOP", settings=Settings()
        )
    assert "opted out" in sent[-1]

    async with session_factory() as session:
        await process_inbound_sms(
            session,
            from_number="+15550101234",
            body="What's my portfolio doing?",
            settings=Settings(),
        )
    assert "Reply START to resume" in sent[-1]

    async with session_factory() as session:
        await process_inbound_sms(
            session, from_number="+15550101234", body="START", settings=Settings()
        )

    async with session_factory() as session:
        row = (await session.scalars(select(SmsLink).where(SmsLink.user_id == user_id))).one()
        assert row.opted_out is False

    await engine.dispose()
