from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.providers.schwab.credentials import TokenVault
from app.providers.schwab.oauth import create_oauth_state, verify_oauth_state


def test_oauth_state_round_trip_and_expiry() -> None:
    user_id = uuid4()
    issued_at = datetime(2026, 7, 22, 12, tzinfo=UTC)
    state = create_oauth_state(user_id=user_id, secret="test-secret", now=issued_at)

    assert (
        verify_oauth_state(
            state,
            secret="test-secret",
            now=issued_at + timedelta(minutes=5),
        )
        == user_id
    )
    with pytest.raises(ValueError, match="Expired"):
        verify_oauth_state(
            state,
            secret="test-secret",
            now=issued_at + timedelta(minutes=11),
        )


def test_token_vault_encrypts_and_rejects_a_different_key() -> None:
    vault = TokenVault("first-secret")
    encrypted = vault.encrypt("sensitive-token")

    assert encrypted != "sensitive-token"
    assert vault.decrypt(encrypted) == "sensitive-token"
    with pytest.raises(ValueError, match="decrypt"):
        TokenVault("different-secret").decrypt(encrypted)


async def test_authorize_requires_schwab_credentials(client: AsyncClient) -> None:
    response = await client.get("/api/v1/connections/schwab/authorize")

    assert response.status_code == 503
    assert "Schwab developer credentials" in response.json()["detail"]
