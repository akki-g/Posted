import re
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from httpx import AsyncClient
from sqlalchemy import select

from app.config import Settings
from app.db.base import Base
from app.db.models import SmsLink, User
from app.db.session import create_engine, create_session_factory
from app.services.sms_link import generate_code, hash_code


def _code_in(text: str) -> str | None:
    """Pull a 6-digit code out of an SMS body, if present.

    verify_code's success path now also sends a codeless opt-in-confirmation
    text (see START_REPLY) through the same monkeypatched send_sms, so
    callers must not assume every send carries a code.
    """
    match = re.search(r"\b(\d{6})\b", text)
    return match.group(1) if match else None


async def test_sms_link_round_trips_through_the_database() -> None:
    settings = Settings(database_url="sqlite+aiosqlite:///:memory:")
    engine = create_engine(settings)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = create_session_factory(engine)

    user_id = uuid4()
    async with session_factory() as session:
        session.add(User(id=user_id, email="sms-link-test@example.com", display_name="Test User"))
        session.add(SmsLink(user_id=user_id, phone_number="+15550101234"))
        await session.commit()

    async with session_factory() as session:
        row = (await session.scalars(select(SmsLink).where(SmsLink.user_id == user_id))).one()
        assert row.phone_number == "+15550101234"
        assert row.verified_at is None
        assert row.opted_out is False
        assert row.attempt_count == 0
        assert row.request_count == 0

    await engine.dispose()


def test_generate_code_is_six_zero_padded_digits() -> None:
    for _ in range(50):
        code = generate_code()
        assert len(code) == 6
        assert code.isdigit()


def test_hash_code_is_deterministic_and_keyed_by_secret() -> None:
    assert hash_code("123456", "secret-a") == hash_code("123456", "secret-a")
    assert hash_code("123456", "secret-a") != hash_code("123456", "secret-b")
    assert hash_code("123456", "secret-a") != hash_code("654321", "secret-a")


async def test_request_code_sends_sms_and_returns_204(client: AsyncClient, monkeypatch) -> None:
    from app.api.routes import sms_link as sms_link_routes

    sent = {}

    async def fake_send_sms(*, settings, to, text) -> str:
        sent["to"] = to
        sent["text"] = text
        return "SMxxxx"

    monkeypatch.setattr(sms_link_routes, "send_sms", fake_send_sms)

    response = await client.post(
        "/api/v1/settings/sms/request", json={"phone_number": "+15550101234"}
    )

    assert response.status_code == 204
    assert sent["to"] == "+15550101234"
    assert "Posted verification code" in sent["text"]
    assert "Reply STOP to opt out" in sent["text"]


async def test_request_code_rejects_bad_phone_format(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/settings/sms/request", json={"phone_number": "not-a-number"}
    )
    assert response.status_code == 400


async def test_request_code_without_a_body_rejects_when_no_pending_link_exists(
    client: AsyncClient,
) -> None:
    response = await client.post("/api/v1/settings/sms/request", json={})
    assert response.status_code == 400


async def test_resend_without_a_phone_number_reuses_the_pending_links_number(
    client: AsyncClient, monkeypatch
) -> None:
    """Regression test: the client only ever has a masked number once a code has
    been sent, so a page refresh mid-flow leaves it with nothing to resupply.
    Resend must fall back to the number already stored on the pending link
    instead of requiring the client to resend the (unavailable) full number."""
    from datetime import timedelta

    from app.api.routes import sms_link as sms_link_routes

    sent = []

    async def fake_send_sms(*, settings, to, text) -> str:
        sent.append(to)
        return "SMxxxx"

    monkeypatch.setattr(sms_link_routes, "send_sms", fake_send_sms)
    monkeypatch.setattr(sms_link_routes, "RESEND_COOLDOWN", timedelta(seconds=0))

    first = await client.post(
        "/api/v1/settings/sms/request", json={"phone_number": "+15550101234"}
    )
    assert first.status_code == 204

    resend = await client.post("/api/v1/settings/sms/request", json={})
    assert resend.status_code == 204
    assert sent == ["+15550101234", "+15550101234"]


async def test_request_code_enforces_resend_cooldown(client: AsyncClient, monkeypatch) -> None:
    from app.api.routes import sms_link as sms_link_routes

    async def fake_send_sms(*, settings, to, text) -> str:
        return "SMxxxx"

    monkeypatch.setattr(sms_link_routes, "send_sms", fake_send_sms)

    first = await client.post(
        "/api/v1/settings/sms/request", json={"phone_number": "+15550101234"}
    )
    assert first.status_code == 204

    second = await client.post(
        "/api/v1/settings/sms/request", json={"phone_number": "+15550101234"}
    )
    assert second.status_code == 429


async def test_request_code_surfaces_delivery_failure_as_502(
    client: AsyncClient, monkeypatch
) -> None:
    from app.api.routes import sms_link as sms_link_routes

    async def failing_send_sms(*, settings, to, text) -> str:
        raise RuntimeError("Telnyx rejected the destination")

    monkeypatch.setattr(sms_link_routes, "send_sms", failing_send_sms)

    response = await client.post(
        "/api/v1/settings/sms/request", json={"phone_number": "+15550101234"}
    )
    assert response.status_code == 502


async def test_verify_code_marks_link_verified(client: AsyncClient, monkeypatch) -> None:
    from app.api.routes import sms_link as sms_link_routes

    sent = {}

    async def fake_send_sms(*, settings, to, text) -> str:
        code = _code_in(text)
        if code is not None:
            sent["code"] = code
        return "SMxxxx"

    monkeypatch.setattr(sms_link_routes, "send_sms", fake_send_sms)

    await client.post("/api/v1/settings/sms/request", json={"phone_number": "+15550101234"})
    response = await client.post("/api/v1/settings/sms/verify", json={"code": sent["code"]})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "verified"
    assert body["phone_number_masked"] == "•••• 1234"


async def test_verify_code_sends_an_optin_confirmation_text(
    client: AsyncClient, monkeypatch
) -> None:
    from app.api.routes import sms_link as sms_link_routes

    sent = []

    async def fake_send_sms(*, settings, to, text) -> str:
        sent.append(text)
        return "SMxxxx"

    monkeypatch.setattr(sms_link_routes, "send_sms", fake_send_sms)

    await client.post("/api/v1/settings/sms/request", json={"phone_number": "+15550101234"})
    code = _code_in(sent[-1])
    assert code is not None
    response = await client.post("/api/v1/settings/sms/verify", json={"code": code})

    assert response.status_code == 200
    assert "set up to text Posted" in sent[-1]


async def test_verify_code_rejects_wrong_code(client: AsyncClient, monkeypatch) -> None:
    from app.api.routes import sms_link as sms_link_routes

    async def fake_send_sms(*, settings, to, text) -> str:
        return "SMxxxx"

    monkeypatch.setattr(sms_link_routes, "send_sms", fake_send_sms)

    await client.post("/api/v1/settings/sms/request", json={"phone_number": "+15550101234"})
    response = await client.post("/api/v1/settings/sms/verify", json={"code": "000000"})

    assert response.status_code == 400


async def test_verify_code_locks_out_after_max_attempts(client: AsyncClient, monkeypatch) -> None:
    from app.api.routes import sms_link as sms_link_routes

    async def fake_send_sms(*, settings, to, text) -> str:
        return "SMxxxx"

    monkeypatch.setattr(sms_link_routes, "send_sms", fake_send_sms)

    await client.post("/api/v1/settings/sms/request", json={"phone_number": "+15550101234"})
    for _ in range(5):
        response = await client.post("/api/v1/settings/sms/verify", json={"code": "000000"})
        assert response.status_code == 400

    locked = await client.post("/api/v1/settings/sms/verify", json={"code": "000000"})
    assert locked.status_code == 429


async def test_verify_code_rejects_an_expired_code() -> None:
    """Test the datetime normalization fix for code_expires_at vs. SQLite naive datetimes.

    This test directly verifies the SQLite datetime normalization by:
    1. Creating an in-memory database
    2. Storing a link with an expired code_expires_at (will become naive datetime from SQLite)
    3. Calling verify_code with the correct code but expired timestamp
    4. Verifying that _as_aware helper normalizes it correctly for comparison
    """
    from fastapi import HTTPException

    from app.api.routes.sms_link import verify_code
    from app.api.schemas import SmsVerifyRequest

    settings = Settings(database_url="sqlite+aiosqlite:///:memory:", app_secret="test-secret")
    engine = create_engine(settings)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = create_session_factory(engine)

    user_id = uuid4()
    code = "123456"

    # Create link with expired code
    async with session_factory() as session:
        session.add(User(id=user_id, email="expire-test@example.com", display_name="Test"))
        session.add(
            SmsLink(
                user_id=user_id,
                phone_number="+15550101234",
                code_hash=hash_code(code, "test-secret"),
                code_expires_at=datetime.now(UTC) - timedelta(minutes=1),  # Expired 1 minute ago
            )
        )
        await session.commit()

    # Verify the code_expires_at is naive after round-trip through SQLite
    async with session_factory() as session:
        link = await session.scalar(select(SmsLink).where(SmsLink.user_id == user_id))
        assert link.code_expires_at.tzinfo is None, "SQLite returns naive datetime"

        # Call verify_code with correct code but expired timestamp
        # With _as_aware normalization, this should raise HTTPException with 400
        raised_exception = False
        try:
            await verify_code(SmsVerifyRequest(code=code), session, user_id, settings)
        except (HTTPException, TypeError) as e:
            raised_exception = True
            # If TypeError: can't compare offset-naive and offset-aware datetimes
            # then the normalization is NOT working
            # If HTTPException with 400: code expired, then normalization IS working
            if isinstance(e, TypeError):
                raise AssertionError(
                    f"DateTime normalization failed. Got TypeError: {e}"
                ) from e

        assert raised_exception, "verify_code should raise HTTPException for expired code"

    await engine.dispose()


async def test_verify_code_transfers_ownership_from_a_previous_user(
    client: AsyncClient, monkeypatch
) -> None:
    from app.api.routes import sms_link as sms_link_routes

    sent = {}

    async def fake_send_sms(*, settings, to, text) -> str:
        code = _code_in(text)
        if code is not None:
            sent["code"] = code
        return "SMxxxx"

    monkeypatch.setattr(sms_link_routes, "send_sms", fake_send_sms)

    original_owner = uuid4()
    await client.post(
        "/api/v1/settings/sms/request",
        json={"phone_number": "+15550101234"},
        headers={"X-Posted-User-Id": str(original_owner)},
    )
    await client.post(
        "/api/v1/settings/sms/verify",
        json={"code": sent["code"]},
        headers={"X-Posted-User-Id": str(original_owner)},
    )

    new_owner = uuid4()
    await client.post(
        "/api/v1/settings/sms/request",
        json={"phone_number": "+15550101234"},
        headers={"X-Posted-User-Id": str(new_owner)},
    )
    verify_response = await client.post(
        "/api/v1/settings/sms/verify",
        json={"code": sent["code"]},
        headers={"X-Posted-User-Id": str(new_owner)},
    )
    assert verify_response.status_code == 200

    original_status = await client.get(
        "/api/v1/settings/sms/link", headers={"X-Posted-User-Id": str(original_owner)}
    )
    assert original_status.json()["status"] == "none"


async def test_link_status_defaults_to_none(client: AsyncClient) -> None:
    response = await client.get("/api/v1/settings/sms/link")
    assert response.status_code == 200
    assert response.json() == {"status": "none", "phone_number_masked": None, "opted_out": False}


async def test_unlink_removes_a_verified_link(client: AsyncClient, monkeypatch) -> None:
    from app.api.routes import sms_link as sms_link_routes

    sent = {}

    async def fake_send_sms(*, settings, to, text) -> str:
        code = _code_in(text)
        if code is not None:
            sent["code"] = code
        return "SMxxxx"

    monkeypatch.setattr(sms_link_routes, "send_sms", fake_send_sms)

    await client.post("/api/v1/settings/sms/request", json={"phone_number": "+15550101234"})
    await client.post("/api/v1/settings/sms/verify", json={"code": sent["code"]})

    delete_response = await client.delete("/api/v1/settings/sms/link")
    assert delete_response.status_code == 204

    status_response = await client.get("/api/v1/settings/sms/link")
    assert status_response.json()["status"] == "none"
