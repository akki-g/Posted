from uuid import uuid4

from httpx import AsyncClient


async def test_health(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "app": "Posted",
        "environment": "test",
        "demo_mode": True,
    }


async def test_dashboard_has_portfolio_holdings_and_events(client: AsyncClient) -> None:
    response = await client.get("/api/v1/dashboard")
    assert response.status_code == 200
    body = response.json()
    assert body["portfolio"]["total_value"] == "284621.4000"
    assert body["portfolio"]["demo_mode"] is True
    assert len(body["accounts"]) == 2
    assert len(body["top_holdings"]) == 5
    assert body["top_holdings"][0]["symbol"] == "MSFT"
    assert body["important_events"][0]["is_demo"] is True


async def test_holdings_aggregate_same_security_across_accounts(client: AsyncClient) -> None:
    response = await client.get("/api/v1/holdings")
    assert response.status_code == 200
    nvda = next(item for item in response.json() if item["symbol"] == "NVDA")
    assert nvda["quantity"] == "320.00000000"
    assert nvda["account_count"] == 2
    assert nvda["market_value"] == "59974.4000"


async def test_feed_can_filter_unread(client: AsyncClient) -> None:
    response = await client.get("/api/v1/feed", params={"unread_only": True})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert all(item["unread"] for item in body["items"])


async def test_event_can_be_marked_read(client: AsyncClient) -> None:
    feed = (await client.get("/api/v1/feed", params={"unread_only": True})).json()
    event_id = feed["items"][0]["id"]
    response = await client.post(f"/api/v1/feed/{event_id}/read")
    assert response.status_code == 204
    refreshed = (await client.get("/api/v1/feed", params={"unread_only": True})).json()
    assert refreshed["total"] == 1


async def test_demo_sync_is_idempotent(client: AsyncClient) -> None:
    connection = (await client.get("/api/v1/connections")).json()[0]
    request = {"idempotency_key": "manual-test-0001"}
    first = await client.post(f"/api/v1/connections/{connection['id']}/sync", json=request)
    second = await client.post(f"/api/v1/connections/{connection['id']}/sync", json=request)
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["sync_run_id"] == second.json()["sync_run_id"]


async def test_preferences_round_trip(client: AsyncClient) -> None:
    updated = {
        "immediate_alert_level": "urgent",
        "push_enabled": False,
        "email_digest_enabled": True,
        "daily_briefing_time": "07:30",
    }
    response = await client.put("/api/v1/settings", json=updated)
    refreshed = await client.get("/api/v1/settings")

    assert response.status_code == 200
    assert refreshed.json() == updated


async def test_preferences_are_scoped_per_user(client: AsyncClient) -> None:
    from app.security.session_token import create_session_token

    first_user = uuid4()
    second_user = uuid4()
    first_headers = {"Authorization": f"Bearer {create_session_token(first_user, 'test-secret')}"}
    second_headers = {"Authorization": f"Bearer {create_session_token(second_user, 'test-secret')}"}

    await client.put(
        "/api/v1/settings",
        json={
            "immediate_alert_level": "urgent",
            "push_enabled": False,
            "email_digest_enabled": True,
            "daily_briefing_time": "06:00",
        },
        headers=first_headers,
    )

    first = await client.get("/api/v1/settings", headers=first_headers)
    second = await client.get("/api/v1/settings", headers=second_headers)

    assert first.json()["daily_briefing_time"] == "06:00"
    assert second.json()["daily_briefing_time"] == "08:00"  # untouched default for a new user


async def test_money_overview_excludes_transfers_and_pending_activity(
    client: AsyncClient,
) -> None:
    response = await client.get("/api/v1/money/overview")

    assert response.status_code == 200
    body = response.json()
    assert body["cash_balance"] == "31702.1800"
    assert body["card_balance"] == "1842.6700"
    assert body["weekly_spending"] == "2153.5100"
    assert body["weekly_income"] == "3250.0000"
    assert len(body["accounts"]) == 3
    assert body["subscriptions"][0]["merchant_name"] == "Parkview Rent"


async def test_money_transactions_are_searchable(client: AsyncClient) -> None:
    response = await client.get("/api/v1/money/transactions", params={"search": "coffee"})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["merchant_name"] == "Northstar Coffee"


async def test_plaid_status_explains_missing_credentials(client: AsyncClient) -> None:
    response = await client.get("/api/v1/money/connections/plaid/status")

    assert response.status_code == 200
    assert response.json()["configured"] is False
    assert response.json()["environment"] == "sandbox"


async def test_health_reports_environment_without_google_credentials(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
