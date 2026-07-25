import base64
import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

SESSION_TOKEN_TTL = timedelta(days=30)
CSRF_STATE_TTL = timedelta(minutes=10)


def sign_payload(payload: str, secret: str, *, now: datetime | None = None) -> str:
    """Sign an arbitrary string payload with an embedded, verifiable issue time."""

    issued_at = int((now or datetime.now(UTC)).timestamp())
    body = f"{issued_at}:{payload}".encode()
    signature = hmac.new(secret.encode(), body, hashlib.sha256).digest()
    return f"{_encode(body)}.{_encode(signature)}"


def verify_payload(
    token: str,
    secret: str,
    *,
    ttl: timedelta,
    now: datetime | None = None,
) -> str | None:
    """Return the signed payload if the token is intact and within `ttl`, else None."""

    try:
        encoded_body, encoded_signature = token.split(".", maxsplit=1)
        body = _decode(encoded_body)
        signature = _decode(encoded_signature)
        expected = hmac.new(secret.encode(), body, hashlib.sha256).digest()
        issued_text, payload = body.decode().split(":", maxsplit=1)
        issued_at = datetime.fromtimestamp(int(issued_text), tz=UTC)
    except (ValueError, UnicodeDecodeError):
        return None

    if not hmac.compare_digest(signature, expected):
        return None
    current = now or datetime.now(UTC)
    if current - issued_at > ttl or issued_at - current > timedelta(minutes=1):
        return None
    return payload


def create_session_token(user_id: UUID, secret: str, *, now: datetime | None = None) -> str:
    return sign_payload(str(user_id), secret, now=now)


def verify_session_token(
    token: str, secret: str, *, now: datetime | None = None
) -> UUID | None:
    payload = verify_payload(token, secret, ttl=SESSION_TOKEN_TTL, now=now)
    if payload is None:
        return None
    try:
        return UUID(payload)
    except ValueError:
        return None


def create_csrf_state(secret: str, *, now: datetime | None = None) -> str:
    return sign_payload(secrets.token_urlsafe(16), secret, now=now)


def verify_csrf_state(state: str, secret: str, *, now: datetime | None = None) -> bool:
    return verify_payload(state, secret, ttl=CSRF_STATE_TTL, now=now) is not None


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
