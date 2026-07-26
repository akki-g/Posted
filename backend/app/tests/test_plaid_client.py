import json

import httpx

from app.providers.plaid.client import PlaidClient


async def test_get_item_posts_item_get_and_returns_item() -> None:
    item_payload = {"item_id": "item-sandbox", "institution_id": "ins_1"}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/item/get"
        body = json.loads(request.content)
        assert body == {
            "client_id": "client-id",
            "secret": "secret",
            "access_token": "access-sandbox",
        }
        return httpx.Response(200, json={"item": item_payload, "request_id": "req-1"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = PlaidClient(client_id="client-id", secret="secret", http=http)
        item = await client.get_item("access-sandbox")

    assert item == item_payload


async def test_remove_item_posts_item_remove() -> None:
    requested: list[tuple[str, dict[str, object]]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append((request.url.path, json.loads(request.content)))
        return httpx.Response(200, json={"request_id": "req-2"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = PlaidClient(client_id="client-id", secret="secret", http=http)
        result = await client.remove_item("access-sandbox")

    assert result is None
    assert requested == [
        (
            "/item/remove",
            {
                "client_id": "client-id",
                "secret": "secret",
                "access_token": "access-sandbox",
            },
        )
    ]
