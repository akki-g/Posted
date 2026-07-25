from uuid import uuid4

from httpx import AsyncClient

from app.security.session_token import create_session_token


async def test_current_user_falls_back_to_dev_user_without_a_token(client: AsyncClient) -> None:
    response = await client.get("/api/v1/holdings")
    assert response.status_code == 200


async def test_bearer_token_overrides_dev_user(client: AsyncClient) -> None:
    other_user_id = uuid4()
    token = create_session_token(other_user_id, "test-secret")

    response = await client.get(
        "/api/v1/holdings", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert response.json() == []  # a brand-new user has no holdings yet


async def test_me_requires_a_valid_bearer_token(client: AsyncClient) -> None:
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401

    response = await client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert response.status_code == 401
