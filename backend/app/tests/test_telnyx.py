import base64
import json
import time
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from asgi_lifespan import LifespanManager
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.config import Settings
from app.db.base import Base
from app.db.models import SmsLink, User
from app.db.session import create_engine, create_session_factory
from app.main import create_app
from app.services.sms import find_verified_user, process_inbound_sms, section_for_sms

PRIVATE_KEY = Ed25519PrivateKey.generate()
PUBLIC_KEY = base64.b64encode(PRIVATE_KEY.public_key().public_bytes_raw()).decode()


def _sign(body: bytes, timestamp: str) -> str:
    message = f"{timestamp}|".encode() + body
    return base64.b64encode(PRIVATE_KEY.sign(message)).decode()


def _inbound_payload(*, from_number: str, text: str, event_type: str = "message.received") -> bytes:
    return json.dumps(
        {
            "data": {
                "event_type": event_type,
                "payload": {"from": {"phone_number": from_number}, "text": text},
            }
        }
    ).encode()


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
        return "msg-id"

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


async def test_process_inbound_sms_stop_synonyms_all_opt_out(monkeypatch) -> None:
    """Carriers/TCR expect the full standard keyword set, not just the literal word STOP."""
    from app.services import sms as sms_service

    for keyword in ("UNSUBSCRIBE", "CANCEL", "END", "QUIT"):
        sent = []

        async def fake_send_sms(*, settings, to, text, _sent=sent) -> str:
            _sent.append(text)
            return "msg-id"

        monkeypatch.setattr(sms_service, "send_sms", fake_send_sms)

        engine, session_factory = await _session_factory()
        user_id = uuid4()
        async with session_factory() as session:
            email = f"{keyword.lower()}-test@example.com"
            session.add(User(id=user_id, email=email, display_name="Test User"))
            session.add(
                SmsLink(user_id=user_id, phone_number="+15550101234", verified_at=datetime.now(UTC))
            )
            await session.commit()

        async with session_factory() as session:
            await process_inbound_sms(
                session, from_number="+15550101234", body=keyword, settings=Settings()
            )
        assert "opted out" in sent[-1]

        async with session_factory() as session:
            row = (await session.scalars(select(SmsLink).where(SmsLink.user_id == user_id))).one()
            assert row.opted_out is True

        await engine.dispose()


async def test_process_inbound_sms_stop_persists_and_blocks_future_questions(monkeypatch) -> None:
    from app.services import sms as sms_service

    sent = []

    async def fake_send_sms(*, settings, to, text) -> str:
        sent.append(text)
        return "msg-id"

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
async def telnyx_client() -> AsyncIterator[AsyncClient]:
    settings = Settings(
        app_env="test",
        database_url="sqlite+aiosqlite:///:memory:",
        telnyx_public_key=PUBLIC_KEY,
        telnyx_allow_unsigned_webhooks=False,
    )
    app = create_app(settings)
    async with (
        LifespanManager(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http,
    ):
        yield http


async def _post_signed(
    client: AsyncClient, body: bytes, *, signature: str | None, timestamp: str | None = None
):
    timestamp = timestamp or str(int(time.time()))
    headers = {"Content-Type": "application/json", "telnyx-timestamp": timestamp}
    if signature is not None:
        headers["telnyx-signature-ed25519"] = signature
    return await client.post("/api/v1/webhooks/telnyx", content=body, headers=headers)


async def test_valid_signed_callback_returns_204(telnyx_client: AsyncClient) -> None:
    body = _inbound_payload(from_number="+15550101234", text="hi")
    timestamp = str(int(time.time()))
    response = await _post_signed(
        telnyx_client, body, signature=_sign(body, timestamp), timestamp=timestamp
    )
    assert response.status_code == 204


async def test_invalid_signature_returns_401(telnyx_client: AsyncClient) -> None:
    body = _inbound_payload(from_number="+15550101234", text="hi")
    response = await _post_signed(telnyx_client, body, signature="not-a-real-signature")
    assert response.status_code == 401


async def test_missing_signature_returns_401(telnyx_client: AsyncClient) -> None:
    body = _inbound_payload(from_number="+15550101234", text="hi")
    response = await _post_signed(telnyx_client, body, signature=None)
    assert response.status_code == 401


async def test_tampered_body_returns_401(telnyx_client: AsyncClient) -> None:
    body = _inbound_payload(from_number="+15550101234", text="hi")
    timestamp = str(int(time.time()))
    signature = _sign(body, timestamp)
    tampered = _inbound_payload(from_number="+15550101234", text="bye")
    response = await _post_signed(telnyx_client, tampered, signature=signature, timestamp=timestamp)
    assert response.status_code == 401


async def test_stale_timestamp_returns_401(telnyx_client: AsyncClient) -> None:
    body = _inbound_payload(from_number="+15550101234", text="hi")
    old_timestamp = str(int(time.time()) - 3600)
    response = await _post_signed(
        telnyx_client, body, signature=_sign(body, old_timestamp), timestamp=old_timestamp
    )
    assert response.status_code == 401


async def test_non_message_received_event_returns_204(telnyx_client: AsyncClient) -> None:
    body = _inbound_payload(from_number="+15550101234", text="hi", event_type="message.sent")
    timestamp = str(int(time.time()))
    response = await _post_signed(
        telnyx_client, body, signature=_sign(body, timestamp), timestamp=timestamp
    )
    assert response.status_code == 204


async def test_malformed_json_body_returns_400(telnyx_client: AsyncClient) -> None:
    response = await telnyx_client.post(
        "/api/v1/webhooks/telnyx",
        content=b"{not valid json",
        headers={
            "Content-Type": "application/json",
            "telnyx-signature-ed25519": "irrelevant",
            "telnyx-timestamp": str(int(time.time())),
        },
    )
    assert response.status_code == 400
