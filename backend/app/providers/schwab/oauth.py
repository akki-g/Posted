import base64
import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode
from uuid import UUID

import httpx
from pydantic import BaseModel, Field

AUTHORIZE_URL = "https://api.schwabapi.com/v1/oauth/authorize"
TOKEN_URL = "https://api.schwabapi.com/v1/oauth/token"
STATE_TTL = timedelta(minutes=10)


class OAuthTokenSet(BaseModel):
    access_token: str
    refresh_token: str | None = None
    token_type: str = "Bearer"
    expires_in: int = Field(gt=0)
    scope: str | None = None
    obtained_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def expires_at(self) -> datetime:
        return self.obtained_at + timedelta(seconds=self.expires_in)


class SchwabOAuthClient:
    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        http: httpx.AsyncClient | None = None,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._redirect_uri = redirect_uri
        self._http = http

    def authorization_url(self, *, state: str) -> str:
        query = urlencode(
            {
                "response_type": "code",
                "client_id": self._client_id,
                "redirect_uri": self._redirect_uri,
                "state": state,
            }
        )
        return f"{AUTHORIZE_URL}?{query}"

    async def exchange_code(self, *, code: str) -> OAuthTokenSet:
        return await self._token_request(
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self._redirect_uri,
            }
        )

    async def refresh(self, *, refresh_token: str) -> OAuthTokenSet:
        return await self._token_request(
            data={"grant_type": "refresh_token", "refresh_token": refresh_token}
        )

    async def _token_request(self, *, data: dict[str, str]) -> OAuthTokenSet:
        owns_client = self._http is None
        client = self._http or httpx.AsyncClient(timeout=20)
        try:
            response = await client.post(
                TOKEN_URL,
                data=data,
                auth=(self._client_id, self._client_secret),
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            return OAuthTokenSet.model_validate(response.json())
        finally:
            if owns_client:
                await client.aclose()


def create_oauth_state(*, user_id: UUID, secret: str, now: datetime | None = None) -> str:
    """Create a short-lived, signed state value without storing browser session state."""

    issued_at = int((now or datetime.now(UTC)).timestamp())
    payload = f"{user_id}:{issued_at}:{secrets.token_urlsafe(12)}".encode()
    signature = hmac.new(secret.encode(), payload, hashlib.sha256).digest()
    return f"{_encode(payload)}.{_encode(signature)}"


def verify_oauth_state(
    state: str,
    *,
    secret: str,
    now: datetime | None = None,
) -> UUID:
    """Validate integrity and age, returning the user encoded in the state."""

    try:
        encoded_payload, encoded_signature = state.split(".", maxsplit=1)
        payload = _decode(encoded_payload)
        signature = _decode(encoded_signature)
        expected = hmac.new(secret.encode(), payload, hashlib.sha256).digest()
        user_text, issued_text, _nonce = payload.decode().split(":", maxsplit=2)
        issued_at = datetime.fromtimestamp(int(issued_text), tz=UTC)
        user_id = UUID(user_text)
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError("Invalid Schwab OAuth state") from exc

    if not hmac.compare_digest(signature, expected):
        raise ValueError("Invalid Schwab OAuth state signature")
    current = now or datetime.now(UTC)
    if current - issued_at > STATE_TTL or issued_at - current > timedelta(minutes=1):
        raise ValueError("Expired Schwab OAuth state")
    return user_id


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
