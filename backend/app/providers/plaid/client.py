from dataclasses import dataclass
from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

PLAID_BASE_URLS = {
    "sandbox": "https://sandbox.plaid.com",
    "development": "https://development.plaid.com",
    "production": "https://production.plaid.com",
}


@dataclass(frozen=True, slots=True)
class PlaidTokenExchange:
    access_token: str
    item_id: str
    request_id: str | None


@dataclass(frozen=True, slots=True)
class PlaidSyncPage:
    added: tuple[dict[str, Any], ...]
    modified: tuple[dict[str, Any], ...]
    removed: tuple[dict[str, Any], ...]
    next_cursor: str
    has_more: bool


class PlaidClient:
    def __init__(
        self,
        *,
        client_id: str,
        secret: str,
        environment: str = "sandbox",
        http: httpx.AsyncClient | None = None,
    ) -> None:
        try:
            self._base_url = PLAID_BASE_URLS[environment]
        except KeyError as exc:
            raise ValueError(f"Unsupported Plaid environment: {environment}") from exc
        self._client_id = client_id
        self._secret = secret
        self._http = http

    async def create_link_token(
        self,
        *,
        user_id: str,
        client_name: str,
        webhook_url: str | None = None,
        redirect_uri: str | None = None,
        android_package_name: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "client_id": self._client_id,
            "secret": self._secret,
            "client_name": client_name,
            "language": "en",
            "country_codes": ["US"],
            "products": ["transactions"],
            "user": {"client_user_id": user_id},
        }
        if webhook_url:
            payload["webhook"] = webhook_url
        if redirect_uri:
            payload["redirect_uri"] = redirect_uri
        if android_package_name:
            payload["android_package_name"] = android_package_name
        return await self._post("/link/token/create", payload)

    async def exchange_public_token(self, public_token: str) -> PlaidTokenExchange:
        payload = await self._post(
            "/item/public_token/exchange",
            {
                "client_id": self._client_id,
                "secret": self._secret,
                "public_token": public_token,
            },
        )
        return PlaidTokenExchange(
            access_token=str(payload["access_token"]),
            item_id=str(payload["item_id"]),
            request_id=str(payload["request_id"]) if payload.get("request_id") else None,
        )

    async def get_accounts(self, access_token: str) -> tuple[dict[str, Any], ...]:
        payload = await self._post(
            "/accounts/get",
            {
                "client_id": self._client_id,
                "secret": self._secret,
                "access_token": access_token,
            },
        )
        return tuple(payload.get("accounts") or ())

    async def sync_transactions(
        self, access_token: str, *, cursor: str | None = None
    ) -> PlaidSyncPage:
        payload: dict[str, Any] = {
            "client_id": self._client_id,
            "secret": self._secret,
            "access_token": access_token,
        }
        if cursor:
            payload["cursor"] = cursor
        response = await self._post("/transactions/sync", payload)
        return PlaidSyncPage(
            added=tuple(response.get("added") or ()),
            modified=tuple(response.get("modified") or ()),
            removed=tuple(response.get("removed") or ()),
            next_cursor=str(response["next_cursor"]),
            has_more=bool(response.get("has_more")),
        )

    @retry(
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
        reraise=True,
    )
    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        owns_client = self._http is None
        client = self._http or httpx.AsyncClient(timeout=20)
        try:
            response = await client.post(f"{self._base_url}{path}", json=payload)
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict):
                raise ValueError("Plaid response must be a JSON object")
            return data
        finally:
            if owns_client:
                await client.aclose()
