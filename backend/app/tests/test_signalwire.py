from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.config import Settings
from app.db.base import Base
from app.db.models import SmsLink, User
from app.db.session import create_engine, create_session_factory
from app.main import create_app
from app.services.signalwire_signature import calculate_legacy_signature
from app.services.sms import find_verified_user, process_inbound_sms, section_for_sms

TOKEN = "test-signalwire-token"  # noqa: S105 - fixture value, not a real secret
URL = "https://example.trycloudflare.com/api/v1/webhooks/signalwire"


def _sign(url: str, params: dict[str, str], token: str = TOKEN) -> str:
    return calculate_legacy_signature(token=token, url=url, form_fields=tuple(params.items()))


def test_sms_section_routing() -> None:
    for message, expected in [
        ("show my spending", "money"),
        ("why did AAPL stock move?", "investing"),
        ("what are the headlines?", "general"),
    ]:
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


# --- Route-level webhook tests -------------------------------------------------


@pytest.fixture
async def signalwire_client() -> AsyncIterator[AsyncClient]:
    settings = Settings(
        app_env="test",
        database_url="sqlite+aiosqlite:///:memory:",
        signalwire_signing_key=TOKEN,
        signalwire_project_id="test-project",
        signalwire_webhook_url=URL,
        signalwire_allow_unsigned_webhooks=False,
    )
    app = create_app(settings)
    async with (
        LifespanManager(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http,
    ):
        yield http


async def _post_signed(client: AsyncClient, params: dict[str, str], *, signature: str | None):
    headers = {}
    if signature is not None:
        headers["X-Twilio-Signature"] = signature
    return await client.post(
        "/api/v1/webhooks/signalwire",
        data=params,
        headers=headers,
    )


async def test_valid_signed_callback_returns_204(signalwire_client: AsyncClient) -> None:
    params = {"From": "+15550101234", "To": "+15550109999", "Body": "hi"}
    response = await _post_signed(signalwire_client, params, signature=_sign(URL, params))
    assert response.status_code == 204


async def test_invalid_signature_returns_401(signalwire_client: AsyncClient) -> None:
    params = {"From": "+15550101234", "To": "+15550109999", "Body": "hi"}
    response = await _post_signed(signalwire_client, params, signature="not-a-real-signature")
    assert response.status_code == 401


async def test_missing_signature_returns_401(signalwire_client: AsyncClient) -> None:
    params = {"From": "+15550101234", "To": "+15550109999", "Body": "hi"}
    response = await _post_signed(signalwire_client, params, signature=None)
    assert response.status_code == 401


async def test_tampered_body_returns_401(signalwire_client: AsyncClient) -> None:
    params = {"From": "+15550101234", "To": "+15550109999", "Body": "hi"}
    signature = _sign(URL, params)
    tampered = {**params, "Body": "bye"}
    response = await _post_signed(signalwire_client, tampered, signature=signature)
    assert response.status_code == 401


async def test_status_callback_without_body_returns_204(signalwire_client: AsyncClient) -> None:
    params = {"MessageSid": "SMxxxx", "MessageStatus": "delivered"}
    response = await _post_signed(signalwire_client, params, signature=_sign(URL, params))
    assert response.status_code == 204


async def test_malformed_utf8_body_returns_400(signalwire_client: AsyncClient) -> None:
    response = await signalwire_client.post(
        "/api/v1/webhooks/signalwire",
        content=b"Body=\xff\xfe",
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "X-Twilio-Signature": "irrelevant",
        },
    )
    assert response.status_code == 400
