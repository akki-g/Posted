from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.security.session_token import (
    create_csrf_state,
    create_session_token,
    verify_csrf_state,
    verify_session_token,
)


def test_session_token_round_trip_and_expiry() -> None:
    user_id = uuid4()
    issued_at = datetime(2026, 7, 24, 12, tzinfo=UTC)
    token = create_session_token(user_id, "test-secret", now=issued_at)

    assert (
        verify_session_token(token, "test-secret", now=issued_at + timedelta(days=1))
        == user_id
    )
    assert (
        verify_session_token(token, "test-secret", now=issued_at + timedelta(days=31))
        is None
    )


def test_session_token_rejects_tampering_and_wrong_secret() -> None:
    user_id = uuid4()
    token = create_session_token(user_id, "test-secret")

    assert verify_session_token(token, "different-secret") is None
    assert verify_session_token(token + "x", "test-secret") is None
    assert verify_session_token("not-a-token", "test-secret") is None


def test_csrf_state_round_trip_and_expiry() -> None:
    issued_at = datetime(2026, 7, 24, 12, tzinfo=UTC)
    state = create_csrf_state("test-secret", now=issued_at)

    assert verify_csrf_state(state, "test-secret", now=issued_at + timedelta(minutes=5))
    assert not verify_csrf_state(state, "test-secret", now=issued_at + timedelta(minutes=11))
    assert not verify_csrf_state(state, "different-secret", now=issued_at)
